"""
SENTINEL-AI Stylometric Feature Extraction Module
=================================================
Extract linguistic and stylistic features for AI attribution and risk scoring.

Features designed for:
- LLM family attribution (GPT, Claude, Llama, etc.)
- Human vs. AI classification
- Coordinated campaign detection via stylometric fingerprints

Hack4Impact - Cybersecurity & Ethical AI Systems Track
"""

import re
import math
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, asdict
from collections import Counter


@dataclass
class StylometricFeatures:
    """
    Container for stylometric feature vector.
    
    All features normalized where applicable for cross-text comparison.
    """
    # Basic counts
    char_count: int
    word_count: int
    sentence_count: int
    
    # Length features
    avg_word_length: float
    avg_sentence_length: float
    
    # Vocabulary features
    unique_word_ratio: float
    # NOTE: type_token_ratio == unique_word_ratio mathematically.
    # Kept for backward compatibility with downstream consumers that reference it by name.
    # ML lead: prefer unique_word_ratio as the canonical key.
    type_token_ratio: float
    
    # Punctuation features
    punctuation_density: float
    comma_ratio: float
    period_ratio: float
    exclamation_ratio: float
    question_ratio: float
    
    # Structural features
    paragraph_count: int
    avg_paragraph_length: float
    
    # Character class features
    digit_ratio: float
    uppercase_ratio: float
    
    # Syntactic patterns
    function_word_ratio: float
    
    # Readability proxy
    avg_syllables_per_word: float
    
    # Complexity indicators
    long_word_ratio: float  # words > 6 chars
    
    # Consistency (for AI detection)
    sentence_length_variance: float
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class StylometricExtractor:
    """
    Extract stylometric features from text for AI attribution.
    
    Design goals:
    - Deterministic: Same text → same features
    - Language-agnostic basics (English-optimized but extensible)
    - Fast: Suitable for real-time processing
    - Privacy-safe: No content storage, only statistics
    """
    
    # Function words (English) - indicative of writing style
    FUNCTION_WORDS = {
        'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'i',
        'it', 'for', 'not', 'on', 'with', 'he', 'as', 'you', 'do', 'at',
        'this', 'but', 'his', 'by', 'from', 'they', 'we', 'say', 'her',
        'she', 'or', 'an', 'will', 'my', 'one', 'all', 'would', 'there',
        'their', 'what', 'so', 'up', 'out', 'if', 'about', 'who', 'get',
        'which', 'go', 'me', 'when', 'make', 'can', 'like', 'time', 'no',
        'just', 'him', 'know', 'take', 'people', 'into', 'year', 'your',
        'good', 'some', 'could', 'them', 'see', 'other', 'than', 'then',
        'now', 'look', 'only', 'come', 'its', 'over', 'think', 'also',
        'back', 'after', 'use', 'two', 'how', 'our', 'work', 'first',
        'well', 'way', 'even', 'new', 'want', 'because', 'any', 'these',
        'give', 'day', 'most', 'us', 'is', 'was', 'are', 'were', 'been',
        'has', 'had', 'did', 'does', 'doing', 'done'
    }
    
    # Punctuation categories
    PUNCTUATION = set('.,;:!?-—"\'()[]{}')
    SENTENCE_END = set('.!?')
    
    def __init__(self):
        """Initialize extractor with compiled regex patterns."""
        # Word tokenization (simple but effective)
        self.word_pattern = re.compile(r"\b[a-zA-Z']+\b")
        # Sentence splitting (handles common cases)
        self.sentence_pattern = re.compile(r'[.!?]+\s+')
        # Paragraph splitting
        self.paragraph_pattern = re.compile(r'\n\s*\n')
        # Syllable estimation (simple heuristic)
        self.vowel_group = re.compile(r'[aeiouy]+', re.IGNORECASE)
    
    def _count_syllables(self, word: str) -> int:
        """
        Estimate syllable count using vowel groups.
        
        Simple heuristic: count vowel groups, with adjustments.
        """
        word = word.lower()
        if len(word) <= 3:
            return 1
        
        # Remove silent e
        if word.endswith('e'):
            word = word[:-1]
        
        vowel_groups = self.vowel_group.findall(word)
        count = len(vowel_groups) if vowel_groups else 1
        
        # Cap at reasonable maximum
        return min(count, 5)
    
    def extract(self, text: str) -> StylometricFeatures:
        """
        Extract complete stylometric feature vector.

        Args:
            text: Pre-cleaned text (run through preprocessing.clean_text first)

        Returns:
            StylometricFeatures dataclass with all metrics.
            Returns zeroed features for empty/None input.
        """
        if not text or not isinstance(text, str) or not text.strip():
            return self._empty_features()
        
        # Basic character metrics
        char_count = len(text)
        
        # Word tokenization
        words = self.word_pattern.findall(text)
        word_count = len(words)
        
        if word_count == 0:
            return self._empty_features()
        
        # Sentence segmentation
        sentences = [s.strip() for s in self.sentence_pattern.split(text) if s.strip()]
        if not sentences:
            # No sentence-ending punctuation — treat whole text as one sentence
            sentences = [text.strip()]
        sentence_count = len(sentences)
        
        # Paragraph segmentation
        paragraphs = [p.strip() for p in self.paragraph_pattern.split(text) if p.strip()]
        paragraph_count = len(paragraphs) if paragraphs else 1
        
        # Word length metrics
        word_lengths = [len(w) for w in words]
        avg_word_length = sum(word_lengths) / word_count
        
        # Vocabulary diversity
        unique_words = set(w.lower() for w in words)
        unique_word_count = len(unique_words)
        unique_word_ratio = unique_word_count / word_count
        type_token_ratio = unique_word_ratio  # Alias for clarity
        
        # Sentence length metrics
        sentence_word_counts = []
        for sent in sentences:
            sent_words = self.word_pattern.findall(sent)
            sentence_word_counts.append(len(sent_words))
        
        avg_sentence_length = sum(sentence_word_counts) / sentence_count
        
        # Sentence length variance (AI tends to be more consistent)
        if sentence_count > 1:
            variance = sum((x - avg_sentence_length) ** 2 for x in sentence_word_counts) / sentence_count
            sentence_length_variance = math.sqrt(variance)  # Standard deviation
        else:
            sentence_length_variance = 0.0
        
        # Punctuation analysis
        punct_count = sum(1 for c in text if c in self.PUNCTUATION)
        punctuation_density = punct_count / char_count if char_count > 0 else 0.0
        
        comma_count = text.count(',')
        period_count = text.count('.')
        exclamation_count = text.count('!')
        question_count = text.count('?')
        
        comma_ratio = comma_count / word_count
        period_ratio = period_count / sentence_count if sentence_count > 0 else 0.0
        exclamation_ratio = exclamation_count / sentence_count if sentence_count > 0 else 0.0
        question_ratio = question_count / sentence_count if sentence_count > 0 else 0.0
        
        # Paragraph metrics
        avg_paragraph_length = word_count / paragraph_count if paragraph_count > 0 else word_count
        
        # Character class ratios
        digit_count = sum(1 for c in text if c.isdigit())
        digit_ratio = digit_count / char_count if char_count > 0 else 0.0
        
        uppercase_count = sum(1 for c in text if c.isupper())
        uppercase_ratio = uppercase_count / char_count if char_count > 0 else 0.0
        
        # Function word usage (style indicator)
        function_word_count = sum(1 for w in words if w.lower() in self.FUNCTION_WORDS)
        function_word_ratio = function_word_count / word_count
        
        # Syllable estimation for readability proxy
        total_syllables = sum(self._count_syllables(w) for w in words)
        avg_syllables_per_word = total_syllables / word_count
        
        # Long word ratio (complexity indicator)
        long_words = sum(1 for w in word_lengths if w > 6)
        long_word_ratio = long_words / word_count
        
        return StylometricFeatures(
            char_count=char_count,
            word_count=word_count,
            sentence_count=sentence_count,
            avg_word_length=round(avg_word_length, 3),
            avg_sentence_length=round(avg_sentence_length, 2),
            unique_word_ratio=round(unique_word_ratio, 4),
            type_token_ratio=round(type_token_ratio, 4),
            punctuation_density=round(punctuation_density, 4),
            comma_ratio=round(comma_ratio, 4),
            period_ratio=round(period_ratio, 4),
            exclamation_ratio=round(exclamation_ratio, 4),
            question_ratio=round(question_ratio, 4),
            paragraph_count=paragraph_count,
            avg_paragraph_length=round(avg_paragraph_length, 2),
            digit_ratio=round(digit_ratio, 4),
            uppercase_ratio=round(uppercase_ratio, 4),
            function_word_ratio=round(function_word_ratio, 4),
            avg_syllables_per_word=round(avg_syllables_per_word, 3),
            long_word_ratio=round(long_word_ratio, 4),
            sentence_length_variance=round(sentence_length_variance, 2)
        )
    
    def _empty_features(self) -> StylometricFeatures:
        """Return zeroed features for empty text."""
        return StylometricFeatures(
            char_count=0, word_count=0, sentence_count=0,
            avg_word_length=0.0, avg_sentence_length=0.0,
            unique_word_ratio=0.0, type_token_ratio=0.0,
            punctuation_density=0.0, comma_ratio=0.0,
            period_ratio=0.0, exclamation_ratio=0.0, question_ratio=0.0,
            paragraph_count=0, avg_paragraph_length=0.0,
            digit_ratio=0.0, uppercase_ratio=0.0,
            function_word_ratio=0.0, avg_syllables_per_word=0.0,
            long_word_ratio=0.0, sentence_length_variance=0.0
        )
    
    def extract_batch(self, texts: List[str]) -> List[Dict]:
        """Extract features for multiple texts."""
        return [self.extract(text).to_dict() for text in texts]


