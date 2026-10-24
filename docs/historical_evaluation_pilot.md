# DEFECTRADAR — Phase 7B: Historical Evaluation Pilot

**Scope:** Bounded event-time pilot using fixed 2015–2019 development and 2020–2024 evaluation periods. This is a comparison against *recorded, matchable actions*—not a test of defect truth, recall prediction, or public actionability. No parameters were tuned on evaluation outcomes.

## Replay and matching

For each of 60 month-end cutoffs from January 2020 through December 2024, the implementation replayed the monthly baseline from rows dated through that cutoff, then regenerated the scorecard and sequential episode states from that prefix. Replayed score, eligibility, episode state, ID, and onset matched the saved scorecard at every evaluated month/system row. All four methods used the common eligible system-month set (1,523 eligible scored rows over the 60 cutoffs): scorecard strength, first-month episode candidate, raw count, and year-over-year count growth. Growth is undefined when prior-year count is zero or missing. Each method selected up to five system-months per cutoff; episode candidates were ranked by score strength and naturally used fewer slots. Consecutive selected months were collapsed to runs for burden and outcome accounting.

The component-normalized-to-system map was frozen from 2015–2019 complaint rows (396 unique mappings; no ambiguous mappings). Outcomes matched only on exact normalized make, model, model year, and component key present in the onset-month complaint cohort. No fuzzy vehicle-year, component, or campaign-prefix fallback was used. Multiple component assignments remain system-specific, but a dated event is credited to at most one alert run per method, preventing repeated credit. Duplicate event IDs and repeated vehicle variants were deduplicated. Investigation openings and recall filings were separate outcomes; campaign links used exact identifiers only.

Use `investigations.opened_date` and `recalls.recall_date` as **recorded event dates**, not publication dates. The canonical snapshot lacks complete public-availability timestamps; therefore this is an event-time replay, not a claim that a signal could have been seen or acted on publicly. The primary horizon is 12 months; 24 months is reported only for cutoffs with complete observed outcome-date coverage. The conservative common endpoint was **2026-09-21**.

## Coverage and eligible samples

- Cutoffs: **60/60** have 12-month observed follow-up; **56/60** have 24-month observed follow-up. There are **1,523** eligible system-months replayed.
- Investigations: **5,349** unique IDs; **5,241** have `opened_date`, **108** are undated; **3,558** have at least one complete normalized vehicle/component key, and **1,791** do not.
- Recalls: **15,286** unique campaigns; all have `recall_date`; **12,227** have a complete normalized vehicle/component key, **3,059** do not.
- Of **1,550** non-null investigation campaign references, **308** match a recall campaign exactly and **1,242** do not. Prefix-only candidates were not joined. Undated or unmatched events are not counted as confirmed negatives; they are omitted from timed/matched outcomes and retained in coverage counts.

## Recorded-event results at the fixed budget

Cells show positive alert runs / eligible alert runs (recorded-event precision), then distinct matched events and median lead time among matched events. Lead time is from the first alert to the recorded milestone; no public-warning interpretation is implied.

### 12-month follow-up

| Method | Investigation opening | Recall filing |
|---|---|---|
| Scorecard | 19/95 (20.0%); 32 events, median 219.5 days | 29/95 (30.5%); 42 events, median 210 days |
| Episode candidate | 6/47 (12.8%); 7 events, median 251 days | 12/47 (25.5%); 14 events, median 181.5 days |
| Raw count | 5/20 (25.0%); 6 events, median 139.5 days | 10/20 (50.0%); 15 events, median 229 days |
| YoY growth | 21/120 (17.5%); 26 events, median 217 days | 33/120 (27.5%); 51 events, median 188 days |

### 24-month follow-up

| Method | Investigation opening | Recall filing |
|---|---|---|
| Scorecard | 21/88 (23.9%); 40 events, median 378 days | 31/88 (35.2%); 53 events, median 294 days |
| Episode candidate | 7/46 (15.2%); 8 events, median 347.5 days | 14/46 (30.4%); 17 events, median 220 days |
| Raw count | 8/18 (44.4%); 11 events, median 461 days | 10/18 (55.6%); 21 events, median 313 days |
| YoY growth | 24/114 (21.1%); 35 events, median 342 days | 38/114 (33.3%); 67 events, median 275 days |

At 12 months, unmatched alert runs were: scorecard **76 investigation / 66 recall**, episode candidate **41/35**, raw count **15/10**, and YoY growth **99/87**. At 24 months: **67/57**, **39/32**, **10/8**, and **90/76**, respectively. These are unmatched runs, not proven false alerts. Exact false-alert run and month burdens by method, outcome, system, and run-onset year are in the metrics artifact.

The episode detector produced **47** candidate starts and **8** confirmations (**17.0%**); median observed episode span was **1 month**, maximum **56 months**, median confirmation delay **2 months**, and **6** confirmed episodes remained open at the evaluation endpoint. Episode state is not backdated: candidate alerts occur at onset and confirmation later. Measuring from confirmation instead of onset, 8 confirmed episodes had complete 12- and 24-month follow-up; 3 investigation events matched (median **200 days**, range 39–205) and 4 recall events matched (median **127.5 days**, range 90–225).

Selected-alert persistence by method: scorecard **95 runs / 300 alert-months**, median run 1 month (max 30); episode candidates **47 / 47**, by definition one onset month each; raw count **20 / 300**, median run 2.5 months (max 60); YoY growth **120 / 300**, median 1 month (max 25). These are run-length summaries of the budgeted selections, not defect durations.

## Interpretation

At this fixed budget, the scorecard was modestly above YoY growth in recorded-event precision for both outcomes at 12 and 24 months, but below raw complaint volume in all four comparisons. Episode candidates were sparser and had lower recorded-event precision than either scorecard or raw count in this pilot. These descriptive differences do **not** establish incremental predictive value: event matching is approximate at the cohort level, official-action linkage is incomplete, public availability is unknown, and evaluable matched-event counts are small. The pilot does not support claims about defects, causation, recall prediction, or public warning lead time.

## Artifacts and verification

- `src/temporal/historical_evaluation.py` — fixed-split replay, exact cohort matching, alert selection, and metrics.
- `tests/test_historical_evaluation.py` — cutoff/future-value invariance, follow-up boundaries, event/variant deduplication, exact matching, one-event crediting, and episode confirmation timing.
- `data/processed/historical_evaluation_alerts.parquet` — **282** selected alert runs across four methods, including onset-month cohort sizes and confirmation cutoffs for episode alerts.
- `data/processed/historical_evaluation_metrics.json` — cutoff/event coverage, precision, onset- and confirmation-anchored lead time, persistence, and per-system/year unmatched burden.

Focused tests: **8 passed**. Full suite: **68 passed**. Reproduce from the project root with:

```bash
python -c 'from src.temporal.historical_evaluation import run_pilot; run_pilot()'
```

The run refuses to overwrite existing artifacts. Canonical datasets, baseline/scorecard outputs, embeddings, clustering artifacts, and the approved design document were not modified.
