"""
Text preparation and narrative quality analysis for DEFECTRADAR Phase 3.
Transforms complaint narratives into focused semantic failure/symptom text
without allowing vehicle metadata (make, model, year, state) to dominate.
"""

import re
from typing import Dict, List, Optional, Tuple

import pyarrow as pa
import pyarrow.compute as pc

# Pattern to strip administrative clerk initials at the very end of complaint text
# (e.g., "*TR", "*LD *TR", "*JB")
RE_TRAILING_CLERK_TAGS = re.compile(r"(\s*\*[A-Z]{2,4}\b)+$", re.IGNORECASE)

# Pattern to strip common administrative telephone intake preambles
RE_PREAMBLE = re.compile(
    r"^(THE CONSUMER STATED THAT|THE CALLER STATED THAT|THE CONSUMER STATES THAT|"
    r"THE CALLER REPORTED THAT|CONSUMER WRITES IN REGARDS TO|CONSUMER STATED THAT|"
    r"CONSUMER STATES THAT|CALLER STATED THAT)\s+",
    re.IGNORECASE,
)

RE_WHITESPACE = re.compile(r"\s+")


def prepare_semantic_text(narrative_clean: Optional[str]) -> str:
    """
    Transforms cleaned complaint narrative into semantic_text representation:
    - Strips leading/trailing whitespace
    - Removes administrative intake boilerplate preambles
    - Strips trailing NHTSA clerk initials / transcription tags
    - Preserves all mechanical symptoms, driving conditions, speeds, and technical terms
    - Explicitly avoids prepending make, model, or year so the vector space
      clusters strictly by failure mechanics rather than brand.
    """
    if not narrative_clean:
        return ""

    text = str(narrative_clean).strip()
    if not text:
        return ""

    # Strip trailing transcription clerk tags
    text = RE_TRAILING_CLERK_TAGS.sub("", text).strip()

    # Strip intake preamble boilerplate
    text = RE_PREAMBLE.sub("", text).strip()

    # Normalize whitespace to single space
    text = RE_WHITESPACE.sub(" ", text).strip()

    return text


def analyze_text_corpus(
    complaints_table: pa.Table,
    text_column: str = "complaint_text_clean",
) -> Dict[str, any]:
    """
    Analyzes narrative text quality, lengths, and anomalies across the corpus.
    """
    total_records = complaints_table.num_rows
    lengths_arr = complaints_table["narrative_length"].to_numpy()

    empty_count = int(pc.sum(pc.equal(complaints_table["narrative_length"], 0)).as_py() or 0)
    short_count = int(pc.sum(pc.and_(
        pc.greater(complaints_table["narrative_length"], 0),
        pc.less(complaints_table["narrative_length"], 50),
    )).as_py() or 0)
    very_long_count = int(pc.sum(pc.greater_equal(complaints_table["narrative_length"], 1500)).as_py() or 0)

    # Calculate median and percentiles
    p50_len = float(__import__("numpy").median(lengths_arr))
    p90_len = float(__import__("numpy").percentile(lengths_arr, 90))
    mean_len = float(__import__("numpy").mean(lengths_arr))
    max_len = int(__import__("numpy").max(lengths_arr))

    return {
        "total_records": total_records,
        "empty_narratives": empty_count,
        "short_narratives_under_50_chars": short_count,
        "very_long_narratives_over_1500_chars": very_long_count,
        "mean_length": round(mean_len, 2),
        "median_length": round(p50_len, 2),
        "p90_length": round(p90_len, 2),
        "max_length": max_len,
        "eligible_for_embedding": total_records - empty_count,
        "excluded_empty": empty_count,
    }
