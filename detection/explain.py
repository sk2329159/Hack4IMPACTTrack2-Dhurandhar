"""
SENTINEL-AI — Explanation Builder
===================================
Generates deterministic, human-readable explanation strings for the
`explanation` field of analyze_text() output.

Design principles:
  - Template-driven (no generative model needed for explanation)
  - Deterministic: same inputs → same output (demo-safe)
  - 1-2 sentences max (per backend contract)
  - Factual, not alarmist
  - Surfaces the dominant signal(s) that drove the score
"""

from typing import Optional


# ── Template library ──────────────────────────────────────────────────────────

# Keyed by (risk_level, model_attribution)
_TEMPLATES = {
    # LOW risk
    ("LOW", "Unknown"): (
        "Text exhibits natural human writing patterns including varied sentence "
        "rhythm and organic discourse structure. AI-generation probability is low."
    ),

    # MEDIUM risk
    ("MEDIUM", "Unknown"): (
        "Text shows mixed signals: {top_signals}. "
        "Moderate AI-generation probability warrants analyst review."
    ),
    ("MEDIUM", "GPT-family"): (
        "Stylometric markers suggest GPT-family origin: {top_signals}. "
        "Confidence is moderate; human review recommended."
    ),
    ("MEDIUM", "Claude-family"): (
        "Discourse patterns consistent with Claude-family detected: {top_signals}. "
        "Score is in the medium range; treat as a soft signal."
    ),
    ("MEDIUM", "Gemini-family"): (
        "Text contains Gemini-family stylistic indicators: {top_signals}. "
        "Attribution confidence is moderate; verify before action."
    ),

    # HIGH risk
    ("HIGH", "Unknown"): (
        "High AI-generation probability detected via {top_signals}. "
        "Model family is ambiguous; escalate for analyst review."
    ),
    ("HIGH", "GPT-family"): (
        "Strong GPT-family stylometric fingerprint: {top_signals}. "
        "Content warrants analyst review before publication or distribution."
    ),
    ("HIGH", "Claude-family"): (
        "Claude-family attribution with high AI probability: {top_signals}. "
        "Recommend analyst triage for context verification."
    ),
    ("HIGH", "Gemini-family"): (
        "Gemini-family markers at high confidence: {top_signals}. "
        "Escalate per SOC protocol for narrative campaign analysis."
    ),

    # CRITICAL risk
    ("CRITICAL", "Unknown"): (
        "CRITICAL: Very high AI-generation probability ({prob:.0%}) with ambiguous "
        "model origin. Dominant signals: {top_signals}. Immediate analyst review required."
    ),
    ("CRITICAL", "GPT-family"): (
        "CRITICAL: Strong GPT-family signature at {prob:.0%} AI probability. "
        "Signals: {top_signals}. Flag for campaign-level intelligence review."
    ),
    ("CRITICAL", "Claude-family"): (
        "CRITICAL: Claude-family pattern at {prob:.0%} AI probability. "
        "Key signals: {top_signals}. Escalate immediately per SOC playbook."
    ),
    ("CRITICAL", "Gemini-family"): (
        "CRITICAL: Gemini-family fingerprint at {prob:.0%} AI probability. "
        "Evidence: {top_signals}. Escalate for malign information operation review."
    ),
}

_FALLBACK_TEMPLATE = (
    "AI-generation probability is {prob:.0%} ({risk_level} risk). "
    "Key signals: {top_signals}."
)


# ── Signal → human-readable labels ───────────────────────────────────────────

_SIGNAL_LABELS = {
    "burstiness_score":  "low sentence-length variance",
    "discourse_hits":    "elevated discourse connector density",
    "filler_hits":       "absence of natural filler language",
    "list_items":        "structured list formatting",
    "hedge_ratio":       "elevated hedging language",
    "punct_density":     "high colon/semicolon density",
    "para_uniformity":   "uniform paragraph lengths",
    "ttr":               "constrained lexical diversity",
}

