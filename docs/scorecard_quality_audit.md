# DEFECTRADAR — Phase 6C: Scorecard Quality Audit

**Scope:** Read-only audit of the scorecard implementation, its documentation, and saved scorecard/monthly baseline outputs. No data or code changed.

## Distribution and boundaries

The scorecard has 6,240 unique month-system rows: 2,085 scored (33.4%), 4,155 ineligible with null strength, and no `invalid_baseline` rows. Among scored rows, `trend_strength` has minimum **0**, median **0**, maximum **116.271**; **1,078** valid rows are exactly zero and **296** exceed 1. No score equals exactly 1. The statistic is uncapped; the maximum is FORWARD COLLISION AVOIDANCE, February 2022. Its count/share ratios are **118.598/116.271**, so the minimum is 116.271. Component-ratio maxima are 118.598 (count) and 517.212 (share).

Zero is a valid floor: evidence at or below either historical median yields a zero component ratio, and the minimum of the two ratios can therefore be zero. This is distinguishable from missing evidence: the 4,155 null scores all have `score_status=ineligible`; none is represented as zero. There are 20 scored rows with zero count MAD and 2 with zero share MAD. The baseline’s positive minimum margins keep normalization finite (minimum count margin **3 complaints**, share margin **0.01 percentage points**); zero or sub-floor variability therefore does not cause division by zero. These floors can make ratios large for low-baseline systems, and no cap or cross-system calibration limits that effect.

## Component behavior and episode state

The implementation applies `max(0, (value - median)/(upper - median))` to each component, then takes the minimum. All 2,085 stored strengths exactly equal the minimum of the stored component ratios. Increasing either input cannot decrease the score; increasing the non-bottleneck component alone may leave it unchanged until that component becomes the minimum. This bottleneck behavior is intentional: both count and share evidence must rise for strength to rise. The value is heuristic, not a probability.

Episode state is appended separately after the numeric calculation. The saved rows contain 112 candidate, 15 confirmed, 286 ongoing, and 9 ended states (plus stable/ineligible). Representative forward-collision rows show a May 2021 candidate at **4.632** and a July 2021 confirmed state at **6.070**; the state label does not enter the formula. A valid zero remains `score_status=scored`, unlike an ineligible null.

## Historical cutoff and flag relationship

`score_monthly_rows` consumes baseline medians and upper thresholds already present in each month’s input row; it does not estimate a baseline from the full series. It then adds the separate episode detector’s sequential annotations. In the saved inputs, the count/share thresholds for representative FORWARD COLLISION AVOIDANCE rows in May 2021, July 2021, and February 2022 were independently recomputed from the five prior observations for the same calendar month; all sampled history dates preceded T and the medians and upper bounds matched exactly. The candidate/confirmed/ongoing labels also agree with those rows’ progression. This is a representative check, not a fresh row-by-row historical audit. The scoring function trusts the provenance of its supplied baseline fields; the saved baseline output is therefore a required historical-only input.

All **296** baseline flags have `trend_strength > 1`, with zero mismatches. This is a mathematical consequence of shared thresholds: a ratio exceeds 1 exactly when its current count/share exceeds the corresponding upper threshold; the score is their minimum, so it exceeds 1 exactly when both do. Because the existing flag uses those same two crossings, matching it is expected and is not independent validation of defect emergence or predictive value.

## Finding and recommendation

No correctness defect was found in the saved scorecard or the inspected scoring logic. The main interpretation risk is the uncapped scale: small positive baseline margins can produce very large values, which may look more precise or calibrated than they are. Preserve the current formula for this audit; display the two component ratios and baseline margins alongside strength, and describe the score as relative heuristic evidence. If a future code change is considered, the smallest conservative option is a presentation-only cap with the uncapped ratios retained—but that would change score interpretation and should require explicit review. No code change is made here.
