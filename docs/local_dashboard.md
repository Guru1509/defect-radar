# Local runbook and demonstration

Commands below assume the project root and the verified `python3.14` environment. If using another Python version, confirm the dependencies install and tests pass in that environment before submission.

## 1. Set up the environment

```bash
cd /path/to/DEFECT_RADAR
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

The project declares pandas, NumPy, PyArrow, python-dateutil, python-dotenv, sentence-transformers, Streamlit, and pytest. The dashboard expects the four locally generated outputs described below; they are not included in a fresh clone, and installation does not generate them. If any are missing, the app lists their paths and points to the local-generation instructions.

## 2. Local data and required dashboard outputs

The repository includes **no data files or generated dashboard outputs**. Raw NHTSA archives, canonical processed tables, embedding shards, clustering outputs, and the four dashboard outputs below are intentionally excluded and ignored by Git. Use only source data you are permitted to obtain and process; this repository does not grant redistribution rights. The source-archive inventory is in [`data_audit.md`](data_audit.md); [`canonical_dataset.md`](canonical_dataset.md) documents canonical tables and the build stage.

To prepare dashboard inputs locally:

1. Place locally obtained source archives under `data/raw/`.
2. From the project root, run the documented canonical build stage: `python -m src.preprocessing.build_dataset`.
3. Follow the stage guides in dependency order: [`temporal_baseline.md`](temporal_baseline.md) generates monthly trends; [`defect_emergence_score.md`](defect_emergence_score.md) generates the scorecard; [`historical_evaluation_pilot.md`](historical_evaluation_pilot.md) generates the historical alert and metrics outputs. The four expected local paths are:
   - `data/processed/monthly_component_trends.parquet` — monthly component-system counts, shares, and historical baselines.
   - `data/processed/monthly_emergence_scorecard.parquet` — heuristic scores and episode states.
   - `data/processed/historical_evaluation_alerts.parquet` — frozen historical alert runs.
   - `data/processed/historical_evaluation_metrics.json` — frozen recorded-action comparison metrics.

There is no single orchestration command. Embeddings and clustering are separate optional work and are not needed for the dashboard. The dashboard does not generate or modify these outputs. If any are absent, it lists the missing paths and points back to this runbook. Run the saved-output demonstration only after generating all four files locally.

## 3. Stage map

There is **no single orchestration command**. The current dependency flow is:

```text
source files → canonical Parquet tables
                   ├─→ embeddings → sample-only clustering experiments
                   └─→ monthly component trends → scorecard → historical evaluation
                                                        └→ dashboard reads saved artifacts
```

Embeddings are not consumed by temporal scoring or historical evaluation. The dashboard is read-only and loads saved trends, scorecard rows, alert runs, and metrics. Optional stage reproduction instructions are in [`temporal_baseline.md`](temporal_baseline.md), [`defect_emergence_score.md`](defect_emergence_score.md), and [`historical_evaluation_pilot.md`](historical_evaluation_pilot.md); do not run those rebuilding commands for this demonstration.

## 4. Run tests

From the project root:

```bash
python -m pytest -v
```

For the dashboard-specific smoke test:

```bash
python -m pytest tests/test_dashboard_smoke.py -q
```

## 5. Start the dashboard

```bash
python -m streamlit run dashboard/app.py --server.address 127.0.0.1
```

Open the local address printed by Streamlit. The app has Overview, Trend explorer, Alert review, and Evaluation comparison tabs. Stop it with `Ctrl-C` in the terminal.

## 6. Reproducible saved-output demonstration

1. In **Trend explorer**, select `FORWARD COLLISION AVOIDANCE`. Inspect the monthly complaint-count chart against its historical median and upper threshold, then the share chart and recorded flags.
2. In **Alert review**, select the same system and `2021-05`. Inspect the saved trend strength, score status, episode state, and evidence fields. This is a heuristic review, not confirmation of a defect.
3. In **Evaluation comparison**, compare scorecard, raw complaint count, and YoY count growth for investigation and recall endpoints at 12- and 24-month horizons. The table uses frozen saved metrics; interpret dates as recorded actions, not public warnings.

## Limitations to state in a demonstration

Clustering was sample-only and did not justify full-corpus use. In the frozen historical comparison, the scorecard did not outperform raw complaint counts in the four fixed-budget endpoint/horizon comparisons. Investigation openings and recall filings are not verified public-warning dates, and historical public-availability timestamps are incomplete. The score is neither a recall probability nor proof of a defect. The pilot measures association with recorded, matchable events, not causation or validated early-warning performance.
