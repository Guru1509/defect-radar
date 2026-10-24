# DefectRadar

DefectRadar is a reproducible research pipeline for analyzing NHTSA consumer vehicle complaints, describing unusual component-system complaint trends, and comparing those signals with later **recorded, matchable** investigation openings and recall filings.

## Research question

Can complaint-derived semantic and temporal signals identify component-system patterns that precede subsequently recorded NHTSA investigations or recall filings, under an explicit historical comparison?

## Objectives

- Normalize NHTSA complaint, component, investigation, recall, and recall-document records into linked Parquet tables.
- Represent complaint narratives with local sentence embeddings and explore semantic grouping on a bounded sample.
- Measure monthly complaint counts and shares against same-calendar-month historical baselines, then calculate a transparent heuristic scorecard.
- Compare the frozen scorecard with simple count/growth comparators using historical event-time replay.
- Provide a read-only local dashboard for exploring saved outputs.

## Technologies

Python, pandas, NumPy, PyArrow/Parquet, Sentence Transformers (`all-MiniLM-L6-v2`), pytest, and Streamlit. The current embedding artifacts contain 651,260 eligible narratives in 27 shards (384-dimensional vectors).

## Pipeline and dependencies

There is **no single orchestration command**. Stages are separate; use existing outputs for review rather than rebuilding them:

```text
NHTSA source files → canonical Parquet tables
                         ├─→ complaint embeddings → sample-only clustering experiments
                         └─→ monthly component trends → heuristic scorecard
                                                   → frozen historical evaluation
                                                   → read-only dashboard
```

Embeddings and clustering are a separate exploratory branch. Embeddings are **not** inputs to monthly temporal scoring or historical evaluation. The dashboard reads the saved trend, scorecard, alert, and metrics artifacts; it does not run pipeline stages. Setup, existing artifact paths, tests, and the demonstration are in [`docs/local_dashboard.md`](docs/local_dashboard.md).

## Current status

The Git repository contains source, tests, documentation, and dashboard code, but **no datasets or generated dashboard outputs**. The raw NHTSA archives, canonical complaint/investigation/recall tables, full-corpus embedding shards, clustering outputs, and all four dashboard artifacts are excluded and ignored by Git. A fresh clone cannot display dashboard results until the required outputs are generated locally. Use only source data you are permitted to obtain and process; this repository does not grant data-redistribution rights. For local setup and the generation sequence, see [`docs/local_dashboard.md`](docs/local_dashboard.md). Place locally obtained source archives under `data/raw/`, run the documented canonical build stage, then follow the linked temporal-baseline, scorecard, and historical-evaluation instructions to generate the dashboard outputs under `data/processed/`. The source-archive inventory is in [`docs/data_audit.md`](docs/data_audit.md), and canonical table/build details are in [`docs/canonical_dataset.md`](docs/canonical_dataset.md). Embeddings and clustering are optional and are not required for the dashboard. The dashboard itself reads local outputs only and does not run pipeline stages.

The frozen evaluation uses a 2015–2019 development period and 2020–2024 evaluation cutoffs. In the fixed top-five comparison, raw complaint counts had higher recorded-event precision than the scorecard in all four reported endpoint/horizon comparisons. This is a descriptive pilot, not evidence of validated detection performance.

## Limitations

- Clustering was sample-only and did not justify full-corpus clustering or use as an integrated pipeline stage.
- The heuristic scorecard did not outperform raw complaint counts in the frozen historical comparison.
- Investigation opening and recall filing dates are recorded action dates, **not verified public-warning dates**; historical public-availability timestamps are incomplete.
- Trend strength is not a recall probability, proof of a defect, causal evidence, or a validated predictor. Complaint shares are not fleet-exposure rates, and event matching is incomplete and cohort-based.
- The historical replay uses complaint received dates, not a complete reconstruction of what information was publicly available at each past cutoff.

For scope, methods, and detailed results, see the relevant documents in `docs/`, especially the canonical dataset, NLP, temporal baseline, scorecard, historical evaluation design/pilot/diagnostic, and local dashboard guides.
