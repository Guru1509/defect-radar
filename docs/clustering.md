# DEFECTRADAR — Phase 4 Sample Clustering Experiment

**Run date:** October 23, 2026  
**Purpose:** Compare two semantic clustering approaches on a manageable sample before considering larger runs. This is an exploratory sample, not a validated defect detector.

## Method

- Sample: **5,000** complaint embeddings, chosen without replacement with NumPy seed **42** from the 651,260 eligible shard rows.
- Join: sampled embedding rows joined to `complaints.parquet` narratives by `complaint_id`; complaint data and embedding shards were read-only.
- Input: normalized 384-dimensional `float32` `all-MiniLM-L6-v2` vectors. Euclidean distance was used for HDBSCAN; on normalized vectors, Euclidean distance ranks pairs monotonically with cosine similarity.
- Hardware/software: local Apple Silicon environment; scikit-learn 1.8.0. No additional clustering package installed.
- Memory: process peak RSS **1,267.73 MB** (measured with `resource.getrusage`; includes imports, sample loading, and both methods, not a per-method peak).

## Measured results

| Method | Parameters | Clusters | Noise | Runtime |
|---|---|---:|---:|---:|
| MiniBatch K-Means | `k=20`, `batch_size=256`, `n_init=3`, `max_iter=100`, `random_state=42` | 20 | 0 / 0.00% | 0.455 s |
| HDBSCAN | `min_cluster_size=30`, `min_samples=10`, Euclidean, `n_jobs=-1` | 2 | 4,093 / 81.86% | 6.094 s |

K-Means cluster sizes (largest to smallest): **512, 399, 325, 296, 288, 276, 271, 244, 241, 234, 229, 226, 219, 217, 198, 188, 183, 164, 160, 130**.

HDBSCAN cluster sizes: **865, 42**; remaining sample points are noise. Cluster labels are arbitrary IDs, not defect names.

## Narrative spot-check

Representatives were chosen nearest to each method's cluster center/mean for its three largest clusters. This hand inspection is qualitative and limited to those examples.

- **K-Means cluster 8 (512):** one narrative describes stalling/overheating/transmission warnings; another describes a pothole followed by suspension/control-arm concerns. These examples do **not** support a single narrow defect interpretation.
- **K-Means cluster 15 (399):** examples describe sudden engine/electrical shutdown and blown fuses, suggesting a broad loss-of-power/electrical theme, but not one precise component failure.
- **K-Means cluster 1 (325):** examples focus on Ford recall notification/repair concerns rather than a shared physical failure symptom. This indicates that complaint narratives can cluster by administrative context.
- **HDBSCAN cluster 0 (865):** inspected examples discuss Takata airbag recall notices and unavailable repair parts. This is a coherent recall-administration theme, but does not itself identify a specific failure mechanism.
- **HDBSCAN cluster 1 (42):** inspected examples describe windshield cracking, including spontaneous cracking. This small cluster appears more symptom-focused.

## Phase 4B: Quantitative and Qualitative Evaluation

The existing sample summary supports these additional **measured/derived-from-counts** findings:

| Method | Assigned/covered | Noise | Cluster-size distribution |
|---|---:|---:|---|
| MiniBatch K-Means | 5,000 / 5,000 (100%) | 0% | 20 clusters; min 130, median 231.5, max 512 (mean 250) |
| HDBSCAN | 907 / 5,000 (18.14%) | 4,093 / 5,000 (81.86%) | 2 clusters: 42 and 865 |

K-Means cluster sizes have a 3.94× max/min ratio; HDBSCAN's two assigned clusters have a 20.60× ratio. These describe size imbalance only, not semantic quality.

**Silhouette scores were not calculated.** The experiment's recorded results include cluster counts and representative examples, but do not preserve row-level labels or the sampled embedding matrix in a reusable project artifact. The saved counts and narrative excerpts are insufficient to calculate either K-Means silhouette or HDBSCAN silhouette on non-noise assignments. Re-running was intentionally avoided for this targeted review; no silhouette value is inferred.

The previous narrative spot-check found clear recall-notification/repair language in K-Means cluster 1 and HDBSCAN cluster 0, suggesting recall-related boilerplate is prominent in those inspected examples. Other inspected groups included mixed symptoms and windshield cracking. Vehicle/model names appear in some complaint narratives, but this small qualitative sample cannot establish that those details dominate clustering; the experiment embeds complaint narratives, not separate canonical make/model metadata.

## Phase 4C: Saved-Label Evaluation and Text-Preparation Comparison

### Method and saved artifacts

