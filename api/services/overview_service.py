"""
api/services/overview_service.py
==================================
All DB query logic for GET /dashboard/overview.

WHO OWNS THIS: Backend team
SOURCE: Renamed from api/services/dashboard_service.py
        Imports updated: api.models (flat) + api.schemas (flat)
"""
import logging
from datetime import datetime, timedelta

from sqlalchemy import func, select, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import Content, DetectionResult
from api.schemas import (
    DashboardStats, DashboardOverviewResponse,
    RecentDetection, TrendBucket,
    GraphData, GraphNode, GraphLink,
)

logger = logging.getLogger("sentinel.overview_service")

WINDOW_MAP = {"1h": 1, "6h": 6, "24h": 24, "7d": 168}


async def get_overview(
    db: AsyncSession,
    *,
    window: str = "24h",
    limit: int = 20,
) -> DashboardOverviewResponse:
    hours = WINDOW_MAP.get(window, 24)
    since = datetime.utcnow() - timedelta(hours=hours)

    # ── Stats: SQL aggregates — O(1) memory regardless of row count ───────
    agg = (await db.execute(
        select(
            func.count(DetectionResult.id).label("total"),
            func.count(DetectionResult.id).filter(
                DetectionResult.ai_probability >= 0.70
            ).label("ai_flagged"),
            func.count(DetectionResult.id).filter(
                DetectionResult.risk_level.in_(["HIGH", "CRITICAL"])
            ).label("high_risk"),
            func.count(distinct(DetectionResult.cluster_id)).label("clusters"),
            func.coalesce(func.avg(DetectionResult.confidence), 0.0).label("avg_conf"),
            func.coalesce(func.avg(DetectionResult.latency_ms), 0).label("avg_lat"),
        ).where(DetectionResult.detected_at >= since)
    )).one()

    stats = DashboardStats(
        total_analyzed=agg.total,
        ai_flagged=agg.ai_flagged,
        high_risk=agg.high_risk,
        campaign_clusters=agg.clusters,
        avg_confidence=round(float(agg.avg_conf), 4),
        avg_latency_ms=int(agg.avg_lat),
    )

    # ── Recent detections ─────────────────────────────────────────────────
    recent_rows = (await db.execute(
        select(DetectionResult, Content)
        .join(Content, DetectionResult.content_id == Content.id)
        .where(DetectionResult.detected_at >= since)
        .order_by(DetectionResult.detected_at.desc())
        .limit(limit)
    )).all()

    recent = [
        RecentDetection(
            content_id=dr.id,
            platform=c.platform,
            risk_level=dr.risk_level,
            ai_probability=dr.ai_probability,
            confidence=dr.confidence,
            model_attribution=dr.model_attribution,
            cluster_id=dr.cluster_id,
            actor_id=c.actor_identifier,
            detected_at=dr.detected_at.isoformat(),
        )
        for dr, c in recent_rows
    ]

    # ── Trend: Python bucketing ───────────────────────────────────────────
    bucket_count = min(hours, 24)
    bucket_size  = max(1, hours // bucket_count)
    now          = datetime.utcnow()
    trend_rows   = (await db.scalars(
        select(DetectionResult).where(DetectionResult.detected_at >= since)
    )).all()

    trend = []
    for i in range(bucket_count - 1, -1, -1):
        b_start = now - timedelta(hours=(i + 1) * bucket_size)
        b_end   = now - timedelta(hours=i * bucket_size)
        bucket  = [r for r in trend_rows if b_start <= r.detected_at < b_end]
        trend.append(TrendBucket(
            bucket=b_start.strftime("%Y-%m-%dT%H:00"),
            total=len(bucket),
            ai_flagged=sum(1 for r in bucket if r.ai_probability >= 0.70),
            high_risk=sum(1 for r in bucket if r.risk_level in ("HIGH", "CRITICAL")),
        ))

    # ── Campaign graph: top 50 by AI risk ────────────────────────────────
    graph_rows = (await db.execute(
        select(DetectionResult, Content)
        .join(Content, DetectionResult.content_id == Content.id)
        .where(DetectionResult.detected_at >= since)
        .order_by(DetectionResult.ai_probability.desc())
        .limit(50)
    )).all()

    nodes, links, seen = [], [], set()

    for dr, _ in graph_rows:  # cluster nodes first (stable anchors)
        nid = f"cluster:{dr.cluster_id}"
        if nid not in seen:
            nodes.append(GraphNode(id=nid, type="cluster", label=dr.cluster_id))
            seen.add(nid)

    for dr, c in graph_rows:
        cnid = f"content:{dr.id}"
        if cnid not in seen:
            nodes.append(GraphNode(
                id=cnid, type="content", label=c.platform,
                ai_probability=dr.ai_probability,
            ))
            seen.add(cnid)

        links.append(GraphLink(source=cnid, target=f"cluster:{dr.cluster_id}",
                               type="belongs_to"))

        if c.actor_identifier:
            anid = f"actor:{c.actor_identifier}"
            if anid not in seen:
                nodes.append(GraphNode(id=anid, type="actor",
                                       label=c.actor_identifier))
                seen.add(anid)
            links.append(GraphLink(source=anid, target=cnid, type="posted"))

    return DashboardOverviewResponse(
        stats=stats, recent=recent, trend=trend,
        graph=GraphData(nodes=nodes, links=links),
    )