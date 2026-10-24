"""Bounded event-time pilot for monthly complaint alerts and recorded actions."""

from collections import defaultdict
from datetime import date
import calendar
import json
from pathlib import Path
from statistics import median

import pyarrow as pa
import pyarrow.parquet as pq

from .monthly_baseline import DEFAULT_BASELINE_CONFIG, evaluate_historical_baseline, _month_start
from .emergence_score import score_monthly_rows

TRAIN_END = date(2019, 12, 31)
EVAL_START = date(2020, 1, 1)
EVAL_END = date(2024, 12, 31)
ALERT_BUDGET = 5


def cutoff_rows(rows, cutoff):
    """Keep monthly observations available by the month-end cutoff."""
    return [row for row in rows if _month_start(row["month"]) <= cutoff]


def _add_months(day, months):
    index = day.year * 12 + day.month - 1 + months
    year, month_index = divmod(index, 12)
    month = month_index + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def event_in_followup(event_date, cutoff, horizon_months):
    """A dated event is in follow-up iff cutoff < event date <= horizon end."""
    return event_date is not None and cutoff < event_date <= _add_months(cutoff, horizon_months)


def deduplicate_events(records):
    """Deduplicate by event ID, retaining earliest date and unique vehicle variants."""
    grouped = {}
    for row in records:
        event_id = row.get("event_id")
        if event_id is None or not str(event_id).strip():
            continue
        event_id = str(event_id).strip()
        item = grouped.setdefault(event_id, {"event_id": event_id, "event_date": None, "vehicle_keys": set()})
        event_date = row.get("event_date")
        if event_date is not None and (item["event_date"] is None or event_date < item["event_date"]):
            item["event_date"] = event_date
        if row.get("vehicle_key") is not None:
            item["vehicle_keys"].add(tuple(row["vehicle_key"]))
    return [grouped[event_id] for event_id in sorted(grouped)]


def event_matches_cohort(alert_cohort, event_vehicle_keys, system, component_to_system):
    """Use exact make/model/year/component overlap and the frozen component map."""
    return any(key in alert_cohort and component_to_system.get(key[3]) == system for key in event_vehicle_keys)


def _iter_parquet(path, columns, batch_size=50_000):
    parquet = pq.ParquetFile(path)
    for batch in parquet.iter_batches(columns=columns, batch_size=batch_size):
        arrays = [batch.column(i).to_pylist() for i in range(len(columns))]
        yield from zip(*arrays)


def _read_table_rows(path):
    return pq.read_table(path).to_pylist()


def _vehicle_key(make, model, year, component):
    if not make or not model or year is None or not component:
        return None
    return (str(make).strip(), str(model).strip(), int(year), str(component).strip())


def _load_cohorts(project_root):
    complaint_info = {}
    for cid, received, make, model, year in _iter_parquet(
        project_root / "data/processed/complaints.parquet",
        ["complaint_id", "received_date", "make_normalized", "model_normalized", "model_year"],
    ):
        complaint_info[cid] = (received, make, model, year)

    component_path = project_root / "data/processed/complaint_components.parquet"
    component_systems = defaultdict(set)
    for cid, component, system in _iter_parquet(component_path, ["complaint_id", "component_normalized", "component_system"]):
        info = complaint_info.get(cid)
        if info and info[0] and info[0] <= TRAIN_END and component and system:
            component_systems[str(component).strip()].add(str(system).strip())
    ambiguous = sum(len(systems) > 1 for systems in component_systems.values())
    component_to_system = {key: next(iter(values)) for key, values in component_systems.items() if len(values) == 1}

    cohorts = defaultdict(set)
    keyed_rows = mapped_rows = 0
    for cid, component, _stored_system in _iter_parquet(component_path, ["complaint_id", "component_normalized", "component_system"]):
        info = complaint_info.get(cid)
        system = component_to_system.get(str(component).strip()) if component else None
        if not info or not info[0] or not system:
            continue
        received, make, model, year = info
        key = _vehicle_key(make, model, year, component)
        if key:
            keyed_rows += 1
            cohorts[(_month_start(received), system)].add(key)
            mapped_rows += 1
    return cohorts, component_to_system, {
        "complaint_rows": len(complaint_info),
        "frozen_component_mappings": len(component_to_system),
        "ambiguous_component_mappings_excluded": ambiguous,
        "cohort_component_rows_with_exact_vehicle_key": keyed_rows,
        "cohort_rows_using_frozen_mapping": mapped_rows,
        "month_system_cohorts": len(cohorts),
    }