- Repeated the fixed seed-42, 5,000-row sample; joined narratives to vectors by `complaint_id`.
- Baseline vectors came from the existing Phase 3 shards. The sole text variation removed only exact clauses matching NHTSA campaign notice, unavailable repair part, and repair-delay templates, then re-applied the normal semantic-text preparation. Canonical narratives and Phase 3 shards were read-only.
- Regenerated vectors only for these 5,000 revised sample texts using `all-MiniLM-L6-v2`; both methods used the previous settings (`MiniBatchKMeans`: `k=20`, batch 256, `n_init=3`, max_iter 100, seed 42; HDBSCAN: min cluster size 30, min_samples 10, Euclidean).
- Saved aligned sample IDs, baseline/revised vectors, and all four label arrays in `data/clustering/sample_seed42.npz` (14,271,888 bytes). Full metrics and deterministic representative examples are in `data/clustering/sample_seed42.json`.
- Peak process RSS: **1,738.62 MB**. The text variation changed **326 / 5,000** narratives and removed **419** matching clauses.
- Silhouette is exact Euclidean silhouette: all K-Means assignments; HDBSCAN only on non-noise assignments. Coverage and noise are reported separately; silhouette does not measure whether a cluster is a useful defect category.

### Measured results

| Text input | Method | Clusters | Coverage / noise | Silhouette | Fit time |
|---|---|---:|---:|---:|---:|
| Baseline | MiniBatch K-Means | 20 | 100% / 0% | 0.042678 | 0.464 s |
| Baseline | HDBSCAN | 2 | 18.14% / 81.86% | 0.182488 | 5.119 s |
| Narrow redaction | MiniBatch K-Means | 20 | 100% / 0% | 0.031077 | 0.044 s |
| Narrow redaction | HDBSCAN | 2 | 17.24% / 82.76% | 0.165121 | 5.134 s |

K-Means cluster sizes, descending:
- Baseline: **512, 399, 325, 296, 288, 276, 271, 244, 241, 234, 229, 226, 219, 217, 198, 188, 183, 164, 160, 130**.
- Narrow redaction: **638, 447, 403, 275, 270, 258, 256, 250, 232, 227, 220, 220, 215, 201, 198, 166, 153, 133, 129, 109**.

HDBSCAN sizes (excluding noise): baseline **865, 42**; narrow redaction **821, 41**. Noise counts are **4,093** baseline and **4,138** revised. Label IDs are arbitrary.

### Representative narrative review and interpretation

The fixed representative selection is nearest-to-center examples from the three largest K-Means groups and all HDBSCAN groups. Baseline inspection again found a mixed K-Means group (stall/overheat versus suspension/pothole concerns), a broad electrical shutdown group, and a recall-notification group. HDBSCAN's large group was dominated in inspected examples by Takata recall notices, unavailable parts, and repair delays; its small group described windshield cracking.

After the narrow redaction, the revised K-Means representatives still included a vehicle stall, an electrical shutdown, and a lost-Takata-recall-letter complaint. HDBSCAN's large-cluster examples still included Takata notice language and dashboard/airbag complaints; the windshield-cracking cluster remained small. The transformation removed campaign-number and unavailable-part boilerplate in some narratives, but standard variants such as “Takata recall” and “recall repair” remained. Vehicle make/model details also remain in narrative text; this experiment does not isolate their effect.

Neither silhouette increased: K-Means fell from **0.042678 to 0.031077**; HDBSCAN fell from **0.182488 to 0.165121**, and HDBSCAN coverage declined by **0.90 percentage points**. These low scores and spot checks do not support improved semantic grouping. The HDBSCAN score applies only to its small assigned subset, so it must be read with its coverage/noise rate.

## Phase 4D: PCA Representation Comparison

### Method and artifacts

- Reused the exact 5,000 sample IDs and original 384-dimensional baseline vectors from `sample_seed42.npz`; no earlier sample generation or clustering was repeated.
- Fit PCA **only on these 5,000 vectors**, using 100 components, randomized solver, seed 42. This reduces dimensions by 73.96% and retains **79.58%** of sample variance; no component-count sweep was performed.
- Rejoined original complaint narratives by saved `complaint_id` for representative review. PCA scores then went to the same MiniBatch K-Means (`k=20`, batch 256, `n_init=3`, max_iter 100, seed 42) and HDBSCAN (`min_cluster_size=30`, `min_samples=10`, Euclidean) settings.
- PCA fit: **0.069 s**; process peak RSS: **674.81 MB**. Fit times below exclude silhouette computation.
- Saved PCA coordinates, IDs, labels, component matrix/mean, and explained-variance ratios in `data/clustering/pca_seed42.npz`; report and representative narratives are in `data/clustering/pca_seed42.json`. Artifact shape, finite values, and ID/label alignment were verified.

### Measured results

| Representation | Method | Clusters | Coverage / noise | Silhouette | Fit time |
|---|---|---:|---:|---:|---:|
| Original 384-D | MiniBatch K-Means | 20 | 100% / 0% | 0.042678 | 0.464 s |
| PCA 100-D | MiniBatch K-Means | 20 | 100% / 0% | 0.058108 | 0.073 s |
| Original 384-D | HDBSCAN | 2 | 18.14% / 81.86% | 0.182488 | 5.119 s |
| PCA 100-D | HDBSCAN | 4 | 42.96% / 57.04% | 0.100721 | 1.118 s |

PCA K-Means cluster sizes (descending): **471, 390, 338, 331, 319, 266, 258, 256, 250, 244, 237, 233, 226, 207, 206, 186, 176, 157, 149, 100**. PCA HDBSCAN cluster sizes (excluding noise): **2,022, 48, 43, 35**; **2,852** sample points were noise.