class HarmScoreHeuristic:
    """
    Lightweight harm potential scoring for narrative analysis.
    
    Flags content with concerning patterns WITHOUT creating harmful content.
    Uses keyword-based detection for demo purposes.
    
    WARNING: This is a DEMO heuristic only. Production systems require:
    - Context-aware models
    - Human-in-the-loop review
    - Regular bias auditing
    """
    
    # Pattern categories (safe for demo - stylistic markers only, no operational instructions)
    PANIC_KEYWORDS = [
        'urgent', 'emergency', 'crisis', 'breaking', 'alert', 'warning',
        'danger', 'threat', 'attack', 'collapse', 'disaster', 'catastrophe',
        'imminent', 'critical', 'code red', 'red alert',
    ]
    
    ELECTION_MANIPULATION = [
        'rigged', 'stolen election', 'voter fraud', 'fake votes',
        'election integrity', 'counting fraud', 'ballot stuffing',
        'election rigged', 'votes stolen', 'electoral fraud',
    ]
    
    FINANCIAL_PANIC = [
        'market crash', 'bank run', 'economic collapse', 'financial crisis',
        'currency collapse', 'stock market collapse', 'bank failure',
        'dollar collapse', 'hyperinflation', 'financial meltdown', 'imminent',
    ]
    
    EXTREMIST_NARRATIVES = [
        'they are coming', 'wake up people', 'do your research',
        'mainstream media lying', 'hidden agenda', 'secret plan',
        'they dont want you', 'they are hiding', 'the truth is',
        'open your eyes', 'before its deleted',
    ]
    
    COORDINATION_INDICATORS = [
        'share this everywhere', 'copy and paste', 'spread the word',
        'make this viral', 'tag everyone', 'pass it on',
        'share before deleted', 'repost this', 'forward to everyone',
        'share now', 'tell everyone',
    ]

    def __init__(self):
        """Initialize heuristic with pattern lookup dict."""
        self.all_patterns = {
            'panic':        self.PANIC_KEYWORDS,
            'election':     self.ELECTION_MANIPULATION,
            'financial':    self.FINANCIAL_PANIC,
            'extremist':    self.EXTREMIST_NARRATIVES,
            'coordination': self.COORDINATION_INDICATORS,
        }

    def score(self, text: str) -> Dict:
        """
        Compute harm potential score.

        Returns:
            {
                'score': float (0.0-1.0),
                'categories': {'panic': float, 'election': float, ...},
                'flags': list of triggered category names,
                'keyword_matches': int (total hits across all categories)
            }
        """
        if not text or not isinstance(text, str):
            return {'score': 0.0, 'categories': {k: 0.0 for k in self.all_patterns}, 
                    'flags': [], 'keyword_matches': 0}
        
        text_lower = text.lower()
        
        category_scores = {}
        flags = []
        total_matches = 0
        
        for category, keywords in self.all_patterns.items():
            hits = sum(1 for kw in keywords if kw in text_lower)
            # Cap contribution per category at 1.0 (3+ hits = full score)
            category_scores[category] = min(1.0, hits / 3.0)
            total_matches += hits
            if hits > 0:
                flags.append(category)
        
        # Weighted combination — panic + coordination are strongest single signals
        weights = {
            'panic':        0.25,
            'election':     0.22,
            'financial':    0.20,
            'extremist':    0.18,
            'coordination': 0.15,
        }
        
        weighted_score = sum(
            category_scores.get(cat, 0.0) * weight
            for cat, weight in weights.items()
        )
        
        # Amplify when multiple categories co-occur (coordinated narratives)
        if len(flags) >= 2:
            weighted_score = min(1.0, weighted_score * 1.4)
        if len(flags) >= 3:
            weighted_score = min(1.0, weighted_score * 1.2)
        
        return {
            'score':            round(min(1.0, weighted_score), 4),
            'categories':       {k: round(v, 4) for k, v in category_scores.items()},
            'flags':            flags,
            'keyword_matches':  total_matches,
        }


