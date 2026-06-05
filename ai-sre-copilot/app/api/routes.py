"""
REST API Routes — Incidents with RCA & Fix
"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.db.session import get_db
from app.models.incident import Incident

router = APIRouter(tags=["incidents"])


@router.get("/incidents")
async def list_incidents(
    status:   str | None = None,
    severity: str | None = None,
    limit:    int = 20,
    db: AsyncSession = Depends(get_db),
):
    """Saare incidents list karo, filter bhi kar sakte ho"""
    query = select(Incident).order_by(desc(Incident.fired_at)).limit(limit)

    if status:
        query = query.where(Incident.status == status)
    if severity:
        query = query.where(Incident.severity == severity)

    result = await db.execute(query)
    incidents = result.scalars().all()

    return [
        {
            "id":         str(i.id),
            "alert_name": i.alert_name,
            "severity":   i.severity,
            "status":     i.status,
            "source":     i.source,
            "labels":     i.labels,
            "fired_at":   i.fired_at.isoformat(),
        }
        for i in incidents
    ]


@router.get("/incidents/{incident_id}")
async def get_incident(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Single incident detail"""
    result = await db.execute(
        select(Incident).where(Incident.id == incident_id)
    )
    incident = result.scalar_one_or_none()

    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    return {
        "id":          str(incident.id),
        "alert_name":  incident.alert_name,
        "severity":    incident.severity,
        "status":      incident.status,
        "source":      incident.source,
        "labels":      incident.labels,
        "annotations": incident.annotations,
        "fired_at":    incident.fired_at.isoformat(),
        "resolved_at": incident.resolved_at.isoformat() if incident.resolved_at else None,
        "created_at":  incident.created_at.isoformat(),
    }


@router.get("/incidents/{incident_id}/analysis")
async def get_analysis(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 2 Analysis — Metrics, Logs, Traces, Evidence
    """
    result = await db.execute(
        select(Incident).where(Incident.id == incident_id)
    )
    incident = result.scalar_one_or_none()

    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    ann = incident.annotations or {}

    return {
        "incident_id":     str(incident.id),
        "alert_name":      incident.alert_name,
        "severity":        incident.severity,
        "status":          incident.status,
        "metrics_summary":  ann.get("metrics_summary",  "Not yet analyzed"),
        "logs_summary":     ann.get("logs_summary",     "Not yet analyzed"),
        "traces_summary":   ann.get("traces_summary",   "Not yet analyzed"),
        "fused_evidence":   ann.get("fused_evidence",   "Not yet analyzed"),
        "runbooks_matched": ann.get("runbooks_matched", []),
    }


@router.get("/incidents/{incident_id}/rca")
async def get_rca(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 3 RCA — Root Cause Analysis & Fix Plan
    """
    result = await db.execute(
        select(Incident).where(Incident.id == incident_id)
    )
    incident = result.scalar_one_or_none()

    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    ann = incident.annotations or {}

    return {
        "incident_id":    str(incident.id),
        "alert_name":     incident.alert_name,
        "severity":       incident.severity,
        "status":         incident.status,
        "root_cause":     ann.get("root_cause",      "RCA not yet done"),
        "confidence":     ann.get("rca_confidence",  0.0),
        "fix_plan":       ann.get("fix_plan",        "Fix not yet generated"),
        "fix_commands":   ann.get("fix_commands",    []),
        "runbooks":       ann.get("runbooks_matched", []),
    }


@router.patch("/incidents/{incident_id}/approve")
async def approve_fix(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """HITL: Fix approve karo"""
    result = await db.execute(
        select(Incident).where(Incident.id == incident_id)
    )
    incident = result.scalar_one_or_none()

    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    incident.status = "fix_approved"
    await db.commit()

    return {"message": "Fix approved", "incident_id": str(incident_id), "status": "fix_approved"}


@router.patch("/incidents/{incident_id}/reject")
async def reject_fix(
    incident_id: UUID,
    reason: str = "User rejected",
    db: AsyncSession = Depends(get_db),
):
    """HITL: Fix reject karo"""
    result = await db.execute(
        select(Incident).where(Incident.id == incident_id)
    )
    incident = result.scalar_one_or_none()

    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    incident.status = "fix_rejected"
    if incident.annotations is None:
        incident.annotations = {}
    incident.annotations["rejection_reason"] = reason
    await db.commit()

    return {"message": "Fix rejected", "incident_id": str(incident_id), "reason": reason}


@router.patch("/incidents/{incident_id}/resolve")
async def resolve_incident(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Incident manually resolve karo"""
    from datetime import datetime, timezone

    result = await db.execute(
        select(Incident).where(Incident.id == incident_id)
    )
    incident = result.scalar_one_or_none()

    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    incident.status      = "resolved"
    incident.resolved_at = datetime.now(timezone.utc)
    await db.commit()

    return {"message": "Incident resolved", "incident_id": str(incident_id)}