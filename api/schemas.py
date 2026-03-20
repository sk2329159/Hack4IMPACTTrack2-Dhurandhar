"""
api/schemas.py
===============
All Pydantic v2 request/response schemas for SENTINEL-AI.
Merged from: schemas/auth.py + schemas/detect.py + schemas/dashboard.py

WHO OWNS THIS: Backend team
"""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ══════════════════════════════════════════════════════════════════════════════
# AUTH schemas
# ══════════════════════════════════════════════════════════════════════════════

class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    expires_in: int  # seconds


# ══════════════════════════════════════════════════════════════════════════════
# DETECT schemas
# ══════════════════════════════════════════════════════════════════════════════

class DetectRequest(BaseModel):
    text: str = Field(..., min_length=10, max_length=10_000,
                      description="Content to analyze. 10–10,000 chars.")
    platform: Literal["twitter", "reddit", "email", "manual"]
    actor_id: str | None = Field(None, max_length=255)


class DetectResponse(BaseModel):
    """Locked response contract — keys must match exactly."""
    content_id: str
    ai_probability: float
    confidence: float
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    model_attribution: str
    explanation: str
    cluster_id: str
    detected_at: datetime


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD schemas
# ══════════════════════════════════════════════════════════════════════════════

class DashboardStats(BaseModel):
    total_analyzed: int
    ai_flagged: int          # ai_probability >= 0.70
    high_risk: int           # risk_level in HIGH | CRITICAL
    campaign_clusters: int   # distinct cluster_id count
    avg_confidence: float
    avg_latency_ms: int


class RecentDetection(BaseModel):
    content_id: str
    platform: str
    risk_level: str
    ai_probability: float
    confidence: float                   # needed for dashboard table display
    model_attribution: str
    cluster_id: str
    actor_id: Optional[str] = None     # needed for graph actor→content links
    detected_at: str


class TrendBucket(BaseModel):
    bucket: str      # ISO hour string e.g. "2024-01-01T14:00"
    total: int
    ai_flagged: int
    high_risk: int


class GraphNode(BaseModel):
    id: str
    type: str                                 # "actor" | "content" | "cluster"
    label: str
    ai_probability: Optional[float] = None    # for D3 node colour coding


class GraphLink(BaseModel):
    source: str
    target: str
    type: str        # "posted" | "belongs_to"


class GraphData(BaseModel):
    nodes: list[GraphNode]
    links: list[GraphLink]


class DashboardOverviewResponse(BaseModel):
    stats: DashboardStats
    recent: list[RecentDetection]
    trend: list[TrendBucket]
    graph: GraphData