def _load_events(project_root, component_to_system, kind):
    if kind == "investigation":
        base = project_root / "data/processed/investigations.parquet"
        vehicles = project_root / "data/processed/investigation_vehicles.parquet"
        id_col, date_col = "investigation_id", "opened_date"
    else:
        base = project_root / "data/processed/recalls.parquet"
        vehicles = project_root / "data/processed/recall_vehicles.parquet"
        id_col, date_col = "campaign_number", "recall_date"

    dates = {}
    for event_id, event_date in _iter_parquet(base, [id_col, date_col]):
        if event_id is None or not str(event_id).strip():
            continue
        event_id = str(event_id).strip()
        prior = dates.get(event_id)
        if event_id not in dates or (event_date is not None and (prior is None or event_date < prior)):
            dates[event_id] = event_date
    raw = [{"event_id": event_id, "event_date": event_date} for event_id, event_date in dates.items()]
    for event_id, make, model, year, component in _iter_parquet(
        vehicles, [id_col, "make_normalized", "model_normalized", "model_year", "component_normalized"]
    ):
        if event_id is None or not component or str(component).strip() not in component_to_system:
            continue
        key = _vehicle_key(make, model, year, str(component).strip())
        if key:
            raw.append({"event_id": str(event_id).strip(), "event_date": dates.get(str(event_id).strip()), "vehicle_key": key})
    events = deduplicate_events(raw)
    return events


def _month_cutoffs():
    result = []
    current = date(EVAL_START.year, EVAL_START.month, 1)
    while current <= EVAL_END:
        result.append(date(current.year, current.month, calendar.monthrange(current.year, current.month)[1]))
        current = _add_months(current, 1)
    return result


def _asof_signal_rows(baseline_rows, cutoff, config):
    # Recompute baseline and sequential episode states from a prefix only.
    prefix = cutoff_rows(baseline_rows, cutoff)
    return score_monthly_rows(evaluate_historical_baseline(prefix, **config))


def _select_alerts(current_rows, baseline_rows, cohorts, cutoff):
    eligible = [row for row in current_rows if row["score_status"] == "scored"]
    month = _month_start(cutoff)
    selected = {}

    def take(method, rows, metric):
        ordered = sorted(rows, key=lambda row: (-metric(row), row["component_system"]))[:ALERT_BUDGET]
        selected[method] = [
            {"method": method, "system": row["component_system"], "month": month, "cutoff": cutoff,
             "strength": row.get("trend_strength"), "signal_value": metric(row),
             "cohort": cohorts.get((month, row["component_system"]), set()),
             "episode_id": row.get("episode_id"), "episode_state": row.get("episode_state")}
            for row in ordered
        ]

    take("scorecard", eligible, lambda row: float(row["trend_strength"]))
    candidates = [row for row in eligible if row["episode_state"] == "candidate"
                  and row.get("episode_onset_month") is not None
                  and _month_start(row["episode_onset_month"]) == month]
    take("episode_candidate", candidates, lambda row: float(row["trend_strength"]))
    take("raw_count", eligible, lambda row: float(row["complaint_count"]))

    baseline_index = {(row["month"], row["component_system"]): row for row in baseline_rows}
    growth = []
    for row in eligible:
        prior_month = date(month.year - 1, month.month, 1)
        prior = baseline_index.get((prior_month, row["component_system"]))
        if prior and int(prior["complaint_count"]) > 0:
            copy = dict(row)
            copy["_growth"] = (int(row["complaint_count"]) - int(prior["complaint_count"])) / int(prior["complaint_count"])
            growth.append(copy)
    take("yoy_growth", growth, lambda row: float(row["_growth"]))
    return selected


