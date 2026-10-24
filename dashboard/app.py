"""Read-only Streamlit dashboard for existing DefectRadar artifacts."""
from __future__ import annotations

import json
import math
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
TREND_PATH = "data/processed/monthly_component_trends.parquet"
SCORE_PATH = "data/processed/monthly_emergence_scorecard.parquet"
ALERT_PATH = "data/processed/historical_evaluation_alerts.parquet"
METRICS_PATH = "data/processed/historical_evaluation_metrics.json"
REQUIRED_ARTIFACTS = (TREND_PATH, SCORE_PATH, ALERT_PATH, METRICS_PATH)


def missing_dashboard_artifacts(root: Path = ROOT) -> list[str]:
    """Return required dashboard outputs absent from a local project tree."""
    root = Path(root)
    return [path for path in REQUIRED_ARTIFACTS if not (root / path).is_file()]


def json_safe(value):
    """Convert selected pandas/numpy scalars and missing values for evidence display."""
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def load_dashboard_data(root: Path = ROOT) -> dict:
    """Load existing artifacts without writing or regenerating data."""
    root = Path(root)
    return {
        "trends": pq.read_table(root / TREND_PATH).to_pylist(),
        "scores": pq.read_table(root / SCORE_PATH).to_pylist(),
        "alerts": pq.read_table(root / ALERT_PATH).to_pylist(),
        "metrics": json.loads((root / METRICS_PATH).read_text(encoding="utf-8")),
    }


