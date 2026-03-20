"""
api/routes/dashboard_routes.py
================================
GET /api/v1/dashboard/overview

WHO OWNS THIS: Backend team
SOURCE: api/routes/dashboard.py — imports updated for flat api/ structure
"""
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import require_role
from api.database import get_db
from api.schemas import DashboardOverviewResponse
from api.services.overview_service import get_overview

logger = logging.getLogger("sentinel.dashboard")
router = APIRouter(tags=["dashboard"])


@router.get(
    "/overview",
    response_model=DashboardOverviewResponse,
    dependencies=[Depends(require_role("viewer", "analyst", "admin"))],
)
async def overview(
    window: Literal["1h", "6h", "24h", "7d"] = Query("24h"),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> DashboardOverviewResponse:
    """
    Full SOC dashboard payload: stats, recent detections, trend chart, campaign graph.

    **Roles required**: viewer, analyst, admin
    """
    try:
        return await get_overview(db, window=window, limit=limit)
    except Exception as exc:
        logger.error("Dashboard query error: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Dashboard query failed",
        )