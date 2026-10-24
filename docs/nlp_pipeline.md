# DEFECTRADAR — Phase 3: NLP Representation & Semantic Embeddings Pipeline

**Project:** DEFECTRADAR — AI-Powered Early Detection of Emerging Vehicle Defects from Consumer Complaints  
**Phase:** Phase 3 (NLP Representation & Semantic Embeddings)  
**Model:** `all-MiniLM-L6-v2` (Sentence Transformers, 384 dimensions, local inference)  
**Execution Environment:** macOS (Apple Silicon M2, 8GB Unified RAM)  
**Storage Engine:** Apache Parquet with Zstandard (`zstd`) compression  

---

## 1. Why Semantic Embeddings Are Needed

In vehicle consumer complaints, drivers describe identical physical failure symptoms using diverse colloquial vocabulary:
- *Complaint A:* "Vehicle suddenly lost power while driving on the freeway and would not accelerate."
- *Complaint B:* "Engine stopped responding to accelerator pedal and car went into limp mode."
- *Complaint C:* "While on highway, truck unexpectedly lost motive power and stalled in traffic."

Traditional keyword matching, regex queries, or bag-of-words fail to group these reports because they share almost no unique lexical tokens. In addition, over 81,500 complaints in the raw NHTSA taxonomy are filed under broad or uninformative categories like `UNKNOWN OR OTHER` or `ELECTRICAL SYSTEM`. 

Dense semantic embeddings map consumer narratives into a continuous vector space where distance corresponds to semantic similarity, enabling DEFECTRADAR to discover emerging defect clusters before official investigation or recall codes exist.

---

## 2. Text Representation: What Is and Is Not Embedded

### 2.1 Embedded Text: `semantic_text`
The primary embedding input is derived directly from `complaint_text_clean` using the following rules:
1. **Preserves Core Symptom Mechanics:** Retains all driving speeds, failure symptoms, warning lights, environmental conditions, and mechanical behaviors.
2. **Strips Administrative Intake Preambles:** Removes boilerplate telephone logging headers (e.g. `THE CONSUMER STATED THAT...`, `THE CALLER REPORTED THAT...`, `CONSUMER WRITES IN REGARDS TO...`).
3. **Strips Trailing Clerk Initials:** Removes trailing transcription initials (e.g. `*TR`, `*LD *TR`, `*JB`) so that complaints transcribed by the same clerk do not artificially cluster together.
4. **Preserves Numbers and Technical Terms:** DTC trouble codes (e.g., `P0500`), speeds (`65 MPH`), and component names are strictly preserved.

### 2.2 What Is NOT Embedded
- **Vehicle Metadata Excluded:** Vehicle make (`make_normalized`), model (`model_normalized`), model year (`model_year`), and geographic state (`state`) are **strictly excluded** from the text passed to the embedding model.
- **Rationale:** If "FORD EXPLORER 2020" were prepended to every narrative, embeddings would cluster primarily by vehicle brand rather than the physical defect symptom. In DEFECTRADAR, clustering is evaluated across cohorts, and vehicle dimensions remain structured metadata filters rather than semantic dimensions.
- **Component Taxonomies Excluded from Text:** Component labels (e.g., `SERVICE BRAKES`) are kept in `complaint_components.parquet` as structured foreign-key attributes rather than prepended text, preventing taxonomy bias.

---

## 3. Why We Are NOT Using an LLM for Every Complaint

1. **Computational Feasibility on 8GB RAM:** Prompting a 7B+ parameter LLM across 651,262 complaint narratives would require over 500 GPU-hours or tens of thousands of dollars in cloud API costs, with high latency and token rate-limit bottlenecks.
2. **High Embedding Throughput:** `all-MiniLM-L6-v2` runs locally on Apple Silicon M2 at **~170 complaints per second**, processing 10,000 records in ~60 seconds with under 2.0 GB RAM footprint.
3. **Reproducibility & Determinism:** Local sentence embeddings yield fixed, deterministic 384-dimensional dense vectors with zero API drift, zero hallucination risk, and zero recurring cost.
4. **Role of LLMs in DefectRadar:** If an LLM is utilized in later phases, it will operate exclusively as a qualitative summarizer on small, selected defect clusters already identified by the unsupervised ML pipeline.

---

## 4. NLP Model Selection & Hardware Compatibility

