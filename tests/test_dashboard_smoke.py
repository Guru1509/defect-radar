from pathlib import Path

from dashboard.app import json_safe, load_dashboard_data


def test_alert_evidence_values_are_json_safe():
    import numpy as np

    assert json_safe(np.int64(7)) == 7
    assert json_safe(float("nan")) is None
    assert json_safe(None) is None


def test_dashboard_loads_existing_artifacts_read_only():
    root = Path(__file__).resolve().parents[1]
    data = load_dashboard_data(root)

    assert len(data["trends"]) == 6240
    assert len(data["scores"]) == 6240
    assert len(data["alerts"]) == 282
    assert data["metrics"]["design"]["evaluation_period"] == "2020-2024"
    assert {row["method"] for row in data["alerts"]} == {
        "scorecard", "raw_count", "yoy_growth", "episode_candidate"
    }
    assert any(row["score_status"] == "ineligible" and row["trend_strength"] is None for row in data["scores"])
    assert any(row["episode_state"] == "candidate" for row in data["scores"])
    assert any(row["episode_state"] == "confirmed" for row in data["scores"])
