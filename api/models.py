"""
api/models.py
==============
SQLAlchemy ORM models for SENTINEL-AI.
All 4 tables: Content, DetectionResult, Actor, NetworkEdge.

WHO OWNS THIS: Backend team
SOURCE: Merged from api/models/tables.py
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    String, Float, Integer, DateTime, ForeignKey,
    UniqueConstraint, Enum as SAEnum, Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from api.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Content(Base):
    __tablename__ = "content"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=_uuid
    )
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    # POLICY: only first 280 chars stored — never the full text
    text_preview: Mapped[str] = mapped_column(String(300), nullable=False)
    platform: Mapped[str] = mapped_column(
        SAEnum("twitter", "reddit", "email", "manual", name="platform_enum"),
        nullable=False,
    )
    actor_identifier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    detections: Mapped[list["DetectionResult"]] = relationship(back_populates="content")
    edges: Mapped[list["NetworkEdge"]] = relationship(back_populates="content")


class DetectionResult(Base):
    __tablename__ = "detection_result"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=_uuid
    )
    content_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("content.id"), nullable=False
    )
    ai_probability: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[str] = mapped_column(
        SAEnum("LOW", "MEDIUM", "HIGH", "CRITICAL", name="risk_enum"), nullable=False
    )
    model_attribution: Mapped[str] = mapped_column(String(50), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    cluster_id: Mapped[str] = mapped_column(String(10), nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    content: Mapped["Content"] = relationship(back_populates="detections")


class Actor(Base):
    __tablename__ = "actor"
    __table_args__ = (UniqueConstraint("actor_identifier", "platform", name="uq_actor_platform"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    content_count: Mapped[int] = mapped_column(Integer, default=0)
    ai_content_count: Mapped[int] = mapped_column(Integer, default=0)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class NetworkEdge(Base):
    __tablename__ = "network_edge"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    content_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("content.id"), nullable=False
    )
    edge_type: Mapped[str] = mapped_column(
        SAEnum("posted", "shared", name="edge_type_enum"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    content: Mapped["Content"] = relationship(back_populates="edges")