def _make_run(method, system, alerts):
    first = alerts[0]
    return {**first, "start_month": first["month"], "end_month": alerts[-1]["month"],
            "alert_months": len(alerts), "selected_months": [row["month"] for row in alerts]}


def _collapse_alerts(selected_by_cutoff, cohorts):
    grouped = defaultdict(list)
    for by_method in selected_by_cutoff.values():
        for method, alerts in by_method.items():
            for alert in alerts:
                grouped[(method, alert["system"])].append(alert)
    runs = []
    for (method, system), alerts in grouped.items():
        alerts.sort(key=lambda row: row["month"])
        if method == "episode_candidate":
            for alert in alerts:
                run = _make_run(method, system, [alert])
                run["cohort"] = cohorts.get((run["start_month"], system), set())
                runs.append(run)
            continue
        active = []
        for alert in alerts:
            if active and _add_months(active[-1]["month"], 1) != alert["month"]:
                run = _make_run(method, system, active)
                run["cohort"] = cohorts.get((run["start_month"], system), set())
                runs.append(run)
                active = []
            active.append(alert)
        if active:
            run = _make_run(method, system, active)
            run["cohort"] = cohorts.get((run["start_month"], system), set())
            runs.append(run)
    for run in runs:
        run["cutoff"] = date(run["start_month"].year, run["start_month"].month,
                             calendar.monthrange(run["start_month"].year, run["start_month"].month)[1])
    return sorted(runs, key=lambda row: (row["method"], row["start_month"], row["system"]))


def _end_of_month(month):
    return date(month.year, month.month, calendar.monthrange(month.year, month.month)[1])


def _evaluate_runs(runs, events, horizon, outcome_end, component_to_system):
    eligible = [run for run in runs if _add_months(run["cutoff"], horizon) <= outcome_end]
    pairs = []
    for event in events:
        if event["event_date"] is None:
            continue
        for index, run in enumerate(eligible):
            if event_in_followup(event["event_date"], run["cutoff"], horizon) and event_matches_cohort(
                run["cohort"], event["vehicle_keys"], run["system"], component_to_system
            ):
                pairs.append((run["cutoff"], event["event_date"], event["event_id"], index))
    pairs.sort()
    assigned = defaultdict(list)
    used_events = set()
    event_by_id = {event["event_id"]: event for event in events}
    for _cutoff, _event_date, event_id, index in pairs:
        if event_id not in used_events:
            used_events.add(event_id)
            assigned[index].append(event_id)
    leads = [(event_by_id[event_id]["event_date"] - eligible[index]["cutoff"]).days
             for index, event_ids in assigned.items() for event_id in event_ids]
    positives = sum(bool(assigned.get(index)) for index in range(len(eligible)))
    burden = defaultdict(lambda: {"eligible_alert_runs": 0, "positive_alert_runs": 0,
                                  "unmatched_alert_runs": 0, "eligible_alert_months": 0,
                                  "unmatched_alert_months": 0})
    for index, run in enumerate(eligible):
        key = (run["start_month"].year, run["system"])
        group = burden[key]
        group["eligible_alert_runs"] += 1
        complete_months = sum(
            _add_months(date(month.year, month.month, calendar.monthrange(month.year, month.month)[1]), horizon) <= outcome_end
            for month in run["selected_months"]
        )
        group["eligible_alert_months"] += complete_months
        if assigned.get(index):
            group["positive_alert_runs"] += 1
        else:
            group["unmatched_alert_runs"] += 1
            group["unmatched_alert_months"] += complete_months
    return {
        "eligible_alert_runs": len(eligible), "positive_alert_runs": positives,
        "recorded_event_precision": positives / len(eligible) if eligible else None,
        "unmatched_alert_runs": len(eligible) - positives,
        "eligible_alert_months": sum(group["eligible_alert_months"] for group in burden.values()),
        "false_alert_burden_by_system_year": [
            {"year": year, "component_system": system, **values}
            for (year, system), values in sorted(burden.items())
        ],
        "distinct_events_matched": len(used_events), "lead_time_events": len(leads),
        "median_lead_days": median(leads) if leads else None,
        "min_lead_days": min(leads) if leads else None, "max_lead_days": max(leads) if leads else None,
    }