_METHOD_LABELS = {
    "transformer+heuristic": "transformer model + stylometric heuristics",
    "heuristic-only":        "stylometric heuristic analysis (model offline)",
}


# ── Public API ────────────────────────────────────────────────────────────────

def build_explanation(
    ai_probability: float,
    risk_level: str,
    model_attribution: str,
    heuristic_signals: Optional[dict] = None,
    method_used: str = "heuristic-only",
) -> str:
    """
    Build a deterministic 1-2 sentence explanation string.

    Args:
        ai_probability:    Final blended score (0..1).
        risk_level:        "LOW|MEDIUM|HIGH|CRITICAL"
        model_attribution: "GPT-family|Claude-family|Gemini-family|Unknown"
        heuristic_signals: Signal dict from _run_heuristics().
        method_used:       "transformer+heuristic" or "heuristic-only"

    Returns:
        str — explanation suitable for the `explanation` field.
    """
    top_signals = _extract_top_signals(heuristic_signals or {}, n=3)
    signals_str = top_signals if top_signals else "structural uniformity and formal register"
    method_str = _METHOD_LABELS.get(method_used, method_used)

    key = (risk_level, model_attribution)
    template = _TEMPLATES.get(key, _FALLBACK_TEMPLATE)

    try:
        explanation = template.format(
            prob=ai_probability,
            risk_level=risk_level,
            top_signals=signals_str,
            method=method_str,
        )
    except KeyError:
        explanation = _FALLBACK_TEMPLATE.format(
            prob=ai_probability,
            risk_level=risk_level,
            top_signals=signals_str,
        )

    # Enforce 2-sentence max (truncate at second period if needed)
    explanation = _truncate_to_two_sentences(explanation)
    return explanation.strip()


def build_short_label(ai_probability: float, risk_level: str) -> str:
    """
    One-line badge label for dashboard cards.
    Example: "HIGH RISK — 78% AI probability"
    """
    return f"{risk_level} RISK — {ai_probability:.0%} AI probability"


# ── Internal helpers ──────────────────────────────────────────────────────────

def _extract_top_signals(signals: dict, n: int = 3) -> str:
    """
    Extract the n most informative signal labels from the heuristic dict.
    Returns a comma-joined human-readable string.
    """
    scored = []

    if signals.get("discourse_hits", 0) >= 2:
        scored.append(("discourse_hits", signals["discourse_hits"] * 0.5))
    if signals.get("burstiness_score", 0) > 0.6:
        scored.append(("burstiness_score", signals["burstiness_score"]))
    if signals.get("filler_hits", 1) == 0:
        scored.append(("filler_hits", 0.7))
    if signals.get("list_items", 0) >= 3:
        scored.append(("list_items", 0.6))
    if signals.get("hedge_ratio", 0) > 0.025:
        scored.append(("hedge_ratio", signals["hedge_ratio"] * 10))
    if signals.get("para_uniformity", 0) > 0.65:
        scored.append(("para_uniformity", signals["para_uniformity"]))
    if signals.get("punct_density", 0) > 0.5:
        scored.append(("punct_density", signals["punct_density"]))
    if signals.get("ttr", 0) > 0:
        scored.append(("ttr", abs(signals["ttr"] - 0.55)))

    # Sort by contribution score descending, take top n
    scored.sort(key=lambda x: x[1], reverse=True)
    top_keys = [k for k, _ in scored[:n]]

    if not top_keys:
        return "structural and lexical AI-like patterns"

    labels = [_SIGNAL_LABELS.get(k, k) for k in top_keys]
    if len(labels) == 1:
        return labels[0]
    elif len(labels) == 2:
        return f"{labels[0]} and {labels[1]}"
    else:
        return f"{labels[0]}, {labels[1]}, and {labels[2]}"


def _truncate_to_two_sentences(text: str) -> str:
    """
    Ensure explanation is at most 2 sentences.
    Splits on sentence-ending punctuation.
    """
    import re
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    if len(sentences) <= 2:
        return text
    return " ".join(sentences[:2])