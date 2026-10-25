# Local runbook and demonstration

Commands below assume the project root and the verified `python3.14` environment. If using another Python version, confirm the dependencies install and tests pass in that environment before submission.

## 1. Set up the environment

```bash
cd /path/to/DEFECT_RADAR
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

The project declares pandas, NumPy, PyArrow, python-dateutil, python-dotenv, sentence-transformers, Streamlit, and pytest. Raw archives, canonical Parquet tables, and the four locally generated dashboard outputs are excluded from a fresh clone; installation does not create them. The dashboard lists missing output paths and points to local-generation instructions, and cannot display results until all four outputs exist.

## 2. Local data and required dashboard outputs

The repository includes **no data files or generated dashboard outputs**. Raw NHTSA archives, canonical processed tables, embedding shards, clustering outputs, and the four dashboard outputs below are intentionally excluded and ignored by Git. Use only source data you are permitted to obtain and process; this repository does not grant redistribution rights. The source-archive inventory is in [`data_audit.md`](data_audit.md); [`canonical_dataset.md`](canonical_dataset.md) documents canonical tables and the build stage.

To prepare dashboard inputs locally, use source data you are permitted to obtain and process. The six expected archive names are listed in [`data_audit.md`](data_audit.md); place the local ZIPs under `data/raw/`. Never add those ZIPs or generated outputs to Git.

1. From the project root, run `python -m src.preprocessing.build_dataset` to build canonical Parquet tables. This module has no `--help` CLI; invoking it runs the pipeline.
2. Generate monthly trends using [`temporal_baseline.md`](temporal_baseline.md):
   ```bash
   python -m src.temporal.monthly_baseline \
     --complaints-path data/processed/complaints.parquet \
     --components-path data/processed/complaint_components.parquet \
     --output-path data/processed/monthly_component_trends.parquet \
     --batch-size 50000
   ```
3. Generate the scorecard using [`defect_emergence_score.md`](defect_emergence_score.md): `python -m src.temporal.emergence_score`.
4. Generate the historical alert and metrics outputs using [`historical_evaluation_pilot.md`](historical_evaluation_pilot.md): `python -c 'from src.temporal.historical_evaluation import run_pilot; run_pilot()'`. This function refuses to overwrite existing evaluation outputs.

The four expected local paths are:
- `data/processed/monthly_component_trends.parquet` — monthly component-system counts, shares, and historical baselines.
- `data/processed/monthly_emergence_scorecard.parquet` — heuristic scores and episode states.
- `data/processed/historical_evaluation_alerts.parquet` — frozen historical alert runs.
- `data/processed/historical_evaluation_metrics.json` — frozen recorded-action comparison metrics.

There is no single orchestration command. Embeddings and clustering are separate optional work and are not needed for the dashboard. The dashboard does not generate or modify these outputs. If any are absent, it lists the missing paths and points back to this runbook. It cannot display results until all four files have been generated locally.

## 3. Stage map

There is **no single orchestration command**. The current dependency flow is:

```text
source files → canonical Parquet tables
                   ├─→ embeddings → sample-only clustering experiments
                   └─→ monthly component trends → scorecard → historical evaluation
                                                        └→ dashboard reads saved artifacts
```

Embeddings are not consumed by temporal scoring or historical evaluation. The dashboard is read-only and loads saved trends, scorecard rows, alert runs, and metrics. On a fresh clone, follow the stage guides above to generate local outputs before using the dashboard. If the outputs already exist and you are only repeating the saved-output demonstration, do not rerun rebuilding stages.

## 4. Run tests

From the project root, after placing the six raw ZIPs and building the canonical Parquet tables. The full suite includes tests that require those excluded data files; `tests/test_dashboard_smoke.py` additionally requires all four dashboard outputs. A fresh clone must complete the local generation steps in section 2 before running the data-dependent tests.

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