def _confirmation_lead_times(runs, events, horizon, outcome_end, component_to_system):
    confirmed = [run for run in runs if run.get("confirmation_cutoff") is not None
                and _add_months(run["confirmation_cutoff"], horizon) <= outcome_end]
    pairs = []
    for event in events:
        if event["event_date"] is None:
            continue
        for index, run in enumerate(confirmed):
            if event_in_followup(event["event_date"], run["confirmation_cutoff"], horizon) and event_matches_cohort(
                run["cohort"], event["vehicle_keys"], run["system"], component_to_system
            ):
                pairs.append((run["confirmation_cutoff"], event["event_date"], event["event_id"], index))
    pairs.sort()
    assigned = {}
    used = set()
    dates = {event["event_id"]: event["event_date"] for event in events}
    for _cutoff, _event_date, event_id, index in pairs:
        if event_id not in used:
            used.add(event_id)
            assigned[event_id] = confirmed[index]["confirmation_cutoff"]
    leads = [(dates[event_id] - cutoff).days for event_id, cutoff in assigned.items()]
    return {"eligible_confirmed_episodes": len(confirmed), "distinct_events_matched": len(used),
            "lead_time_events": len(leads), "median_lead_days": median(leads) if leads else None,
            "min_lead_days": min(leads) if leads else None, "max_lead_days": max(leads) if leads else None}


def _event_coverage(events):
    return {"unique_events": len(events), "dated_events": sum(event["event_date"] is not None for event in events),
            "undated_events": sum(event["event_date"] is None for event in events),
            "events_with_vehicle_component_keys": sum(bool(event["vehicle_keys"]) for event in events),
            "events_without_vehicle_component_keys": sum(not event["vehicle_keys"] for event in events)}


def _episode_persistence(rows):
    grouped = defaultdict(list)
    for row in rows:
        onset = row.get("episode_onset_month")
        if row.get("episode_id") is None or onset is None:
            continue
        onset = _month_start(onset)
        if _month_start(EVAL_START) <= onset <= _month_start(EVAL_END):
            grouped[(row["component_system"], row["episode_id"], onset)].append(row)
    attempts = []
    for (system, episode_id, onset), states in grouped.items():
        states.sort(key=lambda row: _month_start(row["month"]))
        confirmed = [row for row in states if row["episode_state"] == "confirmed"]
        confirmation_delay = None
        if confirmed:
            cm = _month_start(confirmed[0]["month"])
            confirmation_delay = (cm.year - onset.year) * 12 + cm.month - onset.month
        attempts.append({"component_system": system, "episode_id": episode_id, "onset": onset,
                         "observed_months": len({row["month"] for row in states}),
                         "confirmed": bool(confirmed), "confirmation_delay_months": confirmation_delay,
                         "last_state": states[-1]["episode_state"]})
    durations = [item["observed_months"] for item in attempts]
    delays = [item["confirmation_delay_months"] for item in attempts if item["confirmed"]]
    return {"candidate_episodes_onset_in_evaluation": len(attempts),
            "confirmed_episodes": sum(item["confirmed"] for item in attempts),
            "confirmation_rate": sum(item["confirmed"] for item in attempts) / len(attempts) if attempts else None,
            "median_observed_duration_months": median(durations) if durations else None,
            "max_observed_duration_months": max(durations) if durations else 0,
            "median_confirmation_delay_months": median(delays) if delays else None,
            "open_confirmed_at_evaluation_end": sum(item["confirmed"] and item["last_state"] in {"ongoing", "confirmed"} for item in attempts)}


