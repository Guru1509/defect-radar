"""Experimental consecutive-month episode detector, separate from the baseline."""

from collections import defaultdict
from datetime import date

from .monthly_baseline import _median_mad, _month_start


def freeze_seasonal_bounds(
    prior_rows,
    component_system,
    before_month,
    lookback_years=5,
    min_history_months=3,
    min_baseline_total=30,
    mad_multiplier=3.0,
    min_count_margin=3.0,
    min_share_margin_pct=0.01,
):
    """Freeze robust bounds by calendar month using rows strictly before a date."""
    before_month = _month_start(before_month)
    available = [
        row for row in prior_rows
        if row["component_system"] == component_system and _month_start(row["month"]) < before_month
    ]
    bounds = {}
    for month_number in range(1, 13):
        history = sorted(
            (row for row in available if _month_start(row["month"]).month == month_number),
            key=lambda row: _month_start(row["month"]),
        )[-lookback_years:]
        if len(history) < min_history_months or sum(int(row["complaint_count"]) for row in history) < min_baseline_total:
            bounds[month_number] = None
            continue
        counts = [int(row["complaint_count"]) for row in history]
        shares = [float(row["complaint_share_pct"]) for row in history]
        count_median, count_mad = _median_mad(counts)
        share_median, share_mad = _median_mad(shares)
        bounds[month_number] = {
            "count_upper": count_median + max(min_count_margin, mad_multiplier * 1.4826 * count_mad),
            "share_upper_pct": share_median + max(min_share_margin_pct, mad_multiplier * 1.4826 * share_mad),
            "history_n": len(history),
            "history_total_count": sum(counts),
        }
    return bounds


def _eligible(row, min_history_months, min_baseline_total, min_current_count):
    return (
        row.get("is_anomaly") is not None
        and row.get("history_n", 0) >= min_history_months
        and row.get("history_total_count", 0) >= min_baseline_total
        and int(row["complaint_count"]) >= min_current_count
        and row.get("count_upper_threshold") is not None
        and row.get("share_upper_threshold_pct") is not None
    )


def _crosses(row, bounds):
    return (
        bounds is not None
        and int(row["complaint_count"]) > bounds["count_upper"]
        and float(row["complaint_share_pct"]) > bounds["share_upper_pct"]
    )


