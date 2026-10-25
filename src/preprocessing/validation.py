"""
Canonical validation module for DEFECTRADAR Phase 2 processed datasets.
Performs integrity, uniqueness, referential consistency, and bounds checking
on all generated Parquet files in data/processed/.
"""

import os
from typing import Dict, List, Optional, Set

import pyarrow.compute as pc
import pyarrow.parquet as pq


def _campaign_match_metrics(
    investigation_campaign_numbers: List[str], recall_campaign_numbers: Set[str]
) -> Dict[str, int]:
    """Separate exact campaign links from six-character diagnostic candidates.

    Inputs are already source-normalized strings. Prefix candidates are counted
    only when the full identifier has no exact match; they are not links.
    """
    exact_matches = sum(
        1 for campaign in investigation_campaign_numbers
        if campaign in recall_campaign_numbers
    )

    recall_prefixes = {
        recall[:prefix_length]
        for recall in recall_campaign_numbers
        if recall
        for prefix_length in range(1, min(6, len(recall)) + 1)
    }
    prefix_candidates = sum(
        1
        for campaign in investigation_campaign_numbers
        if campaign not in recall_campaign_numbers
        and campaign[:6] in recall_prefixes
    )

    return {
        "investigations_with_exact_recall_campaign_match": exact_matches,
        "investigations_with_prefix_assisted_recall_candidate": prefix_candidates,
    }


def validate_complaints_dataset(
    complaints_path: str, components_path: str
) -> Dict[str, any]:
    """
    Validates complaints and complaint_components Parquet datasets.
    """
    print("  Validating complaints and complaint_components integrity...")
    cmpl_meta = pq.read_metadata(complaints_path)
    comp_meta = pq.read_metadata(components_path)

    total_cmpl_rows = cmpl_meta.num_rows
    total_comp_rows = comp_meta.num_rows

    cmpl_table = pq.read_table(
        complaints_path,
        columns=[
            "complaint_id",
            "received_date",
            "model_year",
            "complaint_text_clean",
            "crash",
            "fire",
            "injuries",
            "deaths",
        ],
    )
    comp_table = pq.read_table(
        components_path, columns=["component_record_id", "complaint_id"]
    )

    # 1. Uniqueness of complaint_id
    cmpl_ids = cmpl_table["complaint_id"].to_pylist()
    unique_cmpl_ids = set(cmpl_ids)
    is_cmpl_unique = len(cmpl_ids) == len(unique_cmpl_ids)
    duplicate_cmpl_count = len(cmpl_ids) - len(unique_cmpl_ids)

    # 2. Referential integrity: Check for orphan components
    comp_cmpl_ids = comp_table["complaint_id"].to_pylist()
    orphan_components = sum(1 for cid in comp_cmpl_ids if cid not in unique_cmpl_ids)

    # 3. Validity of received_date (must be 100% non-null)
    null_received_dates = cmpl_table["received_date"].null_count

    # 4. Text availability
    empty_narratives = sum(
        1 for t in cmpl_table["complaint_text_clean"].to_pylist() if not t
    )

    # 5. Severity field integrity
    inj_neg = pc.sum(pc.less(cmpl_table["injuries"], 0)).as_py() or 0
    deaths_neg = pc.sum(pc.less(cmpl_table["deaths"], 0)).as_py() or 0
    invalid_injuries = cmpl_table["injuries"].null_count + inj_neg
    invalid_deaths = cmpl_table["deaths"].null_count + deaths_neg

    all_passed = (
        is_cmpl_unique
        and orphan_components == 0
        and null_received_dates == 0
        and empty_narratives <= 10
        and invalid_injuries == 0
        and invalid_deaths == 0
    )

    return {
        "dataset": "complaints & complaint_components",
        "total_complaints": total_cmpl_rows,
        "total_components": total_comp_rows,
        "unique_complaint_ids": len(unique_cmpl_ids),
        "duplicate_complaints": duplicate_cmpl_count,
        "is_complaint_id_unique": is_cmpl_unique,
        "orphan_components": orphan_components,
        "null_received_dates": null_received_dates,
        "empty_narratives": empty_narratives,
        "invalid_injuries": invalid_injuries,
        "invalid_deaths": invalid_deaths,
        "all_checks_passed": all_passed,
    }


