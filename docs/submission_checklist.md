# Submission readiness checklist

## Reproducibility
- [ ] Submit the project with its documented Python environment/dependency requirements and these root-relative paths intact.
- [ ] Confirm the canonical processed tables and the dashboard's saved trend, scorecard, alert, and metrics artifacts are present.
- [ ] Keep the pipeline description explicit: stages are separate, there is no one-command orchestrator, and embeddings do not feed temporal scoring or evaluation.
- [ ] Do not regenerate expensive stages merely for the presentation; document any environment-specific setup differences.

## Data integrity
- [ ] Preserve canonical datasets, embedding shards, clustering outputs, frozen evaluation settings, and saved research results.
- [ ] Obtain the six raw source archives locally under `data/raw/` when required; follow [`data_audit.md`](data_audit.md) for filenames and source provenance, and [`canonical_dataset.md`](canonical_dataset.md) for canonical schemas and build details.
- [ ] Do not include credentials or secrets. Check institutional rules for redistributing source data.

## Tests and demo
- [ ] After locally generating the canonical Parquet tables and four dashboard outputs as described in `docs/local_dashboard.md`, install `requirements.txt` and run `python -m pytest -v`; data-dependent tests need those excluded files.
- [ ] Start the dashboard using the command in `docs/local_dashboard.md` only after all four outputs exist, then confirm all four tabs load.
- [ ] Rehearse the saved-output sequence: component monthly trend, a selected system-month alert, then recorded-action comparison.
- [ ] Verify the displayed interpretation distinguishes heuristic signals and recorded action dates from public warnings.

## Limitations and reporting
- [ ] State that clustering was sample-only and did not justify full-corpus use.
- [ ] State that raw complaint counts outperformed the scorecard in the frozen comparison's four fixed-budget endpoint/horizon comparisons.
- [ ] State that recorded investigation/recall dates are not verified public-warning dates and historical public-availability timestamps are incomplete.
- [ ] State that the score is not a recall probability, proof of a defect, causal evidence, or validated predictor.
- [ ] Complete institution-specific formatting, citation, authorship, and submission requirements manually; this repository checklist cannot verify them.
