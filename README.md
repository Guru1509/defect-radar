# DefectRadar

**A reproducible research prototype for analyzing vehicle-safety complaint trends.** DefectRadar organizes NHTSA complaint and action data, measures unusual component-system complaint patterns, and compares a transparent heuristic scorecard with simple baselines against subsequently recorded official actions.

> **Research prototype—not a warning system.** DefectRadar does not predict recalls, establish that a defect exists, or verify when information became publicly available.

## Research question

How do complaint-derived temporal signals compare with simple baselines in their association with subsequently recorded, matchable NHTSA investigation openings and recall filings?

## Problem and objectives

Vehicle complaints arrive across multiple source files and may map to several components. Their volume can change because of reporting or taxonomy shifts as well as underlying vehicle issues. DefectRadar provides a reproducible way to organize these records, describe temporal patterns, and examine how those patterns relate to later recorded actions—without treating an association as proof.

The project aims to:

- Normalize complaint, component, investigation, recall, and recall-document data into linked local Parquet tables.
- Explore narrative similarity with local sentence embeddings and bounded-sample clustering.
- Measure monthly component-system complaint counts and shares against historical seasonal baselines.
- Calculate a transparent heuristic scorecard and compare it with raw-count and year-over-year-growth baselines.
- Provide a read-only dashboard for inspecting locally generated outputs.

## Key features

- **Data preparation:** Source-specific parsing and normalization for complaints, investigations, recalls, vehicles, components, and recall documents.
- **Exploratory NLP:** Sentence embeddings using `all-MiniLM-L6-v2`; clustering work is sample-only and exploratory.
- **Temporal analysis:** Same-calendar-month historical baselines for monthly complaint counts and shares, followed by a normalized heuristic trend-strength score and sequential episode states.
- **Historical comparison:** A frozen 2015–2019 development / 2020–2024 evaluation split compares scorecard strength, episode candidates, raw complaint count, and year-over-year count growth.
- **Local dashboard:** Read-only views of trends, alerts, and saved evaluation metrics.

## Architecture and pipeline

```text
NHTSA source archives (obtained and processed locally)
                         │
                         ▼
              Canonical Parquet tables
                 ┌───────┴────────┐
                 │                │
                 ▼                ▼
       Sentence embeddings   Monthly component trends
                 │                │
       Sample-only clustering     ▼
                         Heuristic scorecard / episode states
                                  │
                                  ▼
                         Historical event-time evaluation
                                  │
                                  ▼
                         Read-only local dashboard
```

Embeddings and clustering are a separate exploratory branch; they are **not** inputs to temporal scoring or historical evaluation. There is no single orchestration command. The dashboard reads saved outputs and does not build datasets or run analysis stages.

## Technology

- **Core:** Python 3.14, pandas, NumPy, PyArrow/Parquet, `python-dateutil`
- **NLP experiments:** Sentence Transformers (`all-MiniLM-L6-v2`)
- **Dashboard:** Streamlit
- **Quality checks:** pytest
- **Exploratory clustering:** K-Means and HDBSCAN on bounded samples

The dependency list is in [`requirements.txt`](requirements.txt). Embedding shards, model files, clustering outputs, and research datasets are not included in the repository.

## Installation and local data setup

Use a Python 3.14 environment. A fresh clone includes code and documentation, **not** the raw archives, canonical datasets, or generated dashboard files.

```bash
git clone https://github.com/Guru1509/defect-radar.git
cd defect-radar
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Obtain only source data you are permitted to use. Place these six ZIP archives under `data/raw/` using the expected filenames documented in [`docs/data_audit.md`](docs/data_audit.md):

- `COMPLAINTS_RECEIVED_2015-2019.zip`
- `COMPLAINTS_RECEIVED_2020-2024.zip`
- `FLAT_INV.zip`
- `FLAT_RCL_POST_2010.zip`
- `RCL_FROM_2015_2019.zip`
- `RCL_FROM_2020_2024.zip`

The repository does not grant permission to redistribute NHTSA data, narratives, or third-party materials. `/data/` and `/models/` are ignored by Git. Do not add local archives or generated artifacts to version control.

## Generate the dashboard inputs

Run these stages from the project root and in order. They build local data and research outputs; they are not needed merely to install the package. Review the stage documentation before running them, especially if local outputs already exist.

```bash
# Build the canonical Parquet tables from data/raw/
python -m src.preprocessing.build_dataset

# Generate monthly complaint trends
python -m src.temporal.monthly_baseline \
  --complaints-path data/processed/complaints.parquet \
  --components-path data/processed/complaint_components.parquet \
  --output-path data/processed/monthly_component_trends.parquet \
  --batch-size 50000

# Generate the heuristic scorecard
python -m src.temporal.emergence_score

