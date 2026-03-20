"""
api/services/detection_service.py
===================================
All DB write logic for POST /detect.

WHO OWNS THIS: Backend team
SOURCE: Renamed from api/services/detect_service.py
        Imports updated: api.models (flat) + api.schemas (flat)

Privacy rules:
  - Only text_preview (first 280 chars) stored — never full text
  - Raw text never logged (hash prefix only)
"""
import hashlib
import logging
import time
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import Actor, Content, DetectionResult, NetworkEdge
from api.schemas import DetectRequest, DetectResponse

logger = logging.getLogger("sentinel.detection_service")

PREVIEW_MAX = 280


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _cluster_id(text: str) -> str:
    """cluster_id = 'CL-' + last 2 hex chars of sha256(normalised_text).upper()"""
    h = _sha256(" ".join(text.lower().split()))
    return "CL-" + h[-2:].upper()


def _preview(text: str) -> str:
    return text[:PREVIEW_MAX]


def _validate_ml(ml: dict) -> None:
    required = {"ai_probability", "confidence", "risk_level",
                "model_attribution", "explanation"}
    missing = required - ml.keys()
    if missing:
        raise ValueError(f"ML output missing keys: {missing}")
    if not 0.0 <= float(ml["ai_probability"]) <= 1.0:
        raise ValueError(f"ai_probability out of range: {ml['ai_probability']}")
    if ml["risk_level"] not in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
        raise ValueError(f"Invalid risk_level: {ml['risk_level']}")
    if ml["model_attribution"] not in (
        "GPT-family", "Claude-family", "Gemini-family", "Unknown"
    ):
        raise ValueError(f"Invalid model_attribution: {ml['model_attribution']}")


async def run_detection(
    db: AsyncSession,
    *,
    text: str,
    platform: str,
    actor_id: str | None,
) -> dict:
    """
    Full detection pipeline:
      1. Check content hash deduplication
      2. Call analyze_text() ML module
      3. Write all 4 DB rows atomically
      4. Return response dict
    """
    from detection.detector import analyze_text  # imported here to allow test patching

    content_hash = _sha256(text)
    hash_prefix  = content_hash[:8]

    # ── Deduplication: return cached result for identical content ─────────
    existing = await db.scalar(
        select(Content).where(Content.content_hash == content_hash)
    )
    if existing:
        cached_dr = await db.scalar(
            select(DetectionResult)
            .where(DetectionResult.content_id == existing.id)
            .order_by(DetectionResult.detected_at.desc())
        )
        if cached_dr:
            logger.info("Cache hit [hash=%s risk=%s]", hash_prefix, cached_dr.risk_level)
            return {
                "content_id":        existing.id,
                "ai_probability":    cached_dr.ai_probability,
                "confidence":        cached_dr.confidence,
                "risk_level":        cached_dr.risk_level,
                "model_attribution": cached_dr.model_attribution,
                "explanation":       cached_dr.explanation,
                "cluster_id":        cached_dr.cluster_id,
                "detected_at":       cached_dr.detected_at,
            }

    # ── ML inference ──────────────────────────────────────────────────────
    t0 = time.monotonic()
    ml = analyze_text(text)
    latency_ms = int((time.monotonic() - t0) * 1000)
    _validate_ml(ml)

    cluster    = _cluster_id(text)
    now        = datetime.utcnow()  # set once; used everywhere — never None

    # ── Atomic DB writes ──────────────────────────────────────────────────
    async with db.begin():
        if existing:
            content = existing
        else:
            content = Content(
                content_hash=content_hash,
                text_preview=_preview(text),
                platform=platform,
                actor_identifier=actor_id,
                created_at=now,
            )
            db.add(content)
            await db.flush()

        dr = DetectionResult(
            content_id=content.id,
            ai_probability=ml["ai_probability"],
            confidence=ml["confidence"],
            risk_level=ml["risk_level"],
            model_attribution=ml["model_attribution"],
            explanation=ml["explanation"],
            cluster_id=cluster,
            latency_ms=latency_ms,
            detected_at=now,
        )
        db.add(dr)

        if actor_id:
            is_ai = ml["ai_probability"] >= 0.70
            actor = await db.scalar(
                select(Actor).where(
                    Actor.actor_identifier == actor_id,
                    Actor.platform == platform,
                )
            )
            if actor:
                actor.content_count    += 1
                actor.ai_content_count += int(is_ai)
                actor.last_seen         = now
            else:
                db.add(Actor(
                    actor_identifier=actor_id,
                    platform=platform,
                    content_count=1,
                    ai_content_count=int(is_ai),
                    last_seen=now,
                ))
            db.add(NetworkEdge(
                actor_identifier=actor_id,
                content_id=content.id,
                edge_type="posted",
                timestamp=now,
            ))

    logger.info(
        "Detection stored [hash=%s risk=%s attr=%s cluster=%s latency=%dms]",
        hash_prefix, ml["risk_level"], ml["model_attribution"], cluster, latency_ms,
    )
    return {
        "content_id":        content.id,
        "ai_probability":    ml["ai_probability"],
        "confidence":        ml["confidence"],
        "risk_level":        ml["risk_level"],
        "model_attribution": ml["model_attribution"],
        "explanation":       ml["explanation"],
        "cluster_id":        cluster,
        "detected_at":       now,
    }