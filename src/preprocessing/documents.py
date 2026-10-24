"""
Canonical preprocessing module for Recall Associated Documents (CSV).
Processes 2015-2019 and 2020-2024 recall documents into:
- recall_documents.parquet (supplementary engineering documentation)
"""

import os
import time
from typing import Dict, List, Tuple

import pyarrow as pa
import pyarrow.parquet as pq

from src.ingestion.documents_ingestion import stream_document_records
from src.preprocessing.normalization import (
    clean_text_narrative,
    normalize_make,
    normalize_model,
    parse_model_year,
)

DOCUMENTS_SCHEMA = pa.schema([
    ("nhtsa_id", pa.string()),
    ("document_name", pa.string()),
    ("document_type", pa.string()),
    ("make_raw", pa.string()),
    ("make_normalized", pa.string()),
    ("model_raw", pa.string()),
    ("model_normalized", pa.string()),
    ("model_year", pa.int32()),
    ("summary", pa.string()),
    ("source_period", pa.string()),
])


def derive_doc_type(doc_name: str) -> str:
    """Extracts document classification prefix (e.g., RCMN, RCRIT, RCONL)."""
    if not doc_name:
        return "OTHER"
    if "-" in doc_name:
        return doc_name.split("-")[0].strip().upper()
    return "OTHER"


def process_documents_pipeline(
    raw_archives: List[Tuple[str, str]],
    output_docs_path: str,
    batch_size: int = 50_000,
) -> Dict:
    """
    Streams and processes recall document CSV archives directly into recall_documents.parquet.
    """
    t0 = time.time()
    os.makedirs(os.path.dirname(output_docs_path), exist_ok=True)

    doc_writer = pq.ParquetWriter(
        output_docs_path, DOCUMENTS_SCHEMA, compression="snappy"
    )
    doc_buffer: List[Dict] = []
    total_raw_rows = 0
    total_docs_written = 0

    def flush_doc_buffer():
        nonlocal doc_buffer
        if doc_buffer:
            table_doc = pa.Table.from_pylist(doc_buffer, schema=DOCUMENTS_SCHEMA)
            doc_writer.write_table(table_doc)
            doc_buffer.clear()

    try:
        for zip_path, period_label in raw_archives:
            print(f"  Ingesting recall documents from {zip_path} ({period_label})...")
            for row in stream_document_records(zip_path):
                total_raw_rows += 1
                nhtsa_id = row[0].strip().upper() if len(row) > 0 else ""
                doc_name = row[1].strip() if len(row) > 1 else ""
                make_raw = row[2].strip() if len(row) > 2 else ""
                model_raw = row[3].strip() if len(row) > 3 else ""
                year_val = parse_model_year(row[4].strip()) if len(row) > 4 else None
                summary_raw = row[5].strip() if len(row) > 5 else ""

                _, summary_clean = clean_text_narrative(summary_raw)
                doc_type = derive_doc_type(doc_name)
                make_norm = normalize_make(make_raw)
                model_norm = normalize_model(model_raw)

                doc_buffer.append({
                    "nhtsa_id": nhtsa_id or None,
                    "document_name": doc_name or None,
                    "document_type": doc_type,
                    "make_raw": make_raw or None,
                    "make_normalized": make_norm or None,
                    "model_raw": model_raw or None,
                    "model_normalized": model_norm or None,
                    "model_year": year_val,
                    "summary": summary_clean or None,
                    "source_period": period_label,
                })
                total_docs_written += 1

                if len(doc_buffer) >= batch_size:
                    flush_doc_buffer()

        flush_doc_buffer()
    finally:
        doc_writer.close()

    elapsed = time.time() - t0
    stats = {
        "dataset": "recall_documents",
        "raw_rows_read": total_raw_rows,
        "canonical_documents_written": total_docs_written,
        "processing_time_sec": round(elapsed, 2),
        "output_location": output_docs_path,
    }
    return stats
