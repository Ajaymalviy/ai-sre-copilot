"""
REST API Routes — Incidents
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

    return {"message": "Fix approved", "incident_id": str(incident_id)}


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
