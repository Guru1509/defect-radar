"""Small, reproducible semantic-clustering comparison on a sampled corpus."""

import argparse
import json
import re
import resource
import time
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
from sklearn.cluster import HDBSCAN, MiniBatchKMeans


DEFAULT_SEED = 42
DEFAULT_SAMPLE_SIZE = 5_000
EXPECTED_MODEL = "all-MiniLM-L6-v2"
EXPECTED_DIMENSION = 384

# Narrow clause-level matches for standard recall administration language.
# They remove notice/repair boilerplate only; symptoms and remaining sentence
# content are retained verbatim apart from whitespace normalization.
RECALL_ADMIN_PATTERNS = [
    re.compile(
        r"\bTHE CONTACT RECEIVED NOTIFICATION OF NHTSA CAMPAIGN NUMBER:?\s*"
        r"[A-Z0-9-]+(?:\s*\([^)]*\))?\.?", re.IGNORECASE
    ),
    re.compile(
        r"\bTHE PART TO DO (?:THE )?(?:RECALL )?REPAIR WAS UNAVAILABLE\.?",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bTHE MANUFACTURER EXCEEDED A REASONABLE AMOUNT OF TIME FOR THE REPAIR\.?",
        re.IGNORECASE,
    ),
]


def remove_recall_repair_boilerplate(text: str) -> tuple[str, int]:
    """Remove only exact, standardized recall notice/repair administration clauses."""
    removed = 0
    for pattern in RECALL_ADMIN_PATTERNS:
        text, count = pattern.subn(" ", text or "")
        removed += count
    text = " ".join(text.split())
    return text, removed


def silhouette_evaluation(matrix, labels) -> dict:
    """Compute exact Euclidean silhouette; ignore HDBSCAN noise label -1."""
    from sklearn.metrics import silhouette_score

    labels = np.asarray(labels)
    keep = labels != -1
    selected_labels = labels[keep]
    n_labels = len(np.unique(selected_labels))
    valid = len(selected_labels) > 1 and 2 <= n_labels < len(selected_labels)
    score = float(silhouette_score(np.asarray(matrix)[keep], selected_labels, metric="euclidean")) if valid else None
    return {
        "valid": valid,
        "score": round(score, 6) if score is not None else None,
        "eligible_count": int(keep.sum()),
        "coverage_pct": round(100 * keep.mean(), 2) if len(labels) else 0.0,
        "reason": None if valid else "silhouette requires at least 2 clusters and fewer clusters than assigned samples",
    }


def select_sample_indices(total_rows: int, sample_size: int, seed: int = DEFAULT_SEED) -> list[int]:
    """Choose unique row offsets reproducibly without replacement."""
    if sample_size <= 0 or total_rows < sample_size:
        raise ValueError("sample_size must be positive and no larger than total_rows")
    return np.random.default_rng(seed).choice(
        total_rows, size=sample_size, replace=False
    ).tolist()


def cluster_summary(labels) -> dict:
    """Return cluster counts and descending sizes; HDBSCAN noise is label -1."""
    labels = np.asarray(labels)
    counts = {int(label): int(count) for label, count in zip(*np.unique(labels, return_counts=True))}
    noise_count = counts.pop(-1, 0)
    ordered = dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))
    return {
        "cluster_count": len(ordered),
        "noise_count": noise_count,
        "noise_pct": round(100 * noise_count / len(labels), 2) if len(labels) else 0.0,
        "cluster_sizes": {str(label): count for label, count in ordered.items()},
    }


