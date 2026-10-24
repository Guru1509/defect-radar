"""
Canonical preprocessing module for NHTSA Defect Investigations (FLAT_INV).
Consolidates raw multi-row investigation records into:
- investigations.parquet (1 canonical row per NHTSA_ACTION_NUMBER)
- investigation_vehicles.parquet (distinct affected vehicle variants per investigation)

Enforces strict investigation-level aggregation rules and documents them.
"""

import os
import time
from typing import Dict, List, Optional

import pyarrow as pa
import pyarrow.parquet as pq

from src.ingestion.investigations_ingestion import stream_investigation_lines
from src.preprocessing.normalization import (
    clean_text_narrative,
    derive_investigation_action_type,
    normalize_component_hierarchy,
    normalize_make,
    normalize_model,
    parse_date_iso,
    parse_model_year,
)

INVESTIGATIONS_SCHEMA = pa.schema([
    ("investigation_id", pa.string()),
    ("action_type", pa.string()),
    ("opened_date", pa.date32()),
    ("closed_date", pa.date32()),
    ("recall_campaign_number", pa.string()),
    ("subject", pa.string()),
    ("summary", pa.string()),
    ("manufacturer", pa.string()),
    ("record_count", pa.int32()),
])

INVESTIGATION_VEHICLES_SCHEMA = pa.schema([
    ("investigation_id", pa.string()),
    ("make_raw", pa.string()),
    ("make_normalized", pa.string()),
    ("model_raw", pa.string()),
    ("model_normalized", pa.string()),
    ("model_year", pa.int32()),
    ("component_raw", pa.string()),
    ("component_normalized", pa.string()),
    ("manufacturer", pa.string()),
])


def process_investigations_pipeline(
    raw_archive_path: str,
    output_inv_path: str,
    output_vehicles_path: str,
    batch_size: int = 50_000,
) -> Dict:
    """
    Streams FLAT_INV archive, aggregates investigation data into investigations.parquet,
    and streams vehicle variants into investigation_vehicles.parquet.
    """
    t0 = time.time()
    os.makedirs(os.path.dirname(output_inv_path), exist_ok=True)

    # Dictionary to accumulate investigation-level records (5,349 investigations is <5MB RAM)
    inv_acc: Dict[str, Dict] = {}

    veh_writer = pq.ParquetWriter(
        output_vehicles_path, INVESTIGATION_VEHICLES_SCHEMA, compression="snappy"
    )
    veh_buffer: List[Dict] = []
    seen_vehicle_keys = set()

    total_raw_rows = 0

    def flush_veh_buffer():
        nonlocal veh_buffer
        if veh_buffer:
            table_veh = pa.Table.from_pylist(
                veh_buffer, schema=INVESTIGATION_VEHICLES_SCHEMA
            )
            veh_writer.write_table(table_veh)
            veh_buffer.clear()

    try:
        print(f"  Ingesting investigations from {raw_archive_path}...")
        for parts in stream_investigation_lines(raw_archive_path):
            total_raw_rows += 1
            action_num = parts[0].strip().upper()
            if not action_num:
                continue

            make_raw = parts[1].strip()
            model_raw = parts[2].strip()
            year_val = parse_model_year(parts[3].strip())
            comp_raw = parts[4].strip()
            mfr_name = parts[5].strip()
            odate_dt = parse_date_iso(parts[6].strip())
            cdate_dt = parse_date_iso(parts[7].strip())
            campno = parts[8].strip().upper()
            subject_raw, subject_clean = clean_text_narrative(parts[9].strip())
            summary_raw, summary_clean = clean_text_narrative(parts[10].strip())

            action_type = derive_investigation_action_type(action_num)
            make_norm = normalize_make(make_raw)
            model_norm = normalize_model(model_raw)
            comp_norm, _, _ = normalize_component_hierarchy(comp_raw)

            # 1. Update Investigation Aggregate Record
            if action_num not in inv_acc:
                inv_acc[action_num] = {
                    "investigation_id": action_num,
                    "action_type": action_type,
                    "opened_date": odate_dt,
                    "closed_date": cdate_dt,
                    "recall_campaign_number": campno or None,
                    "subject": subject_clean or None,
                    "summary": summary_clean or None,
                    "manufacturer": mfr_name or None,
                    "record_count": 1,
                }
            else:
                inv = inv_acc[action_num]
                inv["record_count"] += 1
                if not inv["manufacturer"] and mfr_name:
                    inv["manufacturer"] = mfr_name
                # Earliest opened date
                if odate_dt:
                    if not inv["opened_date"] or odate_dt < inv["opened_date"]:
                        inv["opened_date"] = odate_dt
                # Latest closed date
                if cdate_dt:
                    if not inv["closed_date"] or cdate_dt > inv["closed_date"]:
                        inv["closed_date"] = cdate_dt
                # Associated recall campaign if found
                if not inv["recall_campaign_number"] and campno:
                    inv["recall_campaign_number"] = campno
                # Longest subject and summary
                if subject_clean and len(subject_clean) > len(inv["subject"] or ""):
                    inv["subject"] = subject_clean
                if summary_clean and len(summary_clean) > len(inv["summary"] or ""):
                    inv["summary"] = summary_clean

            # 2. Add to Vehicle Variants (deduplicated per vehicle variant)
            veh_key = (action_num, make_norm, model_norm, year_val, comp_norm)
            if veh_key not in seen_vehicle_keys:
                seen_vehicle_keys.add(veh_key)
                veh_buffer.append({
                    "investigation_id": action_num,
                    "make_raw": make_raw or None,
                    "make_normalized": make_norm or None,
                    "model_raw": model_raw or None,
                    "model_normalized": model_norm or None,
                    "model_year": year_val,
                    "component_raw": comp_raw or None,
                    "component_normalized": comp_norm or None,
                    "manufacturer": mfr_name or None,
                })
                if len(veh_buffer) >= batch_size:
                    flush_veh_buffer()

        flush_veh_buffer()
    finally:
        veh_writer.close()

    # Write canonical investigations to investigations.parquet
    print(f"  Writing {len(inv_acc)} canonical investigations to {output_inv_path}...")
    inv_list = list(inv_acc.values())
    table_inv = pa.Table.from_pylist(inv_list, schema=INVESTIGATIONS_SCHEMA)
    pq.write_table(table_inv, output_inv_path, compression="snappy")

    elapsed = time.time() - t0
    stats = {
        "dataset": "investigations & investigation_vehicles",
        "raw_rows_read": total_raw_rows,
        "canonical_investigations_written": len(inv_list),
        "canonical_investigation_vehicles_written": len(seen_vehicle_keys),
        "processing_time_sec": round(elapsed, 2),
        "investigations_output": output_inv_path,
        "vehicles_output": output_vehicles_path,
    }
    return stats
