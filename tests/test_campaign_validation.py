"""Focused tests for campaign-match metrics using synthetic identifiers."""

import os
import tempfile
import unittest
from datetime import date

import pyarrow as pa
import pyarrow.parquet as pq

from src.preprocessing.validation import (
    _campaign_match_metrics,
    validate_investigations_dataset,
)


class TestCampaignMatchMetrics(unittest.TestCase):
    def test_exact_match_uses_the_full_normalized_identifier(self):
        metrics = _campaign_match_metrics(["SYN123456"], {"SYN123456"})

        self.assertEqual(
            metrics["investigations_with_exact_recall_campaign_match"], 1
        )
        self.assertEqual(
            metrics["investigations_with_prefix_assisted_recall_candidate"], 0
        )

    def test_char9_and_char12_fields_match_after_source_normalization(self):
        # Investigation CAMPNO is CHAR(9); recall CAMPNO is CHAR(12).
        inv_value = "syn123456".strip().upper()
        recall_value = "syn123456   ".strip().upper()
        self.assertEqual(len(inv_value), 9)
        self.assertEqual(len("SYN123456   "), 12)

        metrics = _campaign_match_metrics([inv_value], {recall_value})

        self.assertEqual(
            metrics["investigations_with_exact_recall_campaign_match"], 1
        )
        self.assertEqual(
            metrics["investigations_with_prefix_assisted_recall_candidate"], 0
        )

    def test_shared_six_character_prefix_is_candidate_not_exact(self):
        metrics = _campaign_match_metrics(["SYN123123"], {"SYN123999"})

        self.assertEqual(
            metrics["investigations_with_exact_recall_campaign_match"], 0
        )
        self.assertEqual(
            metrics["investigations_with_prefix_assisted_recall_candidate"], 1
        )

    def test_exact_match_is_not_also_counted_as_prefix_candidate(self):
        metrics = _campaign_match_metrics(
            ["SYN123456"], {"SYN123456", "SYN123999"}
        )

        self.assertEqual(
            metrics["investigations_with_exact_recall_campaign_match"], 1
        )
        self.assertEqual(
            metrics["investigations_with_prefix_assisted_recall_candidate"], 0
        )

    def test_validator_reports_exact_and_prefix_candidates_separately(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            inv_path = os.path.join(tmp_dir, "investigations.parquet")
            inv_vehicles_path = os.path.join(
                tmp_dir, "investigation_vehicles.parquet"
            )
            recalls_path = os.path.join(tmp_dir, "recalls.parquet")

            pq.write_table(
                pa.table(
                    {
                        "investigation_id": ["TEST-INV-001", "TEST-INV-002"],
                        "action_type": ["PE", "PE"],
                        "opened_date": [date(2020, 1, 1), date(2020, 1, 2)],
                        "recall_campaign_number": ["SYN123456", "SYN123123"],
                    }
                ),
                inv_path,
            )
            pq.write_table(
                pa.table(
                    {
                        "investigation_id": ["TEST-INV-001", "TEST-INV-002"],
                        "make_normalized": ["MAKE A", "MAKE B"],
                    }
                ),
                inv_vehicles_path,
            )
            pq.write_table(
                pa.table({"campaign_number": ["SYN123456", "SYN123999"]}),
                recalls_path,
            )

            result = validate_investigations_dataset(
                inv_path, inv_vehicles_path, recalls_path
            )

        self.assertEqual(result["investigations_with_recall_no"], 2)
        self.assertEqual(
            result["investigations_with_exact_recall_campaign_match"], 1
        )
        self.assertEqual(
            result["investigations_with_prefix_assisted_recall_candidate"], 1
        )
        self.assertTrue(result["all_checks_passed"])


if __name__ == "__main__":
    unittest.main()