def load_sample(embeddings_dir: str, complaints_path: str, sample_size: int, seed: int):
    """Read only selected vectors into memory and join their narratives by ID.

    Parquet shards are streamed one at a time; the complete embedding matrix is
    never materialized. Complaints are scanned in batches and only sampled text
    is retained.
    """
    shard_paths = sorted(Path(embeddings_dir, "shards").glob("shard_*.parquet"))
    if not shard_paths:
        raise FileNotFoundError(f"No embedding shards in {embeddings_dir}")
    shard_rows = [pq.read_metadata(path).num_rows for path in shard_paths]
    total_rows = sum(shard_rows)
    offsets = select_sample_indices(total_rows, sample_size, seed)
    sample_ids, sample_vectors = [], []
    global_offset = 0
    for path, rows in zip(shard_paths, shard_rows):
        local_wanted = [i - global_offset for i in offsets if global_offset <= i < global_offset + rows]
        if local_wanted:
            table = pq.read_table(path, columns=["complaint_id", "embedding", "model_name", "dimension"])
            ids = table["complaint_id"].to_pylist()
            models = set(table["model_name"].to_pylist())
            dims = set(table["dimension"].to_pylist())
            if models != {EXPECTED_MODEL} or dims != {EXPECTED_DIMENSION}:
                raise ValueError(f"Unexpected model/dimension metadata in {path.name}")
            vectors = table["embedding"].to_pylist()
            sample_ids.extend(ids[i] for i in local_wanted)
            sample_vectors.extend(vectors[i] for i in local_wanted)
        global_offset += rows

    wanted_ids = set(sample_ids)
    narratives = {}
    parquet_file = pq.ParquetFile(complaints_path)
    for batch in parquet_file.iter_batches(
        columns=["complaint_id", "complaint_text_clean"], batch_size=10_000
    ):
        id_col = batch.column(0).to_pylist()
        text_col = batch.column(1).to_pylist()
        for complaint_id, narrative in zip(id_col, text_col):
            if complaint_id in wanted_ids:
                narratives[complaint_id] = narrative or ""
        if len(narratives) == sample_size:
            break
    if set(narratives) != wanted_ids:
        raise ValueError(f"Narrative join incomplete: {len(narratives)}/{sample_size} IDs")
    if any(not text.strip() for text in narratives.values()):
        raise ValueError("Sample unexpectedly contains empty complaint narratives")

    ordered_narratives = [narratives[complaint_id] for complaint_id in sample_ids]
    matrix = np.asarray(sample_vectors, dtype=np.float32)
    if matrix.shape != (sample_size, EXPECTED_DIMENSION):
        raise ValueError(f"Expected {(sample_size, EXPECTED_DIMENSION)} embeddings, got {matrix.shape}")
    return sample_ids, matrix, ordered_narratives


def _representatives(labels, matrix, ids, narratives, limit=3, per_cluster=2):
    labels = np.asarray(labels)
    counts = [(int(label), int((labels == label).sum())) for label in np.unique(labels) if label != -1]
    counts.sort(key=lambda pair: (-pair[1], pair[0]))
    examples = []
    for label, count in counts[:limit]:
        indices = np.flatnonzero(labels == label)
        center = matrix[indices].mean(axis=0)
        distances = np.linalg.norm(matrix[indices] - center, axis=1)
        for local_idx in np.argsort(distances)[:per_cluster]:
            idx = int(indices[local_idx])
            examples.append({
                "cluster": label,
                "cluster_size": count,
                "complaint_id": ids[idx],
                "narrative": narratives[idx],
            })
    return examples


def _fit_pair(matrix, ids, narratives, seed):
    outputs = {}
    labels_by_method = {}
    methods = [
        ("minibatch_kmeans", MiniBatchKMeans(
            n_clusters=20, random_state=seed, batch_size=256, n_init=3, max_iter=100
        ), {"k": 20, "batch_size": 256, "n_init": 3, "max_iter": 100, "random_state": seed}),
        ("hdbscan", HDBSCAN(
            min_cluster_size=30, min_samples=10, metric="euclidean", n_jobs=-1, copy=True
        ), {"min_cluster_size": 30, "min_samples": 10, "metric": "euclidean", "n_jobs": -1}),
    ]
    for name, estimator, parameters in methods:
        started = time.perf_counter()
        labels = estimator.fit_predict(matrix)
        fit_seconds = time.perf_counter() - started
        started = time.perf_counter()
        silhouette = silhouette_evaluation(matrix, labels)
        silhouette_seconds = time.perf_counter() - started
        labels_by_method[name] = np.asarray(labels, dtype=np.int32)
        outputs[name] = {
            **cluster_summary(labels),
            "parameters": parameters,
            "runtime_sec": round(fit_seconds, 3),
            "silhouette_runtime_sec": round(silhouette_seconds, 3),
            "silhouette": silhouette,
            "representatives": _representatives(labels, matrix, ids, narratives),
        }
    return outputs, labels_by_method