# Convenience functions
def extract_stylometric_features(text: str) -> Dict:
    """
    Main entry point for feature extraction.
    
    Returns dict compatible with ML lead's attribution pipeline.
    """
    extractor = StylometricExtractor()
    return extractor.extract(text).to_dict()


def compute_harm_score(text: str) -> Dict:
    """
    Compute harm potential score.
    
    Returns dict with score and category breakdown.
    """
    heuristic = HarmScoreHeuristic()
    return heuristic.score(text)


def extract_all(text: str) -> Dict:
    """
    Extract all features and scores in one call.
    
    Returns comprehensive feature dict for dashboard and ML pipeline.
    """
    return {
        'stylometric': extract_stylometric_features(text),
        'harm_potential': compute_harm_score(text)
    }


if __name__ == "__main__":
    # Validation test
    test_text = """
    The quick brown fox jumps over the lazy dog. This is a test sentence.
    Another sentence here! And one more? Great.
    
    The economic situation requires urgent attention. Share this everywhere!
    """
    
    extractor = StylometricExtractor()
    features = extractor.extract(test_text)
    
    print("=== SENTINEL-AI Feature Extraction Test ===")
    print(f"Words: {features.word_count}, Sentences: {features.sentence_count}")
    print(f"Avg word length: {features.avg_word_length}")
    print(f"Unique word ratio: {features.unique_word_ratio}")
    print(f"Punctuation density: {features.punctuation_density}")
    print(f"Sentence length variance: {features.sentence_length_variance}")
    
    # Test harm score
    harm = compute_harm_score(test_text)
    print(f"\nHarm score: {harm['score']}")
    print(f"Categories: {harm['categories']}")