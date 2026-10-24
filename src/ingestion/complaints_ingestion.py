"""
Streaming ingestion module for NHTSA Consumer Complaints.
Reads compressed tab-delimited files directly from zip archives in chunks.
Exploits ODINO contiguity to yield grouped complaint cases with O(1) memory overhead.
"""

import io
import os
import zipfile
from typing import Generator, List, Tuple

from src.utils.audit_datasets import CMPL_COLUMNS


def stream_complaint_lines(zip_path: str) -> Generator[List[str], None, None]:
    """
    Generator yielding parsed fields for each row in a complaint archive.
    """
    if not os.path.isfile(zip_path):
        raise FileNotFoundError(f"Complaint archive not found: {zip_path}")

    with zipfile.ZipFile(zip_path, "r") as z:
        inner_name = z.namelist()[0]
        with z.open(inner_name, "r") as f:
            # 1MB buffer for fast I/O throughput
            buffered = io.BufferedReader(f, buffer_size=1024 * 1024)
            for line_bytes in buffered:
                line_str = line_bytes.decode("latin-1", errors="replace").rstrip("\r\n")
                if not line_str:
                    continue
                parts = line_str.split("\t")
                if len(parts) < len(CMPL_COLUMNS):
                    parts.extend([""] * (len(CMPL_COLUMNS) - len(parts)))
                yield parts


def stream_complaint_groups(
    zip_path: str,
) -> Generator[Tuple[str, List[List[str]]], None, None]:
    """
    Yields (odino, list_of_component_rows) for each complaint case.
    Takes advantage of empirical verification that ODINOs are 100% contiguous in NHTSA files.
    """
    current_odino = None
    current_group: List[List[str]] = []

    for parts in stream_complaint_lines(zip_path):
        odino = parts[1].strip()
        if not odino:
            continue

        if odino != current_odino:
            if current_odino is not None and current_group:
                yield current_odino, current_group
            current_odino = odino
            current_group = [parts]
        else:
            current_group.append(parts)

    if current_odino is not None and current_group:
        yield current_odino, current_group