def run_sample_experiment(
    embeddings_dir="data/embeddings",
    complaints_path="data/processed/complaints.parquet",
    sample_size=DEFAULT_SAMPLE_SIZE,
    seed=DEFAULT_SEED,
    artifact_path="data/clustering/sample_seed42.npz",
):
    from src.embeddings.generator import ComplaintEmbeddingGenerator
    from src.embeddings.text_preparation import prepare_semantic_text

    artifact = Path(artifact_path)
    if artifact.exists():
        raise FileExistsError(f"Refusing to overwrite existing sample artifact: {artifact}")
    ids, baseline_matrix, narratives = load_sample(embeddings_dir, complaints_path, sample_size, seed)
    baseline_results, baseline_labels = _fit_pair(baseline_matrix, ids, narratives, seed)

    redacted = [remove_recall_repair_boilerplate(text) for text in narratives]
    revised_texts = [prepare_semantic_text(text) for text, _ in redacted]
    revised_matrix = ComplaintEmbeddingGenerator(model_name=EXPECTED_MODEL, device="cpu").encode_texts(
        revised_texts, batch_size=256, show_progress=False
    )
    revised_results, revised_labels = _fit_pair(revised_matrix, ids, narratives, seed)

    artifact = Path(artifact_path)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    if artifact.exists():
        raise FileExistsError(f"Refusing to overwrite existing sample artifact: {artifact}")
    np.savez_compressed(
        artifact,
        sample_ids=np.asarray(ids),
        baseline_vectors=baseline_matrix,
        baseline_kmeans_labels=baseline_labels["minibatch_kmeans"],
        baseline_hdbscan_labels=baseline_labels["hdbscan"],
        revised_vectors=revised_matrix,
        revised_kmeans_labels=revised_labels["minibatch_kmeans"],
        revised_hdbscan_labels=revised_labels["hdbscan"],
    )
    removed_clause_count = sum(count for _, count in redacted)
    results = {
        "sample_size": sample_size,
        "seed": seed,
        "dimension": EXPECTED_DIMENSION,
        "text_variation": {
            "description": "remove only exact NHTSA campaign-notice, unavailable-repair-part, and repair-delay clauses",
            "narratives_changed": sum(text != original for (text, _), original in zip(redacted, narratives)),
            "clauses_removed": removed_clause_count,
            "symptom_text_preserved_by_narrow_clause_substitution": True,
        },
        "baseline": baseline_results,
        "revised_text": revised_results,
        "sample_artifact": str(artifact),
    }
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    results["peak_rss_mb"] = round(rss / (1024 * 1024) if __import__("sys").platform == "darwin" else rss / 1024, 2)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-size", type=int, default=DEFAULT_SAMPLE_SIZE)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--embeddings-dir", default="data/embeddings")
    parser.add_argument("--complaints-path", default="data/processed/complaints.parquet")
    parser.add_argument("--artifact-path", default="data/clustering/sample_seed42.npz")
    parser.add_argument("--report-path", default="data/clustering/sample_seed42.json")
    args = parser.parse_args()
    report_path = Path(args.report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    result = run_sample_experiment(
        embeddings_dir=args.embeddings_dir,
        complaints_path=args.complaints_path,
        sample_size=args.sample_size,
        seed=args.seed,
        artifact_path=args.artifact_path,
    )
    with report_path.open("x") as f:
        json.dump(result, f, indent=2)
    print(json.dumps({
        "sample_size": result["sample_size"],
        "seed": result["seed"],
        "text_variation": result["text_variation"],
        "baseline": {k: {"clusters": v["cluster_count"], "coverage_pct": v["silhouette"]["coverage_pct"], "noise_pct": v["noise_pct"], "silhouette": v["silhouette"]["score"], "runtime_sec": v["runtime_sec"]} for k, v in result["baseline"].items()},
        "revised_text": {k: {"clusters": v["cluster_count"], "coverage_pct": v["silhouette"]["coverage_pct"], "noise_pct": v["noise_pct"], "silhouette": v["silhouette"]["score"], "runtime_sec": v["runtime_sec"]} for k, v in result["revised_text"].items()},
        "peak_rss_mb": result["peak_rss_mb"],
        "artifact": result["sample_artifact"],
        "report": str(report_path),
    }, indent=2))


if __name__ == "__main__":
    main()
