# DEFECTRADAR — Phase 7C: Historical Evaluation Diagnostic Audit

**Scope:** Read-only audit of the frozen Phase 7B pilot, its evaluator/artifacts, and relevant score/baseline definitions. No thresholds, weights, or evaluation dates changed; no evaluation rerun. Results are associations with recorded, matchable actions—not defect truth, causal effects, recall prediction, or evidence of public warning.

## Findings

### Comparability and cutoff integrity

- The evaluator replays month-end cutoffs January 2020–December 2024 (60 total), recomputes baseline/score/episode states from complaint-month rows at or before each cutoff, and checks replayed fields against saved scorecard rows. Baselines use prior same-calendar-month observations only. The 2015–2019 development / 2020–2024 evaluation split and frozen 2015–2019 component map remain intact.
- Scorecard, raw count, and episode candidate ranking start from the same 1,523 scored/eligible system-months. All use the same monthly cutoff, exact normalized vehicle/component cohort match, event dates, and follow-up horizons. Each ranks up to five per cutoff; candidate alerts naturally use fewer slots (47 total). YoY growth excludes rows with zero/missing prior-year counts, so it has a narrower candidate pool and 120 alert runs versus 300 selected months for the other full-budget methods. This is inherent to undefined growth, but means “same eligible universe” applies to the common base risk set, not every comparator's rankable rows.
- Event IDs and repeated vehicle variants are deduplicated; each event is assigned at most once per method, to its earliest qualifying alert. Multiple component assignments can still make an event eligible in more than one system-specific cohort, so system-level contributions are not independent.
- Follow-up denominators correctly exclude runs without complete horizon coverage: observed endpoint 2026-09-21; 60/60 cutoffs complete at 12 months and 56/60 at 24 months. The reported primary and extended windows agree with the design.

### Ranking, missingness, and potential comparator effects

- Ineligible or invalid score rows are excluded from every method's shared base pool, not treated as zero. Valid zero scores are included in scorecard ranking. Growth-undefined rows are excluded only from growth ranking.
- Ties are broken deterministically by alphabetical `component_system`. This is reproducible but not neutral: especially for scorecard's many zero-strength ties, the selected systems can depend on naming rather than evidence. It can disadvantage or advantage any method's measured precision. The smallest corrective action is to treat this as an audit limitation now; before any future evaluation, predeclare a method-neutral tie rule (e.g. seeded, recorded random tie-break) and freeze it. Do not revise this pilot's result post hoc.
- The episode method is onset-only and ranked by score strength, as specified. Its 47 alerts versus 300 for full-budget methods mean its precision is not a same-volume comparison; present its coverage alongside precision.
- Precision is positive **alert runs** divided by horizon-eligible runs, not unique events divided by alerts. A run can match multiple events, while each event receives one run per method. The metrics correctly report both quantities, but they should not be conflated.

### Observed results, contributors, and overlap

At 12 months, investigation / recall recorded-event precision was: scorecard 19/95 (20.0%) / 29/95 (30.5%); raw count 5/20 (25.0%) / 10/20 (50.0%); YoY 21/120 (17.5%) / 33/120 (27.5%); episode candidates 6/47 (12.8%) / 12/47 (25.5%). At 24 months the corresponding values were scorecard 21/88 / 31/88, raw count 8/18 / 10/18, YoY 24/114 / 38/114, and episodes 7/46 / 14/46. These are descriptive, with small numbers of distinct matched events (12-month scorecard: 32 investigations/42 recalls; raw: 6/15; YoY: 26/51; episode: 7/14).

System aggregates in the saved metrics show scorecard matches distributed across more system categories (e.g. ENGINE and ELECTRICAL SYSTEM lead investigation/recall counts); raw-count matches are concentrated in STEERING (2 investigation and 5 recall matched events at 12 months) and one each in several other systems. These are event-match counts aggregated by alerted system, not named event-level records; the alert artifact does not store matched event IDs, so a precise event-by-event contribution audit cannot be recovered from these artifacts without rerunning/augmenting the evaluator.

I expanded alert runs to selected system-months and compared method pairs: shared selections / Jaccard were scorecard–episode 34 / 10.9%; scorecard–raw 25 / 4.4%; scorecard–YoY 171 / 39.9%; episode–raw 3 / 0.9%; episode–YoY 30 / 9.5%; raw–YoY 14 / 2.4%. This indicates markedly different ranked choices, except stronger scorecard–YoY overlap; it does not by itself explain precision.

### Is raw count capturing persistent high-volume systems?

Observed: raw count produced only 20 alert runs across 300 selected system-months, versus scorecard's 95 runs across 300 months. Its longest runs were ENGINE, ELECTRICAL SYSTEM, and UNKNOWN OR OTHER, each selected continuously for 60 months; POWER TRAIN was selected in a 25-month run then a 34-month run. The count method's top-five slots were therefore heavily occupied by persistent high-volume series, not just newly increasing series. Some separate shorter STEERING and SERVICE BRAKES runs also occurred. Scorecard/raw overlap was only 25 selected system-months, consistent with the scorecard applying a different rank ordering.

Interpretation: these observations support that the raw-count comparator largely rewards sustained complaint volume in this pilot. Raw count nevertheless had higher recorded-event precision than the scorecard at both horizons/endpoints, but this is not evidence that persistent volume detects emerging defects early. Recorded lead times are measured to later database action dates; cohort matching is approximate, complaint volume is not fleet exposure, and public availability is unknown. The pilot cannot distinguish useful early detection from persistence, reporting volume, or linkage/coverage effects.

## Material limitations and recommendation

- Matching is strict at normalized make/model/year/component and uses 396 component mappings frozen from development data; no ambiguous mappings, prefix campaign fallback, or fuzzy matching are used. This limits false linkage but misses legitimate matches. Of 5,349 investigations, 1,791 lack complete vehicle/component keys and 108 lack opening dates; 3,059 of 15,286 recalls lack keys. Only 308/1,550 investigation campaign references match recall campaigns exactly. Unmatched alerts are not proven false, and unmatched/undated events are not confirmed negatives.
- Outcome clocks are recorded `opened_date` and `recall_date`, not publication/announcement timestamps. Historical complaint snapshots and public-release dates are incomplete; `received_date` replay is not proof information was publicly available at that time. Consequently no public-warning lead time can be claimed.
- The 24-month analysis has four fewer fully followed cutoffs; horizon-specific denominators differ. The run-level one-event assignment and multi-event-per-run precision definition are consistent with the design but make event counts and alert precision distinct measures.

**Recommendation:** Make no scorecard or split changes from this audit. Treat Phase 7B as a descriptive feasibility result: raw count exceeded scorecard recorded-event precision at the fixed budget, while the audit shows the raw ranking was dominated by persistent high-volume systems. Neither result establishes early detection or prediction. If another evaluation is authorized, first resolve and predeclare tie handling and store alert-to-event assignment IDs for auditability; retain the frozen historical result as-is, and obtain historical public-availability timestamps before making any public-warning claim.
