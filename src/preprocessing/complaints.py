"""
Canonical preprocessing module for NHTSA Consumer Complaints.
Processes raw 2015-2019 and 2020-2024 complaints datasets into:
- complaints.parquet (1 canonical row per ODINO case)
- complaint_components.parquet (1 row per component record, linked via ODINO)

Enforces zero data leakage:
- Preserves received_date as the ground-truth intake timestamp.
- Does NOT attach any future recall/investigation labels to complaints.
- Runs chunked streaming with O(1) memory overhead.
"""

import os
import time
from typing import Dict, List, Optional, Tuple

import pyarrow as pa
import pyarrow.parquet as pq

from src.ingestion.complaints_ingestion import stream_complaint_groups
from src.preprocessing.normalization import (
    clean_text_narrative,
    normalize_component_hierarchy,
    normalize_make,
    normalize_model,
    parse_bool_yn,
    parse_date_iso,
    parse_failure_date,
    parse_int_safe,
    parse_model_year,
)

# PyArrow schemas
COMPLAINTS_SCHEMA = pa.schema([
    ("complaint_id", pa.string()),
    ("manufacturer", pa.string()),
    ("make_raw", pa.string()),
    ("make_normalized", pa.string()),
    ("model_raw", pa.string()),
    ("model_normalized", pa.string()),
    ("model_year", pa.int32()),
    ("received_date", pa.date32()),
    ("failure_date", pa.date32()),
    ("date_added", pa.date32()),
    ("complaint_text_raw", pa.string()),
    ("complaint_text_clean", pa.string()),
    ("narrative_length", pa.int32()),
    ("mileage", pa.int64()),
    ("vehicle_speed", pa.int32()),
    ("crash", pa.bool_()),
    ("fire", pa.bool_()),
    ("injuries", pa.int32()),
    ("deaths", pa.int32()),
    ("medical_attention", pa.bool_()),
    ("vehicle_towed", pa.bool_()),
    ("product_type", pa.string()),
    ("vin_prefix", pa.string()),
    ("city", pa.string()),
    ("state", pa.string()),
    ("source_period", pa.string()),
])

COMPONENTS_SCHEMA = pa.schema([
    ("component_record_id", pa.string()),
    ("complaint_id", pa.string()),
    ("component_raw", pa.string()),
    ("component_normalized", pa.string()),
    ("component_system", pa.string()),
    ("component_subsystem", pa.string()),
])


def process_single_complaint_group(
    odino: str, rows: List[List[str]], source_period: str
) -> Tuple[Dict, List[Dict]]:
    """
    Processes a group of contiguous raw rows sharing the same ODINO into:
    1. A single canonical complaint dictionary.
    2. A list of component dictionaries.

    Aggregation Rules:
    - Text: longest narrative among rows (in 99.99% of cases, identical).
    - Dates: received_date from LDATE; failure_date with sanity/outlier check.
    - Booleans (crash, fire, medical_attn, towed): True if True in ANY row (logical OR).
    - Counts (injuries, deaths): MAX across rows (prevents duplicate counting).
    - Mileage / Speed: MAX valid numeric value.
    - Vehicle attributes (make, model, year, mfr): first non-empty.
    """
    # 1. Received date (LDATE is field 16)
    received_dt = None
    for r in rows:
        dt = parse_date_iso(r[16].strip() if len(r) > 16 else "")
        if dt:
            received_dt = dt
            break

    # 2. Failure date (FAILDATE is field 7)
    failure_dt = None
    for r in rows:
        f_str = r[7].strip() if len(r) > 7 else ""
        dt = parse_failure_date(f_str, received_dt)
        if dt:
            failure_dt = dt
            break

    # 3. Date added (DATEA is field 15)
    date_added_dt = None
    for r in rows:
        dt = parse_date_iso(r[15].strip() if len(r) > 15 else "")
        if dt:
            date_added_dt = dt
            break

    # 4. Vehicle attributes
    mfr_raw = ""
    make_raw = ""
    model_raw = ""
    year_val = None
    prod_type = "V"
    vin_prefix = ""
    city = ""
    state = ""

    for r in rows:
        if not mfr_raw and len(r) > 2 and r[2].strip():
            mfr_raw = r[2].strip()
        if not make_raw and len(r) > 3 and r[3].strip():
            make_raw = r[3].strip()
        if not model_raw and len(r) > 4 and r[4].strip():
            model_raw = r[4].strip()
        if year_val is None and len(r) > 5 and r[5].strip():
            year_val = parse_model_year(r[5].strip())
        if len(r) > 45 and r[45].strip():
            prod_type = r[45].strip().upper()
        if not vin_prefix and len(r) > 14 and r[14].strip():
            vin_prefix = r[14].strip()[:11]
        if not city and len(r) > 12 and r[12].strip():
            city = r[12].strip().upper()
        if not state and len(r) > 13 and r[13].strip():
            state = r[13].strip().upper()

    make_norm = normalize_make(make_raw)
    model_norm = normalize_model(model_raw)

    # 5. Narrative Text (CDESCR is field 19)
    longest_raw_text = ""
    for r in rows:
        t = r[19].strip() if len(r) > 19 else ""
        if len(t) > len(longest_raw_text):
            longest_raw_text = t

    raw_text, clean_text = clean_text_narrative(longest_raw_text)

    # 6. Severity and numerical fields
    crash = any(parse_bool_yn(r[6].strip()) for r in rows if len(r) > 6)
    fire = any(parse_bool_yn(r[8].strip()) for r in rows if len(r) > 8)
    injuries = max([parse_int_safe(r[9].strip(), 0) for r in rows if len(r) > 9] or [0])
    deaths = max([parse_int_safe(r[10].strip(), 0) for r in rows if len(r) > 10] or [0])
    medical_attn = any(parse_bool_yn(r[47].strip()) for r in rows if len(r) > 47)
    towed = any(parse_bool_yn(r[48].strip()) for r in rows if len(r) > 48)

    mileage_vals = [parse_int_safe(r[17].strip()) for r in rows if len(r) > 17]
    mileage_valid = [m for m in mileage_vals if m is not None and 0 <= m <= 1_000_000]
    mileage = max(mileage_valid) if mileage_valid else None

    speed_vals = [parse_int_safe(r[31].strip()) for r in rows if len(r) > 31]
    speed_valid = [s for s in speed_vals if s is not None and 0 <= s <= 150]
    speed = max(speed_valid) if speed_valid else None

    complaint_dict = {
        "complaint_id": str(odino),
        "manufacturer": mfr_raw or None,
        "make_raw": make_raw or None,
        "make_normalized": make_norm or None,
        "model_raw": model_raw or None,
        "model_normalized": model_norm or None,
        "model_year": year_val,
        "received_date": received_dt,
        "failure_date": failure_dt,
        "date_added": date_added_dt,
        "complaint_text_raw": raw_text or None,
        "complaint_text_clean": clean_text or None,
        "narrative_length": len(clean_text),
        "mileage": mileage,
        "vehicle_speed": speed,
        "crash": crash,
        "fire": fire,
        "injuries": injuries,
        "deaths": deaths,
        "medical_attention": medical_attn,
        "vehicle_towed": towed,
        "product_type": prod_type,
        "vin_prefix": vin_prefix or None,
        "city": city or None,
        "state": state or None,
        "source_period": source_period,
    }

    # 7. Components
    components_list = []
    seen_comp_keys = set()
    for r in rows:
        cmplid = r[0].strip() if len(r) > 0 else ""
        raw_comp = r[11].strip() if len(r) > 11 else ""
        comp_norm, sys_name, sub_name = normalize_component_hierarchy(raw_comp)

        # Unique key within the complaint
        comp_key = (cmplid, comp_norm)
        if comp_key in seen_comp_keys:
            continue
        seen_comp_keys.add(comp_key)

        components_list.append({
            "component_record_id": str(cmplid) if cmplid else f"{odino}_{len(components_list)+1}",
            "complaint_id": str(odino),
            "component_raw": raw_comp or None,
            "component_normalized": comp_norm or None,
            "component_system": sys_name or None,
            "component_subsystem": sub_name or None,
        })

    return complaint_dict, components_list


