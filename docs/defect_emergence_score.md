# DEFECTRADAR — Phase 6B: Initial Defect Emergence Scorecard

**Status:** Small, descriptive scorecard over the existing monthly series. It is not a validated defect detector and does not prove defects or predict recalls. The Phase 5B baseline and Phase 5E episode detector remain unchanged.

## Calculation

For an eligible system-month, use the historical-only same-calendar-month median $m$ and upper bound $u$ already stored by the baseline:

- `count_trend_ratio = max(0, (complaint_count - baseline_count_median) / (count_upper_threshold - baseline_count_median))`
- `share_trend_ratio = max(0, (complaint_share_pct - baseline_share_median_pct) / (share_upper_threshold_pct - baseline_share_median_pct))`
- `trend_strength = min(count_trend_ratio, share_trend_ratio)`

Each ratio is 0 at/below its median and 1 at its upper bound; values above 1 remain uncapped. The minimum requires count and share movement together, without arbitrary weights. It is a heuristic normalized strength, not a probability or a calibrated 0–100 scale. Report both ratios with the score and underlying bounds to preserve interpretability.

Eligibility follows the saved baseline: at least three prior same-calendar-month observations, historical count total ≥30, current count ≥10, and a non-null baseline signal. Ineligible rows have null component ratios and null `trend_strength`, with `score_status=ineligible` and the baseline `signal_status` as reason. Missing/nonpositive normalization margins yield `invalid_baseline` and null overall strength; any available component ratio is retained rather than hidden.

Episode state (`stable`, `candidate`, `confirmed`, `ongoing`, `ended`, `ineligible`) is stored separately and never changes the numeric score. The first-month candidate is visible immediately; confirmation appears only at the third qualifying month, with its confirmation month distinct from onset. Severity and semantic coherence are omitted from this scorecard: severity inputs require separate field/support and as-of-availability validation, and narrative coherence is not yet reliable enough for the score. No severity or semantic fields are read into this artifact.

## Saved output

Ran `python -m src.temporal.emergence_score` on `data/processed/monthly_component_trends.parquet`. The separate output is `data/processed/monthly_emergence_scorecard.parquet` (6,240 unique month-system rows): **2,085 scored**, **4,155 ineligible**, **0 invalid baselines**. All **296** existing count-and-share flags correspond to `trend_strength > 1`; this follows from the shared thresholds and is not independent validation. Episode annotations include 15 confirmation rows, 112 candidate-state rows, 286 ongoing rows, and 9 ended rows; ineligible and stable rows remain separately labeled.

Among scored rows, trend strength ranged from **0** to **116.271**, with median **0** and inclusive 90th percentile **1.519**. Example: FORWARD COLLISION AVOIDANCE in May 2021 had count/share ratios **4.632/7.762**, strength **4.632**, and state `candidate`. In February 2022 the ratios were **118.598/116.272**, strength **116.272**, and state `ongoing`. The very large value reflects a small historical upper-bound margin for a low-baseline category-month; it is a relative heuristic, not extraordinary certainty. Keep component values and source baselines visible.

The Parquet output preserves the baseline metadata and records the score formula and exclusions. The writer refuses to overwrite an existing output. Canonical datasets, embedding/clustering artifacts, and the saved baseline output were not modified.

## Limitations and leakage controls

The score reuses baseline medians/upper bounds computed only from earlier same-calendar months; the episode detector processes rows sequentially and freezes bounds before candidate onset. Future-month invariance is covered by focused tests. A later confirmed state must not be backdated as information known at onset: confirmation is available two months after the first candidate crossing. The static complaint snapshot lacks complete historical publication timestamps, so `received_date` cutoffs cannot guarantee what an analyst knew at the time.

Complaint shares are not fleet-exposure rates and may be non-exclusive because one complaint can name multiple systems. Baseline thresholds and normalized ratios are uncalibrated heuristic quantities; they can be unstable for narrow historical distributions. Severity and narrative content are not included. No recall labels, predictors, causal claims, clustering, or application features were added.

## Tests

Focused tests cover normalization/bottleneck behavior, unavailable evidence, retained partial components, historical cutoff invariance, and separation of candidate/confirmed state from numeric strength. Focused result: **5 passed**. The project test suite was run once after these passed.
