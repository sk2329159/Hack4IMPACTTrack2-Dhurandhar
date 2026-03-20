"""
SENTINEL-AI Text Preprocessing Module
======================================
Privacy-preserving text preprocessing for AI-generated content detection.
Handles normalization, cleaning, and PII masking for demo previews.

Hack4Impact - Cybersecurity & Ethical AI Systems Track
"""

import re
import hashlib
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class PreprocessingResult:
    """Container for preprocessing outputs."""
    original_hash: str  # SHA-256 hash for audit trail (not the content)
    cleaned_text: str
    preview_safe_text: str  # PII-masked version for storage/display
    metadata: Dict
    pii_detected: List[str]  # Types of PII found (not the actual values)


class TextPreprocessor:
    """
    Production-style text preprocessor with privacy safeguards.
    
    Design principles:
    - Data minimization: Never store raw PII
    - Deterministic: Same input → same output
    - Audit-friendly: Hash-based content tracking
    """
    
    # PII patterns for detection and masking
    PII_PATTERNS = {
        'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
        # Phone: require at least one separator to avoid matching 10-digit SSN-like strings
        'phone': re.compile(
            r'\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s][0-9]{3}[-.\s][0-9]{4}\b'
        ),
        # SSN: strict dashes/dots only (avoids phone collision)
        'ssn': re.compile(r'\b\d{3}[-]\d{2}[-]\d{4}\b'),
        'credit_card': re.compile(r'\b(?:\d{4}[-.\s]?){3}\d{4}\b'),
        'ip_address': re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'),
    }
    
    # Control characters and unwanted unicode
    CONTROL_CHARS = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]')
    
    # Multiple whitespace
    MULTI_WHITESPACE = re.compile(r'\s+')
    
    # URL pattern (for optional redaction)
    URL_PATTERN = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+')
    
    def __init__(self, mask_pii: bool = True, redact_urls: bool = False):
        """
        Initialize preprocessor.

        Args:
            mask_pii:    Whether to mask PII in preview output.
            redact_urls: Whether to redact URLs (useful for some platform compliance).
        """
        self._mask_pii = mask_pii       # stored as private to avoid shadowing method
        self._redact_urls = redact_urls  # stored as private to avoid shadowing method
    
    def clean_text(self, text: str) -> str:
        """
        Clean and normalize text for feature extraction.
        
        Pipeline:
        1. Remove control characters
        2. Normalize whitespace
        3. Preserve sentence structure
        
        Args:
            text: Raw input text
            
        Returns:
            Cleaned text ready for feature extraction
        """
        if not text or not isinstance(text, str):
            return ""
        
        # Step 1: Remove control characters
        cleaned = self.CONTROL_CHARS.sub('', text)
        
        # Step 2: Normalize whitespace (preserve paragraph breaks)
        # First, normalize within paragraphs
        cleaned = self.MULTI_WHITESPACE.sub(' ', cleaned)
        
        # Step 3: Strip leading/trailing whitespace
        cleaned = cleaned.strip()
        
        return cleaned
    
    def detect_pii(self, text: str) -> Tuple[List[str], Dict[str, List[str]]]:
        """
        Detect PII in text without storing the actual values.
        
        Args:
            text: Input text to analyze
            
        Returns:
            Tuple of (list of PII types found, dict of positions for masking)
        """
        pii_types = []
        pii_positions = {}
        
        for pii_type, pattern in self.PII_PATTERNS.items():
            matches = list(pattern.finditer(text))
            if matches:
                pii_types.append(pii_type)
                pii_positions[pii_type] = [(m.start(), m.end()) for m in matches]
        
        return pii_types, pii_positions
    
    # Masking token map: pii_type_key → display token
    PII_MASK_TOKENS = {
        'email':       '[EMAIL]',
        'phone':       '[PHONE]',
        'ssn':         '[SSN]',
        'credit_card': '[CARD]',
        'ip_address':  '[IP]',
    }

    def mask_pii_for_preview(self, text: str, pii_positions: Optional[Dict] = None) -> str:
        """
        Create PII-masked version safe for storage/display.

        Masking tokens:
            email       → [EMAIL]
            phone       → [PHONE]
            ssn         → [SSN]
            credit_card → [CARD]
            ip_address  → [IP]

        Args:
            text:          Original text.
            pii_positions: Pre-computed positions dict from detect_pii() (optional).

        Returns:
            Masked text safe for preview storage.
        """
        if not self._mask_pii:
            return text

        if pii_positions is None:
            _, pii_positions = self.detect_pii(text)

        # Build replacement list with correct tokens
        replacements = []
        for pii_type, positions in pii_positions.items():
            mask_token = self.PII_MASK_TOKENS.get(pii_type, f"[{pii_type.upper()}]")
            for start, end in positions:
                replacements.append((start, end, mask_token))

        # Sort by start position descending so replacements don't shift offsets
        replacements.sort(key=lambda x: x[0], reverse=True)

        masked = text
        for start, end, token in replacements:
            masked = masked[:start] + token + masked[end:]

        return masked
    
    def redact_urls(self, text: str) -> str:
        """Optional URL redaction for platform compliance."""
        if not self._redact_urls:
            return text
        return self.URL_PATTERN.sub('[URL]', text)
    
    def compute_content_hash(self, text: str) -> str:
        """
        Compute SHA-256 hash for audit trail.
        Returns first 16 hex chars (64-bit) — sufficient for demo deduplication.
        """
        return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]
    
    def process(self, text: str) -> 'PreprocessingResult':
        """
        Full preprocessing pipeline.

        Args:
            text: Raw input text

        Returns:
            PreprocessingResult with all outputs
        """
        if not text or not isinstance(text, str):
            return PreprocessingResult(
                original_hash="0000000000000000",
                cleaned_text="",
                preview_safe_text="",
                metadata={"original_length": 0, "cleaned_length": 0,
                          "pii_types_detected": [], "pii_count": 0},
                pii_detected=[],
            )

        # Compute hash of original (for audit)
        original_hash = self.compute_content_hash(text)
        
        # Detect PII before cleaning
        pii_types, pii_positions = self.detect_pii(text)
        
        # Clean text (for ML inference)
        cleaned = self.clean_text(text)
        
        # Create preview-safe version (PII-masked, for storage)
        preview = self.mask_pii_for_preview(text, pii_positions)
        preview = self.clean_text(preview)   # Apply same whitespace cleaning
        
        # Optional URL redaction on preview
        if self._redact_urls:
            preview = self.redact_urls(preview)
        
        metadata = {
            'original_length':     len(text),
            'cleaned_length':      len(cleaned),
            'pii_types_detected':  pii_types,
            'pii_count':           sum(len(pos) for pos in pii_positions.values()),
        }
        
        return PreprocessingResult(
            original_hash=original_hash,
            cleaned_text=cleaned,
            preview_safe_text=preview,
            metadata=metadata,
            pii_detected=pii_types,
        )


