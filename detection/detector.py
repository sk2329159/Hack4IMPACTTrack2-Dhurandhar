"""
detection/detector.py
---------------------
SENTINEL-AI ML Detection Module

CONTRACT (frozen — backend depends on this exact shape):
    analyze_text(text: str) -> dict with keys:
        ai_probability   : float  0.0–1.0
        confidence       : float  0.0–1.0
        risk_level       : "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
        model_attribution: "GPT-family" | "Claude-family" | "Gemini-family" | "Unknown"
        explanation      : str  (1–2 sentence human-readable reason)

Architecture: Transformer primary → Heuristic fallback → Always returns.
The backend calls ONLY this function. No other ML module is called directly.

Privacy: Raw text is NEVER logged. Only hash prefixes appear in logs.
"""

import logging

logger = logging.getLogger("sentinel.detector")

# ── Module-level transformer state ────────────────────────────────────────────
_transformer_pipeline   = None
_transformer_available  = False
_load_attempted         = False

DETECTOR_MODEL_ID  = "roberta-base-openai-detector"
DETECTOR_CACHE_DIR = "/tmp/sentinel_model_cache"


def _load_transformer() -> bool:
    """Attempt once to load the HuggingFace transformer. Idempotent."""
    global _transformer_pipeline, _transformer_available, _load_attempted
    if _load_attempted:
        return _transformer_available
    _load_attempted = True
    try:
        from transformers import pipeline as hf_pipeline
        logger.info("Loading transformer model '%s'...", DETECTOR_MODEL_ID)
        _transformer_pipeline = hf_pipeline(
            "text-classification",
            model=DETECTOR_MODEL_ID,
            cache_dir=DETECTOR_CACHE_DIR,
            truncation=True,
            max_length=512,
        )
        _transformer_available = True
        logger.info("Transformer model loaded.")
    except Exception as exc:
        logger.warning(
            "Transformer unavailable (%s). Using heuristic fallback.",
            type(exc).__name__,
        )
        _transformer_available = False
    return _transformer_available


def _run_transformer(text: str):
    """Run roberta-base-openai-detector. Returns (score, confidence) or (None, None)."""
    try:
        result    = _transformer_pipeline(text[:1024])[0]
        label     = result.get("label", "").upper()
        raw_score = float(result.get("score", 0.5))
        score     = raw_score if label in ("LABEL_1", "FAKE", "AI") else 1.0 - raw_score
        conf      = min(1.0, abs(score - 0.5) * 2.0)
        return score, conf
    except Exception as exc:
        logger.warning("Transformer inference failed: %s", type(exc).__name__)
        return None, None


def analyze_text(text: str) -> dict:
    """
    Analyze text for AI-generation probability and model family attribution.

    Uses layered architecture:
      Layer 1 — HuggingFace transformer (if available)
      Layer 2 — Heuristic + stylometry (always runs; fallback if transformer fails)
      Layer 3 — Attribution fingerprinting
      Layer 4 — Deterministic explanation builder

    Args:
        text: The narrative/content to analyze. Raw text; never logged.

    Returns:
        {
            "ai_probability": float,         # 0..1
            "confidence":     float,          # 0..1
            "risk_level":     str,            # LOW|MEDIUM|HIGH|CRITICAL
            "model_attribution": str,         # GPT-family|Claude-family|Gemini-family|Unknown
            "explanation":    str             # 1-2 line human-readable reason
        }
    """
    if not isinstance(text, str) or not text.strip():
        return {
            "ai_probability":    0.0,
            "confidence":        0.0,
            "risk_level":        "LOW",
            "model_attribution": "Unknown",
            "explanation":       "Input was empty or invalid.",
        }

    # Import heuristic engine (always available — no external deps)
    from detection._heuristics import run_heuristics
    from detection.attribution import attribute_model
    from detection.explain import build_explanation

    # Layer 1: Transformer
    transformer_score = transformer_conf = None
    if _load_transformer():
        transformer_score, transformer_conf = _run_transformer(text)

    # Layer 2: Heuristics (always runs)
    heuristic_score, heuristic_conf, signals = run_heuristics(text)

    # Blend
    if transformer_score is not None:
        ai_probability = round(0.70 * transformer_score + 0.30 * heuristic_score, 4)
        confidence     = round(0.70 * transformer_conf  + 0.30 * heuristic_conf,  4)
        method_used    = "transformer+heuristic"
    else:
        ai_probability = round(heuristic_score, 4)
        confidence     = round(heuristic_conf,  4)
        method_used    = "heuristic-only"

    # Layer 3: Attribution
    model_attribution = attribute_model(text, ai_probability, signals)

    # Layer 4: Risk + explanation
    risk_level  = _classify_risk(ai_probability)
    explanation = build_explanation(
        ai_probability, risk_level, model_attribution, signals, method_used
    )

    return {
        "ai_probability":    ai_probability,
        "confidence":        confidence,
        "risk_level":        risk_level,
        "model_attribution": model_attribution,
        "explanation":       explanation,
    }


def _classify_risk(probability: float) -> str:
    """Map probability to risk level (LOCKED thresholds)."""
    if probability >= 0.85: return "CRITICAL"
    if probability >= 0.70: return "HIGH"
    if probability >= 0.50: return "MEDIUM"
    return "LOW"