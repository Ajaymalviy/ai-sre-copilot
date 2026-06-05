"""
KnowledgeAgent
==============
Qdrant vector DB se relevant runbooks retrieve karta hai.
Fused evidence ko query ke roop mein use karta hai.
"""
import structlog
from qdrant_client import QdrantClient
from qdrant_client.models import Filter
from sentence_transformers import SentenceTransformer

from app.orchestrator.state import IncidentState
from app.core.config import settings

logger = structlog.get_logger()

# Model ek baar load karo (slow hai pehli baar)
_embedding_model = None

def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        logger.info("Loading embedding model...")
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Embedding model loaded")
    return _embedding_model


class KnowledgeAgent:

    def __init__(self):
        self.qdrant = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
        )

    async def __call__(self, state: IncidentState) -> IncidentState:
        logger.info(
            "KnowledgeAgent starting",
            incident_id=state.get("incident_id"),
        )

        try:
            # Query: alert name + fused evidence se
            query_text = (
                f"{state.get('alert_name', '')} "
                f"{state.get('fused_evidence', '')[:500]}"  # First 500 chars
            )

            # Embed karo
            model     = get_embedding_model()
            embedding = model.encode(query_text).tolist()

            # Qdrant se similar runbooks search karo
            results = self.qdrant.search(
                collection_name=settings.QDRANT_COLLECTION,
                query_vector=embedding,
                limit=3,                    # Top 3 most relevant
                score_threshold=0.3,        # Min similarity score
            )

            runbooks = []
            for hit in results:
                payload = hit.payload or {}
                runbooks.append({
                    "title":   payload.get("title", "Unknown"),
                    "content": payload.get("content", ""),
                    "score":   round(hit.score, 3),
                })
                logger.info(
                    "Runbook matched",
                    title=payload.get("title"),
                    score=round(hit.score, 3),
                )

            state["relevant_runbooks"] = runbooks
            state["current_step"]      = "knowledge_done"

            logger.info(
                "KnowledgeAgent done",
                incident_id=state.get("incident_id"),
                runbooks_found=len(runbooks),
            )

        except Exception as e:
            logger.error("KnowledgeAgent failed", error=str(e))
            state.setdefault("errors", []).append(f"KnowledgeAgent: {str(e)}")
            state["relevant_runbooks"] = []

        return state
