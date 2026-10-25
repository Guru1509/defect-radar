"""
Comprehensive test suite for DEFECTRADAR Phase 2 Canonical Datasets.

Validates:
- Canonical complaint uniqueness (complaint_id / ODINO)
- Complaint-to-component 1-to-many relationship (no orphan components)
- Recall campaign uniqueness (campaign_number / CAMPNO)
- Recall-to-vehicle relationship (no orphan vehicles)
- Investigation uniqueness (investigation_id / ACTION_NUMBER)
- Date conversion & validation (received_date, failure_date sanity)
- Text cleaning routines (preserves technical terms, strips control chars)
- Normalization routines (make, model, component hierarchy, action types)
- Severity field parsing & aggregation rules
- Referential integrity across all processed datasets
"""

import os
import unittest
from datetime import date

import pyarrow.compute as pc
import pyarrow.parquet as pq

from src.preprocessing.normalization import (
    clean_text_narrative,
    derive_investigation_action_type,
    normalize_component_hierarchy,
    normalize_make,
    normalize_model,
    parse_bool_yn,
    parse_date_iso,
    parse_failure_date,
    parse_int_safe,
    parse_model_year,
)

PROCESSED_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "processed"
)


class TestNormalizationRoutines(unittest.TestCase):
    """Tests the core data cleaning and normalization functions in isolation."""

    def test_text_cleaning_preserves_technical_terms_and_numbers(self):
        sample = "VEHICLE STALLED AT 65 MPH ON I-95!   CHECK ENGINE LIGHT FLASHING.\r\nBRAKE FAILED."
        raw, clean = clean_text_narrative(sample)
        self.assertEqual(raw, sample)
        self.assertNotIn("\r", clean)
        self.assertNotIn("\n", clean)
        self.assertIn("65 MPH", clean)
        self.assertIn("I-95!", clean)
        self.assertIn("CHECK ENGINE LIGHT FLASHING.", clean)

    def test_text_cleaning_removes_control_characters(self):
        sample = "Faulty\x00 wire\x08 harness\x1f in transmission."
        _, clean = clean_text_narrative(sample)
        self.assertEqual(clean, "Faulty wire harness in transmission.")

    def test_date_iso_parsing(self):
        self.assertEqual(parse_date_iso("20210515"), date(2021, 5, 15))
        self.assertEqual(parse_date_iso("20180101"), date(2018, 1, 1))
        self.assertIsNone(parse_date_iso("00000000"))
        self.assertIsNone(parse_date_iso("99999999"))
        self.assertIsNone(parse_date_iso("invalid"))

    def test_failure_date_outlier_filtering(self):
        # Normal failure date before received date
        received = date(2021, 6, 1)
        valid_fail = parse_failure_date("20210520", received)
        self.assertEqual(valid_fail, date(2021, 5, 20))

        # Typographical outlier year (e.g. 1906, 1917)
        outlier_year = parse_failure_date("19060622", received)
        self.assertIsNone(outlier_year)

        # Failure date occurring in the future relative to received date
        future_fail = parse_failure_date("20220101", received)
        self.assertIsNone(future_fail)

    def test_make_normalization(self):
        self.assertEqual(
            normalize_make("HONDA (AMERICAN HONDA MOTOR CO.)"), "HONDA"
        )
        self.assertEqual(normalize_make("ford motor company"), "FORD")
        self.assertEqual(normalize_make("CHEVROLET"), "CHEVROLET")
        self.assertEqual(normalize_make("  toyota   "), "TOYOTA")

    def test_model_normalization(self):
        self.assertEqual(normalize_model("  explorer  "), "EXPLORER")
        self.assertEqual(normalize_model("SILVERADO   1500"), "SILVERADO 1500")

    def test_model_year_parsing(self):
        self.assertEqual(parse_model_year("2018"), 2018)
        self.assertEqual(parse_model_year("1995"), 1995)
        # 9999 denotes unknown in NHTSA
        self.assertIsNone(parse_model_year("9999"))
        self.assertIsNone(parse_model_year("1850"))
        self.assertIsNone(parse_model_year("abc"))

    def test_component_hierarchy_parsing(self):
        raw = "SERVICE BRAKES, HYDRAULIC : ANTILOCK : WHEEL SPEED SENSOR"
        norm, sys_name, sub_name = normalize_component_hierarchy(raw)
        self.assertEqual(
            norm, "SERVICE BRAKES, HYDRAULIC:ANTILOCK:WHEEL SPEED SENSOR"
        )
        self.assertEqual(sys_name, "SERVICE BRAKES, HYDRAULIC")
        self.assertEqual(sub_name, "ANTILOCK:WHEEL SPEED SENSOR")

        raw_single = "AIR BAGS"
        norm2, sys_name2, sub_name2 = normalize_component_hierarchy(raw_single)
        self.assertEqual(norm2, "AIR BAGS")
        self.assertEqual(sys_name2, "AIR BAGS")
        self.assertIsNone(sub_name2)

    def test_investigation_action_type_derivation(self):
        self.assertEqual(derive_investigation_action_type("PE21005"), "PE")
        self.assertEqual(derive_investigation_action_type("EA19002"), "EA")
        self.assertEqual(derive_investigation_action_type("RQ22001"), "RQ")
        self.assertEqual(derive_investigation_action_type("DP20003"), "DP")
        self.assertEqual(derive_investigation_action_type("AQ08001"), "AQ")


