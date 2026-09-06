"""
Input Normalization and Content Validation Guardrail.
Performs Unicode NFKC normalization, removes invisible characters, and validates payload bounds.
"""
import re
import unicodedata
from backend.app.core.config import settings
from backend.app.core.exceptions import SecurityBlockException

# Regex pattern for invisible and zero-width characters
ZERO_WIDTH_CHARS = re.compile(r"[\u200B-\u200D\uFEFF\u200E\u200F\u202A-\u202E]")
# Whitespace control characters (vertical tab, form feed) to convert to space
WHITESPACE_CONTROL_CHARS = re.compile(r"[\x0B\x0C]")
# Dangerous non-printable control characters to completely strip
NON_PRINTABLE_CHARS = re.compile(r"[\x00-\x08\x0E-\x1F\x7F]")


def normalize_input(text: str) -> str:
    """
    Normalizes user input string:
    1. Unicode NFKC normalization (combats homoglyphs and hidden ligatures)
    2. Stripping zero-width / invisible format characters
    3. Stripping dangerous control characters
    4. Trimming whitespace
    """
    if not text:
        return ""

    # Unicode NFKC normalization
    normalized = unicodedata.normalize("NFKC", text)

    # Strip zero-width / bidirectional override characters
    normalized = ZERO_WIDTH_CHARS.sub("", normalized)

    # Replace whitespace control characters with space (preserves word boundaries)
    normalized = WHITESPACE_CONTROL_CHARS.sub(" ", normalized)

    # Strip non-printable control characters
    normalized = NON_PRINTABLE_CHARS.sub("", normalized)

    # Collapse multiple consecutive spaces
    normalized = re.sub(r" {2,}", " ", normalized)

    return normalized.strip()


def validate_input_bounds(text: str) -> None:
    """
    Validates input length constraints to prevent resource exhaustion and buffer overflows.
    """
    if not text:
        raise SecurityBlockException("Empty input text", reason="empty_payload")

    if len(text) > settings.MAX_INPUT_CHARS:
        raise SecurityBlockException(
            f"Input text exceeds maximum allowed length of {settings.MAX_INPUT_CHARS} characters.",
            reason="input_length_exceeded",
            user_safe_message=f"Message is too long. Please keep your message under {settings.MAX_INPUT_CHARS} characters."
        )
