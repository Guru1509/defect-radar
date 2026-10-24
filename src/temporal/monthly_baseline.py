"""Monthly, leakage-aware complaint trend baseline utilities."""

from collections import Counter, defaultdict
from datetime import date, datetime


MISSING_CATEGORY = "__MISSING__"


def _month_start(value):
    if isinstance(value, datetime):
        value = value.date()
    if not isinstance(value, date):
        raise ValueError(f"Expected a date for received_date, got {value!r}")
    return date(value.year, value.month, 1)


def aggregate_monthly_counts(complaint_rows, component_rows):
    """Aggregate unique complaint/system pairs by received month.

    Inputs are iterables of ``(complaint_id, received_date)`` and
    ``(complaint_id, component_system)``. A complaint mapped to multiple distinct
    systems counts once in each; repeated rows for the same system count once.
    Complaints without any nonblank system use ``MISSING_CATEGORY``.
    """
    complaint_month = {}
    monthly_totals = Counter()
    for complaint_id, received_date in complaint_rows:
        if complaint_id is None or not str(complaint_id).strip():
            raise ValueError("complaint_id must be nonempty")
        if complaint_id in complaint_month:
            raise ValueError(f"Duplicate complaint_id: {complaint_id}")
        month = _month_start(received_date)
        complaint_month[complaint_id] = month
        monthly_totals[month] += 1
    if not complaint_month:
        raise ValueError("No complaint rows supplied")

    systems_by_complaint = defaultdict(set)
    systems = set()
    for complaint_id, component_system in component_rows:
        if complaint_id is None or complaint_id not in complaint_month:
            raise ValueError(f"Orphan or null component complaint_id: {complaint_id!r}")
        system = str(component_system).strip() if component_system is not None else ""
        if system:
            systems_by_complaint[complaint_id].add(system)
            systems.add(system)
    if MISSING_CATEGORY in systems:
        raise ValueError(f"Reserved category value is present: {MISSING_CATEGORY}")

    counts = Counter()
    for complaint_id, month in complaint_month.items():
        observed_systems = systems_by_complaint.get(complaint_id)
        if observed_systems:
            for system in observed_systems:
                counts[(month, system)] += 1
        else:
            counts[(month, MISSING_CATEGORY)] += 1

    first_month = min(complaint_month.values())
    last_month = max(complaint_month.values())
    months = []
    current = first_month
    while current <= last_month:
        months.append(current)
        current = date(current.year + (current.month == 12), current.month % 12 + 1, 1)

    categories = sorted(systems | {MISSING_CATEGORY})
    rows = []
    for month in months:
        total = monthly_totals[month]
        for system in categories:
            count = counts[(month, system)]
            rows.append({
                "month": month,
                "component_system": system,
                "complaint_count": count,
                "total_monthly_complaints": total,
                "complaint_share_pct": round(100.0 * count / total, 6) if total else 0.0,
            })
    return rows


DEFAULT_BASELINE_CONFIG = {
    "lookback_years": 5,
    "min_history_months": 3,
    "min_baseline_total": 30,
    "min_current_count": 10,
    "mad_multiplier": 3.0,
    "min_count_margin": 3.0,
    "min_share_margin_pct": 0.01,
}


def _median_mad(values):
    from statistics import median

    center = float(median(values))
    deviation = float(median([abs(value - center) for value in values]))
    return center, deviation