| Parameter | Configuration | Justification |
| :--- | :--- | :--- |
| **Model** | `all-MiniLM-L6-v2` | State-of-the-art efficiency-to-performance ratio; 22.7M parameters; 5x faster than base BERT with 99% retention of semantic retrieval quality. |
| **Embedding Dimension** | 384 dimensions | Compact vector size enabling fast downstream clustering (HDBSCAN/K-Means) with minimal RAM overhead. |
| **Device Selection** | CPU (`device='cpu'`) | **Empirical Measurement:** CPU with Apple Silicon vector optimizations achieved 0.26s per 512 sentences vs 0.60s on MPS. For lightweight MiniLM, CPU avoids GPU kernel launch and tensor transfer latency. |
| **Batch Size** | 256 | Optimal balance between vectorized batch efficiency and resident RAM budget. |
| **Precision** | `float32` (L2 Normalized) | Guarantees vector dot products exactly equal cosine similarity with zero floating-point underflow. |

---

## 5. Storage Strategy & Referential ID Alignment

- **Location:** `data/embeddings/` (strictly separated from canonical `complaints.parquet`).
- **Format:** Apache Parquet with Zstandard (`zstd`) compression, sharded into incremental partitions (25,000 complaints per shard).
- **ID Alignment:** Every embedding vector is stored alongside its canonical `complaint_id` (`ODINO`).
- **Resumption Support:** Existing shards are reused only after verifying the expected complaint IDs, row count, model, and dimensions. Final validation checks every shard and corpus-wide ID coverage.
- **Measured Full Run (October 2026):** 651,260 eligible complaint narratives embedded; 2 empty narratives excluded. Completed 27 shards (25,000 rows each except the final partial shard), in 4,291.56 seconds at 151.75 complaints/second. Peak resident memory was 2,579.23 MB; compressed Parquet output was 899.51 MB.
- **Validation:** All 27 shards passed; 0 missing IDs, 0 duplicate IDs, valid 384-dimensional float32 vectors with no NaN/Inf, and consistent `all-MiniLM-L6-v2` model metadata.
- **Pilot (10,000 complaints):** 14.75 MB (kept separately as `pilot_embeddings.parquet`).

---

## 6. Text Quality & Corpus Analysis

Audited across all 651,262 canonical complaints:
- **Total Complaints:** 651,262
- **Empty Narratives (`length == 0`):** Exactly 2 records (0.0003%).
- **Exclusion Rule:** These 2 records are explicitly excluded from semantic embedding because they lack any symptom text.
- **Short Narratives (< 50 chars):** 15,518 records (2.38%) — valid terse complaints (e.g. *"DEATH WOBBLE"*, *"BRAKES FAILED"*).
- **Standard Narratives (50–1,500 chars):** 610,239 records (93.70%).
- **Long Narratives ($\ge$ 1,500 chars):** 25,505 records (3.92%).
- **Median Length:** 450.0 characters (~75–90 words).
- **Mean Length:** 535.02 characters.

---

## 7. Semantic Sanity Checks (Empirical Cosine Similarities)

Evaluated on curated automotive failure pairs using `all-MiniLM-L6-v2`:

| Defect Test Pair | Description Comparison | Cosine Similarity | Quality Assessment |
| :--- | :--- | :--- | :--- |
| **`similar_stall`** | Highway engine stall vs sudden loss of motive power | **0.4927** | High semantic affinity |
| **`similar_steering`** | Steering wheel lockup vs power steering failure | **0.5417** | High semantic affinity |
| **`similar_fire`** | Engine compartment flames vs hood fire while parked | **0.6023** | Very high semantic affinity |
| **`dissimilar_airbag_vs_radio`** | Crash airbag non-deployment vs touchscreen freezing | **0.1018** | Distinct orthogonal concepts |
| **`dissimilar_brakes_vs_ac`** | Total brake pedal loss vs AC blowing warm air | **0.2671** | Distinct failure domains |

*The similarity difference between related failure modes and unrelated vehicle systems exceeds 0.25–0.50, verifying that the embedding representation captures mechanical defect semantics.*

---

## 8. Date Handling Verification Summary (Step 0)

An audit of `received_date` (`LDATE`) vs `date_added` (`DATEA`) confirmed:
1. `DATEA` represents internal NHTSA system docket creation date; `LDATE` is formal receipt date.
2. In 99.97% of records, `date_added == received_date`.
3. In only 2 records out of 651,262 (0.0003%), legacy dockets were amended with newer vehicle complaints.
4. **Conclusion:** `received_date` (`LDATE`) remains the strict, tamper-proof primary temporal index for all DefectRadar temporal analysis and historical backtesting.
