import unittest
from datetime import date

from src.temporal.emergence_score import score_monthly_rows
from src.temporal.monthly_baseline import evaluate_historical_baseline


def baseline_row(**overrides):
    row = {
        "month": date(2022, 1, 1),
        "component_system": "ENGINE",
        "complaint_count": 15,
        "total_monthly_complaints": 1_000,
        "complaint_share_pct": 1.5,
        "history_n": 3,
        "history_total_count": 60,
        "baseline_count_median": 10.0,
        "count_upper_threshold": 20.0,
        "baseline_share_median_pct": 1.0,
        "share_upper_threshold_pct": 2.0,
        "is_anomaly": False,
        "signal_status": "within_threshold",
    }
    row.update(overrides)
    return row


def series_with_future(future_high=False, end=date(2021, 12, 1)):
    rows = []
    year, month = 2015, 1
    while date(year, month, 1) <= end:
        period = date(year, month, 1)
        count = 100 if period == date(2020, 1, 1) else 40
        if future_high and period >= date(2021, 1, 1):
            count = 5_000
        rows.append({
            "month": period,
            "component_system": "ENGINE",
            "complaint_count": count,
            "total_monthly_complaints": 10_000,
            "complaint_share_pct": count / 100.0,
        })
        month += 1
        if month == 13:
            year += 1
            month = 1
    return evaluate_historical_baseline(rows)


class TestEmergenceScore(unittest.TestCase):
    def test_normalizes_count_and_share_then_uses_bottleneck(self):
        row = baseline_row(complaint_count=30, complaint_share_pct=1.5)
        scored = score_monthly_rows([row])[0]

        self.assertEqual(scored["count_trend_ratio"], 2.0)
        self.assertEqual(scored["share_trend_ratio"], 0.5)
        self.assertEqual(scored["trend_strength"], 0.5)
        self.assertEqual(scored["score_status"], "scored")

    def test_ineligible_or_missing_baseline_is_not_scored_as_zero(self):
        row = baseline_row(
            is_anomaly=None,
            signal_status="insufficient_history",
            baseline_count_median=None,
            count_upper_threshold=None,
            baseline_share_median_pct=None,
            share_upper_threshold_pct=None,
        )
        scored = score_monthly_rows([row])[0]

        self.assertIsNone(scored["count_trend_ratio"])
        self.assertIsNone(scored["share_trend_ratio"])
        self.assertIsNone(scored["trend_strength"])
        self.assertEqual(scored["score_status"], "ineligible")
        self.assertEqual(scored["score_reason"], "insufficient_history")

    def test_missing_component_keeps_available_ratio_but_not_total_score(self):
        row = baseline_row(share_upper_threshold_pct=None)
        scored = score_monthly_rows([row])[0]

        self.assertEqual(scored["count_trend_ratio"], 0.5)
        self.assertIsNone(scored["share_trend_ratio"])
        self.assertIsNone(scored["trend_strength"])
        self.assertEqual(scored["score_status"], "invalid_baseline")

    def test_candidate_and_confirmed_state_do_not_change_numeric_trend(self):
        rows = []
        year, month = 2015, 1
        end = date(2020, 3, 1)
        while date(year, month, 1) <= end:
            period = date(year, month, 1)
            count = 100 if period.year == 2020 and period.month <= 3 else 40
            rows.append({
                "month": period,
                "component_system": "ENGINE",
                "complaint_count": count,
                "total_monthly_complaints": 10_000,
                "complaint_share_pct": count / 100.0,
            })
            month += 1
            if month == 13:
                year += 1
                month = 1
        scored = {r["month"]: r for r in score_monthly_rows(evaluate_historical_baseline(rows))}

        candidate = scored[date(2020, 1, 1)]
        confirmed = scored[date(2020, 3, 1)]
        self.assertEqual(candidate["episode_state"], "candidate")
        self.assertEqual(confirmed["episode_state"], "confirmed")
        self.assertEqual(candidate["trend_strength"], confirmed["trend_strength"])

    def test_early_score_is_invariant_to_future_months(self):
        cutoff = date(2020, 1, 1)
        prefix = [r for r in series_with_future(end=cutoff)]
        extended = series_with_future(future_high=True)

        prefix_score = next(r for r in score_monthly_rows(prefix) if r["month"] == cutoff)
        extended_score = next(r for r in score_monthly_rows(extended) if r["month"] == cutoff)

        self.assertEqual(prefix_score["trend_strength"], extended_score["trend_strength"])
        self.assertEqual(prefix_score["count_trend_ratio"], extended_score["count_trend_ratio"])
        self.assertEqual(prefix_score["share_trend_ratio"], extended_score["share_trend_ratio"])
        self.assertEqual(prefix_score["episode_state"], extended_score["episode_state"])


if __name__ == "__main__":
    unittest.main()
