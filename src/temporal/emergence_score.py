"""Explainable count/share emergence scorecard over monthly baseline rows."""

import json
import math
from pathlib import Path

from .episode_detector import detect_episodes
from .monthly_baseline import _month_start


def _normalized_excess(value, median, upper):
    if value is None or median is None or upper is None:
        return None
    value, median, upper = float(value), float(median), float(upper)
    margin = upper - median
    if not all(math.isfinite(x) for x in (value, median, upper)) or margin <= 0:
        return None
    return max(0.0, (value - median) / margin)


def score_monthly_rows(monthly_rows):
    """Add count/share normalized excesses and separate episode-state fields.

    Input rows must already contain historical-only baseline fields from
    ``evaluate_historical_baseline``. Episode states are generated sequentially
    by the separate episode detector; they do not alter the numeric score.
    """
    monthly_rows = [dict(row) for row in monthly_rows]
    episodes = detect_episodes(monthly_rows)
    episode_by_key = {
        (_month_start(row["month"]), row["component_system"]): row
        for row in episodes
    }

    scored = []
    for row in monthly_rows:
        key = (_month_start(row["month"]), row["component_system"])
        episode = episode_by_key[key]
        eligible = row.get("is_anomaly") is not None
        count_ratio = share_ratio = strength = None
        reason = None

        if not eligible:
            status = "ineligible"
            reason = row.get("signal_status") or "baseline_ineligible"
        else:
            count_ratio = _normalized_excess(
                row.get("complaint_count"), row.get("baseline_count_median"), row.get("count_upper_threshold")
            )
            share_ratio = _normalized_excess(
                row.get("complaint_share_pct"), row.get("baseline_share_median_pct"), row.get("share_upper_threshold_pct")
            )
            if count_ratio is None or share_ratio is None:
                status = "invalid_baseline"
                reason = "missing_or_nonpositive_baseline_margin"
            else:
                strength = min(count_ratio, share_ratio)
                status = "scored"

        result = dict(row)
        result.update({
            "count_trend_ratio": count_ratio,
            "share_trend_ratio": share_ratio,
            "trend_strength": strength,
            "score_status": status,
            "score_reason": reason,
            "episode_state": episode["episode_state"],
            "episode_id": episode["episode_id"],
            "episode_onset_month": episode["episode_onset_month"],
            "episode_confirmation_month": key[0] if episode["episode_state"] == "confirmed" else None,
            "episode_end_month": episode["episode_end_month"],
            "episode_crosses_frozen_bounds": episode["episode_crosses_frozen_bounds"],
        })
        scored.append(result)
    return scored


def run_scorecard(
    input_path="data/processed/monthly_component_trends.parquet",
    output_path="data/processed/monthly_emergence_scorecard.parquet",
):
    """Create a separate derived scorecard; refuse to overwrite prior output."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    output = Path(output_path)
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing output: {output}")
    source = pq.read_table(input_path)
    rows = score_monthly_rows(source.to_pylist())
    table = pa.Table.from_pylist(rows)
    metadata = dict(source.schema.metadata or {})
    metadata[b"defectradar.emergence_score"] = json.dumps({
        "method": "min_of_uncapped_count_share_excess_ratios",
        "count_ratio": "max(0, (current_count - historical_median) / (count_upper - historical_median))",
        "share_ratio": "max(0, (current_share_pct - historical_median_share_pct) / (share_upper_pct - historical_median_share_pct))",
        "trend_strength": "min(count_trend_ratio, share_trend_ratio)",
        "episode_state_is_separate": True,
        "severity_in_score": False,
        "semantic_coherence_in_score": False,
        "input_path": str(input_path),
    }, sort_keys=True).encode("utf-8")
    pq.write_table(table.replace_schema_metadata(metadata), output, compression="snappy")
    return {
        "output_path": str(output),
        "rows": len(rows),
        "scored_rows": sum(row["trend_strength"] is not None for row in rows),
        "ineligible_rows": sum(row["score_status"] == "ineligible" for row in rows),
        "invalid_baseline_rows": sum(row["score_status"] == "invalid_baseline" for row in rows),
        "episode_confirmations": sum(row["episode_state"] == "confirmed" for row in rows),
    }


def main():
    import argparse
    import json as json_module

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-path", default="data/processed/monthly_component_trends.parquet")
    parser.add_argument("--output-path", default="data/processed/monthly_emergence_scorecard.parquet")
    args = parser.parse_args()
    print(json_module.dumps(run_scorecard(args.input_path, args.output_path), indent=2))


if __name__ == "__main__":
    main()
