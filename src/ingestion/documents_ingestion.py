"""
Streaming ingestion module for Recall Associated Documents (CSV).
Reads CSV records directly from zip archives.
"""

import csv
import io
import os
import zipfile
from typing import Generator, List


def stream_document_records(zip_path: str) -> Generator[List[str], None, None]:
    """
    Generator yielding row lists for each record in a recall documents CSV archive.
    Skips the header row.
    """
    if not os.path.isfile(zip_path):
        raise FileNotFoundError(f"Recall documents archive not found: {zip_path}")

    with zipfile.ZipFile(zip_path, "r") as z:
        inner_name = z.namelist()[0]
        with z.open(inner_name, "r") as f:
            text_stream = io.TextIOWrapper(f, encoding="utf-8", errors="replace")
            reader = csv.reader(text_stream)
            # Skip header
            _ = next(reader, None)
            for row in reader:
                if not row or not any(row):
                    continue
                yield row