def validate_recalls_dataset(
    recalls_path: str, vehicles_path: str
) -> Dict[str, any]:
    """
    Validates recalls and recall_vehicles Parquet datasets.
    """
    print("  Validating recalls and recall_vehicles integrity...")
    rec_meta = pq.read_metadata(recalls_path)
    veh_meta = pq.read_metadata(vehicles_path)

    rec_table = pq.read_table(
        recalls_path,
        columns=["campaign_number", "recall_date", "affected_units"],
    )
    veh_table = pq.read_table(
        vehicles_path, columns=["campaign_number", "make_normalized", "model_normalized"]
    )

    # 1. Uniqueness of campaign_number
    camp_nos = rec_table["campaign_number"].to_pylist()
    unique_camp_nos = set(camp_nos)
    is_camp_unique = len(camp_nos) == len(unique_camp_nos)
    duplicate_camps = len(camp_nos) - len(unique_camp_nos)

    # 2. Referential integrity: Check for orphan vehicles
    veh_camp_nos = veh_table["campaign_number"].to_pylist()
    orphan_vehicles = sum(1 for cno in veh_camp_nos if cno not in unique_camp_nos)

    # 3. Recall date validity
    null_recall_dates = rec_table["recall_date"].null_count

    # 4. Units affected numeric validity
    negative_units = pc.sum(pc.less(rec_table["affected_units"], 0)).as_py() or 0

    all_passed = (
        is_camp_unique
        and orphan_vehicles == 0
        and null_recall_dates == 0
        and negative_units == 0
    )

    return {
        "dataset": "recalls & recall_vehicles",
        "total_campaigns": rec_meta.num_rows,
        "total_recall_vehicles": veh_meta.num_rows,
        "unique_campaign_numbers": len(unique_camp_nos),
        "duplicate_campaigns": duplicate_camps,
        "is_campaign_number_unique": is_camp_unique,
        "orphan_recall_vehicles": orphan_vehicles,
        "null_recall_dates": null_recall_dates,
        "negative_affected_units": negative_units,
        "all_checks_passed": all_passed,
    }


def validate_investigations_dataset(
    inv_path: str, inv_vehicles_path: str, recalls_path: Optional[str] = None
) -> Dict[str, any]:
    """
    Validates investigations and investigation_vehicles Parquet datasets.
    """
    print("  Validating investigations and investigation_vehicles integrity...")
    inv_meta = pq.read_metadata(inv_path)
    veh_meta = pq.read_metadata(inv_vehicles_path)

    inv_table = pq.read_table(
        inv_path,
        columns=[
            "investigation_id",
            "action_type",
            "opened_date",
            "recall_campaign_number",
        ],
    )
    veh_table = pq.read_table(
        inv_vehicles_path, columns=["investigation_id", "make_normalized"]
    )

    # 1. Uniqueness of investigation_id
    inv_ids = inv_table["investigation_id"].to_pylist()
    unique_inv_ids = set(inv_ids)
    is_inv_unique = len(inv_ids) == len(unique_inv_ids)
    duplicate_invs = len(inv_ids) - len(unique_inv_ids)

    # 2. Referential integrity: Check for orphan vehicles
    veh_inv_ids = veh_table["investigation_id"].to_pylist()
    orphan_vehicles = sum(1 for iid in veh_inv_ids if iid not in unique_inv_ids)

    # 3. Dates validity
    null_opened_dates = inv_table["opened_date"].null_count

    # 4. Recall cross-reference check
    total_with_recall = 0
    campaign_match_metrics = _campaign_match_metrics([], set())
    if recalls_path and os.path.exists(recalls_path):
        rec_campnos = set(
            pq.read_table(recalls_path, columns=["campaign_number"])["campaign_number"].to_pylist()
        )
        linked_campnos = [
            c for c in inv_table["recall_campaign_number"].to_pylist() if c
        ]
        total_with_recall = len(linked_campnos)
        campaign_match_metrics = _campaign_match_metrics(linked_campnos, rec_campnos)

    all_passed = (
        is_inv_unique
        and orphan_vehicles == 0
        and null_opened_dates <= 120  # ~108 vintage investigations from 1970s without open date
    )

    return {
        "dataset": "investigations & investigation_vehicles",
        "total_investigations": inv_meta.num_rows,
        "total_investigation_vehicles": veh_meta.num_rows,
        "unique_investigation_ids": len(unique_inv_ids),
        "duplicate_investigations": duplicate_invs,
        "is_investigation_id_unique": is_inv_unique,
        "orphan_investigation_vehicles": orphan_vehicles,
        "null_opened_dates": null_opened_dates,
        "investigations_with_recall_no": total_with_recall,
        **campaign_match_metrics,
        "all_checks_passed": all_passed,
    }


def validate_all_processed_datasets(processed_dir: str) -> Dict[str, Dict]:
    """
    Runs complete validation suite across all 7 canonical datasets.
    """
    cmpl_path = os.path.join(processed_dir, "complaints.parquet")
    comp_path = os.path.join(processed_dir, "complaint_components.parquet")
    rec_path = os.path.join(processed_dir, "recalls.parquet")
    rec_veh_path = os.path.join(processed_dir, "recall_vehicles.parquet")
    inv_path = os.path.join(processed_dir, "investigations.parquet")
    inv_veh_path = os.path.join(processed_dir, "investigation_vehicles.parquet")
    doc_path = os.path.join(processed_dir, "recall_documents.parquet")

    results = {}
    results["complaints"] = validate_complaints_dataset(cmpl_path, comp_path)
    results["recalls"] = validate_recalls_dataset(rec_path, rec_veh_path)
    results["investigations"] = validate_investigations_dataset(
        inv_path, inv_veh_path, rec_path
    )

    if os.path.exists(doc_path):
        doc_meta = pq.read_metadata(doc_path)
        results["recall_documents"] = {
            "dataset": "recall_documents",
            "total_documents": doc_meta.num_rows,
            "all_checks_passed": doc_meta.num_rows > 0,
        }

    return results
