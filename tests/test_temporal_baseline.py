import unittest
from datetime import date

from src.temporal.monthly_baseline import (
    MISSING_CATEGORY,
    aggregate_monthly_counts,
    evaluate_historical_baseline,
)


class TestMonthlyAggregation(unittest.TestCase):
    def test_counts_unique_complaint_system_pairs_by_received_month(self):
        complaints = [
            ("c1", date(2020, 1, 31)),
            ("c2", date(2020, 2, 1)),
        ]
        components = [
            ("c1", "ENGINE"),
            ("c1", "ENGINE"),  # duplicate component row
            ("c1", "STEERING"),
            ("c2", "ENGINE"),
        ]

        rows = aggregate_monthly_counts(complaints, components)
        by_key = {(row["month"], row["component_system"]): row for row in rows}

        january_engine = by_key[(date(2020, 1, 1), "ENGINE")]
        january_steering = by_key[(date(2020, 1, 1), "STEERING")]
        february_engine = by_key[(date(2020, 2, 1), "ENGINE")]
        self.assertEqual(january_engine["complaint_count"], 1)
        self.assertEqual(january_engine["total_monthly_complaints"], 1)
        self.assertEqual(january_engine["complaint_share_pct"], 100.0)
        self.assertEqual(january_steering["complaint_count"], 1)
        self.assertEqual(february_engine["complaint_count"], 1)

    def test_missing_and_blank_component_systems_use_explicit_bucket(self):
        rows = aggregate_monthly_counts(
            [("c1", date(2020, 1, 4)), ("c2", date(2020, 1, 9)), ("c3", date(2020, 1, 10))],
            [("c1", None), ("c2", "  ")],
        )
        missing = next(row for row in rows if row["component_system"] == MISSING_CATEGORY)
        self.assertEqual(missing["complaint_count"], 3)
        self.assertEqual(missing["total_monthly_complaints"], 3)
        self.assertEqual(missing["complaint_share_pct"], 100.0)

    def test_date_cutoff_excludes_future_and_other_month_history(self):
        rows = [
            {"month": date(2018, 1, 1), "component_system": "ENGINE", "complaint_count": 40, "total_monthly_complaints": 1000, "complaint_share_pct": 4.0},
            {"month": date(2019, 1, 1), "component_system": "ENGINE", "complaint_count": 41, "total_monthly_complaints": 1000, "complaint_share_pct": 4.1},
            {"month": date(2020, 1, 1), "component_system": "ENGINE", "complaint_count": 40, "total_monthly_complaints": 1000, "complaint_share_pct": 4.0},
            {"month": date(2020, 12, 1), "component_system": "ENGINE", "complaint_count": 900, "total_monthly_complaints": 1000, "complaint_share_pct": 90.0},
            {"month": date(2021, 1, 1), "component_system": "ENGINE", "complaint_count": 100, "total_monthly_complaints": 1000, "complaint_share_pct": 10.0},
            {"month": date(2022, 1, 1), "component_system": "ENGINE", "complaint_count": 9000, "total_monthly_complaints": 10000, "complaint_share_pct": 90.0},
        ]

        evaluated = evaluate_historical_baseline(rows)
        january_2021 = next(row for row in evaluated if row["month"] == date(2021, 1, 1))

        self.assertEqual(january_2021["history_n"], 3)
        self.assertEqual(january_2021["baseline_count_median"], 40.0)
        self.assertEqual(january_2021["count_upper_threshold"], 43.0)
        self.assertTrue(january_2021["is_anomaly"])
        self.assertEqual(january_2021["signal_status"], "above_both_thresholds")

    def test_low_volume_history_does_not_create_signal(self):
        rows = [
            {"month": date(2018, 3, 1), "component_system": "RARE", "complaint_count": 1, "total_monthly_complaints": 100, "complaint_share_pct": 1.0},
            {"month": date(2019, 3, 1), "component_system": "RARE", "complaint_count": 0, "total_monthly_complaints": 100, "complaint_share_pct": 0.0},
            {"month": date(2020, 3, 1), "component_system": "RARE", "complaint_count": 2, "total_monthly_complaints": 100, "complaint_share_pct": 2.0},
            {"month": date(2021, 3, 1), "component_system": "RARE", "complaint_count": 10, "total_monthly_complaints": 100, "complaint_share_pct": 10.0},
        ]
        evaluated = evaluate_historical_baseline(rows)
        current = evaluated[-1]
        self.assertEqual(current["signal_status"], "low_baseline_volume")
        self.assertIsNone(current["is_anomaly"])


if __name__ == "__main__":
    unittest.main()
