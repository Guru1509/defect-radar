"""
Normalization and data sanitization routines for DEFECTRADAR Phase 2.
Adheres strictly to the rule:
- Basic cleaning only (no stemming, no lemmatization, no stopword removal, no LLM).
- Both raw and normalized values preserved.
"""

import re
import unicodedata
from datetime import date
from typing import Optional, Tuple

# Precompiled regexes for performance
RE_WHITESPACE = re.compile(r"\s+")
RE_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
RE_COLON_SPACING = re.compile(r"\s*:\s*")

KNOWN_MAKE_ALIASES = {
    "HONDA (AMERICAN HONDA MOTOR CO.)": "HONDA",
    "AMERICAN HONDA MOTOR CO.": "HONDA",
    "FORD MOTOR COMPANY": "FORD",
    "GENERAL MOTORS, LLC": "GENERAL MOTORS",
    "GENERAL MOTORS CORP.": "GENERAL MOTORS",
    "TOYOTA MOTOR NORTH AMERICA, INC.": "TOYOTA",
    "TOYOTA MOTOR CORPORATION": "TOYOTA",
    "NISSAN NORTH AMERICA, INC.": "NISSAN",
    "HYUNDAI MOTOR AMERICA": "HYUNDAI",
    "KIA MOTORS AMERICA": "KIA",
    "KIA AMERICA, INC.": "KIA",
    "VOLKSWAGEN GROUP OF AMERICA, INC.": "VOLKSWAGEN",
    "FCA US LLC": "CHRYSLER",
    "CHRYSLER GROUP LLC": "CHRYSLER",
    "BMW OF NORTH AMERICA, LLC": "BMW",
    "SUBARU OF AMERICA, INC.": "SUBARU",
    "MAZDA NORTH AMERICAN OPERATIONS": "MAZDA",
    "MERCEDES-BENZ USA, LLC": "MERCEDES-BENZ",
    "VOLVO CAR USA, LLC": "VOLVO",
    "TESLA, INC.": "TESLA",
    "TESLA MOTORS, INC.": "TESLA",
    "JAGUAR LAND ROVER NORTH AMERICA, LLC": "JAGUAR LAND ROVER",
    "MITSUBISHI MOTORS NORTH AMERICA, INC.": "MITSUBISHI",
}


def clean_text_narrative(text: Optional[str]) -> Tuple[str, str]:
    """
    Cleans complaint text according to Phase 2 guidelines:
    - Normalizes whitespace (replaces newlines, tabs, multiple spaces)
    - Removes control characters
    - Fixes encoding artifacts via unicode normalization
    - Preserves all punctuation, digits, and technical terms
    Returns: (raw_text, clean_text)
    """
    if not text:
        return "", ""

    raw = str(text)
    # Normalize unicode to NFKC
    cleaned = unicodedata.normalize("NFKC", raw)
    # Remove control characters
    cleaned = RE_CONTROL_CHARS.sub(" ", cleaned)
    # Normalize whitespace to single space
    cleaned = RE_WHITESPACE.sub(" ", cleaned).strip()

    return raw, cleaned


def parse_date_iso(val: Optional[str]) -> Optional[date]:
    """
    Parses NHTSA YYYYMMDD string to Python datetime.date.
    Returns None if empty, invalid length, or invalid date.
    """
    if not val or len(val) != 8 or not val.isdigit():
        return None
    try:
        y, m, d = int(val[:4]), int(val[4:6]), int(val[6:8])
        if 1900 <= y <= 2030 and 1 <= m <= 12 and 1 <= d <= 31:
            return date(y, m, d)
    except (ValueError, OverflowError):
        pass
    return None


def parse_failure_date(fail_str: Optional[str], received_dt: Optional[date]) -> Optional[date]:
    """
    Parses failure/incident date (FAILDATE).
    Enforces quality checks:
    - Must be a valid date
    - Year must be >= 1980 (catches consumer typographical outliers like 1906, 1917)
    - Must not be in the future relative to received_date (if received_date is known)
    """
    dt = parse_date_iso(fail_str)
    if not dt:
        return None

    # Typo / historical outlier check
    if dt.year < 1980 or dt.year > 2026:
        return None

    # Temporal logic: failure cannot occur after NHTSA received the complaint
    if received_dt and dt > received_dt:
        return None

    return dt


def normalize_make(raw_make: Optional[str]) -> str:
    """Normalizes vehicle make: trims, uppercases, maps common manufacturer/brand aliases."""
    if not raw_make:
        return ""
    m = RE_WHITESPACE.sub(" ", raw_make.strip().upper())
    return KNOWN_MAKE_ALIASES.get(m, m)


def normalize_model(raw_model: Optional[str]) -> str:
    """Normalizes vehicle model: trims, uppercases, collapses whitespace."""
    if not raw_model:
        return ""
    m = RE_WHITESPACE.sub(" ", raw_model.strip().upper())
    return m


def parse_model_year(val: Optional[str]) -> Optional[int]:
    """
    Parses 4-digit model year.
    Returns None for 9999 (NHTSA code for unknown/N/A) or out of bounds [1970, 2027].
    """
    if not val:
        return None
    val_s = str(val).strip()
    if val_s.isdigit() and len(val_s) == 4:
        y = int(val_s)
        if 1970 <= y <= 2027 and y != 9999:
            return y
    return None


def parse_bool_yn(val: Optional[str], default: bool = False) -> bool:
    """Parses 'Y'/'N' string to boolean. Defaults to False for blanks/unspecified."""
    if not val:
        return default
    v = str(val).strip().upper()
    if v in ("Y", "YES", "1", "TRUE"):
        return True
    if v in ("N", "NO", "0", "FALSE"):
        return False
    return default


def parse_int_safe(val: Optional[str], default: Optional[int] = None) -> Optional[int]:
    """Safely parses string to integer."""
    if not val:
        return default
    try:
        # handle potential float strings like "10.0"
        return int(float(str(val).strip()))
    except (ValueError, TypeError):
        return default


def normalize_component_hierarchy(raw_comp: Optional[str]) -> Tuple[str, str, Optional[str]]:
    """
    Parses NHTSA hierarchical component string:
    e.g. 'SERVICE BRAKES, HYDRAULIC:ANTILOCK:WHEEL SPEED SENSOR'
    Returns: (normalized_comp, primary_system, subsystem)
    """
    if not raw_comp:
        return "", "", None

    # Clean colon spacing and whitespace
    comp_clean = RE_WHITESPACE.sub(" ", raw_comp.strip().upper())
    comp_norm = RE_COLON_SPACING.sub(":", comp_clean)

    parts = comp_norm.split(":", 1)
    primary_system = parts[0].strip()
    subsystem = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None

    return comp_norm, primary_system, subsystem


def derive_investigation_action_type(action_number: str) -> str:
    """
    Extracts action type prefix from NHTSA action number (e.g., PE21005 -> PE, EA19002 -> EA).
    Prefix meanings:
    PE = Preliminary Evaluation
    EA = Engineering Analysis
    RQ = Recall Query
    DP = Defect Petition
    AQ = Audit Query
    EQ = Equipment Query
    SQ = Special Query
    """
    if not action_number:
        return "UNKNOWN"
    alpha_prefix = "".join([c for c in str(action_number).strip().upper() if c.isalpha()])
    return alpha_prefix if alpha_prefix else "OTHER"