# Convenience functions for direct import
def clean_text(text: str) -> str:
    """Quick clean without PII masking."""
    preprocessor = TextPreprocessor(mask_pii=False)
    return preprocessor.clean_text(text)


def mask_pii(text: str) -> str:
    """Quick PII masking."""
    preprocessor = TextPreprocessor(mask_pii=True)
    _, positions = preprocessor.detect_pii(text)
    return preprocessor.mask_pii_for_preview(text, positions)


def preprocess_for_detection(text: str) -> Dict:
    """
    Full preprocessing for detection pipeline.

    Returns dict with BOTH 'hash' (legacy) and 'content_hash' (canonical per
    INTEGRATION.md) so both ML lead and NLP lead code works without changes.

    Keys:
        content_hash   : 16-char SHA-256 prefix (canonical name for ML pipeline)
        hash           : same value (legacy alias — do not remove)
        text           : cleaned text for ML inference
        preview        : PII-masked text for storage/display (≤ raw length)
        metadata       : {original_length, cleaned_length, pii_types_detected, pii_count}
        privacy_flags  : list of PII type strings (types only, never values)
    """
    preprocessor = TextPreprocessor(mask_pii=True)
    result = preprocessor.process(text)

    return {
        'content_hash':  result.original_hash,   # canonical key (INTEGRATION.md)
        'hash':          result.original_hash,   # legacy alias (do not remove)
        'text':          result.cleaned_text,
        'preview':       result.preview_safe_text,
        'metadata':      result.metadata,
        'privacy_flags': result.pii_detected,
    }


# Validation utilities
def validate_preprocessing(text: str, expected_hash: str) -> bool:
    """Verify content integrity via hash comparison."""
    preprocessor = TextPreprocessor()
    computed = preprocessor.compute_content_hash(text)
    return computed == expected_hash


if __name__ == "__main__":
    # Quick validation test
    test_text = """
    Contact me at john.doe@example.com or call 555-123-4567.
    My SSN is 123-45-6789 for verification.
    
    This is a test message with   extra   spaces and some
    line breaks that should be normalized.
    """
    
    preprocessor = TextPreprocessor()
    result = preprocessor.process(test_text)
    
    print("=== SENTINEL-AI Preprocessing Test ===")
    print(f"Hash: {result.original_hash}")
    print(f"PII detected: {result.pii_detected}")
    print(f"Metadata: {result.metadata}")
    print(f"\nCleaned ({len(result.cleaned_text)} chars):")
    print(result.cleaned_text[:200] + "...")
    print(f"\nPreview-safe ({len(result.preview_safe_text)} chars):")
    print(result.preview_safe_text[:200] + "...")