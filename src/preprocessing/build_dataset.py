"""
Master Pipeline Entry Point for DEFECTRADAR Phase 2 Canonical Dataset Creation.

Executes streaming ingestion, cleaning, normalization, Parquet serialization,
and multi-table referential validation across all 7 canonical datasets.

Usage:
    python -m src.preprocessing.build_dataset
"""

import gc
import json
import os
import resource
import sys
import time

from src.preprocessing.complaints import process_complaints_pipeline
from src.preprocessing.documents import process_documents_pipeline
from src.preprocessing.investigations import process_investigations_pipeline
from src.preprocessing.recalls import process_recalls_pipeline
from src.preprocessing.validation import validate_all_processed_datasets


def get_peak_memory_mb() -> float:
    """Returns peak resident set size in megabytes."""
    # On macOS, ru_maxrss is in bytes; on Linux, in kilobytes.
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return usage / (1024 * 1024)
    return usage / 1024


def run_pipeline(
    raw_dir: str = "data/raw",
    processed_dir: str = "data/processed",
    batch_size: int = 50_000,
):
    print("=" * 70)
    print("DEFECTRADAR — Phase 2: Canonical Dataset Preprocessing Pipeline")
    print(f"Source Directory:      {raw_dir}")
    print(f"Destination Directory: {processed_dir}")
    print(f"Streaming Batch Size:  {batch_size:,} records")
    print("=" * 70)

    total_start_time = time.time()
    os.makedirs(processed_dir, exist_ok=True)

    summary_report = {
        "pipeline_version": "Phase 2 Canonical Preprocessing",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "datasets": {},
    }

    # =========================================================================
    # STEP 1: Process Complaints & Complaint Components
    # =========================================================================
    print("\n[1/4] Processing Consumer Complaints (2015-2019 & 2020-2024)...")
    complaints_archives = [
        (
            os.path.join(raw_dir, "COMPLAINTS_RECEIVED_2015-2019.zip"),
            "2015-2019",
        ),
        (
            os.path.join(raw_dir, "COMPLAINTS_RECEIVED_2020-2024.zip"),
            "2020-2024",
        ),
    ]
    out_cmpl = os.path.join(processed_dir, "complaints.parquet")
    out_comp = os.path.join(processed_dir, "complaint_components.parquet")

    cmpl_stats = process_complaints_pipeline(
        complaints_archives, out_cmpl, out_comp, batch_size=batch_size
    )
    summary_report["datasets"]["complaints"] = cmpl_stats
    print(f"  -> Written: {cmpl_stats['canonical_complaints_written']:,} canonical complaints")
    print(f"  -> Written: {cmpl_stats['canonical_components_written']:,} canonical components")
    print(f"  -> Time:    {cmpl_stats['processing_time_sec']} seconds")
    print(f"  -> Memory:  {get_peak_memory_mb():.1f} MB RSS")

    # Garbage collect before next dataset
    gc.collect()

    # =========================================================================
    # STEP 2: Process Safety Recalls & Recall Vehicles
    # =========================================================================
    print("\n[2/4] Processing Safety Recalls (FLAT_RCL_POST_2010)...")
    rcl_archive = os.path.join(raw_dir, "FLAT_RCL_POST_2010.zip")
    out_rec = os.path.join(processed_dir, "recalls.parquet")
    out_rec_veh = os.path.join(processed_dir, "recall_vehicles.parquet")

    rcl_stats = process_recalls_pipeline(
        rcl_archive, out_rec, out_rec_veh, batch_size=batch_size
    )
    summary_report["datasets"]["recalls"] = rcl_stats
    print(f"  -> Written: {rcl_stats['canonical_recalls_written']:,} canonical recall campaigns")
    print(f"  -> Written: {rcl_stats['canonical_recall_vehicles_written']:,} affected vehicle variants")
    print(f"  -> Time:    {rcl_stats['processing_time_sec']} seconds")
    print(f"  -> Memory:  {get_peak_memory_mb():.1f} MB RSS")

    gc.collect()

    # =========================================================================
    # STEP 3: Process Defect Investigations & Investigation Vehicles
    # =========================================================================
    print("\n[3/4] Processing Defect Investigations (FLAT_INV)...")
    inv_archive = os.path.join(raw_dir, "FLAT_INV.zip")
    out_inv = os.path.join(processed_dir, "investigations.parquet")
    out_inv_veh = os.path.join(processed_dir, "investigation_vehicles.parquet")

    inv_stats = process_investigations_pipeline(
        inv_archive, out_inv, out_inv_veh, batch_size=batch_size
    )
    summary_report["datasets"]["investigations"] = inv_stats
    print(f"  -> Written: {inv_stats['canonical_investigations_written']:,} canonical investigations")
    print(f"  -> Written: {inv_stats['canonical_investigation_vehicles_written']:,} investigation vehicle variants")
    print(f"  -> Time:    {inv_stats['processing_time_sec']} seconds")
    print(f"  -> Memory:  {get_peak_memory_mb():.1f} MB RSS")

    gc.collect()

    # =========================================================================
    # STEP 4: Process Recall Associated Documents
    # =========================================================================
    print("\n[4/4] Processing Recall Documents (2015-2019 & 2020-2024)...")
    docs_archives = [
        (os.path.join(raw_dir, "RCL_FROM_2015_2019.zip"), "2015-2019"),
        (os.path.join(raw_dir, "RCL_FROM_2020_2024.zip"), "2020-2024"),
    ]
    out_docs = os.path.join(processed_dir, "recall_documents.parquet")

    docs_stats = process_documents_pipeline(
        docs_archives, out_docs, batch_size=batch_size
    )
    summary_report["datasets"]["recall_documents"] = docs_stats
    print(f"  -> Written: {docs_stats['canonical_documents_written']:,} document records")
    print(f"  -> Time:    {docs_stats['processing_time_sec']} seconds")
    print(f"  -> Memory:  {get_peak_memory_mb():.1f} MB RSS")

    gc.collect()

    # =========================================================================
    # STEP 5: Run Full Dataset Validation Suite
    # =========================================================================
    print("\n" + "=" * 70)
    print("Running Referential Integrity & Validation Suite...")
    print("=" * 70)

    val_results = validate_all_processed_datasets(processed_dir)
    summary_report["validation"] = val_results

    all_passed = True
    for ds_name, res in val_results.items():
        passed = res.get("all_checks_passed", False)
        status = "PASSED" if passed else "FAILED"
        print(f"  [{status}] {ds_name.upper()}")
        if not passed:
            all_passed = False

    total_elapsed = time.time() - total_start_time
    summary_report["total_time_sec"] = round(total_elapsed, 2)
    summary_report["peak_memory_mb"] = round(get_peak_memory_mb(), 2)

    stats_path = os.path.join(processed_dir, "pipeline_summary.json")
    with open(stats_path, "w") as f:
        json.dump(summary_report, f, indent=2, default=str)

    print("\n" + "=" * 70)
    print(f"PIPELINE COMPLETED SUCCESSFULLY in {total_elapsed:.2f} seconds!")
    print(f"Peak Memory Footprint: {summary_report['peak_memory_mb']} MB RSS")
    print(f"Summary Metrics Saved: {stats_path}")
    print("=" * 70)

    return summary_report


if __name__ == "__main__":
    run_pipeline()
