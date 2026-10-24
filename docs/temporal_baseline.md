# DEFECTRADAR — Phase 5B: Monthly Complaint Trend Baseline

**Status:** Sample-independent descriptive baseline over the canonical complaint/component corpus. This is not a recall predictor or validated defect detector.

## Method

- Read only `complaint_id`, `received_date` from `complaints.parquet` and `complaint_id`, `component_system` from `complaint_components.parquet`, in 50,000-row Parquet batches. Source datasets are unchanged.
- Use `received_date` as the event date and group to the first day of each calendar month. Monthly denominator is the number of unique complaint IDs received in that month.
- Deduplicate `(complaint_id, component_system)` pairs. A complaint appearing multiple times for the same system counts once for that system; a complaint with multiple distinct systems counts once in each system. Consequently, per-system shares use all unique monthly complaints as denominator and may sum to more than 100% across systems.
- A complaint with no nonblank component system (including no component row) is assigned to `__MISSING__`. A complaint with at least one valid system is counted only in its valid system(s), not again as missing. The output zero-fills every observed system plus this explicit bucket across every month in the corpus range.
- For each system-month, use up to five **prior observations of the same calendar month** (January compared with previous Januaries, etc.). This handles broad seasonal differences without using the current or future month. Require at least three prior observations and a combined historical count of at least 30; otherwise the result is ineligible, not a negative or positive signal.
- For eligible rows, calculate median and MAD (median absolute deviation) separately for historical monthly counts and complaint shares. Upper bounds are `median + max(3, 3 × 1.4826 × MAD)` complaints and `median share + max(0.01, 3 × 1.4826 × share MAD)` percentage points. Require current count ≥10. A candidate increase is flagged only when **both** current count and share exceed their respective bounds. `signal_status` distinguishes insufficient history, low baseline/current volume, count-only, share-only, both-threshold, and within-threshold cases. `is_anomaly` is null when ineligible.

## Measured output

The run covered **651,262 complaints**, **120 months** (2015-01 through 2024-12), and **52 categories** (51 observed systems plus `__MISSING__`), producing **6,240** month-system rows in `data/processed/monthly_component_trends.parquet`. The file stores monthly unique counts, monthly total, share, history size/volume, robust baseline statistics, thresholds, component exceedance flags, and nullable candidate flag. Baseline configuration and source paths are embedded in Parquet schema metadata.

- Eligible comparisons: **2,085**; ineligible: **4,155** (1,872 insufficient seasonal history, 2,076 low baseline volume, 207 low current volume).
- Candidate rows exceeding both thresholds: **296**; count-only: **103**; share-only: **149**; within both thresholds: **1,537**.
- Runtime: **2.324 s**; process peak RSS: **407.69 MB** (measured on the local run; environment-specific).
- Output verification confirmed 6,240 unique month-system pairs, 120 monthly denominators summing to 651,262, valid shares, and no candidate signal for ineligible rows.

These flags describe unusual complaint counts and shares under this fixed heuristic only. They are not evidence that a defect is real, increasing in the vehicle population, or predictive of an investigation or recall.

## Limitations and assumptions

- Same-calendar-month history is used only after at least three prior annual observations; earlier periods and sparse systems are explicitly ineligible. The five-year window can miss long-term drift and structural changes in reporting or taxonomy.
- A complaint with multiple component systems contributes to each system. This preserves multi-system observations but makes system shares non-exclusive.
- `__MISSING__` is a low-information bucket; thresholds prevent signals without sufficient historical volume. No make/model/year stratification or severity weighting is applied.
- Complaint shares adjust for the total number of complaints received, not vehicle fleet exposure. They must not be interpreted as defect incidence rates.
- The canonical snapshot has no historical row versions/publication timestamps. `received_date` provides complaint event time, but cannot alone prove that every field was available to a historical analyst by that cutoff.
- The threshold values are transparent starting rules, not calibrated statistical guarantees. No recall/investigation labels were used; the candidate flags do not predict recalls.

## Reproduction

From the project root:

```bash
python -m src.temporal.monthly_baseline \
  --complaints-path data/processed/complaints.parquet \
  --components-path data/processed/complaint_components.parquet \
  --output-path data/processed/monthly_component_trends.parquet \
  --batch-size 50000
```

The command refuses to overwrite an existing output. Remove or choose a new derived-output path only after separately preserving any prior result.