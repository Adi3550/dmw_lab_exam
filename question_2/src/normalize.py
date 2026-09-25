import re
import unicodedata


REFERENCE_PATTERNS = [
    r"\bNPAS[-/][A-Z0-9/-]+\b",
    r"\bSPC[-/][A-Z0-9/-]+\b",
    r"\bPWD[-/][A-Z0-9/-]+\b",
    r"\bMC[-/][A-Z0-9/-]+\b",
    r"\bTN[-/][A-Z0-9/-]+\b",
    r"\bREF[-/][A-Z0-9/-]+\b",
]


def normalize_text(title, body):
    """
    Convert a tender notice into a canonical text representation.

    The goal is to remove formatting differences and portal-specific
    noise while keeping information useful for identifying the tender.
    """

    text = f"{title} {body}"

    # Unicode normalization
    text = unicodedata.normalize("NFKC", str(text))

    # Case normalization
    text = text.lower()

    # Replace portal-specific reference numbers
    for pattern in REFERENCE_PATTERNS:
        text = re.sub(pattern, " REFNUM ", text, flags=re.IGNORECASE)

    # Normalize monetary expressions
    text = re.sub(
        r"(rs\.?|inr|rupees?)\s*[\d,]+(?:\.\d+)?\s*(?:/-)?",
        " MONEY ",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\b\d+(?:\.\d+)?\s*(?:cr|crore|crores|lakh|lakhs)\b",
        " MONEY ",
        text,
        flags=re.IGNORECASE,
    )

    # Normalize common date formats
    date_patterns = [
        r"\b\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}\b",
        r"\b\d{4}[-/.]\d{1,2}[-/.]\d{1,2}\b",
        r"\b\d{1,2}\s+[a-z]{3,9}\s+\d{2,4}\b",
        r"\b[a-z]{3,9}\s+\d{1,2},?\s+\d{2,4}\b",
    ]

    for pattern in date_patterns:
        text = re.sub(pattern, " DATE ", text)

    # Remove known nodal-portal boilerplate
    text = re.sub(
        r"national procurement aggregation service",
        " ",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"state procurement cell",
        " ",
        text,
        flags=re.IGNORECASE,
    )

    # Remove punctuation
    text = re.sub(r"[^a-z0-9\s]", " ", text)

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


def word_shingles(text, size=5):
    """
    Create word-level shingles.

    Example:
    'road widening work at patan'
    with size=3 becomes:
    ('road', 'widening', 'work')
    ('widening', 'work', 'at')
    ('work', 'at', 'patan')
    """

    words = text.split()

    if len(words) < size:
        return set()

    return {
        tuple(words[i:i + size])
        for i in range(len(words) - size + 1)
    }


def jaccard_similarity(set_a, set_b):
    """Calculate Jaccard similarity."""

    union = set_a | set_b

    if not union:
        return 0.0

    return len(set_a & set_b) / len(union)