def _run_app() -> None:
    import pandas as pd
    import streamlit as st

    st.set_page_config(page_title="DefectRadar Research Dashboard", layout="wide")
    st.title("DefectRadar · Local Research Dashboard")
    st.caption("Read-only view of existing research artifacts. No detection or evaluation is run here.")
    st.warning("Trend strength is a heuristic—not a probability, confirmed defect, or recall prediction. Evaluation dates are recorded action dates, not verified public-warning dates.")

    missing = missing_dashboard_artifacts(ROOT)
    if missing:
        st.error("Local dashboard outputs are missing. They are intentionally excluded from this repository.")
        st.write("Missing files:")
        st.code("\n".join(missing))
        st.info(
            "To generate them locally, use source data you are permitted to obtain and process: "
            "place source archives under `data/raw/`, run `python -m src.preprocessing.build_dataset`, "
            "then follow the trend-baseline, scorecard, and historical-evaluation steps linked in "
            "`docs/local_dashboard.md`. Embeddings and clustering are not required. "
            "This dashboard does not generate outputs; see the runbook before restarting it."
        )
        st.stop()

    @st.cache_data
    def cached_data(root: str):
        return load_dashboard_data(Path(root))

    data = cached_data(str(ROOT))
    trends = pd.DataFrame(data["trends"])
    scores = pd.DataFrame(data["scores"])
    alerts = pd.DataFrame(data["alerts"])
    trends["month"] = pd.to_datetime(trends["month"])
    scores["month"] = pd.to_datetime(scores["month"])
    alerts["start_month"] = pd.to_datetime(alerts["start_month"])

    overview, explorer, review, evaluation = st.tabs(["Overview", "Trend explorer", "Alert review", "Evaluation comparison"])
    with overview:
        scored = scores[scores.score_status == "scored"]
        episodes = scores.episode_state.value_counts()
        a, b, c, d = st.columns(4)
        a.metric("Complaint history", f"{trends.month.min():%b %Y} – {trends.month.max():%b %Y}")
        b.metric("Eligible scored rows", f"{len(scored):,}")
        c.metric("Candidate episode rows", f"{int(episodes.get('candidate', 0)):,}")
        d.metric("Confirmed episode rows", f"{int(episodes.get('confirmed', 0)):,}")
        st.markdown("**Limitations:** historical publication timestamps are incomplete; complaints are not fleet-exposure rates; event matches are approximate and incomplete; recorded actions do not establish defect truth.")

    systems = sorted(trends.component_system.dropna().unique().tolist())
    with explorer:
        system = st.selectbox("Component system", systems, key="trend_system")
        frame = trends[trends.component_system == system].sort_values("month").set_index("month")
        st.subheader(f"{system} · monthly history")
        count_data = frame[["complaint_count", "baseline_count_median", "count_upper_threshold"]].rename(columns={"complaint_count": "Complaints", "baseline_count_median": "Historical median", "count_upper_threshold": "Upper threshold"})
        st.caption("Counts and same-calendar-month historical baseline")
        st.line_chart(count_data)
        share_data = frame[["complaint_share_pct", "baseline_share_median_pct", "share_upper_threshold_pct"]].rename(columns={"complaint_share_pct": "Complaint share (%)", "baseline_share_median_pct": "Historical share median (%)", "share_upper_threshold_pct": "Share upper threshold (%)"})
        st.caption("Complaint share is not fleet exposure")
        st.line_chart(share_data)
        scored_system = scores[scores.component_system == system].set_index("month")
        flags = scored_system[scored_system.is_anomaly == True]
        st.metric("Recorded count-and-share flags", len(flags))
        if not flags.empty:
            st.dataframe(flags[["complaint_count", "complaint_share_pct", "trend_strength", "episode_state"]], width="stretch")

    with review:
        system = st.selectbox("System", systems, key="review_system")
        months = scores.loc[scores.component_system == system, "month"].sort_values()
        month = st.selectbox("System-month", months.dt.strftime("%Y-%m").tolist(), index=len(months)-1)
        selected = scores[(scores.component_system == system) & (scores.month.dt.strftime("%Y-%m") == month)].iloc[0]
        st.subheader(f"{system} · {month}")
        st.caption("Trend strength is a heuristic normalized count/share measure, not a probability.")
        x, y, z = st.columns(3)
        x.metric("Trend strength", "Unavailable" if pd.isna(selected.trend_strength) else f"{selected.trend_strength:.3f}")
        y.metric("Score status", str(selected.score_status))
        z.metric("Episode state", str(selected.episode_state))
        evidence = {key: json_safe(value) for key, value in {
                    "complaint_count": selected.complaint_count, "historical_count_median": selected.baseline_count_median,
                    "count_upper_threshold": selected.count_upper_threshold, "complaint_share_pct": selected.complaint_share_pct,
                    "historical_share_median_pct": selected.baseline_share_median_pct, "share_upper_threshold_pct": selected.share_upper_threshold_pct,
                    "count_trend_ratio": selected.count_trend_ratio, "share_trend_ratio": selected.share_trend_ratio,
                    "count_spike": selected.count_spike, "share_spike": selected.share_spike, "signal_status": selected.signal_status,
                    "score_reason": selected.score_reason, "episode_onset_month": selected.episode_onset_month,
                    "episode_confirmation_month": selected.episode_confirmation_month}.items()}
        st.json(evidence, expanded=True)
        matched_alerts = alerts[(alerts.component_system == system) & (alerts.start_month == pd.Timestamp(month))]
        if not matched_alerts.empty:
            st.caption("Historical evaluation alert runs beginning in this system-month")
            st.dataframe(matched_alerts.drop(columns="start_month"), width="stretch")

    with evaluation:
        st.caption("Frozen recorded-event results. These are recorded-action dates, not public-warning dates.")
        rows = []
        for horizon in (12, 24):
            for endpoint in ("investigation", "recall"):
                for method, label in (("scorecard", "Scorecard (heuristic)"), ("raw_count", "Raw complaint count"), ("yoy_growth", "YoY count growth")):
                    metric = data["metrics"]["metrics"][f"{method}|{endpoint}|{horizon}m"]
                    rows.append({"Horizon": f"{horizon} months", "Recorded endpoint": endpoint.title(), "Method": label,
                                 "Positive alert runs": metric["positive_alert_runs"], "Eligible runs": metric["eligible_alert_runs"],
                                 "Recorded-event precision": f"{metric['recorded_event_precision']:.1%}",
                                 "Distinct matched events": metric["distinct_events_matched"],
                                 "Median lead to recorded action (days)": metric["median_lead_days"]})
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        st.info("In the frozen pilot, raw complaint count had higher recorded-event precision than the scorecard in all four endpoint/horizon comparisons. This does not establish early detection or prediction.")


if __name__ == "__main__":
    _run_app()
