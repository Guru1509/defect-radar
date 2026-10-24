from datetime import date

from src.temporal.historical_evaluation import (
    _asof_signal_rows,
    _confirmation_lead_times,
    _episode_persistence,
    _evaluate_runs,
    cutoff_rows,
    deduplicate_events,
    event_in_followup,
    event_matches_cohort,
)


def test_cutoff_rows_excludes_future_even_when_appended():
    historical = {"month": date(2020, 1, 1), "component_system": "BRAKES", "complaint_count": 12}
    future = {"month": date(2020, 2, 1), "component_system": "BRAKES", "complaint_count": 999999}
    prefix = cutoff_rows([historical], date(2020, 1, 31))
    extended = cutoff_rows([historical, future], date(2020, 1, 31))
    assert prefix == extended == [historical]


def test_cutoff_replay_signal_is_invariant_to_future_extreme_row():
    from src.temporal.monthly_baseline import DEFAULT_BASELINE_CONFIG

    history = [
        {"month": date(year, 1, 1), "component_system": "BRAKES", "complaint_count": 20,
         "total_monthly_complaints": 100, "complaint_share_pct": 20.0}
        for year in range(2015, 2020)
    ]
    future = {"month": date(2020, 1, 1), "component_system": "BRAKES", "complaint_count": 999999,
              "total_monthly_complaints": 100, "complaint_share_pct": 99.0}
    cutoff = date(2019, 1, 31)
    before = _asof_signal_rows(history, cutoff, DEFAULT_BASELINE_CONFIG)
    after = _asof_signal_rows(history + [future], cutoff, DEFAULT_BASELINE_CONFIG)
    target_before = next(row for row in before if row["month"] == date(2019, 1, 1))
    target_after = next(row for row in after if row["month"] == date(2019, 1, 1))
    assert target_before["trend_strength"] == target_after["trend_strength"]
    assert target_before["episode_state"] == target_after["episode_state"]


def test_followup_is_strictly_after_cutoff_and_inclusive_at_horizon():
    cutoff = date(2020, 1, 31)
    assert not event_in_followup(cutoff, cutoff, 12)
    assert event_in_followup(date(2020, 2, 1), cutoff, 12)
    assert event_in_followup(date(2021, 1, 31), cutoff, 12)
    assert not event_in_followup(date(2021, 2, 1), cutoff, 12)
    assert not event_in_followup(None, cutoff, 12)


def test_event_dedup_keeps_one_event_and_counts_variant_rows_once():
    records = [
        {"event_id": "PE123", "event_date": date(2020, 5, 1), "vehicle_key": ("A", "M", 2020, "BRAKES:HYDRAULIC")},
        {"event_id": "PE123", "event_date": date(2020, 5, 1), "vehicle_key": ("A", "M", 2020, "BRAKES:HYDRAULIC")},
        {"event_id": "PE123", "event_date": date(2020, 5, 1), "vehicle_key": ("A", "M", 2021, "BRAKES:HYDRAULIC")},
    ]
    events = deduplicate_events(records)
    assert len(events) == 1
    assert events[0]["event_id"] == "PE123"
    assert len(events[0]["vehicle_keys"]) == 2


def test_event_match_requires_exact_vehicle_component_and_system():
    cohort = {("A", "M", 2020, "BRAKES:HYDRAULIC")}
    event_keys = {("A", "M", 2020, "BRAKES:HYDRAULIC")}
    mapping = {"BRAKES:HYDRAULIC": "BRAKES"}
    assert event_matches_cohort(cohort, event_keys, "BRAKES", mapping)
    assert not event_matches_cohort(cohort, event_keys, "ENGINE", mapping)
    assert not event_matches_cohort(cohort, {("A", "M", 2021, "BRAKES:HYDRAULIC")}, "BRAKES", mapping)


def test_one_recorded_event_is_not_credited_to_repeated_alert_runs():
    key = ("A", "M", 2020, "BRAKES:HYDRAULIC")
    runs = [
        {"cutoff": date(2020, 1, 31), "start_month": date(2020, 1, 1), "system": "BRAKES",
         "cohort": {key}, "selected_months": [date(2020, 1, 1)], "alert_months": 1},
        {"cutoff": date(2020, 3, 31), "start_month": date(2020, 3, 1), "system": "BRAKES",
         "cohort": {key}, "selected_months": [date(2020, 3, 1)], "alert_months": 1},
    ]
    events = [{"event_id": "PE123", "event_date": date(2020, 5, 1), "vehicle_keys": {key}}]
    result = _evaluate_runs(runs, events, 12, date(2022, 1, 1), {"BRAKES:HYDRAULIC": "BRAKES"})
    assert result["distinct_events_matched"] == 1
    assert result["positive_alert_runs"] == 1
    assert result["eligible_alert_runs"] == 2


def test_episode_persistence_counts_confirmation_from_onset_without_backdating():
    rows = [
        {"month": date(2020, 1, 1), "component_system": "BRAKES", "episode_id": 1,
         "episode_onset_month": date(2020, 1, 1), "episode_state": "candidate"},
        {"month": date(2020, 2, 1), "component_system": "BRAKES", "episode_id": 1,
         "episode_onset_month": date(2020, 1, 1), "episode_state": "candidate"},
        {"month": date(2020, 3, 1), "component_system": "BRAKES", "episode_id": 1,
         "episode_onset_month": date(2020, 1, 1), "episode_state": "confirmed"},
        {"month": date(2020, 4, 1), "component_system": "BRAKES", "episode_id": 1,
         "episode_onset_month": date(2020, 1, 1), "episode_state": "ongoing"},
    ]
    result = _episode_persistence(rows)
    assert result["candidate_episodes_onset_in_evaluation"] == 1
    assert result["confirmed_episodes"] == 1
    assert result["median_confirmation_delay_months"] == 2
    assert result["open_confirmed_at_evaluation_end"] == 1


def test_confirmation_lead_time_starts_when_confirmation_becomes_known():
    key = ("A", "M", 2020, "BRAKES:HYDRAULIC")
    runs = [{"method": "episode_candidate", "cutoff": date(2020, 1, 31),
             "confirmation_cutoff": date(2020, 3, 31), "system": "BRAKES", "cohort": {key}}]
    events = [{"event_id": "PE123", "event_date": date(2020, 6, 30), "vehicle_keys": {key}}]
    result = _confirmation_lead_times(runs, events, 12, date(2022, 1, 1), {"BRAKES:HYDRAULIC": "BRAKES"})
    assert result["eligible_confirmed_episodes"] == 1
    assert result["distinct_events_matched"] == 1
    assert result["median_lead_days"] == 91
