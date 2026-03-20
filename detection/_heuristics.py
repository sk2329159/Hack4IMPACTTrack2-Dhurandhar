"""
SENTINEL-AI — Heuristic Engine
================================
Extracted from detector.py for clean separation.
Called by analyzer_text() in detector.py as the always-available fallback.
"""
import re
import math


def run_heuristics(text: str):
    """
    Compute AI-likelihood from 9 stylometric signals.
    Returns (score 0..1, confidence 0..1, signals dict).
    """
    words     = text.split()
    sentences = _split_sentences(text)
    word_count = len(words)
    sent_count = max(1, len(sentences))

    if word_count < 20:
        return 0.5, 0.2, {"too_short": True}

    signals   = {}
    text_lower = text.lower()

    # 1. Burstiness
    sent_lengths = [len(s.split()) for s in sentences if s.strip()]
    mean_len  = sum(sent_lengths) / max(1, len(sent_lengths))
    variance  = sum((l - mean_len) ** 2 for l in sent_lengths) / max(1, len(sent_lengths))
    burstiness = math.sqrt(variance) / max(1.0, mean_len)
    burstiness_score = max(0.0, min(1.0, 1.0 - burstiness / 0.5))
    signals["burstiness"]       = round(burstiness, 3)
    signals["burstiness_score"] = round(burstiness_score, 3)

    # 2. TTR
    lower_words  = [w.lower().strip(".,!?;:\"'()") for w in words]
    raw_ttr      = len(set(lower_words)) / max(1, word_count)
    expected_ttr = max(0.35, 0.65 - (word_count / 1000))
    ttr_score    = max(0.0, 1.0 - abs(raw_ttr - expected_ttr) / 0.40)
    signals["ttr"]          = round(raw_ttr, 3)
    signals["expected_ttr"] = round(expected_ttr, 3)

    # 3. Discourse connectors
    discourse_markers = [
        "furthermore","moreover","additionally","consequently","nevertheless",
        "notwithstanding","in conclusion","to summarize","it is important to note",
        "it should be noted","in essence","as such","with that said",
        "certainly","absolutely","of course","feel free to",
        "let's dive into","happy to help","here are some",
    ]
    discourse_hits  = sum(1 for m in discourse_markers if m in text_lower)
    discourse_score = min(1.0, discourse_hits / 2.5)
    signals["discourse_hits"] = discourse_hits

    # 4. List formatting
    list_patterns   = len(re.findall(r"^\s*[-•*]\s+", text, re.MULTILINE))
    numbered        = len(re.findall(r"^\s*\d+\.\s+", text, re.MULTILINE))
    list_score      = min(1.0, (list_patterns + numbered) / 5.0)
    signals["list_items"] = list_patterns + numbered

    # 5. Hedge words
    hedge_words = ["may","might","could","would","potentially","likely",
                   "possibly","arguably","suggest","indicate","seem","tend to"]
    hedge_count  = sum(text_lower.count(h) for h in hedge_words)
    hedge_ratio  = hedge_count / max(1, word_count)
    hedge_score  = min(1.0, hedge_ratio / 0.04)
    signals["hedge_ratio"] = round(hedge_ratio, 4)

    # 6. Filler absence
    filler_words = ["um","uh","yeah","gonna","wanna","kinda","sorta",
                    "you know","honestly","basically","literally"]
    filler_hits        = sum(1 for f in filler_words if f in text_lower)
    filler_abs_score   = max(0.0, 1.0 - filler_hits / 3.0)
    signals["filler_hits"] = filler_hits

    # 7. Punctuation density
    sc_count    = text.count(";") + text.count(":")
    punct_density = sc_count / max(1, sent_count)
    punct_score = min(1.0, punct_density / 1.5)
    signals["punct_density"] = round(punct_density, 3)

    # 8. Paragraph uniformity
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) >= 3:
        para_lens    = [len(p.split()) for p in paragraphs]
        para_mean    = sum(para_lens) / len(para_lens)
        para_var     = sum((l - para_mean) ** 2 for l in para_lens) / len(para_lens)
        para_cv      = math.sqrt(para_var) / max(1.0, para_mean)
        uniformity   = max(0.0, 1.0 - para_cv / 0.5)
    else:
        uniformity = 0.5
    signals["para_uniformity"] = round(uniformity, 3)

    # 9. Section headers
    header_patterns = len(re.findall(
        r'^\s*(executive summary|key findings|analysis|recommendations|'
        r'introduction|conclusion|background|overview|summary)\s*$',
        text, re.MULTILINE | re.IGNORECASE
    ))
    md_headers    = len(re.findall(r'^\s*#{1,3}\s+\w', text, re.MULTILINE))
    header_score  = min(1.0, (header_patterns + md_headers * 0.5) / 2.0)
    signals["header_score"] = round(header_score, 3)

    # Weighted composite
    composite = (
        0.20 * burstiness_score +
        0.23 * discourse_score  +
        0.16 * filler_abs_score +
        0.09 * hedge_score      +
        0.11 * list_score       +
        0.06 * ttr_score        +
        0.04 * punct_score      +
        0.04 * uniformity       +
        0.07 * header_score
    )

    # Confidence from signal agreement + text length
    strong = sum(1 for s in [
        burstiness_score > 0.65, discourse_score > 0.5,
        filler_abs_score > 0.7,  list_score > 0.4,
    ] if s)
    length_factor = min(1.0, word_count / 300)
    confidence    = min(0.82, 0.35 + (strong / 4.0) * 0.35 + length_factor * 0.12)

    signals["composite_score"] = round(composite, 3)
    return composite, confidence, signals


def _split_sentences(text: str):
    cleaned = re.sub(r'^\s*\d+\.\s*', '', text, flags=re.MULTILINE)
    cleaned = re.sub(r'^\s*[-•*]\s*', '', cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r'\n+', ' ', cleaned)
    pattern = r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|!)\s'
    sents   = re.split(pattern, cleaned.strip())
    return [s for s in sents if len(s.split()) >= 3]