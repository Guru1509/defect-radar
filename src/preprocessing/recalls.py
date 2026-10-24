"""
Canonical preprocessing module for NHTSA Safety Recalls (FLAT_RCL).
Consolidates raw multi-row recall campaigns into:
- recalls.parquet (1 canonical row per CAMPNO)
- recall_vehicles.parquet (distinct affected vehicle variants per CAMPNO)

Enforces strict campaign-level aggregation rules and documents them.
"""

import os
import time
from typing import Dict, List, Optional

import pyarrow as pa
import pyarrow.parquet as pq

from src.ingestion.recalls_ingestion import stream_recall_lines
from src.preprocessing.normalization import (
    clean_text_narrative,
    normalize_component_hierarchy,
    normalize_make,
    normalize_model,
    parse_bool_yn,
    parse_date_iso,
    parse_int_safe,
    parse_model_year,
)

RECALLS_SCHEMA = pa.schema([
    ("campaign_number", pa.string()),
    ("manufacturer", pa.string()),
    ("recall_date", pa.date32()),
    ("owner_notification_date", pa.date32()),
    ("affected_units", pa.int64()),
    ("defect_description", pa.string()),
    ("consequence", pa.string()),
    ("corrective_action", pa.string()),
    ("do_not_drive", pa.bool_()),
    ("park_outside", pa.bool_()),
    ("influenced_by", pa.string()),
    ("record_count", pa.int32()),
])

RECALL_VEHICLES_SCHEMA = pa.schema([
    ("campaign_number", pa.string()),
    ("make_raw", pa.string()),
    ("make_normalized", pa.string()),
    ("model_raw", pa.string()),
    ("model_normalized", pa.string()),
    ("model_year", pa.int32()),
    ("component_raw", pa.string()),
    ("component_normalized", pa.string()),
])


def process_recalls_pipeline(
    raw_archive_path: str,
    output_recalls_path: str,
    output_vehicles_path: str,
    batch_size: int = 50_000,
) -> Dict:
    """
    Streams FLAT_RCL archive, aggregates campaign data into recalls.parquet,
    and streams vehicle variants into recall_vehicles.parquet.
    """
    t0 = time.time()
    os.makedirs(os.path.dirname(output_recalls_path), exist_ok=True)

    # Dictionary to accumulate campaign-level records (15,286 campaigns is ~15MB RAM)
    campaigns_acc: Dict[str, Dict] = {}

    veh_writer = pq.ParquetWriter(
        output_vehicles_path, RECALL_VEHICLES_SCHEMA, compression="snappy"
    )
    veh_buffer: List[Dict] = []
    seen_vehicle_keys = set()

    total_raw_rows = 0

    def flush_veh_buffer():
        nonlocal veh_buffer
        if veh_buffer:
            table_veh = pa.Table.from_pylist(veh_buffer, schema=RECALL_VEHICLES_SCHEMA)
            veh_writer.write_table(table_veh)
            veh_buffer.clear()

    try:
        print(f"  Ingesting recalls from {raw_archive_path}...")
        for parts in stream_recall_lines(raw_archive_path):
            total_raw_rows += 1
            campno = parts[1].strip().upper()
            if not campno:
                continue

            make_raw = parts[2].strip()
            model_raw = parts[3].strip()
            year_val = parse_model_year(parts[4].strip())
            comp_raw = parts[6].strip()
            mfg_name = parts[7].strip()
            potaff = parse_int_safe(parts[11].strip(), 0) or 0
            odate_dt = parse_date_iso(parts[12].strip())
            inf_by = parts[13].strip().upper()
            rcdate_dt = parse_date_iso(parts[15].strip())

            desc_raw, desc_clean = clean_text_narrative(parts[19].strip())
            conseq_raw, conseq_clean = clean_text_narrative(parts[20].strip())
            corr_raw, corr_clean = clean_text_narrative(parts[21].strip())

            do_not_drive = parse_bool_yn(parts[27].strip())
            park_outside = parse_bool_yn(parts[28].strip())

            make_norm = normalize_make(make_raw)
            model_norm = normalize_model(model_raw)
            comp_norm, _, _ = normalize_component_hierarchy(comp_raw)

            # 1. Update Campaign Aggregate Record
            if campno not in campaigns_acc:
                campaigns_acc[campno] = {
                    "campaign_number": campno,
                    "manufacturer": mfg_name or None,
                    "recall_date": rcdate_dt,
                    "owner_notification_date": odate_dt,
                    "affected_units": potaff,
                    "defect_description": desc_clean or None,
                    "consequence": conseq_clean or None,
                    "corrective_action": corr_clean or None,
                    "do_not_drive": do_not_drive,
                    "park_outside": park_outside,
                    "influenced_by": inf_by or None,
                    "record_count": 1,
                }
            else:
                c = campaigns_acc[campno]
                c["record_count"] += 1
                if not c["manufacturer"] and mfg_name:
                    c["manufacturer"] = mfg_name
                # Earliest recall date
                if rcdate_dt:
                    if not c["recall_date"] or rcdate_dt < c["recall_date"]:
                        c["recall_date"] = rcdate_dt
                # Earliest owner notification date
                if odate_dt:
                    if not c["owner_notification_date"] or odate_dt < c["owner_notification_date"]:
                        c["owner_notification_date"] = odate_dt
                # Max potential units affected
                if potaff > c["affected_units"]:
                    c["affected_units"] = potaff
                # Longest descriptions
                if desc_clean and len(desc_clean) > len(c["defect_description"] or ""):
                    c["defect_description"] = desc_clean
                if conseq_clean and len(conseq_clean) > len(c["consequence"] or ""):
                    c["consequence"] = conseq_clean
                if corr_clean and len(corr_clean) > len(c["corrective_action"] or ""):
                    c["corrective_action"] = corr_clean
                # Logical OR for warnings
                if do_not_drive:
                    c["do_not_drive"] = True
                if park_outside:
                    c["park_outside"] = True
                if not c["influenced_by"] and inf_by:
                    c["influenced_by"] = inf_by

            # 2. Add to Vehicle Variants (deduplicated per vehicle variant)
            veh_key = (campno, make_norm, model_norm, year_val, comp_norm)
            if veh_key not in seen_vehicle_keys:
                seen_vehicle_keys.add(veh_key)
                veh_buffer.append({
                    "campaign_number": campno,
                    "make_raw": make_raw or None,
                    "make_normalized": make_norm or None,
                    "model_raw": model_raw or None,
                    "model_normalized": model_norm or None,
                    "model_year": year_val,
                    "component_raw": comp_raw or None,
                    "component_normalized": comp_norm or None,
                })
                if len(veh_buffer) >= batch_size:
                    flush_veh_buffer()

        flush_veh_buffer()
    finally:
        veh_writer.close()

    # Write canonical campaigns to recalls.parquet
    print(f"  Writing {len(campaigns_acc)} canonical recall campaigns to {output_recalls_path}...")
    campaign_list = list(campaigns_acc.values())
    table_recalls = pa.Table.from_pylist(campaign_list, schema=RECALLS_SCHEMA)
    pq.write_table(table_recalls, output_recalls_path, compression="snappy")

    elapsed = time.time() - t0
    stats = {
        "dataset": "recalls & recall_vehicles",
        "raw_rows_read": total_raw_rows,
        "canonical_recalls_written": len(campaign_list),
        "canonical_recall_vehicles_written": len(seen_vehicle_keys),
        "processing_time_sec": round(elapsed, 2),
        "recalls_output": output_recalls_path,
        "vehicles_output": output_vehicles_path,
    }
    return stats
