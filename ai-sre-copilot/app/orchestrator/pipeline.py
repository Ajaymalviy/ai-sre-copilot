"""
Incident Orchestrator — Full Pipeline (Phase 3)
===============================================
Yeh poori pipeline:

  alert input
      ↓
  [MetricsAgent, LogsAgent, TracesAgent] ← parallel
      ↓
  EvidenceFusion
      ↓
  KnowledgeAgent (Qdrant RAG)
      ↓
  RCAAgent ← NEW: Root cause analysis
      ↓
  FixAgent ← NEW: Fix generation
      ↓
  result return (human approval next phase)
"""
import asyncio
import structlog
from datetime import datetime, timezone

from app.orchestrator.state import IncidentState
from app.agents.metrics_agent   import MetricsAgent
from app.agents.logs_agent      import LogsAgent
from app.agents.traces_agent    import TracesAgent
from app.agents.evidence_fusion import EvidenceFusion
from app.agents.knowledge_agent import KnowledgeAgent
from app.db.session import AsyncSessionLocal
from app.models.incident import Incident
from sqlalchemy import select

logger = structlog.get_logger()


class IncidentOrchestrator:
    """Full LangGraph style pipeline with RCA and Fix agents."""

    def __init__(self):
        self.metrics_agent   = MetricsAgent()
        self.logs_agent      = LogsAgent()
        self.traces_agent    = TracesAgent()
        self.evidence_fusion = EvidenceFusion()
        self.knowledge_agent = KnowledgeAgent()
        
        # Phase 3 agents
        self._rca_agent = None
        self._fix_agent = None

    async def _get_rca_agent(self):
        """Lazy load RCA agent (import here to avoid circular deps)"""
        if self._rca_agent is None:
            from app.agents.rca_agent import RCAAgent
            self._rca_agent = RCAAgent()
        return self._rca_agent

    async def _get_fix_agent(self):
        """Lazy load Fix agent (import here to avoid circular deps)"""
        if self._fix_agent is None:
            from app.agents.fix_agent import FixAgent
            self._fix_agent = FixAgent()
        return self._fix_agent

    async def run(self, incident_id: str, alert_payload: dict) -> IncidentState:
        """
        Poori pipeline run karo ek incident ke liye.
        """
        labels      = alert_payload.get("labels", {})
        annotations = alert_payload.get("annotations", {})

        # Initial state banao
        state: IncidentState = {
            "incident_id":      incident_id,
            "alert_name":       labels.get("alertname", "UnknownAlert"),
            "severity":         labels.get("severity", "warning"),
            "labels":           labels,
            "annotations":      annotations,
            "fired_at":         alert_payload.get("startsAt", datetime.now(timezone.utc).isoformat()),

            # Phase 2
            "metrics_data":     {},
            "metrics_summary":  "",
            "logs_data":        [],
            "logs_summary":     "",
            "traces_data":      [],
            "traces_summary":   "",
            "fused_evidence":   "",
            "relevant_runbooks": [],
            
            # Phase 3
            "root_cause":       "",
            "confidence":       0.0,
            "fix_plan":         "",
            "fix_commands":     [],
            
            # Pipeline control
            "current_step":     "started",
            "errors":           [],
            "retry_count":      0,
        }

        logger.info(
            "Pipeline started",
            incident_id=incident_id,
            alert=state["alert_name"],
            severity=state["severity"],
        )

        # ── Phase 2: Parallel data collection ──────
        logger.info("Phase 2: Running parallel agents...", incident_id=incident_id)

        metrics_state = dict(state)
        logs_state    = dict(state)
        traces_state  = dict(state)

        results = await asyncio.gather(
            self.metrics_agent(metrics_state),
            self.logs_agent(logs_state),
            self.traces_agent(traces_state),
            return_exceptions=True,
        )

        # Results merge karo
        for result in results:
            if isinstance(result, Exception):
                logger.error("Agent raised exception", error=str(result))
                state.setdefault("errors", []).append(str(result))
            elif isinstance(result, dict):
                for key in ["metrics_data", "metrics_summary",
                            "logs_data", "logs_summary",
                            "traces_data", "traces_summary"]:
                    if result.get(key):
                        state[key] = result[key]

        logger.info("Phase 2: Parallel agents done", incident_id=incident_id)

        # ── Phase 2: Evidence Fusion & Knowledge ───
        state = await self.evidence_fusion(state)
        state = await self.knowledge_agent(state)

        # ── Phase 3: RCA ───────────────────────────
        logger.info("Phase 3: RCA Agent starting...", incident_id=incident_id)
        rca_agent = await self._get_rca_agent()
        state = await rca_agent(state)
        logger.info("Phase 3: RCA done", incident_id=incident_id, confidence=state.get("confidence", 0.0))

        # ── Phase 3: Fix Generation ────────────────
        logger.info("Phase 3: Fix Agent starting...", incident_id=incident_id)
        fix_agent = await self._get_fix_agent()
        state = await fix_agent(state)
        logger.info("Phase 3: Fix done", incident_id=incident_id, commands=len(state.get("fix_commands", [])))

        # ── Save to DB ─────────────────────────────
        await self._save_results(state)

        logger.info(
            "Pipeline COMPLETE",
            incident_id=incident_id,
            steps_done=state.get("current_step"),
            errors=len(state.get("errors", [])),
            root_cause_confidence=state.get("confidence", 0.0),
        )

        return state

    async def _save_results(self, state: IncidentState):
        """Pipeline results PostgreSQL mein save karo"""
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(Incident).where(
                        Incident.id == state["incident_id"]
                    )
                )
                incident = result.scalar_one_or_none()

                if incident:
                    incident.status = "rca_complete"
                    incident.annotations = {
                        **incident.annotations,
                        # Phase 2
                        "metrics_summary":  state.get("metrics_summary", ""),
                        "logs_summary":     state.get("logs_summary", ""),
                        "traces_summary":   state.get("traces_summary", ""),
                        "fused_evidence":   state.get("fused_evidence", ""),
                        "runbooks_matched": [
                            rb.get("title") for rb in state.get("relevant_runbooks", [])
                        ],
                        # Phase 3
                        "root_cause":       state.get("root_cause", ""),
                        "rca_confidence":   state.get("confidence", 0.0),
                        "fix_plan":         state.get("fix_plan", ""),
                        "fix_commands":     state.get("fix_commands", []),
                        # Errors
                        "pipeline_errors":  state.get("errors", []),
                    }
                    await session.commit()
                    logger.info("Results saved to DB", incident_id=state["incident_id"])

        except Exception as e:
            logger.error("Failed to save results", error=str(e))


# ── Singleton ─────────────────────────────
orchestrator = IncidentOrchestrator()