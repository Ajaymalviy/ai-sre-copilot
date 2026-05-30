"""
Incident SQLAlchemy Model
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, JSON, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


def utcnow():
    return datetime.now(timezone.utc)


class Incident(Base):
    __tablename__ = "incidents"

    id:          Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_name:  Mapped[str]        = mapped_column(String(255), nullable=False)
    severity:    Mapped[str]        = mapped_column(String(50),  default="warning")
    status:      Mapped[str]        = mapped_column(String(50),  default="open")
    source:      Mapped[str | None] = mapped_column(String(100))
    labels:      Mapped[dict]       = mapped_column(JSON, default=dict)
    annotations: Mapped[dict]       = mapped_column(JSON, default=dict)
    fired_at:    Mapped[datetime]   = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at:  Mapped[datetime]   = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at:  Mapped[datetime]   = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    def __repr__(self):
        return f"<Incident {self.alert_name} [{self.severity}] {self.status}>"