def evaluate_historical_baseline(
    monthly_rows,
    lookback_years=5,
    min_history_months=3,
    min_baseline_total=30,
    min_current_count=10,
    mad_multiplier=3.0,
    min_count_margin=3.0,
    min_share_margin_pct=0.01,
):
    """Score each row against prior same-calendar-month observations only.

    A signal requires both count and complaint-share to exceed their historical
    robust upper bounds. Ineligible rows have ``is_anomaly=None`` and an explicit
    status rather than being represented as a negative or positive signal.
    """
    if lookback_years < 1 or min_history_months < 1:
        raise ValueError("lookback_years and min_history_months must be positive")
    if min_baseline_total < 0 or min_current_count < 0:
        raise ValueError("volume thresholds cannot be negative")

    ordered = sorted(monthly_rows, key=lambda row: (row["month"], row["component_system"]))
    by_key = {}
    for row in ordered:
        month = _month_start(row["month"])
        if month != row["month"]:
            raise ValueError("Monthly rows must use first-of-month dates")
        system = row["component_system"]
        if not system:
            raise ValueError("component_system must be nonempty; use the missing bucket")
        key = (month, system)
        if key in by_key:
            raise ValueError(f"Duplicate monthly system row: {key}")
        count = int(row["complaint_count"])
        total = int(row["total_monthly_complaints"])
        share = float(row["complaint_share_pct"])
        if count < 0 or total <= 0 or count > total or not 0.0 <= share <= 100.0:
            raise ValueError(f"Invalid monthly values for {key}")
        by_key[key] = row

    evaluated = []
    for row in ordered:
        month = row["month"]
        system = row["component_system"]
        history = []
        for years_back in range(1, lookback_years + 1):
            year = month.year - years_back
            if year >= 1:
                prior = by_key.get((date(year, month.month, 1), system))
                if prior is not None and prior["month"] < month:
                    history.append(prior)
        history_counts = [int(item["complaint_count"]) for item in history]
        history_shares = [float(item["complaint_share_pct"]) for item in history]
        history_total = sum(history_counts)
        count_median = count_mad = share_median = share_mad = None
        count_upper = share_upper = None
        if history:
            count_median, count_mad = _median_mad(history_counts)
            share_median, share_mad = _median_mad(history_shares)
            count_upper = count_median + max(min_count_margin, mad_multiplier * 1.4826 * count_mad)
            share_upper = share_median + max(min_share_margin_pct, mad_multiplier * 1.4826 * share_mad)

        count_spike = share_spike = is_anomaly = None
        current_count = int(row["complaint_count"])
        if len(history) < min_history_months:
            status = "insufficient_history"
        elif history_total < min_baseline_total:
            status = "low_baseline_volume"
        elif current_count < min_current_count:
            status = "low_current_volume"
        else:
            count_spike = current_count > count_upper
            share_spike = float(row["complaint_share_pct"]) > share_upper
            is_anomaly = count_spike and share_spike
            if is_anomaly:
                status = "above_both_thresholds"
            elif count_spike:
                status = "count_only"
            elif share_spike:
                status = "share_only"
            else:
                status = "within_threshold"

        result = dict(row)
        result.update({
            "history_n": len(history),
            "history_total_count": history_total,
            "baseline_count_median": count_median,
            "baseline_count_mad": count_mad,
            "count_upper_threshold": count_upper,
            "baseline_share_median_pct": share_median,
            "baseline_share_mad_pct": share_mad,
            "share_upper_threshold_pct": share_upper,
            "count_spike": count_spike,
            "share_spike": share_spike,
            "is_anomaly": is_anomaly,
            "signal_status": status,
        })
        evaluated.append(result)
    return evaluated


def _complaint_rows(path, batch_size):
    import pyarrow.parquet as pq

    parquet = pq.ParquetFile(path)
    for batch in parquet.iter_batches(columns=["complaint_id", "received_date"], batch_size=batch_size):
        yield from zip(batch.column(0).to_pylist(), batch.column(1).to_pylist())


def _component_rows(path, batch_size):
    import pyarrow.parquet as pq

    parquet = pq.ParquetFile(path)
    for batch in parquet.iter_batches(columns=["complaint_id", "component_system"], batch_size=batch_size):
        yield from zip(batch.column(0).to_pylist(), batch.column(1).to_pylist())


def run_monthly_baseline(
    complaints_path="data/processed/complaints.parquet",
    components_path="data/processed/complaint_components.parquet",
    output_path="data/processed/monthly_component_trends.parquet",
    batch_size=50_000,
):
    """Stream canonical source columns and write a derived monthly Parquet file."""
    import json
    import resource
    import sys
    import time

    import pyarrow as pa
    import pyarrow.parquet as pq

    output = __import__("pathlib").Path(output_path)
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing output: {output}")
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")

    started = time.perf_counter()
    monthly = aggregate_monthly_counts(
        _complaint_rows(complaints_path, batch_size),
        _component_rows(components_path, batch_size),
    )
    evaluated = evaluate_historical_baseline(monthly, **DEFAULT_BASELINE_CONFIG)
    output.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(evaluated)
    metadata = dict(table.schema.metadata or {})
    metadata[b"defectradar.baseline"] = json.dumps({
        "method": "prior_same_calendar_month_median_plus_scaled_MAD",
        "config": DEFAULT_BASELINE_CONFIG,
        "signals_require_count_and_share_exceedance": True,
        "missing_category": MISSING_CATEGORY,
        "source_complaints": str(complaints_path),
        "source_components": str(components_path),
    }, sort_keys=True).encode("utf-8")
    table = table.replace_schema_metadata(metadata)
    pq.write_table(table, output, compression="snappy")

    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_mb = round(rss / (1024 * 1024) if sys.platform == "darwin" else rss / 1024, 2)
    signals = sum(row["is_anomaly"] is True for row in evaluated)
    eligible = sum(row["is_anomaly"] is not None for row in evaluated)
    return {
        "output_path": str(output),
        "months": len({row["month"] for row in evaluated}),
        "systems_including_missing": len({row["component_system"] for row in evaluated}),
        "monthly_rows": len(evaluated),
        "eligible_rows": eligible,
        "signal_rows": signals,
        "runtime_sec": round(time.perf_counter() - started, 3),
        "peak_rss_mb": peak_mb,
    }


def main():
    import argparse
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--complaints-path", default="data/processed/complaints.parquet")
    parser.add_argument("--components-path", default="data/processed/complaint_components.parquet")
    parser.add_argument("--output-path", default="data/processed/monthly_component_trends.parquet")
    parser.add_argument("--batch-size", type=int, default=50_000)
    args = parser.parse_args()
    print(json.dumps(run_monthly_baseline(
        complaints_path=args.complaints_path,
        components_path=args.components_path,
        output_path=args.output_path,
        batch_size=args.batch_size,
    ), indent=2))


if __name__ == "__main__":
    main()