def run_pilot(project_root=".", alerts_output="data/processed/historical_evaluation_alerts.parquet",
              metrics_output="data/processed/historical_evaluation_metrics.json"):
    """Execute the frozen chronological pilot and write separate derived outputs."""
    root = Path(project_root)
    alert_path, metrics_path = root / alerts_output, root / metrics_output
    if alert_path.exists() or metrics_path.exists():
        raise FileExistsError("Refusing to overwrite a historical evaluation artifact")
    source = pq.read_table(root / "data/processed/monthly_component_trends.parquet")
    baseline_rows = source.to_pylist()
    score_rows = pq.read_table(root / "data/processed/monthly_emergence_scorecard.parquet").to_pylist()
    if len(score_rows) != len(baseline_rows):
        raise ValueError("Scorecard and baseline row counts differ")
    saved_scores = {(row["month"], row["component_system"]): row for row in score_rows}
    metadata = json.loads((source.schema.metadata or {}).get(b"defectradar.baseline", b"{}"))
    config = metadata.get("config", DEFAULT_BASELINE_CONFIG)
    cohorts, component_to_system, cohort_stats = _load_cohorts(root)
    inv_base = _read_table_rows(root / "data/processed/investigations.parquet")
    recall_base = _read_table_rows(root / "data/processed/recalls.parquet")
    inv_events = _load_events(root, component_to_system, "investigation")
    recall_events = _load_events(root, component_to_system, "recall")
    inv_dates = [row["opened_date"] for row in inv_base if row.get("opened_date") is not None]
    recall_dates = [row["recall_date"] for row in recall_base if row.get("recall_date") is not None]
    outcome_end = min(max(inv_dates), max(recall_dates))
    cutoffs = _month_cutoffs()
    selected_by_cutoff = {}
    replayed_scored_rows = 0
    replay_rows = []
    native = {"scorecard_flags_gt_1": 0, "episode_candidate_starts": 0, "episode_confirmations": 0}
    episode_attempts = {}

    for cutoff in cutoffs:
        asof = _asof_signal_rows(baseline_rows, cutoff, config)
        current = [row for row in asof if _month_start(row["month"]) == _month_start(cutoff)]
        for row in current:
            saved = saved_scores.get((row["month"], row["component_system"]))
            if saved is None or any(saved[field] != row[field] for field in (
                "trend_strength", "score_status", "episode_state", "episode_id", "episode_onset_month"
            )):
                raise ValueError(f"Cutoff replay differs from saved scorecard at {row['month']} / {row['component_system']}")
        replay_rows.extend(current)
        replayed_scored_rows += sum(row["score_status"] == "scored" for row in current)
        native["scorecard_flags_gt_1"] += sum(row["trend_strength"] is not None and row["trend_strength"] > 1 for row in current)
        for row in current:
            onset = row.get("episode_onset_month")
            if onset is None:
                continue
            onset = _month_start(onset)
            if not (_month_start(EVAL_START) <= onset <= _month_start(EVAL_END)):
                continue
            key = (row["component_system"], row["episode_id"], onset)
            if row["episode_state"] == "candidate" and onset == _month_start(cutoff):
                native["episode_candidate_starts"] += 1
                episode_attempts.setdefault(key, False)
            if row["episode_state"] == "confirmed":
                native["episode_confirmations"] += 1
                episode_attempts[key] = True
        selected_by_cutoff[cutoff] = _select_alerts(current, baseline_rows, cohorts, cutoff)

    runs = _collapse_alerts(selected_by_cutoff, cohorts)
    confirmation_dates = {}
    for row in replay_rows:
        if row["episode_state"] == "confirmed" and row.get("episode_onset_month") is not None:
            key = (row["component_system"], row["episode_id"], _month_start(row["episode_onset_month"]))
            confirmation_dates[key] = _end_of_month(_month_start(row["month"]))
    for run in runs:
        if run["method"] == "episode_candidate":
            key = (run["system"], run["episode_id"], run["start_month"])
            run["confirmation_cutoff"] = confirmation_dates.get(key)
    endpoints = {"investigation": inv_events, "recall": recall_events}
    metrics = {
        "design": {"development_period": "2015-2019", "evaluation_period": "2020-2024", "alert_budget_per_month": ALERT_BUDGET,
                   "primary_horizon_months": 12, "event_time_replay_only": True,
                   "recorded_outcomes_not_publication_dates": True,
                   "vehicle_component_matching": "exact normalized make/model/year/component; component map frozen from 2015-2019 complaints"},
        "cutoffs": {"scheduled": len(cutoffs), "with_complete_12_month_followup": sum(_add_months(cutoff, 12) <= outcome_end for cutoff in cutoffs),
                    "with_complete_24_month_followup": sum(_add_months(cutoff, 24) <= outcome_end for cutoff in cutoffs),
                    "observed_outcome_coverage_end": outcome_end.isoformat(), "scored_system_months_replayed": replayed_scored_rows},
        "native_signal_counts": native,
        "episode_persistence": _episode_persistence(replay_rows),
        "episode_attempts": len(episode_attempts), "cohort_matching": cohort_stats,
        "event_coverage": {kind: _event_coverage(events) for kind, events in endpoints.items()},
        "exact_investigation_recall_campaign_links": None, "metrics": {}, "persistence": {},
    }
    recall_campaigns = {row.get("campaign_number") for row in recall_base if row.get("campaign_number")}
    inv_campaigns = [row.get("recall_campaign_number") for row in inv_base if row.get("recall_campaign_number")]
    exact_links = sum(campaign in recall_campaigns for campaign in inv_campaigns)
    metrics["exact_investigation_recall_campaign_links"] = {
        "investigations_with_campaign_number": len(inv_campaigns), "exact_campaign_matches": exact_links,
        "unmatched_campaign_values": len(inv_campaigns) - exact_links,
    }

    alert_rows = []
    methods = sorted({run["method"] for run in runs})
    for method in methods:
        method_runs = [run for run in runs if run["method"] == method]
        lengths = [run["alert_months"] for run in method_runs]
        metrics["persistence"][method] = {"alert_runs": len(lengths), "selected_alert_months": sum(lengths),
            "median_run_months": median(lengths) if lengths else None, "max_run_months": max(lengths) if lengths else 0,
            "runs_longer_than_one_month": sum(length > 1 for length in lengths)}
        for horizon in (12, 24):
            for kind, events in endpoints.items():
                metrics["metrics"][f"{method}|{kind}|{horizon}m"] = _evaluate_runs(
                    method_runs, events, horizon, outcome_end, component_to_system
                )
                if method == "episode_candidate":
                    metrics["metrics"][f"{method}|{kind}|{horizon}m|from_confirmation"] = _confirmation_lead_times(
                        method_runs, events, horizon, outcome_end, component_to_system
                    )
        for run in method_runs:
            alert_rows.append({"method": method, "component_system": run["system"], "start_month": run["start_month"],
                "end_month": run["end_month"], "alert_months": run["alert_months"], "start_strength": run.get("strength"),
                "start_signal_value": run.get("signal_value"), "episode_id": run.get("episode_id"),
                "episode_state_at_start": run.get("episode_state"), "episode_confirmation_cutoff": run.get("confirmation_cutoff"),
                "onset_cohort_vehicle_component_keys": len(run["cohort"])})

    alert_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(alert_rows), alert_path, compression="snappy")
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(metrics, indent=2, sort_keys=True), encoding="utf-8")
    return {"alerts_path": str(alert_path), "metrics_path": str(metrics_path), "alert_runs": len(alert_rows), "metrics": metrics}
