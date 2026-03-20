"""
SENTINEL-AI — Model Attribution Module
========================================
Stylometric fingerprinting to attribute AI-generated text to likely
LLM families: GPT-family, Claude-family, Gemini-family, or Unknown.

IMPORTANT LIMITATIONS (see bottom of file):
  - Attribution is probabilistic heuristics, NOT forensic certainty.
  - These markers shift with model versions and prompt styles.
  - All attributions must be treated as intelligence signals, not verdicts.
  - Always display confidence alongside attribution in the UI.

Methodology:
  Each LLM family has measurable stylometric tendencies in:
    - Discourse structure and connector preference
    - Formatting habits (lists, headers, markdown)
    - Hedging and epistemic language patterns
    - Sentence rhythm and clause nesting depth
    - Vocabulary domains and register
    - Response framing ("Certainly!", "I'd be happy to", etc.)

  We compute family affinity scores, then pick the winner if it
  clears a minimum confidence threshold; otherwise → Unknown.
"""

import re
from typing import Optional


# ═══════════════════════════════════════════════════════════════════════════════
# Family signature dictionaries
# Each entry: (pattern_or_string, weight)
# Higher weight = stronger indicator
# ═══════════════════════════════════════════════════════════════════════════════

GPT_SIGNATURES = {
    # Discourse openers GPT-3.5/4 overuses
    "discourse": [
        ("of course",             1.2),
        ("certainly",             1.0),
        ("absolutely",            1.0),
        ("great question",        1.5),
        ("that's a great",        1.5),
        ("happy to help",         1.0),
        ("let's dive into",       1.2),
        ("let's explore",         1.0),
        ("to address your",       1.0),
        ("in summary",            0.8),
        ("to summarize",          0.8),
        ("in conclusion",         0.8),
        ("it's worth noting",     0.9),
        ("it is important to",    0.9),
    ],
    # GPT tends toward well-structured markdown with numbered steps
    "formatting": [
        (r"^\s*#+\s",             1.0),   # Markdown headers
        (r"^\s*\d+\.\s",          0.7),   # Numbered lists
        (r"\*\*[^*]+\*\*",        0.8),   # Bold markdown
    ],
    # Characteristic GPT phrases
    "phrases": [
        ("as an ai",              2.0),   # Strong: GPT-3.5 often self-references
        ("as a language model",   2.0),
        ("i don't have personal", 1.5),
        ("my training data",      1.5),
        ("based on the context",  0.8),
        ("tailored to your",      0.8),
        ("here are some",         0.6),
        ("here's a",              0.6),
        ("feel free to",          0.8),
    ],
}

CLAUDE_SIGNATURES = {
    "discourse": [
        ("i'd be happy to",       1.0),
        ("i'd be glad to",        1.0),
        ("let me think through",  1.5),
        ("that's an interesting", 1.2),
        ("this is a nuanced",     1.3),
        ("to be clear",           0.9),
        ("to be direct",          0.9),
        ("i want to be honest",   1.2),
        ("i should note",         1.0),
        ("it's worth mentioning", 0.8),
        ("what strikes me",       1.3),
        ("my honest assessment",  1.2),
    ],
    "formatting": [
        (r"^\s*[-–]\s",           0.9),   # Dash lists (Claude prefers dashes)
        (r"\n\n",                 0.5),   # Double newline paragraph breaks
    ],
    "phrases": [
        ("i'm claude",            3.0),   # Very strong
        ("anthropic",             2.0),
        ("i try to",              0.9),
        ("i aim to",              1.0),
        ("i believe that",        0.7),
        ("the tradeoffs here",    1.2),
        ("on balance",            1.0),
        ("there's genuine",       1.1),
        ("i think it's",          0.7),
        ("one important",         0.8),
        ("reasonable people",     1.2),
        ("it depends on",         0.8),
    ],
}

