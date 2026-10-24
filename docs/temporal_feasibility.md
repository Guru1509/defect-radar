# DEFECTRADAR — Phase 5A: Temporal Data Feasibility

**Audit date:** 2026-10-23. Read-only column summaries of the four canonical Parquet tables; no detector, clustering, or dataset changes were made. Documentation reviewed: `data_model.md`, `canonical_dataset.md`, and `clustering.md`.

## Available fields and measured coverage

Counts below are rows in the respective Parquet table. Missingness counts treat Arrow nulls (and, for strings, blank values) as missing. Date ranges are over non-null values.

| Table | Relevant fields and observed availability |
|---|---|
| `complaints.parquet` (651,262) | `received_date`: 0 missing; 2015-01-01–2024-12-31. `failure_date`: 148 missing (0.0227%); 1980-03-16–2024-12-31. `date_added`: 0 missing; 1997-06-27–2024-12-31. `make_raw`/`make_normalized` and `model_raw`/`model_normalized`: 14 missing each (0.0021%). `model_year`: 3,841 missing (0.5898%); 1970–2025. `crash`, `fire`, `injuries`, `deaths`, `medical_attention`, `vehicle_towed`: 0 nulls; injury/death counts span 0–99. |
| `complaint_components.parquet` (908,693) | `component_record_id` and `complaint_id`: 0 nulls. `component_raw`, `component_normalized`, `component_system`: 7 missing each (0.0008%); 51 distinct nonmissing systems. `component_subsystem`: 814,430 missing (89.6265%), so the top-level `component_system` is the more complete initial category. |
| `recalls.parquet` (15,286) | `campaign_number` and `recall_date`: 0 missing; `recall_date` spans 2010-01-01–2026-09-30. `owner_notification_date`: 374 missing (2.4467%); non-null range 1980-12-31–2027-08-16. One notification date is later than the audit date and should be flagged, not treated as an observed event. `influenced_by`: 1 missing. |
| `investigations.parquet` (5,349) | `investigation_id` and `action_type`: 0 missing. `opened_date`: 108 missing (2.0191%); 1972-03-10–2026-09-21. `closed_date`: 223 missing (4.1690%); 1972-05-30–2026-09-24 (null may mean still open). `recall_campaign_number`: 3,799 missing (71.0226%); 1,550 non-null. |

The measured complaint and component keys had no nulls. The documentation specifies `complaints.complaint_id` → `complaint_components.complaint_id` as one-to-many. Complaint severity fields are available, but these self-reported flags/counts are not exposure-adjusted measures of defect risk.

## Temporal unit and initial baseline

Start with **monthly** aggregation by `component_system`: the complaint history has 120 calendar months and this category is nearly complete; weekly or make/model/year slices are more likely to be sparse. Keep both monthly complaint counts and each system's share of all complaints, so changes in overall reporting volume are visible. A transparent initial flag can compare each system-month with its trailing historical baseline, adjusting for month-of-year, and use a one-sided predictive bound (or a robust median/MAD threshold), a minimum-volume rule, and persistence across consecutive months. Fit/calibrate the baseline only on earlier months. This is an exploratory complaint-volume signal, not a vehicle failure rate: no fleet/exposure denominator is present. Pool or suppress sparse make/model/year strata rather than treating their spikes as reliable.

## Leakage-safe historical evaluation

At each simulated month-end cutoff, construct features only from complaints received by that cutoff and from fields demonstrably available then. Estimate category mappings, scaling, dimensionality reduction, and baselines using only that historical window; never use later complaint text, labels, or official-action summaries as features. Evaluate future milestones separately, using investigation `opened_date` and recall `recall_date` only when they occur after the cutoff and within a prespecified follow-up horizon.

`received_date` is the documented primary complaint event time. `date_added` is complete, but the data model describes it as an administrative docket/file timestamp, not a verified public-availability timestamp; the documentation reports 213 records where it follows `received_date` and two where it precedes it. The static canonical table has no row-version/publication history. Thus a strict historical “known as of date” replay cannot be guaranteed from these Parquet files alone. Prefer dated source snapshots or an explicitly conservative availability lag, and document the limitation. Fields such as component coding and severity are also not versioned in this snapshot.

Outcome coverage is finite: complaints end in 2024, while investigation and recall dates extend through September 2026. Later cutoffs therefore have shorter observable follow-up; right-censor horizons that extend past the available outcome data. `owner_notification_date` should not replace `recall_date` as the recall milestone, and its single future-dated value needs data-quality handling.

## Outcome linkage and interpretation

- **Complaint to component:** join `complaints.complaint_id` to `complaint_components.complaint_id`; one complaint may have multiple component rows. Aggregate to one complaint/category/month or explicitly account for multi-component duplication.
- **Official investigation to recall:** join `investigations.recall_campaign_number` to `recalls.campaign_number` where the campaign key matches. Of 1,550 non-null investigation campaign values, 308 matched exactly to the supplied recall table; 375 matched by a first-six-character prefix, which is not an exact foreign-key join. The recall table begins in 2010, while investigations include older dates; unmatched values must not be silently discarded or prefix-joined as if unique.
- **Complaint signal to official action:** there is no direct complaint-ID-to-investigation or complaint-ID-to-recall key in these four tables. For candidate association, use `investigation_vehicles` / `recall_vehicles` (documented child tables) to compare normalized make, model, model year, and component against complaint cohorts, and retain the official milestone dates and action/campaign IDs. Component vocabularies and vehicle variants can differ, so this is an approximate cohort linkage requiring explicit matching rules and ambiguity reporting.

A signal preceding an investigation opening or recall filing establishes temporal ordering/association only. It does not show that the complaints caused, or were individually confirmed by, the official action. Recall/investigation linkage is incomplete in the available tables, and consumer complaints are not a complete or exposure-adjusted population.

## Feasibility conclusion

Monthly component-system monitoring is feasible for an initial sample-bounded temporal study: the complaint intake date and top-level component category are highly complete, and severity and vehicle metadata are present. Important constraints are sparse model-year/child-subsystem fields, incomplete investigation-to-recall links, future-dated notification data, lack of historical row versions, and limited outcome follow-up. Resolve the as-of availability policy and outcome-link matching policy before any detector or historical evaluation is built.