def detect_episodes(
    monthly_rows,
    lookback_years=5,
    min_history_months=3,
    min_baseline_total=30,
    min_current_count=10,
    mad_multiplier=3.0,
    min_count_margin=3.0,
    min_share_margin_pct=0.01,
    confirm_months=3,
    end_months=3,
):
    """Annotate rows with candidate/confirmed/ongoing/ended episode states.

    A candidate starts on an existing eligible baseline flag. It is confirmed
    after ``confirm_months`` adjacent eligible months exceed the frozen seasonal
    bounds. A confirmed episode ends after ``end_months`` adjacent eligible
    months fail the count-and-share conjunction. Missing/ineligible periods break
    candidate streaks and reset an active episode's end streak; they never count
    as below-bound observations.
    """
    if confirm_months < 1 or end_months < 1 or lookback_years < 1:
        raise ValueError("episode and lookback lengths must be positive")

    ordered = sorted(monthly_rows, key=lambda row: (_month_start(row["month"]), row["component_system"]))
    keys = [(_month_start(row["month"]), row["component_system"]) for row in ordered]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate month/system rows supplied")

    history_by_system = defaultdict(list)
    state_by_system = {}
    last_month_by_system = {}
    next_id_by_system = defaultdict(int)
    result = []

    for source in ordered:
        row = dict(source)
        month = _month_start(row["month"])
        if month != row["month"]:
            raise ValueError("Monthly rows must use first-of-month dates")
        system = row["component_system"]
        previous_month = last_month_by_system.get(system)
        adjacent = previous_month is not None and _month_start(previous_month).year * 12 + _month_start(previous_month).month == month.year * 12 + month.month - 1
        if previous_month is not None and not adjacent:
            state = state_by_system.get(system)
            if state and state["kind"] == "candidate":
                state_by_system.pop(system, None)
            elif state and state["kind"] == "active":
                state["below_streak"] = 0

        state = state_by_system.get(system)
        eligible = _eligible(row, min_history_months, min_baseline_total, min_current_count)
        live_bounds = None
        if eligible:
            live_bounds = {
                "count_upper": float(row["count_upper_threshold"]),
                "share_upper_pct": float(row["share_upper_threshold_pct"]),
            }
        live_cross = eligible and _crosses(row, live_bounds)

        row.update({
            "episode_state": "ineligible" if not eligible else "stable",
            "episode_id": None,
            "episode_onset_month": None,
            "episode_end_month": None,
            "episode_count_upper_threshold": None,
            "episode_share_upper_threshold_pct": None,
            "episode_crosses_frozen_bounds": None,
        })

        confirmed_this_month = False
        if state and state["kind"] == "candidate":
            frozen = state["bounds"].get(month.month)
            crossed = eligible and _crosses(row, frozen)
            if adjacent and crossed:
                state["months"].append(month)
                row["episode_state"] = "candidate"
                if frozen:
                    row["episode_count_upper_threshold"] = frozen["count_upper"]
                    row["episode_share_upper_threshold_pct"] = frozen["share_upper_pct"]
                row["episode_crosses_frozen_bounds"] = True
                if len(state["months"]) >= confirm_months:
                    state["kind"] = "active"
                    state["below_streak"] = 0
                    confirmed_this_month = True
                    row["episode_state"] = "confirmed"
                    row["episode_id"] = state["episode_id"]
                    row["episode_onset_month"] = state["onset_month"]
            else:
                state_by_system.pop(system, None)
                state = None

        if state and state["kind"] == "active" and not confirmed_this_month:
            frozen = state["bounds"].get(month.month)
            if not eligible or frozen is None:
                row["episode_state"] = "ongoing"
                state["below_streak"] = 0
                crossed = None
            else:
                crossed = _crosses(row, frozen)
                row["episode_state"] = "ongoing"
                state["below_streak"] = 0 if crossed else state["below_streak"] + 1
                if state["below_streak"] >= end_months:
                    row["episode_state"] = "ended"
                    row["episode_end_month"] = month
                    state_by_system.pop(system, None)
            row["episode_id"] = state["episode_id"]
            row["episode_onset_month"] = state["onset_month"]
            if frozen:
                row["episode_count_upper_threshold"] = frozen["count_upper"]
                row["episode_share_upper_threshold_pct"] = frozen["share_upper_pct"]
            row["episode_crosses_frozen_bounds"] = crossed
            state = state_by_system.get(system)

        if state is None and live_cross:
            bounds = freeze_seasonal_bounds(
                history_by_system[system], system, month,
                lookback_years=lookback_years,
                min_history_months=min_history_months,
                min_baseline_total=min_baseline_total,
                mad_multiplier=mad_multiplier,
                min_count_margin=min_count_margin,
                min_share_margin_pct=min_share_margin_pct,
            )
            frozen = bounds.get(month.month)
            if frozen is not None and _crosses(row, frozen):
                next_id_by_system[system] += 1
                state = {
                    "kind": "candidate",
                    "episode_id": next_id_by_system[system],
                    "onset_month": month,
                    "months": [month],
                    "bounds": bounds,
                }
                state_by_system[system] = state
                row["episode_state"] = "candidate"
                row["episode_id"] = state["episode_id"]
                row["episode_onset_month"] = month
                row["episode_count_upper_threshold"] = frozen["count_upper"]
                row["episode_share_upper_threshold_pct"] = frozen["share_upper_pct"]
                row["episode_crosses_frozen_bounds"] = True
                if confirm_months == 1:
                    state["kind"] = "active"
                    state["below_streak"] = 0
                    confirmed_this_month = True
                    row["episode_state"] = "confirmed"
                    row["episode_id"] = state["episode_id"]
                    row["episode_onset_month"] = state["onset_month"]

        if state and state["kind"] == "candidate":
            row["episode_id"] = state["episode_id"]
            row["episode_onset_month"] = state["onset_month"]
            frozen = state["bounds"].get(month.month)
            if frozen:
                row["episode_count_upper_threshold"] = frozen["count_upper"]
                row["episode_share_upper_threshold_pct"] = frozen["share_upper_pct"]
            if row["episode_crosses_frozen_bounds"] is None:
                row["episode_crosses_frozen_bounds"] = _crosses(row, frozen) if eligible else None

        result.append(row)
        history_by_system[system].append(source)
        last_month_by_system[system] = month

    return result