def process_complaints_pipeline(
    raw_archives: List[Tuple[str, str]],
    output_complaints_path: str,
    output_components_path: str,
    batch_size: int = 50_000,
) -> Dict:
    """
    Streams and processes complaints from all raw archives directly into Parquet files.
    """
    t0 = time.time()
    os.makedirs(os.path.dirname(output_complaints_path), exist_ok=True)

    cmpl_writer = pq.ParquetWriter(
        output_complaints_path, COMPLAINTS_SCHEMA, compression="snappy"
    )
    comp_writer = pq.ParquetWriter(
        output_components_path, COMPONENTS_SCHEMA, compression="snappy"
    )

    total_raw_rows = 0
    total_complaints = 0
    total_components = 0
    multi_component_cases = 0

    cmpl_buffer: List[Dict] = []
    comp_buffer: List[Dict] = []

    def flush_buffers():
        nonlocal cmpl_buffer, comp_buffer
        if cmpl_buffer:
            table_cmpl = pa.Table.from_pylist(cmpl_buffer, schema=COMPLAINTS_SCHEMA)
            cmpl_writer.write_table(table_cmpl)
            cmpl_buffer.clear()
        if comp_buffer:
            table_comp = pa.Table.from_pylist(comp_buffer, schema=COMPONENTS_SCHEMA)
            comp_writer.write_table(table_comp)
            comp_buffer.clear()

    try:
        for zip_path, period_label in raw_archives:
            print(f"  Ingesting complaints from {zip_path} ({period_label})...")
            for odino, rows in stream_complaint_groups(zip_path):
                total_raw_rows += len(rows)
                if len(rows) > 1:
                    multi_component_cases += 1

                cmpl_dict, comp_dicts = process_single_complaint_group(
                    odino, rows, period_label
                )
                cmpl_buffer.append(cmpl_dict)
                comp_buffer.extend(comp_dicts)
                total_complaints += 1
                total_components += len(comp_dicts)

                if len(cmpl_buffer) >= batch_size:
                    flush_buffers()

        flush_buffers()
    finally:
        cmpl_writer.close()
        comp_writer.close()

    elapsed = time.time() - t0
    stats = {
        "dataset": "complaints & complaint_components",
        "raw_rows_read": total_raw_rows,
        "canonical_complaints_written": total_complaints,
        "canonical_components_written": total_components,
        "multi_component_complaints": multi_component_cases,
        "processing_time_sec": round(elapsed, 2),
        "complaints_output": output_complaints_path,
        "components_output": output_components_path,
    }
    return stats
