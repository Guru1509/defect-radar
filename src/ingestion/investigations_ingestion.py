"""
Streaming ingestion module for NHTSA Defect Investigations (FLAT_INV).
Streams tab-delimited records directly from zip archive.
"""

import io
import os
import zipfile
from typing import Generator, List

from src.utils.audit_datasets import INV_COLUMNS


def stream_investigation_lines(zip_path: str) -> Generator[List[str], None, None]:
    """
    Generator yielding parsed fields for each row in the FLAT_INV archive.
    """
    if not os.path.isfile(zip_path):
        raise FileNotFoundError(f"Investigation archive not found: {zip_path}")

    with zipfile.ZipFile(zip_path, "r") as z:
        inner_name = z.namelist()[0]
        with z.open(inner_name, "r") as f:
            buffered = io.BufferedReader(f, buffer_size=1024 * 1024)
            for line_bytes in buffered:
                line_str = line_bytes.decode("latin-1", errors="replace").rstrip("\r\n")
                if not line_str:
                    continue
                parts = line_str.split("\t")
                if len(parts) < len(INV_COLUMNS):
                    parts.extend([""] * (len(INV_COLUMNS) - len(parts)))
                yield parts
