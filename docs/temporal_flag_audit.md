# DEFECTRADAR — Phase 5C: Temporal Flag Quality Audit

**Scope:** Read-only audit of the 296 `is_anomaly=true` rows in `data/processed/monthly_component_trends.parquet`, the baseline implementation, and feasibility/method docs. Eight records were reviewed locally as a qualitative check; individual complaint narratives and record identifiers are not reproduced here. No detector or canonical data was changed.

NHTSA supplies the underlying complaint records; the flag counts, comparisons, and interpretations below are project-authored aggregate analysis. Field and dataset provenance is listed in [the data audit](data_audit.md).

## Flag distribution

The 296 flags occurred across **26 systems** and **2018–2024**. Years with the most flags: **2022 (75), 2023 (53), 2021 (47), 2019 (41), 2018 (28), 2020 (27), 2024 (25)**. There were no flags in 2015–2017, when the baseline lacked sufficient prior seasons.

Most-flagged systems:

| Component system | Flags |
|---|---:|
| SERVICE BRAKES, HYDRAULIC | 33 |
| ENGINE AND ENGINE COOLING | 32 |
| FORWARD COLLISION AVOIDANCE | 32 |
| FUEL SYSTEM, GASOLINE | 31 |
| LANE DEPARTURE | 26 |
| BACK OVER PREVENTION | 25 |
| VISIBILITY/WIPER | 17 |
| VISIBILITY | 14 |

Other flagged systems: ELECTRONIC STABILITY CONTROL (ESC) 11; ENGINE 10; STEERING 10; EXTERIOR LIGHTING 7; TIRES 7; POWER TRAIN 6; LATCHES/LOCKS/LINKAGES 6; WHEELS 4; SERVICE BRAKES 4; EQUIPMENT 4; SEATS 3; UNKNOWN OR OTHER 3; SUSPENSION 3; FUEL SYSTEM, DIESEL 3; VEHICLE SPEED CONTROL 2; FUEL/PROPULSION SYSTEM 1; ELECTRICAL SYSTEM 1; SERVICE BRAKES, AIR 1.

Highest system-year counts were BACK OVER PREVENTION, FORWARD COLLISION AVOIDANCE, and LANE DEPARTURE (12 each in 2022), followed by SERVICE BRAKES, HYDRAULIC and ENGINE AND ENGINE COOLING (11 each in 2022), and LANE DEPARTURE (11 in 2023).

The busiest individual months were **2022-09** and **2022-12** (8 flagged systems each). **2019-05, 2021-11, 2022-02, 2022-08, 2022-11, and 2023-02** had 7 each.

## Persistence and baseline comparisons

Flags were more often persistent than isolated: **36 consecutive-month runs** (same system) contained **227 of 296 flags**; the other 69 flags were isolated. The longest run was **FORWARD COLLISION AVOIDANCE, May 2021–October 2023 (30 months)**. BACK OVER PREVENTION and LANE DEPARTURE also had runs of 24 months. These patterns look like sustained level/category changes, not only short-lived spikes.

Selected high-count flags (count/share thresholds both had to be crossed):

| Month / system | Current count (share) | Historical count median → upper bound | Historical share median → upper bound |
|---|---:|---:|---:|
| 2019-07 POWER TRAIN | 1,507 (20.206%) | 763.5 → 850.232 | 11.276% → 12.909% |
| 2019-07 ENGINE | 1,454 (19.496%) | 846.5 → 926.560 | 13.425% → 18.930% |
| 2020-07 ELECTRICAL SYSTEM | 1,055 (19.161%) | 884 → 1,039.673 | 15.286% → 15.733% |
| 2022-02 FORWARD COLLISION AVOIDANCE | 1,059 (21.494%) | 4 → 12.896 | 0.076% → 0.260% |

For these rows, history comprised 3–5 prior same-calendar-month observations. The ADAS example is a particularly large category-level jump from a low baseline; it persists over many later months, which is consistent with a taxonomy/reporting adoption shift as well as with increased reports, and cannot be interpreted as a single new defect.

## Aggregate qualitative check and artifacts

Eight records were selected reproducibly without retaining their identifiers in this document: for 2019-07, the two lowest-sorted IDs in the ENGINE/POWER TRAIN overlap and one lowest-sorted ID unique to each system; for 2020-07 ELECTRICAL SYSTEM and 2022-02 FORWARD COLLISION AVOIDANCE, two IDs per flag were selected from sorted eligible IDs using `random.Random(2526)`.

Across the eight reviewed records, themes were heterogeneous within broad component-system categories. The small qualitative sample does not establish one narrow defect theme or show that a statistical flag preceded official attention. Individual complaint wording and record-level dates are intentionally omitted.

The July 2019 ENGINE and POWER TRAIN flags share **238 complaints**; 1,454 and 1,507 unique complaints respectively were assigned to those systems that month. This is expected multi-label counting, not duplicate rows within a system. Across all 120 months, summed system shares ranged from **126.24% to 147.60%** because one complaint may name multiple systems. No `__MISSING__` category flags occurred. Every flag met the implementation’s minimums: current count at least **19**, at least **3** prior seasons, and at least **30** historical complaints; no low-volume gate was bypassed.

## Historical-only verification and assessment

The implementation selects only the same calendar month in years `t-1` through `t-5`, additionally requiring each prior month to precede the evaluated month. I independently recomputed history counts, medians, MADs, and thresholds for all **6,240** month-system rows from the saved monthly output; all matched, with no evaluated-month or future-month contribution.

**Assessment:** The baseline is behaving plausibly as a conservative screen for unusual monthly count-and-share changes, and its eligibility gates prevent missing/low-volume flags. However, long consecutive runs and broad/mixed narratives show it currently flags persistent category-level shifts as well as isolated increases. Its flags are not validated defect detections, and none should be presented as predicting a recall. Static data also lacks complete historical publication timestamps, so as-of availability cannot be guaranteed; temporal precedence or association is not causation.

**Next improvement:** Before adding any downstream score or predictor, distinguish persistent level shifts from short-term spikes (for example, report onset/change episodes separately from repeated monthly crossings) and review whether category/taxonomy or reporting-volume changes explain the long ADAS runs. More granular subsystem or narrative-theme validation may be needed; do not interpret these flags as recall predictions.