GEMINI_SIGNATURES = {
    "discourse": [
        ("absolutely right",      1.0),
        ("you're right that",     0.9),
        ("great point",           1.0),
        ("let me provide",        0.9),
        ("here is a",             0.7),
        ("here's what",           0.7),
        ("i can help you",        0.8),
        ("according to",          0.7),
        ("as per",                1.0),   # Gemini uses this frequently
    ],
    "formatting": [
        (r"^\*\s",                1.0),   # Bullet with asterisk
        (r"^\*\*\w",              0.8),   # Bold-first bullets
    ],
    "phrases": [
        ("bard",                  2.5),   # Legacy name reference
        ("google",                1.0),
        ("i'm designed to",       1.2),
        ("as a google",           2.0),
        ("my purpose is to",      0.9),
        ("note that i",           0.8),
        ("please note",           0.9),
        ("for example,",          0.6),
        ("keep in mind",          0.7),
    ],
}


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def attribute_model(
    text: str,
    ai_probability: float,
    heuristic_signals: Optional[dict] = None,
) -> str:
    """
    Attribute text to an LLM family based on stylometric signatures.

    Args:
        text:             Raw text (not logged).
        ai_probability:   From detector layer (0..1).
        heuristic_signals: Optional dict from heuristic engine.

    Returns:
        One of: "GPT-family" | "Claude-family" | "Gemini-family" | "Unknown"

    Logic:
        - If ai_probability < 0.40: skip attribution (likely human) → Unknown
        - Score each family against text
        - Winner must score > MIN_WIN_SCORE and lead runner-up by MIN_GAP
        - Otherwise → Unknown
    """
    MIN_AI_PROB_FOR_ATTRIBUTION = 0.40
    MIN_WIN_SCORE = 1.5   # minimum raw score to claim attribution
    MIN_GAP = 0.8         # winner must beat runner-up by this margin

    if ai_probability < MIN_AI_PROB_FOR_ATTRIBUTION:
        return "Unknown"

    text_lower = text.lower()

    scores = {
        "GPT-family":    _score_family(text_lower, text, GPT_SIGNATURES),
        "Claude-family": _score_family(text_lower, text, CLAUDE_SIGNATURES),
        "Gemini-family": _score_family(text_lower, text, GEMINI_SIGNATURES),
    }

    winner = max(scores, key=scores.get)
    winner_score = scores[winner]
    runner_up_score = sorted(scores.values())[-2]

    if winner_score >= MIN_WIN_SCORE and (winner_score - runner_up_score) >= MIN_GAP:
        return winner
    else:
        return "Unknown"


def get_attribution_scores(text: str) -> dict:
    """
    Return raw attribution scores for all families.
    Useful for dashboard confidence bars and debugging.

    Returns:
        {
            "GPT-family": float,
            "Claude-family": float,
            "Gemini-family": float,
        }
    """
    text_lower = text.lower()
    return {
        "GPT-family":    round(_score_family(text_lower, text, GPT_SIGNATURES), 3),
        "Claude-family": round(_score_family(text_lower, text, CLAUDE_SIGNATURES), 3),
        "Gemini-family": round(_score_family(text_lower, text, GEMINI_SIGNATURES), 3),
    }


def get_matched_signatures(text: str, family: str) -> list[str]:
    """
    Return list of matched signature strings for a given family.
    Useful for explainability panel in the SOC dashboard.
    """
    family_map = {
        "GPT-family":    GPT_SIGNATURES,
        "Claude-family": CLAUDE_SIGNATURES,
        "Gemini-family": GEMINI_SIGNATURES,
    }
    if family not in family_map:
        return []

    text_lower = text.lower()
    sigs = family_map[family]
    matches = []

    for patterns in sigs.values():
        for pattern, _ in patterns:
            if pattern.startswith("^") or "\\" in pattern or "(" in pattern:
                # Regex pattern
                if re.search(pattern, text, re.MULTILINE | re.IGNORECASE):
                    matches.append(f"[formatting] {pattern}")
            else:
                # Plain string
                if pattern in text_lower:
                    matches.append(pattern)

    return matches[:8]  # cap for display


# ═══════════════════════════════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _score_family(text_lower: str, text_raw: str, signatures: dict) -> float:
    """
    Score a text against one family's signature dictionary.
    Returns cumulative weighted hit score.
    """
    total = 0.0

    for category, patterns in signatures.items():
        for pattern, weight in patterns:
            if pattern.startswith("^") or "\\" in pattern or "(" in pattern:
                # Regex (formatting patterns)
                hits = len(re.findall(pattern, text_raw, re.MULTILINE | re.IGNORECASE))
                total += min(hits, 5) * weight * 0.5   # cap regex contribution
            else:
                # Plain substring — count occurrences, cap at 3
                count = text_lower.count(pattern)
                total += min(count, 3) * weight

    return total


# ═══════════════════════════════════════════════════════════════════════════════
# Ethical limitations note (see also LIMITATIONS.md)
# ═══════════════════════════════════════════════════════════════════════════════

ATTRIBUTION_LIMITATIONS = """
ATTRIBUTION LIMITATIONS — SENTINEL-AI v0.1 (MVP)
==================================================
1. STYLOMETRIC DRIFT: LLM families update frequently. Signature patterns
   effective for GPT-4 / Claude 3 / Gemini 1.5 may degrade for newer versions.

2. PROMPT SENSITIVITY: System prompts can suppress or amplify any of these
   markers. An adversary explicitly instructed to avoid discourse markers will
   reduce our F1 significantly.

3. SHORT TEXT PENALTY: Texts under 100 words have low attribution reliability.
   The dashboard should display a "Low confidence — short text" warning.

4. MULTILINGUAL: Signatures are English-only. Non-English text should route
   to Unknown without penalizing ai_probability.

5. FALSE POSITIVE RISK ON HUMAN AUTHORS: Some humans (academics, journalists)
   naturally produce structured, connector-rich text that scores as AI-like.
   HUMAN REVIEW IS MANDATORY before any consequential action.

6. NOT FOR LEGAL/ENFORCEMENT USE: Attribution output is an intelligence signal
   for SOC analysts. It must never be used as standalone evidence for
   attribution, disciplinary action, or content removal decisions.
"""