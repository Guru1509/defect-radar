# DEFECTRADAR — Phase 7A: Historical Evaluation Design

**Design only.** No backtest, code, or dataset changes. The target is association with subsequently *recorded* official actions, not defect truth or historical public actionability.

## Cutoff and outcome clock

Use monthly month-end cutoffs $T$. Generate every signal from complaints with `received_date <= T`; aggregate distinct `(complaint_id, component_system)` pairs, preserve multi-system assignments, and use only history before the evaluated month for the baseline. Candidate state is available at its first crossing; episode confirmation is available only on the third consecutive crossing, never backdated to onset. Apply the same cutoff to all methods.

This is an **event-time replay**, not a true historical information replay. The canonical snapshot has no historical versions or public-release timestamps. `date_added` is an administrative timestamp, not proof of public availability; component coding and complaint fields may also have changed. Label all findings accordingly. Do not describe a complaint signal as publicly actionable based on `received_date` alone.

Treat `investigations.opened_date` as the recorded opening milestone, and `recalls.recall_date` as the recorded recall filing milestone. They are outcome dates, not verified announcement/publication dates. `owner_notification_date` is incomplete and includes a future-dated value in the feasibility audit; exclude it as the primary clock. `closed_date` is not the investigation onset. An action is a later recorded event only if its usable milestone date is strictly after $T$ and within the prespecified follow-up window.

## Linkage and event definitions

There is no complaint-to-investigation/recall ID. Associate a future event with a prior system alert only through a predeclared cohort match using normalized make, model, model year, and component, from the vehicle child tables plus complaint component assignments. Freeze the component crosswalk and exact-match rules before the evaluation period. Start with exact normalized vehicle/component matches; report any broader vehicle-year or component matches separately as sensitivity results, not equal-confidence matches. A matched association is not confirmation that the alerted complaints caused or comprise the official action.

Use `investigation_id` and `campaign_number` as event identifiers. Link investigations to recalls only by exact `recall_campaign_number == campaign_number`; do not prefix-match. The prior feasibility audit found only 308 exact matches among 1,550 non-null investigation campaign values (375 additional prefix-only matches), so retain and report unmatched investigations and recalls rather than silently dropping or forcing joins. Evaluate investigation openings and recall filings as separate endpoints; when reporting a combined action chain, count an exactly linked investigation/recall chain once and retain both milestone dates.

Collapse repeated vehicle variants to distinct normalized vehicle keys within each event for matching; do not count repeated variant rows as multiple events. Complaints with multiple component assignments may enter each relevant system-specific cohort once, but deduplicate official outcomes by event ID for overall event totals and disclose system-level multi-assignment. Events with missing `opened_date` (108 in the feasibility audit) or otherwise unusable dates remain in an undated-event tally and are excluded from lead-time and post-cutoff denominators for that endpoint—not treated as non-events. If an undated investigation links by exact campaign number to a recall with a usable `recall_date`, it can still contribute to the separate recall endpoint. Keep unmatched IDs and ambiguous/multiple cohort matches as separate linkage-quality counts.

## Comparators and measures

Compare on the same system-month risk set and report each method's coverage and unavailable cases:

1. Existing scorecard strength (`trend_strength`), with component ratios retained for explanation.
2. Episode detector, treating first-month `candidate` as the prompt alert and `confirmed` as a later persistence state; report both onset and confirmation timing.
3. Raw monthly complaint count.
4. Growth-only: year-over-year count change against the same calendar month 12 months earlier; if that denominator is zero or unavailable, mark growth undefined, not zero.

For a small, predeclared alert budget, rank eligible system-months separately per method and select the **top 5 alerts per month**. For episode candidates, use the existing score strength only to order candidate starts and disclose that ranking convention; confirmation itself adds no retrospective alert credit. Report results both at the fixed budget and for the methods' native flags/states. Collapse consecutive selected alerts for the same system into alert runs for burden summaries. Match an official event to at most one preceding alert run (earliest eligible run within the horizon) so a persistent alert cannot claim repeated credit for the same action.

Use a fixed **12-month follow-up** as the primary window, plus a separately reported 24-month window where outcome coverage permits. Report:

- Recorded-event precision at the fixed alert budget: share of selected alert runs followed by a matched, dated event within the horizon. Name it *recorded-event precision*, not defect precision.
- False-alert burden: unmatched alert runs and alert-months per system/year, alongside linkage coverage and right-censoring. Unmatched alerts are not proven false because linkage and action records are incomplete.
- Lead time only for dated, matched events: days/months from the first alert (and separately confirmation) to `opened_date` or `recall_date`; report count evaluable, median and distribution. Negative/zero intervals are not future outcomes.
- Alert persistence: consecutive alert-months, run lengths, candidate-to-confirmation rate, and open/right-censored runs at the data endpoint.
- Event coverage: distinct dated investigations and recalls eligible for evaluation, exact linked chains, unmatched IDs, ambiguous matches, undated records, and events with no vehicle/component match. Always show these denominators; do not hide low evaluability behind a precision number.

## Bounded pilot and freeze policy

Pilot only the monthly top-level component-system series first. Use 2015–2019 as the development period to finalize matching rules, risk-set definitions, horizon, and reporting; freeze them before opening evaluation results. Run a later untouched chronological evaluation on 2020–2024 cutoffs, retaining only cutoffs with the full 12-month follow-up available in the outcome snapshot. The 24-month analysis uses only cutoffs with complete 24-month follow-up. Keep thresholds and score/episode rules at their already documented definitions; do not optimize them on the evaluation period. If any rule changes after inspecting evaluation results, label the next period as a new holdout rather than reusing this one. This pilot is a feasibility and measurement check, not broad backtesting or model selection.

## Interpretation limits

The complaint history ends in 2024; investigation/recall event dates extend later, but the static tables do not establish when records became public. Investigation-to-recall linkage is sparse, and complaint-to-action linkage is approximate through vehicle/component cohorts. Reporting volume is not fleet exposure; system shares are non-exclusive. Therefore the data can estimate whether historical complaint signals preceded **recorded and matchable** investigation/recall milestones under stated rules, and compare their alert burden with simple baselines. It cannot establish public warning lead time, defect causality, true defect sensitivity/specificity, recalls prevented, or that a score predicts recalls. If event counts or linkage coverage are too small, report the pilot as descriptive/inconclusive rather than drawing ranking conclusions.