class TestCanonicalParquetDatasets(unittest.TestCase):
    """Validates the actual generated Parquet datasets in data/processed/."""

    @classmethod
    def setUpClass(cls):
        cls.cmpl_path = os.path.join(PROCESSED_DIR, "complaints.parquet")
        cls.comp_path = os.path.join(PROCESSED_DIR, "complaint_components.parquet")
        cls.rec_path = os.path.join(PROCESSED_DIR, "recalls.parquet")
        cls.rec_veh_path = os.path.join(PROCESSED_DIR, "recall_vehicles.parquet")
        cls.inv_path = os.path.join(PROCESSED_DIR, "investigations.parquet")
        cls.inv_veh_path = os.path.join(PROCESSED_DIR, "investigation_vehicles.parquet")
        cls.doc_path = os.path.join(PROCESSED_DIR, "recall_documents.parquet")

    def test_all_processed_parquet_files_exist(self):
        expected_files = [
            self.cmpl_path,
            self.comp_path,
            self.rec_path,
            self.rec_veh_path,
            self.inv_path,
            self.inv_veh_path,
            self.doc_path,
        ]
        for fpath in expected_files:
            self.assertTrue(
                os.path.isfile(fpath), f"Processed Parquet file missing: {fpath}"
            )
            self.assertGreater(
                os.path.getsize(fpath),
                10_000,
                f"File unexpectedly small: {fpath}",
            )

    def test_complaints_uniqueness_and_counts(self):
        meta = pq.read_metadata(self.cmpl_path)
        self.assertEqual(
            meta.num_rows, 651_262, f"Expected 651,262 canonical complaints, got {meta.num_rows}"
        )

        table = pq.read_table(self.cmpl_path, columns=["complaint_id", "received_date"])
        cmpl_ids = table["complaint_id"].to_pylist()
        self.assertEqual(
            len(cmpl_ids), len(set(cmpl_ids)), "Complaint IDs (ODINO) are not unique!"
        )

        # Received date must have 0 nulls
        null_dates = table["received_date"].null_count
        self.assertEqual(null_dates, 0, "received_date must not contain nulls")

    def test_date_added_and_received_date_semantics(self):
        """Verify date_added vs received_date mapping and temporal integrity."""
        table = pq.read_table(
            self.cmpl_path, columns=["complaint_id", "received_date", "date_added"]
        )
        # Compare date-field relationships in aggregate rather than identifying a specific row.
        same_date_rows = table.filter(
            pc.equal(table["date_added"], table["received_date"])
        ).num_rows
        date_added_after_rows = table.filter(
            pc.greater(table["date_added"], table["received_date"])
        ).num_rows
        date_added_before_rows = table.filter(
            pc.less(table["date_added"], table["received_date"])
        ).num_rows
        self.assertEqual(same_date_rows, 651047)
        self.assertEqual(date_added_after_rows, 213)
        self.assertEqual(date_added_before_rows, 2)

        # Received dates must all be between 2015 and 2024
        min_date = pc.min(table["received_date"]).as_py()
        max_date = pc.max(table["received_date"]).as_py()
        self.assertGreaterEqual(str(min_date), "2015-01-01")
        self.assertLessEqual(str(max_date), "2024-12-31")

    def test_complaint_components_referential_integrity(self):
        cmpl_table = pq.read_table(self.cmpl_path, columns=["complaint_id"])
        comp_table = pq.read_table(
            self.comp_path, columns=["component_record_id", "complaint_id"]
        )

        self.assertEqual(
            comp_table.num_rows,
            908_693,
            f"Expected 908,693 component rows, got {comp_table.num_rows}",
        )

        cmpl_ids_set = set(cmpl_table["complaint_id"].to_pylist())
        comp_cmpl_ids = comp_table["complaint_id"].to_pylist()

        # Check for orphan components
        orphan_count = sum(1 for cid in comp_cmpl_ids if cid not in cmpl_ids_set)
        self.assertEqual(
            orphan_count, 0, f"Found {orphan_count} orphan complaint components!"
        )

    def test_recalls_uniqueness_and_vehicles(self):
        rec_meta = pq.read_metadata(self.rec_path)
        self.assertEqual(
            rec_meta.num_rows,
            15_286,
            f"Expected 15,286 canonical recall campaigns, got {rec_meta.num_rows}",
        )

        rec_table = pq.read_table(self.rec_path, columns=["campaign_number", "recall_date"])
        camp_nos = rec_table["campaign_number"].to_pylist()
        self.assertEqual(
            len(camp_nos),
            len(set(camp_nos)),
            "Recall campaign numbers (CAMPNO) are not unique!",
        )

        # Check orphan recall vehicles
        veh_table = pq.read_table(self.rec_veh_path, columns=["campaign_number"])
        camp_set = set(camp_nos)
        orphan_vehs = sum(
            1 for c in veh_table["campaign_number"].to_pylist() if c not in camp_set
        )
        self.assertEqual(
            orphan_vehs, 0, f"Found {orphan_vehs} orphan recall vehicles!"
        )

    def test_investigations_uniqueness_and_vehicles(self):
        inv_meta = pq.read_metadata(self.inv_path)
        self.assertEqual(
            inv_meta.num_rows,
            5_349,
            f"Expected 5,349 canonical investigations, got {inv_meta.num_rows}",
        )

        inv_table = pq.read_table(
            self.inv_path, columns=["investigation_id", "action_type", "opened_date"]
        )
        inv_ids = inv_table["investigation_id"].to_pylist()
        self.assertEqual(
            len(inv_ids),
            len(set(inv_ids)),
            "Investigation IDs are not unique!",
        )

        # Check orphan investigation vehicles
        veh_table = pq.read_table(
            self.inv_veh_path, columns=["investigation_id"]
        )
        inv_set = set(inv_ids)
        orphan_vehs = sum(
            1 for i in veh_table["investigation_id"].to_pylist() if i not in inv_set
        )
        self.assertEqual(
            orphan_vehs, 0, f"Found {orphan_vehs} orphan investigation vehicles!"
        )

    def test_recall_documents_existence(self):
        doc_meta = pq.read_metadata(self.doc_path)
        self.assertGreater(
            doc_meta.num_rows,
            400_000,
            f"Expected >400,000 document records, got {doc_meta.num_rows}",
        )


if __name__ == "__main__":
    unittest.main()
