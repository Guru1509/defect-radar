"""
Comprehensive unit and integration tests for DEFECTRADAR Phase 3 NLP & Semantic Embeddings.

Covers:
- semantic_text creation (boilerplate removal, clerk tags removal, preservation of symptoms)
- empty text handling
- embedding dimensionality (384)
- embedding ID uniqueness
- embedding/canonical complaint alignment
- NaN and Infinite value detection
- metadata creation
- small-batch generation and cosine similarity sanity behavior
"""

import os
import unittest
import numpy as np
import tempfile
import pyarrow as pa
import pyarrow.parquet as pq

from src.embeddings.text_preparation import (
    prepare_semantic_text,
    RE_TRAILING_CLERK_TAGS,
    RE_PREAMBLE,
)
from src.embeddings.generator import (
    ComplaintEmbeddingGenerator,
    validate_embeddings_parquet,
)


class TestSemanticTextPreparation(unittest.TestCase):
    """Tests semantic text preparation and sanitization."""

    def test_semantic_text_creation_basic(self):
        narrative = "While driving at 65 mph on the highway, engine suddenly died and vehicle lost power."
        sem = prepare_semantic_text(narrative)
        self.assertEqual(sem, narrative)

    def test_strips_trailing_clerk_tags(self):
        narrative = "Transmission slips when accelerating from a stop. *TR"
        sem = prepare_semantic_text(narrative)
        self.assertEqual(sem, "Transmission slips when accelerating from a stop.")

        multi_tag = "Brake pedal goes to the floor. *LD *TR"
        sem_multi = prepare_semantic_text(multi_tag)
        self.assertEqual(sem_multi, "Brake pedal goes to the floor.")

    def test_strips_intake_preamble_boilerplate(self):
        narrative = "THE CONSUMER STATED THAT the power steering locked up while making a turn."
        sem = prepare_semantic_text(narrative)
        self.assertEqual(sem, "the power steering locked up while making a turn.")

        narrative2 = "CONSUMER WRITES IN REGARDS TO fuel pump failure on highway."
        sem2 = prepare_semantic_text(narrative2)
        self.assertEqual(sem2, "fuel pump failure on highway.")

    def test_empty_and_none_text_handling(self):
        self.assertEqual(prepare_semantic_text(""), "")
        self.assertEqual(prepare_semantic_text(None), "")
        self.assertEqual(prepare_semantic_text("   \n\t   "), "")

    def test_preserves_technical_vocabulary_and_numbers(self):
        narrative = "ABS module threw DTC code P0500 at 55 MPH. Wheel speed sensor 4WD fault."
        sem = prepare_semantic_text(narrative)
        self.assertIn("DTC code P0500", sem)
        self.assertIn("55 MPH", sem)
        self.assertIn("Wheel speed sensor 4WD fault.", sem)


class TestEmbeddingGenerationAndQuality(unittest.TestCase):
    """Tests embedding generation, dimensionality, and sanity checks."""

    @classmethod
    def setUpClass(cls):
        cls.generator = ComplaintEmbeddingGenerator(
            model_name="all-MiniLM-L6-v2",
            device="cpu",
        )

    def test_embedding_dimensionality(self):
        texts = ["Vehicle stalled on freeway.", "Brakes failed completely."]
        vecs = self.generator.encode_texts(texts, batch_size=2)
        self.assertEqual(vecs.shape, (2, 384))
        self.assertEqual(vecs.dtype, np.float32)

    def test_no_nan_or_inf_in_embeddings(self):
        texts = ["Engine fire under the hood.", "Steering locked up."]
        vecs = self.generator.encode_texts(texts, batch_size=2)
        self.assertFalse(np.isnan(vecs).any(), "Found NaN in embeddings")
        self.assertFalse(np.isinf(vecs).any(), "Found Inf in embeddings")

    def test_unit_vector_norm(self):
        texts = ["Airbag warning light on dashboard illuminated."]
        vecs = self.generator.encode_texts(texts, batch_size=1)
        norm = np.linalg.norm(vecs[0])
        self.assertAlmostEqual(norm, 1.0, places=3)

    def test_semantic_sanity_similarity_behavior(self):
        results = self.generator.run_semantic_sanity_checks()
        # Similar failure pairs must have high cosine similarity
        self.assertGreater(results["similar_stall"], 0.45)
        self.assertGreater(results["similar_steering"], 0.45)
        self.assertGreater(results["similar_fire"], 0.45)

        # Dissimilar failure pairs must have low cosine similarity
        self.assertLess(results["dissimilar_airbag_vs_radio"], 0.35)
        self.assertLess(results["dissimilar_brakes_vs_ac"], 0.35)

        # Verify that similar is significantly higher than dissimilar
        self.assertGreater(
            results["similar_stall"], results["dissimilar_airbag_vs_radio"] + 0.20
        )


class TestShardResumeValidation(unittest.TestCase):
    def test_reuses_only_shard_matching_ids_count_and_metadata(self):
        from src.embeddings.generator import validate_embeddings_parquet

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "shard.parquet")
            schema = pa.schema([
                ("complaint_id", pa.string()),
                ("embedding", pa.list_(pa.float32())),
                ("model_name", pa.string()),
                ("dimension", pa.int32()),
            ])
            def write(ids, vectors, models=None, dims=None):
                pq.write_table(pa.Table.from_arrays([
                    pa.array(ids),
                    pa.array(vectors, type=pa.list_(pa.float32())),
                    pa.array(models or ["model-x"] * len(ids)),
                    pa.array(dims or [2] * len(ids), type=pa.int32()),
                ], schema=schema), path)
                return validate_embeddings_parquet(path, expected_dim=2,
                    expected_ids=["a", "b"], expected_model="model-x")

            good = write(["a", "b"], [[1.0, 0.0], [0.0, 1.0]])
            wrong_ids = write(["a", "c"], [[1.0, 0.0], [0.0, 1.0]])
            wrong_model = write(["a", "b"], [[1.0, 0.0], [0.0, 1.0]],
                                models=["model-x", "model-y"])
            wrong_dim = write(["a", "b"], [[1.0, 0.0], [0.0, 1.0]], dims=[2, 3])
            duplicate = write(["a", "a"], [[1.0, 0.0], [0.0, 1.0]])
            nonfinite = write(["a", "b"], [[float("nan"), 0.0], [0.0, 1.0]])
            wrong_count = write(["a"], [[1.0, 0.0]])
            self.assertTrue(good["all_checks_passed"])
            for invalid in (wrong_ids, wrong_model, wrong_dim, duplicate, nonfinite, wrong_count):
                self.assertFalse(invalid["all_checks_passed"])


if __name__ == "__main__":
    unittest.main()