### Representative narrative review and comparison

The reproducible review used the two nearest-to-centroid representatives from each of the three largest K-Means clusters and every HDBSCAN cluster. PCA K-Means' largest reviewed cluster had two stalling/loss-of-acceleration narratives, a coherent broad symptom theme. Another reviewed K-Means cluster mixed a recall appointment narrative with an intake-manifold warning/repair narrative; a separate cluster was strongly Takata recall boilerplate. HDBSCAN's largest group mixed recall-repair language with a stall/crash/airbag nondeployment report. Its smaller groups had more coherent headlight-failure examples and door-latch/door-opening examples.

Compared with original vectors, PCA K-Means silhouette rose by **0.015430** but remains near zero. PCA HDBSCAN coverage rose by **24.82 percentage points**, while its silhouette fell by **0.081767**; the newly assigned majority-sized cluster includes mixed recall administration and physical symptoms in reviewed examples. The larger HDBSCAN coverage is therefore not by itself evidence of better defect grouping.

## Phase 4E: Seed-123 Reproducibility Check

### Method and artifacts

- Drew a reproducible 5,000-complaint sample with seed **123** from the existing Phase 3 embeddings and joined narratives by `complaint_id`; 39 IDs overlap the seed-42 sample.
- Applied the same 100-component randomized PCA configuration (random state 42, `iterated_power=3`), fitted only on the new sample. It retained **79.53%** of sample variance. Original and PCA vectors each received the same MiniBatch K-Means and HDBSCAN configurations documented above.
- PCA fit took **0.082 s**; process peak RSS was **1,482.17 MB**. Method fit times exclude silhouette computation.
- Saved IDs, original/PCA vectors, PCA transform, and all four label arrays in `data/clustering/sample_seed123.npz`; compact metrics and reproducible representative narratives are in `data/clustering/sample_seed123.json`. Shapes, finite vectors, unique IDs, and label alignment were verified.

### Measured results

| Representation | Method | Clusters | Coverage / noise | Silhouette | Fit time |
|---|---|---:|---:|---:|---:|
| Original 384-D | MiniBatch K-Means | 20 | 100% / 0% | 0.034731 | 0.173 s |
| PCA 100-D | MiniBatch K-Means | 20 | 100% / 0% | 0.054894 | 0.017 s |
| Original 384-D | HDBSCAN | 2 | 19.70% / 80.30% | 0.190062 | 5.120 s |
| PCA 100-D | HDBSCAN | 2 | 44.52% / 55.48% | 0.135929 | 1.088 s |

Seed-123 cluster sizes, descending: original K-Means **647, 341, 337, 332, 317, 313, 280, 273, 270, 229, 216, 213, 206, 185, 182, 170, 155, 134, 102, 98**; PCA K-Means **520, 453, 355, 313, 311, 281, 279, 256, 247, 240, 229, 225, 225, 210, 202, 191, 171, 162, 117, 13**. Original HDBSCAN: **931, 54** (4,015 noise); PCA HDBSCAN: **2,194, 32** (2,774 noise).

### Narrative review and cross-sample comparison

Review used two deterministic representative narratives from each of the three largest K-Means clusters and both HDBSCAN clusters for each representation. Original K-Means examples included Takata recall boilerplate and mixed steering/acceleration reports, alongside a broad power-loss group. PCA K-Means examples included related powertrain/electrical failures, but also combined distinct power-steering and engine-stall reports. Original HDBSCAN separated a Takata-heavy group from a small windshield/dashboard-cracking group. PCA HDBSCAN's small group was coherent low-beam-headlight complaints; its large group mixed an automatic-braking malfunction report with recall-repair boilerplate.

The metric direction matched seed 42: K-Means silhouette increased with PCA (**+0.015430** on seed 42; **+0.020163** on seed 123), though both PCA scores remain low (**0.058108**, **0.054894**). HDBSCAN coverage increased by **24.82 percentage points** on each sample (seed 42: 18.14% to 42.96%; seed 123: 19.70% to 44.52%), while its silhouette decreased on both (by **0.081767** and **0.054133**, respectively). PCA HDBSCAN formed four clusters on seed 42 but two on seed 123. Coverage gains are reproducible; semantic coherence is mixed and the large assigned groups remain broad. Cluster label numbers are arbitrary and must not be compared directly across independent runs.

## Interpretation, limitations, and recommendation

The sample check supports a consistent PCA effect on these metrics, not a demonstrated improvement in defect discovery: K-Means separation remains weak, HDBSCAN silhouette falls, and representative review finds mixed themes in large clusters. The two samples overlap by 39 complaints, so they are not fully independent; PCA is fit separately on each evaluation sample, and no component-count sensitivity was tested. Runtime and memory are environment-specific.

**Recommendation:** PCA's coverage increase reproduces, but the evidence does **not** justify full-corpus clustering or a quality claim. Keep any next step sample-bounded and require stronger defect-theme validation. No temporal analysis, scoring, backtesting, or application work was performed.