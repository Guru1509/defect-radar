import tempfile
import unittest
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from src.clustering.experiment import (
    cluster_summary,
    load_sample,
    select_sample_indices,
    silhouette_evaluation,
    remove_recall_repair_boilerplate,
)


class TestClusteringHelpers(unittest.TestCase):
    def test_sample_indices_are_reproducible_unique_and_sized(self):
        first = select_sample_indices(total_rows=100, sample_size=12, seed=42)
        second = select_sample_indices(total_rows=100, sample_size=12, seed=42)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 12)
        self.assertEqual(len(set(first)), 12)
        self.assertTrue(all(0 <= index < 100 for index in first))

    def test_silhouette_excludes_hdbscan_noise(self):
        matrix = np.array([[0.0, 0.0], [0.0, 0.1], [5.0, 5.0], [5.0, 5.1], [20.0, 20.0]])
        result = silhouette_evaluation(matrix, [0, 0, 1, 1, -1])
        self.assertTrue(result["valid"])
        self.assertEqual(result["eligible_count"], 4)
        self.assertEqual(result["coverage_pct"], 80.0)
        self.assertGreater(result["score"], 0.9)

    def test_recall_boilerplate_removal_preserves_symptom_text(self):
        text = (
            "THE CONTACT RECEIVED NOTIFICATION OF NHTSA CAMPAIGN NUMBER: 15V312000 (AIR BAGS). "
            "THE PART TO DO THE RECALL REPAIR WAS UNAVAILABLE. AIRBAG DID NOT DEPLOY IN A CRASH."
        )
        revised, removed_count = remove_recall_repair_boilerplate(text)
        self.assertEqual(removed_count, 2)
        self.assertNotIn("CAMPAIGN NUMBER", revised)
        self.assertNotIn("RECALL REPAIR WAS UNAVAILABLE", revised)
        self.assertIn("AIRBAG DID NOT DEPLOY IN A CRASH", revised)

    def test_cluster_summary_counts_noise_and_sorts_cluster_sizes(self):
        summary = cluster_summary([0, 0, 1, 1, 1, -1])
        self.assertEqual(summary["cluster_count"], 2)
        self.assertEqual(summary["noise_count"], 1)
        self.assertAlmostEqual(summary["noise_pct"], 100 / 6, places=2)
        self.assertEqual(summary["cluster_sizes"], {"1": 3, "0": 2})

    def test_sample_loader_joins_narratives_by_complaint_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shard_dir = root / "shards"
            shard_dir.mkdir()
            ids = ["c1", "c2", "c3", "c4"]
            vectors = np.zeros((4, 384), dtype=np.float32)
            vectors[:, 0] = 1.0
            pq.write_table(pa.table({
                "complaint_id": ids,
                "embedding": pa.array(vectors.tolist(), type=pa.list_(pa.float32())),
                "model_name": ["all-MiniLM-L6-v2"] * 4,
                "dimension": [384] * 4,
            }), shard_dir / "shard_000.parquet")
            pq.write_table(pa.table({
                "complaint_id": ids,
                "complaint_text_clean": [f"Narrative for {item}" for item in ids],
            }), root / "complaints.parquet")
            sample_ids, matrix, narratives = load_sample(
                str(root), str(root / "complaints.parquet"), sample_size=2, seed=7
            )
            self.assertEqual(len(sample_ids), 2)
            self.assertEqual(matrix.shape, (2, 384))
            self.assertEqual(narratives, [f"Narrative for {item}" for item in sample_ids])


if __name__ == "__main__":
    unittest.main()
