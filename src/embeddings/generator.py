"""
Core Embedding Generator module for DEFECTRADAR Phase 3.
Encapsulates Sentence Transformers encoding, batch chunking, device handling,
incremental Parquet serialization, and validation sanity checks.
"""

import os
import time
from typing import Dict, List, Optional, Tuple

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from sentence_transformers import SentenceTransformer

from src.embeddings.text_preparation import prepare_semantic_text

EMBEDDINGS_SCHEMA = pa.schema([
    ("complaint_id", pa.string()),
    ("embedding", pa.list_(pa.float32())),
    ("model_name", pa.string()),
    ("dimension", pa.int32()),
])


class ComplaintEmbeddingGenerator:
    """
    Manages sentence-transformer embedding generation with memory-safe batching.
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        device: str = "cpu",
        dimension: int = 384,
    ):
        self.model_name = model_name
        self.device = device
        self.dimension = dimension
        print(f"Loading embedding model '{model_name}' on device '{device}'...")
        t0 = time.time()
        self.model = SentenceTransformer(model_name, device=device)
        print(f"Model loaded successfully in {time.time()-t0:.2f}s")

    def encode_texts(
        self, texts: List[str], batch_size: int = 256, show_progress: bool = False
    ) -> np.ndarray:
        """
        Encodes list of texts into L2-normalized float32 vectors.
        """
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            normalize_embeddings=True,
            convert_to_numpy=True,
            device=self.device,
        )
        return embeddings.astype(np.float32)

    def run_semantic_sanity_checks(self) -> Dict[str, float]:
        """
        Evaluates cosine similarity on curated automotive defect symptom pairs
        to verify that the embedding space captures semantic similarity.
        """
        test_pairs = [
            (
                "similar_stall",
                "Vehicle suddenly stalled and lost motive power at 65 mph on the highway.",
                "Car died while driving at high speed and would not accelerate.",
            ),
            (
                "similar_steering",
                "Steering wheel locked up completely while making a left turn.",
                "Power steering failed suddenly making it impossible to steer the vehicle.",
            ),
            (
                "similar_fire",
                "Smoke and flames observed coming from the engine compartment after parking.",
                "Engine caught fire under the hood while the vehicle was turned off.",
            ),
            (
                "dissimilar_airbag_vs_radio",
                "Airbag failed to deploy during a severe head-on crash.",
                "Radio touchscreen infotainment display keeps freezing and rebooting.",
            ),
            (
                "dissimilar_brakes_vs_ac",
                "Brake pedal went straight to the floor and vehicle would not stop.",
                "Air conditioning blows warm air and passenger window is stuck.",
            ),
        ]

        results = {}
        for label, text_a, text_b in test_pairs:
            vecs = self.encode_texts([text_a, text_b], batch_size=2)
            # Vectors are normalized, so dot product == cosine similarity
            sim = float(np.dot(vecs[0], vecs[1]))
            results[label] = round(sim, 4)

        return results


def validate_embeddings_parquet(
    embeddings_path: str,
    expected_dim: int = 384,
    expected_ids: Optional[List[str]] = None,
    expected_model: Optional[str] = None,
) -> Dict[str, any]:
    """
    Validates structural and numerical integrity of generated embeddings Parquet file:
    - Verifies non-empty rows
    - Verifies unique complaint_ids
    - Verifies embedding dimension
    - Verifies zero NaNs, zero Infs
    - Verifies unit L2 norm
    """
    if not os.path.isfile(embeddings_path):
        raise FileNotFoundError(f"Embeddings file not found: {embeddings_path}")

    meta = pq.read_metadata(embeddings_path)
    total_rows = meta.num_rows

    table = pq.read_table(embeddings_path)
    ids = table["complaint_id"].to_pylist()
    unique_ids = set(ids)
    duplicates = len(ids) - len(unique_ids)
    ids_match = expected_ids is None or ids == expected_ids

    vectors = table["embedding"].to_pylist()
    try:
        arr = np.asarray(vectors, dtype=np.float32)
        rectangular = arr.ndim == 2
    except (TypeError, ValueError):
        arr = np.empty((0, 0), dtype=np.float32)
        rectangular = False
    has_nan = bool(np.isnan(arr).any())
    has_inf = bool(np.isinf(arr).any())
    dims_correct = rectangular and arr.shape[1] == expected_dim and all(
        len(v) == expected_dim for v in vectors
    )
    row_dims_correct = all(d == expected_dim for d in table["dimension"].to_pylist())
    models = table["model_name"].to_pylist()
    metadata_consistent = len(set(models)) <= 1 and row_dims_correct
    model_matches = expected_model is None or (len(models) > 0 and all(m == expected_model for m in models))
    norms = np.linalg.norm(arr, axis=1) if rectangular and len(arr) else np.array([])
    norm_valid = bool(len(norms) == total_rows and np.allclose(norms, 1.0, atol=1e-3))
    row_count_valid = expected_ids is None or total_rows == len(expected_ids)

    all_passed = (len(unique_ids) == len(ids) and ids_match and row_count_valid
                  and dims_correct and metadata_consistent and model_matches
                  and not has_nan and not has_inf and norm_valid and total_rows > 0)
    return {
        "file_path": embeddings_path, "total_embeddings": total_rows,
        "unique_complaint_ids": len(unique_ids), "duplicate_ids": duplicates,
        "ids_match": ids_match, "row_count_valid": row_count_valid,
        "dimension": expected_dim, "dimension_valid": dims_correct,
        "metadata_consistent": metadata_consistent, "model_matches": model_matches,
        "has_nan": has_nan, "has_inf": has_inf,
        "unit_norm_valid": norm_valid, "all_checks_passed": all_passed,
    }
