import unittest
from datetime import date

from src.temporal.episode_detector import detect_episodes
from src.temporal.monthly_baseline import evaluate_historical_baseline


def build_series(overrides=None, end=date(2021, 12, 1), omitted=()):
    overrides = overrides or {}
    omitted = set(omitted)
    rows = []
    year, month = 2015, 1
    while date(year, month, 1) <= end:
        period = date(year, month, 1)
        if period not in omitted:
            count = overrides.get(period, 40)
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


def by_month(rows):
    return {row["month"]: row for row in rows}


class TestEpisodeDetector(unittest.TestCase):
    def test_three_consecutive_crossings_confirm_once_and_show_delay(self):
        start = date(2020, 1, 1)
        overrides = {date(2020, m, 1): 100 for m in range(1, 5)}
        baseline = build_series(overrides)
        episodes = by_month(detect_episodes(baseline))

        self.assertEqual([episodes[date(2020, m, 1)]["episode_state"] for m in range(1, 5)],
                         ["candidate", "candidate", "confirmed", "ongoing"])
        self.assertEqual(episodes[date(2020, 1, 1)]["episode_onset_month"], start)
        self.assertEqual(episodes[date(2020, 3, 1)]["episode_onset_month"], start)
        self.assertEqual(episodes[date(2020, 1, 1)]["episode_id"], episodes[date(2020, 4, 1)]["episode_id"])
        self.assertTrue(all(episodes[date(2020, m, 1)]["is_anomaly"] for m in range(1, 4)))

    def test_bounds_remain_frozen_from_before_candidate_month(self):
        overrides = {date(2020, m, 1): 100 for m in range(1, 4)}
        overrides[date(2020, 4, 1)] = 900
        episodes = by_month(detect_episodes(build_series(overrides)))

        february = episodes[date(2020, 2, 1)]
        april = episodes[date(2020, 4, 1)]
        self.assertEqual(february["episode_count_upper_threshold"], 43.0)
        self.assertAlmostEqual(february["episode_share_upper_threshold_pct"], 0.41)
        self.assertEqual(april["episode_count_upper_threshold"], 43.0)
        self.assertAlmostEqual(april["episode_share_upper_threshold_pct"], 0.41)

    def test_missing_calendar_month_breaks_candidate_streak(self):
        overrides = {date(2020, m, 1): 100 for m in (1, 3, 4, 5)}
        episodes = by_month(detect_episodes(build_series(overrides, omitted=[date(2020, 2, 1)])))

        self.assertEqual(episodes[date(2020, 1, 1)]["episode_state"], "candidate")
        self.assertEqual(episodes[date(2020, 3, 1)]["episode_state"], "candidate")
        self.assertEqual(episodes[date(2020, 4, 1)]["episode_state"], "candidate")
        self.assertEqual(episodes[date(2020, 5, 1)]["episode_state"], "confirmed")
        self.assertEqual(episodes[date(2020, 5, 1)]["episode_onset_month"], date(2020, 3, 1))

    def test_episode_ends_after_three_consecutive_non_crossings(self):
        overrides = {date(2020, m, 1): 100 for m in range(1, 4)}
        episodes = by_month(detect_episodes(build_series(overrides)))

        self.assertEqual(episodes[date(2020, 3, 1)]["episode_state"], "confirmed")
        self.assertEqual(episodes[date(2020, 4, 1)]["episode_state"], "ongoing")
        self.assertEqual(episodes[date(2020, 5, 1)]["episode_state"], "ongoing")
        self.assertEqual(episodes[date(2020, 6, 1)]["episode_state"], "ended")
        self.assertEqual(episodes[date(2020, 6, 1)]["episode_end_month"], date(2020, 6, 1))
        self.assertEqual(episodes[date(2020, 7, 1)]["episode_state"], "stable")

    def test_ineligible_month_breaks_candidate_streak(self):
        overrides = {
            date(2020, 1, 1): 100,
            date(2020, 2, 1): 5,
            date(2020, 3, 1): 100,
            date(2020, 4, 1): 100,
            date(2020, 5, 1): 100,
        }
        episodes = by_month(detect_episodes(build_series(overrides, end=date(2020, 5, 1))))

        self.assertEqual(episodes[date(2020, 1, 1)]["episode_state"], "candidate")
        self.assertEqual(episodes[date(2020, 2, 1)]["episode_state"], "ineligible")
        self.assertEqual(episodes[date(2020, 3, 1)]["episode_state"], "candidate")
        self.assertEqual(episodes[date(2020, 4, 1)]["episode_state"], "candidate")
        self.assertEqual(episodes[date(2020, 5, 1)]["episode_state"], "confirmed")
        self.assertEqual(episodes[date(2020, 5, 1)]["episode_onset_month"], date(2020, 3, 1))

    def test_missing_month_resets_active_end_streak(self):
        overrides = {date(2020, m, 1): 100 for m in range(1, 4)}
        episodes = by_month(detect_episodes(build_series(
            overrides, end=date(2020, 8, 1), omitted=[date(2020, 5, 1)]
        )))

        self.assertEqual(episodes[date(2020, 3, 1)]["episode_state"], "confirmed")
        self.assertEqual(episodes[date(2020, 4, 1)]["episode_state"], "ongoing")
        self.assertNotIn(date(2020, 5, 1), episodes)
        self.assertEqual(episodes[date(2020, 6, 1)]["episode_state"], "ongoing")
        self.assertEqual(episodes[date(2020, 7, 1)]["episode_state"], "ongoing")
        self.assertEqual(episodes[date(2020, 8, 1)]["episode_state"], "ended")

    def test_ineligible_month_resets_active_end_streak(self):
        overrides = {date(2020, m, 1): 100 for m in range(1, 4)}
        overrides.update({date(2020, 5, 1): 5})
        episodes = by_month(detect_episodes(build_series(overrides, end=date(2020, 8, 1))))

        self.assertEqual(episodes[date(2020, 4, 1)]["episode_state"], "ongoing")
        self.assertEqual(episodes[date(2020, 5, 1)]["episode_state"], "ongoing")
        self.assertEqual(episodes[date(2020, 6, 1)]["episode_state"], "ongoing")
        self.assertEqual(episodes[date(2020, 7, 1)]["episode_state"], "ongoing")
        self.assertEqual(episodes[date(2020, 8, 1)]["episode_state"], "ended")

    def test_exact_count_bound_is_not_a_crossing(self):
        episodes = by_month(detect_episodes(build_series({date(2020, 1, 1): 43})))

        january = episodes[date(2020, 1, 1)]
        self.assertEqual(january["count_upper_threshold"], 43.0)
        self.assertFalse(january["is_anomaly"])
        self.assertEqual(january["episode_state"], "stable")

    def test_dataset_endpoint_on_confirmation_month_is_not_marked_ended(self):
        overrides = {date(2020, m, 1): 100 for m in range(1, 4)}
        episodes = by_month(detect_episodes(build_series(overrides, end=date(2020, 3, 1))))

        march = episodes[date(2020, 3, 1)]
        self.assertEqual(march["episode_state"], "confirmed")
        self.assertIsNone(march["episode_end_month"])
        self.assertTrue(all(row["episode_state"] != "ended" for row in episodes.values()))

    def test_future_values_do_not_change_prior_episode_or_frozen_bounds(self):
        overrides = {date(2020, m, 1): 100 for m in range(1, 4)}
        cutoff = date(2020, 3, 1)
        prefix = build_series(overrides, end=cutoff)
        future_overrides = dict(overrides)
        future_overrides.update({date(2021, m, 1): 5_000 for m in range(1, 13)})
        extended = build_series(future_overrides, end=date(2021, 12, 1))

        prefix_result = by_month(detect_episodes(prefix))
        extended_result = by_month(detect_episodes(extended))
        for month in (date(2020, m, 1) for m in range(1, 4)):
            self.assertEqual(prefix_result[month]["episode_state"], extended_result[month]["episode_state"])
            self.assertEqual(prefix_result[month]["episode_count_upper_threshold"],
                             extended_result[month]["episode_count_upper_threshold"])
            self.assertEqual(prefix_result[month]["episode_share_upper_threshold_pct"],
                             extended_result[month]["episode_share_upper_threshold_pct"])


if __name__ == "__main__":
    unittest.main()
