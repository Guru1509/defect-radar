"""
Master CLI script for generating complaint semantic embeddings in DEFECTRADAR Phase 3.

Features:
- Configurable --batch-size, --model, --device, --shard-size, and --limit
- Sharded incremental Parquet writes with safe resumption (skips already computed shards)
- Memory-safe for 8GB RAM (processes one shard at a time, frees memory)
- Tracks peak RSS memory, total execution duration, and throughput
- Validates ID alignment, vector norms, and semantic sanity checks
- Writes machine-readable metadata to data/embeddings/embedding_metadata.json

Usage:
    python -m src.embeddings.generate_embeddings --limit 10000        # Pilot test
    python -m src.embeddings.generate_embeddings                     # Full corpus
"""

import argparse
import json
import os
import resource
import sys
import time
from typing import Dict, List

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from src.embeddings.generator import (
    ComplaintEmbeddingGenerator,
    EMBEDDINGS_SCHEMA,
    validate_embeddings_parquet,
)
from src.embeddings.text_preparation import (
    analyze_text_corpus,
    prepare_semantic_text,
)


def get_peak_memory_mb() -> float:
    """Returns peak resident set size in megabytes."""
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return usage / (1024 * 1024)
    return usage / 1024


def parse_args():
    parser = argparse.ArgumentParser(
        description="DEFECTRADAR Phase 3: Semantic Complaint Embedding Generator"
    )
    parser.add_argument(
        "--complaints-path",
        type=str,
        default="data/processed/complaints.parquet",
        help="Path to canonical complaints Parquet file",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/embeddings",
        help="Directory to store embeddings and metadata",
    )
    parser.add_argument(
        "--output-path",
        type=str,
        default=None,
        help="Optional explicit single output Parquet file (used for pilot runs)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="all-MiniLM-L6-v2",
        help="Sentence Transformers model name",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=256,
        help="Inference batch size for model encoding",
    )
    parser.add_argument(
        "--shard-size",
        type=int,
        default=25000,
        help="Number of records per Parquet shard for safe resumption",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cpu",
        help="Compute device ('cpu' or 'mps')",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of complaints to process (for pilot runs)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    print("=" * 70)
    print("DEFECTRADAR — Phase 3: Semantic Embedding Generation")
    print(f"Complaints Source: {args.complaints_path}")
    print(f"Output Directory:  {args.output_dir}")
    print(f"Model:             {args.model} (dim=384)")
    print(f"Compute Device:    {args.device}")
    print(f"Batch Size:        {args.batch_size}")
    if args.limit:
        print(f"Execution Mode:    PILOT TEST (limit={args.limit:,} complaints)")
    else:
        print(f"Execution Mode:    FULL CORPUS (shard_size={args.shard_size:,})")
    print("=" * 70)

    start_time = time.time()
    os.makedirs(args.output_dir, exist_ok=True)
    shards_dir = os.path.join(args.output_dir, "shards")
    os.makedirs(shards_dir, exist_ok=True)

    # 1. Inspect input complaints table
    print("\n[1/5] Loading canonical complaints table metadata...")
    cmpl_meta = pq.read_metadata(args.complaints_path)
    total_in_file = cmpl_meta.num_rows
    print(f"  Total canonical complaints in database: {total_in_file:,}")

    # Read necessary columns
    print("  Reading complaint narratives and identifiers...")
    t_in = pq.read_table(
        args.complaints_path,
        columns=["complaint_id", "complaint_text_clean", "narrative_length"],
    )

    # 2. Text quality analysis
    print("\n[2/5] Performing text corpus quality analysis...")
    quality_stats = analyze_text_corpus(t_in)
    print(f"  Total records:                {quality_stats['total_records']:,}")
    print(f"  Empty narratives (excluded):  {quality_stats['empty_narratives']}")
    print(f"  Short (< 50 chars):           {quality_stats['short_narratives_under_50_chars']:,}")
    print(f"  Long (>= 1500 chars):         {quality_stats['very_long_narratives_over_1500_chars']:,}")
    print(f"  Median narrative length:      {quality_stats['median_length']} characters")
    print(f"  Mean narrative length:        {quality_stats['mean_length']} characters")

    # Filter out empty narratives (2 records with narrative_length == 0)
    valid_mask = pc.greater(t_in["narrative_length"], 0)
    t_valid = t_in.filter(valid_mask)
    if args.limit:
        t_valid = t_valid.slice(0, args.limit)

    total_to_embed = t_valid.num_rows
    excluded_count = total_in_file - (t_in.filter(valid_mask).num_rows)
    print(f"\n  Complaints eligible to embed: {total_to_embed:,} (Excluded: {excluded_count})")

    # 3. Initialize Model and Run Semantic Sanity Checks
    print("\n[3/5] Initializing Sentence Transformer and running sanity checks...")
    generator = ComplaintEmbeddingGenerator(
        model_name=args.model,
        device=args.device,
    )
    sanity_results = generator.run_semantic_sanity_checks()
    print("  Curated Defect Pair Cosine Similarities:")
    for pair_name, sim_score in sanity_results.items():
        print(f"    - {pair_name:28s}: {sim_score:.4f}")

    assert sanity_results["similar_stall"] > 0.45, "Sanity check failed for similar stall pair"
    assert sanity_results["similar_steering"] > 0.45, "Sanity check failed for similar steering pair"
    assert sanity_results["dissimilar_airbag_vs_radio"] < 0.35, "Sanity check failed for dissimilar pair"
    assert sanity_results["similar_stall"] > sanity_results["dissimilar_airbag_vs_radio"] + 0.20
    print("  Sanity check assertions PASSED.")

    # 4. Stream and Encode in Shards
    ids_all = t_valid["complaint_id"].to_pylist()
    texts_raw = t_valid["complaint_text_clean"].to_pylist()

    # Determine execution targets: if single output file specified (e.g. pilot), write single file
    if args.output_path:
        target_files = [(0, total_to_embed, args.output_path)]
    else:
        target_files = []
        shard_idx = 0
        for offset in range(0, total_to_embed, args.shard_size):
            chunk_end = min(offset + args.shard_size, total_to_embed)
            shard_path = os.path.join(shards_dir, f"shard_{shard_idx:03d}.parquet")
            target_files.append((offset, chunk_end, shard_path))
            shard_idx += 1

    print(f"\n[4/5] Encoding {total_to_embed:,} complaints into {len(target_files)} target partition(s)...")
    total_encoded = 0
    t_encoding_start = time.time()

    for start_idx, end_idx, fpath in target_files:
        shard_len = end_idx - start_idx
        # Check if shard already exists and is complete (resumption support)
        if os.path.exists(fpath):
            try:
                reuse_report = validate_embeddings_parquet(
                    fpath, expected_dim=generator.dimension,
                    expected_ids=ids_all[start_idx:end_idx], expected_model=args.model,
                )
                if reuse_report["all_checks_passed"]:
                    print(f"  Shard {os.path.basename(fpath)} verified; reusing.")
                    total_encoded += shard_len
                    continue
                print(f"  Shard {os.path.basename(fpath)} unverified; recomputing.")
            except Exception as exc:
                print(f"  Shard {os.path.basename(fpath)} unverified ({exc}); recomputing.")

        chunk_ids = ids_all[start_idx:end_idx]
        chunk_raw_texts = texts_raw[start_idx:end_idx]

        # Prepare semantic texts
        chunk_sem_texts = [prepare_semantic_text(t) for t in chunk_raw_texts]

        # Encode shard in mini-batches
        chunk_vecs = generator.encode_texts(
            chunk_sem_texts,
            batch_size=args.batch_size,
            show_progress=False,
        )

        # Write shard Parquet
        chunk_table = pa.Table.from_arrays(
            [
                pa.array(chunk_ids, type=pa.string()),
                pa.array(list(chunk_vecs), type=pa.list_(pa.float32())),
                pa.array([args.model] * len(chunk_ids), type=pa.string()),
                pa.array([384] * len(chunk_ids), type=pa.int32()),
            ],
            schema=EMBEDDINGS_SCHEMA,
        )
        pq.write_table(chunk_table, fpath, compression="zstd")

        total_encoded += len(chunk_ids)
        pct = (total_encoded / total_to_embed) * 100
        elapsed_sec = time.time() - t_encoding_start
        rate = total_encoded / elapsed_sec if elapsed_sec > 0 else 0
        rss_mb = get_peak_memory_mb()
        print(
            f"  [{total_encoded:,}/{total_to_embed:,}] {pct:5.1f}% committed "
            f"({rate:5.1f} complaints/s, Shard: {os.path.basename(fpath)}, Peak RSS: {rss_mb:.1f} MB)"
        )

    total_time = time.time() - start_time

    print("\n[5/5] Validating all embedding outputs...")
    shard_reports = []
    all_output_ids = []
    for start_idx, end_idx, fpath in target_files:
        report = validate_embeddings_parquet(
            fpath, expected_dim=generator.dimension,
            expected_ids=ids_all[start_idx:end_idx], expected_model=args.model,
        )
        shard_reports.append(report)
        all_output_ids.extend(pq.read_table(fpath, columns=["complaint_id"])["complaint_id"].to_pylist())
    expected_all = ids_all
    missing_ids = set(expected_all) - set(all_output_ids)
    duplicate_ids = len(all_output_ids) - len(set(all_output_ids))
    all_shards_passed = (all(r["all_checks_passed"] for r in shard_reports)
                         and not missing_ids and duplicate_ids == 0)
    val_report = {
        "all_checks_passed": all_shards_passed,
        "shard_count": len(shard_reports),
        "shards": shard_reports,
        "missing_ids": len(missing_ids),
        "duplicate_ids": duplicate_ids,
    }
    print(f"  Shards validated:            {len(shard_reports)}")
    print(f"  Missing complaint IDs:       {len(missing_ids)}")
    print(f"  Duplicate complaint IDs:     {duplicate_ids}")
    print(f"  Validation status:           {'PASSED' if all_shards_passed else 'FAILED'}")
    if not all_shards_passed:
        raise RuntimeError("Embedding shard validation failed; see report above")

    # Compute total size of all output files
    total_size_bytes = sum(os.path.getsize(f[2]) for f in target_files if os.path.exists(f[2]))
    file_size_mb = total_size_bytes / (1024 * 1024)

    metadata_path = os.path.join(args.output_dir, "embedding_metadata.json")
    metadata = {
        "model_name": args.model,
        "embedding_dimension": 384,
        "dtype": "float32",
        "total_complaints_in_source": total_in_file,
        "total_complaints_embedded": total_encoded,
        "total_complaints_excluded": excluded_count,
        "exclusion_reason": "narrative_length == 0 (no symptom text present)",
        "batch_size": args.batch_size,
        "shard_size": args.shard_size,
        "device_used": args.device,
        "total_processing_time_sec": round(total_time, 2),
        "embedding_throughput_per_sec": round(total_encoded / total_time, 2) if total_time > 0 else 0,
        "peak_memory_mb": round(get_peak_memory_mb(), 2),
        "output_shards_count": len(target_files),
        "output_storage_mb": round(file_size_mb, 2),
        "sanity_check_similarities": sanity_results,
        "validation_sample": val_report,
    }

    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print("\n" + "=" * 70)
    print("PHASE 3 EMBEDDING PIPELINE COMPLETE!")
    print(f"Embeddings committed: {total_encoded:,} records in {len(target_files)} partition(s)")
    print(f"Total storage:        {file_size_mb:.2f} MB")
    print(f"Metadata committed:   {metadata_path}")
    print(f"Total pipeline time:  {total_time:.2f} seconds")
    print(f"Peak resident RAM:    {metadata['peak_memory_mb']} MB")
    print("=" * 70)


if __name__ == "__main__":
    main()
