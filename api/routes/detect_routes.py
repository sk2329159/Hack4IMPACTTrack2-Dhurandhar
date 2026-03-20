"""
api/routes/detect_routes.py
=============================
POST /api/v1/detect

WHO OWNS THIS: Backend team
SOURCE: api/routes/detect.py — imports updated for flat api/ structure
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import require_role
from api.database import get_db
from api.schemas import DetectRequest, DetectResponse
from api.services.detection_service import run_detection

logger = logging.getLogger("sentinel.detect")
router = APIRouter(tags=["detect"])


@router.post(
    "/detect",
    response_model=DetectResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_role("analyst", "admin"))],
)
async def detect(
    body: DetectRequest,
    db: AsyncSession = Depends(get_db),
) -> DetectResponse:
    """
    Analyze text for AI-generation probability.
    Persists content hash + preview (never full text).
    Idempotent on content_hash.

    **Roles required**: analyst, admin
    """
    try:
        result = await run_detection(
            db,
            text=body.text,
            platform=body.platform,
            actor_id=body.actor_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"ML pipeline error: {exc}",
        )
    except Exception as exc:
        logger.error("Detection pipeline error: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Detection pipeline failed",
        )
    return DetectResponse(**result)