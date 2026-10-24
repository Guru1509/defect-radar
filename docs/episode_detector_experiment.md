# DEFECTRADAR — Phase 5E: Sample-Level Episode Detector Experiment

**Status:** Separate experimental module; the Phase 5B detector and derived monthly output were not modified. Analysis uses the saved 6,240 month-system rows (2015-01–2024-12). Episodes are statistical complaint-volume states only—not confirmed defects, causal findings, or recall predictions.

## Rules implemented

`src/temporal/episode_detector.py` annotates monthly rows; it does not replace or alter `monthly_baseline.py`.

- **Eligible month:** the existing baseline has a non-null `is_anomaly`, at least 3 prior seasonal observations, at least 30 historical complaints, current count at least 10, and both current bounds available. Crossings use strict `count > count bound AND share > share bound`.
- **Candidate begins:** an eligible month is flagged by the existing detector. At that point, freeze count/share upper bounds for all calendar months from up to the five most recent observations of that same month that are strictly earlier than the candidate month. Require at least 3 observations and 30 historical complaints for a frozen seasonal bound; otherwise that month has no frozen bound. Bounds use the existing median/MAD formula and margins.
- **Confirmation:** the candidate month and the next two adjacent eligible calendar months must all cross their frozen seasonal bounds. The onset is dated to the first crossing; status changes from `candidate` to `confirmed` on the third crossing, then to `ongoing` on later months. Later months do not count as new onsets.
- **Candidate failure / gaps:** a non-crossing, ineligible month, or missing calendar month before confirmation abandons the candidate. A crossing can start a new candidate using history available before that new candidate. Gaps never count as crossing months.
- **Termination:** after confirmation, three adjacent eligible months that do not cross *both* frozen bounds end the episode; the third such month is marked `ended`. Ineligible or missing months reset the end streak but do not count as evidence of return to baseline. At the data endpoint, an episode with post-confirmation months is last labeled `ongoing`; if the endpoint itself is the third confirmation month, it remains labeled `confirmed` with no end date and is still open/right-censored.

The frozen seasonal reference is calculated sequentially from earlier rows only; the evaluated month and future observations are excluded. The test suite also checks that appending extreme future values does not change earlier episode states or frozen bounds.

## Results on the saved series

- Existing detector: **296** monthly flags.
- Episode experiment: **15 confirmed episodes**—**9 ended**, **6 ongoing** at 2024-12. Their recorded spans total **340 system-months**; duration range is **6–56 months**, median **10 months**.
- **214** of the existing flags fall within confirmed episodes. The remaining **82** flags occurred in **71 unconfirmed candidate attempts** (some lasted two months); none met the three-consecutive-month confirmation rule.
- One confirmed episode represents one onset rather than repeating each monthly flag. Confirmation arrives at the end of the third crossing month: **two months after the first crossing**. A one- or two-month spike remains unconfirmed.

| Component system | Existing flagged run referenced | Experimental onset → confirmation | Episode at 2024-12 | Span months | Existing flags in episode |
|---|---|---|---|---:|---:|
| FORWARD COLLISION AVOIDANCE | 30 months, 2021-05–2023-10 | 2021-05 → 2021-07 | Ongoing | 44 | 30 |
| BACK OVER PREVENTION | 24 months, 2021-10–2023-09 | 2021-10 → 2021-12 | Ongoing | 39 | 25 |
| LANE DEPARTURE | 24 months, 2021-11–2023-10 | 2021-11 → 2022-01 | Ongoing | 38 | 26 |
| ENGINE AND ENGINE COOLING | Longest existing run: 16 months, 2022-02–2023-05 | 2021-09 → 2021-11 | Ongoing | 40 | 30 |

For forward collision avoidance, the episode begins with the existing run and remains open through the data endpoint under frozen pre-onset bounds—even though the rolling-baseline flags stop after October 2023. Back-over prevention and lane departure likewise remain experimental ongoing episodes beyond their last long runs of monthly flags. Engine/engine cooling starts earlier than its longest existing run and bridges interrupted monthly flags because the frozen-bound termination rule was not met. These results show how an episode view can distinguish an onset from continued elevated levels, but the long open spans also show the sensitivity of conclusions to the frozen bounds and three-month termination rule.

The experiment is descriptive. The monthly data lacks fleet-exposure denominators and complete historical publication timestamps; broad component categories can mix report themes. Neither an episode nor its timing establishes a defect, its cause, or a relationship to an official action.

## Phase 5F robustness audit

The targeted checks found no code correction necessary. Candidate runs reset on missing and ineligible months; active episodes do not treat either as a below-bound month, and the end streak restarts after the gap. Boundary tests also confirmed that equality with a bound is not a crossing (the comparison is strict), and three adjacent eligible non-crossings are required to end an episode.

Re-running the experiment on the saved output reproduced **15 confirmed episodes**, **9 ended**, **6 open**, and the **214/82** split of the 296 existing flags. For every confirmed episode, the stored episode bounds matched the same-calendar bounds recomputed from observations strictly before that candidate's onset. The future-value invariance test also passed. At the actual 2024-12 endpoint, all six open episodes have later `ongoing` rows; the added boundary test clarifies that an episode ending exactly on its confirmation month remains `confirmed` and open, not `ended`.

The two-month confirmation delay is **not appropriate as the sole early-warning signal**: a rapid safety concern should not wait for two more monthly observations. It is reasonable as a persistence-confirmation layer if the first-month `candidate`/existing flag remains visible for prompt review and is not suppressed. This trades confirmation speed for avoiding promotion of isolated or two-month crossings; it does not establish that any candidate is true or false.

## Focused tests

The original five tests were supplemented with boundary tests for an ineligible month during candidacy, ineligible and missing months during termination, exact-threshold equality, and an endpoint on the confirmation month. Focused run: **10 passed**. No full test suite was run.