# Generate the frozen historical alert and metrics outputs
python -c 'from src.temporal.historical_evaluation import run_pilot; run_pilot()'
```

The dashboard expects these four locally generated files:

1. `data/processed/monthly_component_trends.parquet`
2. `data/processed/monthly_emergence_scorecard.parquet`
3. `data/processed/historical_evaluation_alerts.parquet`
4. `data/processed/historical_evaluation_metrics.json`

The historical-evaluation writer refuses to overwrite existing evaluation outputs. See [`docs/local_dashboard.md`](docs/local_dashboard.md) for prerequisites, stage details, and output behavior. Embedding and clustering runs are optional and are not required for the dashboard.

## Run the tests

The full suite includes data-dependent tests. Before running it on a fresh clone, provide the local raw ZIPs and generate the canonical tables and dashboard outputs as described above.

```bash
python3.14 -m pytest -v
```

## Explore the dashboard

Start Streamlit from the project root after all four dashboard inputs exist:

```bash
python -m streamlit run dashboard/app.py --server.address 127.0.0.1
```

Open the local address printed by Streamlit. The app provides **Overview**, **Trend explorer**, **Alert review**, and **Evaluation comparison** tabs. For a guided review, select `FORWARD COLLISION AVOIDANCE` in Trend explorer, inspect the saved `2021-05` alert in Alert review, and compare the scorecard with raw-count and YoY methods in Evaluation comparison. These are aggregate research outputs, not confirmation of a defect or a public warning. Stop the local server with `Ctrl-C`.

## Historical evaluation results

The pilot replayed **60 month-end cutoffs** from January 2020 through December 2024, using **1,523 eligible system-months** and up to five selected system-months per cutoff. The primary horizon is 12 months; the 24-month analysis includes 56 cutoffs with complete follow-up. Results below are **recorded-event precision** (positive alert runs / horizon-eligible alert runs), not defect precision:

| Follow-up | Recorded endpoint | Scorecard | Raw complaint count | YoY growth | Episode candidate |
|---|---|---:|---:|---:|---:|
| 12 months | Investigation opening | 19/95 (20.0%) | 5/20 (25.0%) | 21/120 (17.5%) | 6/47 (12.8%) |
| 12 months | Recall filing | 29/95 (30.5%) | 10/20 (50.0%) | 33/120 (27.5%) | 12/47 (25.5%) |
| 24 months | Investigation opening | 21/88 (23.9%) | 8/18 (44.4%) | 24/114 (21.1%) | 7/46 (15.2%) |
| 24 months | Recall filing | 31/88 (35.2%) | 10/18 (55.6%) | 38/114 (33.3%) | 14/46 (30.4%) |

Raw complaint counts had higher recorded-event precision than the scorecard in **all four** endpoint/horizon comparisons. These descriptive results do not establish incremental predictive value: eligible samples and matched-event counts are limited, event linkage is cohort-based, and alert ranking has known tie-handling limitations. The dates are recorded investigation-opening and recall-filing dates—not verified publication or public-warning dates. **No verified public-warning lead time is claimed.**

See the full [historical evaluation pilot](docs/historical_evaluation_pilot.md) and its [diagnostic](docs/historical_evaluation_diagnostic.md) for methodology, coverage, and interpretation limits.

## Limitations and next steps

- The score is a heuristic, not a calibrated probability, validated defect detector, or recall predictor.
- Complaint counts and shares are not normalized by vehicle-fleet exposure; one complaint can map to multiple component systems.
- Complaint-to-action matching is approximate at the vehicle/component cohort level, and official-action records are incomplete.
- The historical replay uses recorded event dates and a static snapshot without complete historical public-availability timestamps.
- Clustering was exploratory and sample-only; it did not establish reliable defect classes or justify full-corpus clustering.

Potential next steps include improving linkage coverage and auditability, predeclaring a method-neutral tie-breaking rule, preserving alert-to-event assignments, obtaining historically versioned/publication-timestamped data where available, and evaluating on a separately frozen future period. These would require new data and a separately designed evaluation; they are not completed project capabilities.

## Data, documentation, and license

The [`MIT License`](LICENSE) is explicitly scoped to original project code in its stated directories. It does **not** license NHTSA source material, derived datasets or research artifacts, third-party material, dependencies, model weights, or documentation. Their rights and terms remain separate and have not been cleared by this repository. Do not interpret attribution as redistribution permission.

- [Local setup, pipeline commands, and dashboard guide](docs/local_dashboard.md)
- [Data provenance, source layouts, and archive inventory](docs/data_audit.md)
- [Canonical dataset schemas and build details](docs/canonical_dataset.md)
- [Data dictionary](docs/data_dictionary.md) · [Data model](docs/data_model.md)
- [NLP pipeline](docs/nlp_pipeline.md) · [Sample clustering study](docs/clustering.md)
- [Monthly temporal baseline](docs/temporal_baseline.md)
- [Scorecard method](docs/defect_emergence_score.md) · [Scorecard design](docs/defect_emergence_score_design.md) · [Quality audit](docs/scorecard_quality_audit.md)
- [Episode detector experiment](docs/episode_detector_experiment.md)
- [Historical evaluation design](docs/historical_evaluation_design.md) · [Pilot results](docs/historical_evaluation_pilot.md) · [Diagnostic](docs/historical_evaluation_diagnostic.md)
- [Temporal flag audit](docs/temporal_flag_audit.md) · [Submission checklist](docs/submission_checklist.md)
