# Defect Emergence Score — Design Proposal (Phase 6A)

**Status:** Design only. No code, detector, or dataset changes. This is a proposed descriptive prioritization aid—not a validated defect detector, causal measure, investigation predictor, or recall predictor.

## Design principle

Start with a transparent **scorecard**, not a weighted sum. Report the numeric trend strength beside an explicit episode state and separate severity/semantic evidence fields. This avoids inventing weights that current data cannot validate and keeps immediate candidates visible. A single composite should be considered only after time-censored evaluation supports its calibration.

## Component definitions

### 1. Count increase

For system $s$ and month $t$, use the saved baseline's prior same-calendar-month median $m_c$ and upper bound $u_c$. Define

$$R_c=\max\left(0,\frac{c_t-m_c}{u_c-m_c}\right).$$

This expresses the current count's lift above its historical median in units of the historical upper-bound margin: 0 at/below the median and 1 at the bound. Keep values above 1 uncapped to distinguish larger exceedances. The current baseline's eligibility gates remain in force (at least 3 prior seasons, historical count total ≥30, current count ≥10); if ineligible or baseline fields are missing, report **not scored**, not zero. Its lookback and thresholds must contain only earlier same-calendar months. A final-state snapshot has incomplete publication timestamps, so `received_date` cutoffs do not prove all fields were available to an analyst then.

### 2. Complaint-share change

Use the same normalization for the monthly share: $R_h=\max(0,(h_t-m_h)/(u_h-m_h))$, where $m_h,u_h$ are the historical share median and upper bound. Shares use unique monthly complaints as denominator and are non-exclusive across systems when complaints have multiple component assignments. Do not call them fleet-adjusted defect rates. Apply the same eligibility and historical-only rules as counts; missing/ineligible history yields null.

**Trend strength:** $T=\min(R_c,R_h)$. The bottleneck makes both count and share evidence matter, consistent with the existing detector's conjunction, without assigning a fitted-looking weight. $T>1$ means both measures exceed their respective bounds; smaller values can show sub-threshold movement. Report $R_c$ and $R_h$ too, so the bottleneck is explainable. These are heuristic normalized units, not probabilities.

### 3. Episode state

Attach the episode detector's categorical state: `stable`, `candidate`, `confirmed`, `ongoing`, `ended`, or `ineligible`. This component is categorical and has no numeric normalization in v0; do not one-hot-and-sum it or multiply the numeric trend strength by an arbitrary candidate/confirmed factor. Show a first-month candidate immediately as *provisional*; mark it confirmed only at the third consecutive eligible crossing. Record both onset month and confirmation month. For a real-time evaluation, confirmation is not available at onset: using the backdated onset as if it were known then would leak two months of future evidence. An open episode at the data endpoint is censored, not ended. Missing/ineligible episode evidence remains `ineligible` or `candidate`/`ongoing` according to the detector's transition rules; it is never silently treated as stable.

For the initial scorecard, state changes interpretation/priority, not numeric $T$. A later scalar could use an explicitly calibrated persistence component, but its rule and parameters must be learned using training periods only and then frozen for later periods.

### 4. Severity evidence

First verify field definitions, completeness, and whether severity is known as of complaint receipt; the monthly baseline itself does not use severity. At complaint level, collapse repeated component rows to one record per `complaint_id`; derive separate indicators such as “any reported injury” and “any reported death” (or validated event-level counts), not a sum of repeated severity values. For each system-month, calculate unique severe-complaint rates over unique complaints assigned to that system. If a complaint names multiple systems, it can contribute once to each system-specific rate, but a portfolio-wide total must fractionally allocate its event contribution across its $k$ distinct systems ($1/k$ each) or deduplicate it once at vehicle-complaint level. Never sum duplicated component rows as independent events.

If later enabled, for each severe-complaint rate $q$ define $R_q=\max(0,(q_t-m_q)/(u_q-m_q))$, with $m_q,u_q$ the prior same-calendar-month median and robust upper bound (`median + max(fixed floor, 3 × 1.4826 × MAD)`). Set the floor and minimum complaint/event support before evaluation; if support fails or historical rates are all-zero/too sparse to estimate a usable bound, return unknown. Show injury and death channels separately, and define severity evidence as $S=\max(R_{injury},R_{death})$ rather than adding overlapping indicators. Always show denominators. When severity fields are missing, delayed, ambiguous, or too sparse, return **unknown/not scored**, not “no severity.” Initially show raw unique severe-complaint counts/rates as context only; do not add severity to $T$ until its semantics, support gates, and incremental value are tested. Leakage risks include post-receipt field updates, future investigation/recall fields, repeated values on component rows, and selecting severity cutoffs after viewing evaluation outcomes.

### 5. Semantic coherence

Do **not** include a semantic contribution in the initial score. Phase 5C found broad component labels and mixed narrative themes; sample-only clustering was not validated for full-corpus use. If later tested without clusters, a candidate measure is $c_t$, the median cosine similarity of each unique complaint's symptom-focused embedding to its system-month centroid. Normalize only against that system's earlier-month same-season distribution: $R_{sem}=\max(0,(c_t-m_{sem})/(u_{sem}-m_{sem}))$, where $u_{sem}=m_{sem}+\max(\epsilon,3\times1.4826\times MAD_{sem})$ and $\epsilon>0$ is fixed before evaluation. Require a predeclared minimum narrative count. This needs a fixed/versioned embedding model, robust boilerplate handling, ID-level deduplication, enough narratives per month, and blinded human checks that coherence reflects a shared symptom rather than templates. Insufficient narratives, a missing bound, or unverifiable model/text availability means null/omitted—not zero. Build centroids only from text available by the cutoff; never fit/tune embeddings or text transformations on future periods. Until this proxy is shown reliable, it is an annotation—not a score term.

## Recommended initial testable version

Publish a month-system scorecard with:

- `trend_strength = min(R_count, R_share)` plus both component values and the underlying medians/bounds;
- immediate `candidate`/later `confirmed`/`ongoing`/`ended` episode state, with confirmation timestamp kept distinct from onset;
- severity counts/rates and denominators as **context only** when fields pass a data-quality audit; otherwise `unknown`;
- semantic coherence disabled (`not validated`).

Keep the existing eligibility gates; do not impute missing components as zero or create a numeric total from unavailable evidence. This is deliberately a small v0: no arbitrary weights, no probabilities, and no claim that the score establishes a defect.

## Future evaluation without leakage

Use rolling-origin, time-censored evaluation. At each month-end cutoff, construct counts/shares using only complaints received by that cutoff; construct baseline and any severity/coherence reference distributions only from periods strictly before the evaluated month; freeze episode bounds before candidate onset; and expose confirmation only after the third qualifying month. Fit any normalization, feature choices, thresholds, or future weights on earlier training windows, freeze them, then evaluate on later untouched months—never random-split complaints across time. Keep any lead-time or later-investigation analysis separate, and use official-action dates only when their historical publication/availability is verified. This corpus's incomplete publication timestamps support event-time replay at best, not a strict historical analyst-as-of replay. Report coverage, missingness, false-alarm duration, prospective stability, and performance on later periods; association or temporal precedence is not causation and does not make the score a recall predictor.
