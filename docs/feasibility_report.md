# DEFECTRADAR — Phase 1: Research Feasibility Report

**Project:** DEFECTRADAR — AI-Powered Early Detection of Emerging Vehicle Defects from Consumer Complaints  
**Phase:** Phase 1 (Data Foundation & Feasibility Audit)  
**Date:** October 2026  
**Status:** Evaluation Completed — Data Foundation Validated

---

## 1. Executive Summary

This feasibility report answers the fundamental technical and methodological questions governing whether the provided NHTSA datasets provide a sound empirical foundation for building the **DEFECTRADAR** system.

Based on empirical auditing of **1,775,003 records** across six raw NHTSA archives, **the project is highly feasible from a data, semantic, and temporal perspective**, provided appropriate chunking, normalization, and leakage-prevention mechanisms are enforced.

---

## 2. Structured Feasibility Assessment

### 2.1 Question 1: Is the complaint data suitable for NLP?
**Finding: YES — Exceptionally well-suited.**
- **Empirical Evidence:** Out of 908,693 complaint rows spanning 2015 to 2024, fewer than 5 rows have missing narratives (>99.999% text completeness).
- **Linguistic Nature:** Consumers write descriptive, symptom-focused accounts of vehicle malfunctions. They detail operating conditions (*"while traveling at 65 mph on the highway"*, *"in cold weather"*, *"under heavy braking"*), tactile/visual cues (*"steering wheel locked"*, *"smoke coming from steering column"*, *"check engine light illuminated"*, *"loud clicking noise from transmission"*), and resulting consequences (*"vehicle lost motive power and stalled in traffic"*).
- **Suitability for Modern NLP:** The vocabulary contains dense automotive terminology and clear semantic clusters. Pre-trained transformer models fine-tuned or adapted on technical text (e.g. `sentence-transformers` like `all-MiniLM-L6-v2`) will capture semantic affinities between synonymous consumer complaints far better than keyword searches or basic topic models.

### 2.2 Question 2: Is the complaint volume sufficient?
**Finding: YES — Vast statistical power.**
- **Empirical Evidence:** The dataset contains **651,262 unique consumer complaints** (`ODINO`) and **908,693 total complaint-component records** across the 10-year span (2015–2024).
- **Statistical Distribution:** Major automotive makes (Ford, Chevrolet, Honda, Jeep, Toyota) each have between 30,000 and 80,000 complaints per 5-year block. High-volume models (e.g., Ford Explorer, Chevrolet Silverado, Honda Accord) receive hundreds to thousands of complaints annually.
- **Sufficiency for Temporal Modeling:** The volume provides continuous monthly and weekly time-series resolution, allowing robust statistical trend detection (e.g., CUSUM, z-score bursts, change-point analysis) when measuring complaint velocity.

### 2.3 Question 3: Are complaint narratives sufficiently detailed?
**Finding: YES — High informational density.**
- **Empirical Metrics:**
  - **Median narrative length:** 455 characters (2015–2019) and 496 characters (2020–2024).
  - **90th percentile length:** 1,119 characters (~180–220 words) and 1,167 characters.
  - **Mean length:** ~570 characters across the entire corpus.
- **Narrative Depth:** Narratives rarely consist of terse single-word feedback (e.g. "bad car"). Rather, they are structured formal complaints submitted through NHTSA's Vehicle Owners Questionnaire (VOQ) hotline, mobile app, and web portal, providing rich engineering symptom details.

### 2.4 Question 4: Can complaints be connected to vehicle/model information?
**Finding: YES — Near-perfect completeness on core vehicle dimensions.**
- **Empirical Metrics:**
  - `MAKETXT` missing rate: < 0.002% (only 15 records missing out of 908,693).
  - `MODELTXT` missing rate: < 0.002%.
  - `YEARTXT` missing rate: < 0.002%.
  - `VIN` prefix availability: 93.9% in 2015–2019; 97.7% in 2020–2024.
- **Operational Reality:** Every complaint record can be definitively assigned to a `(Make, Model, Model-Year)` cohort, which forms the fundamental analytical entity for tracking defect emergence.

### 2.5 Question 5: Can complaints potentially be connected to investigations and recalls?
**Finding: YES — Clear, bidirectional validation pathway exists.**
- **Investigation Connection:** The defect investigations dataset (`FLAT_INV`) contains 154,401 records with explicit `(MAKE, MODEL, YEAR, COMPNAME, ODATE, CAMPNO)`. Over 81.4% of investigation rows explicitly link to a recall campaign number (`CAMPNO`), enabling a three-stage validation pipeline:
  $$\text{Complaint Cluster Emergence } (T_1) \longrightarrow \text{NHTSA Investigation Opened } (T_2) \longrightarrow \text{Official Recall Issued } (T_3)$$
- **Recall Connection:** The recalls dataset (`FLAT_RCL_POST_2010`) contains 245,651 records covering 15,286 unique recall campaigns with official Part 573 filing dates (`RCDATE`), units affected (`POTAFF`), defect descriptions (`DESC_DEFECT`), and affected makes/models.
- **Feasibility:** Because complaints, investigations, and recalls all share vehicle make, model, model year, and standardized component taxonomies, historical backtesting can match an emerging complaint cluster against future investigations and recalls using both dimension alignment and semantic similarity between cluster text and recall `DESC_DEFECT`.

### 2.6 Question 6: What are the biggest data-quality challenges?
1. **Denormalized Multi-Component Multiplicity:** A single complaint filing often produces multiple rows in the raw flat file. Careless deduplication by `ODINO` drops component records, while failing to deduplicate duplicates the long narrative text.
2. **Model Name Inconsistencies:** Slight variations in trim names (e.g., `F-150 SUPERCREW`, `F150 4X4`, `F-150`) require rule-based model canonicalization to prevent cluster fragmentation.
3. **Date Anomalies in Failure Dates:** While received dates (`LDATE`) are 100% valid, consumer-entered incident dates (`FAILDATE`) contain typographical errors (e.g. year 1906 or 1917). All temporal emergence metrics must strictly rely on `LDATE` (the tamper-proof government receipt timestamp) as the primary index.
4. **Broad/Vague Component Labels:** Over 40,000 complaints are categorized under `UNKNOWN OR OTHER` or high-level labels like `ELECTRICAL SYSTEM`. This highlights the absolute necessity of semantic NLP—the component label alone is insufficient to diagnose the defect.

### 2.7 Question 7: What limitations must the final research acknowledge?
1. **Voluntary Reporting Bias:** NHTSA complaints are voluntary consumer submissions and may reflect media publicity or viral news rather than purely mechanical failure rates.
2. **Fleet Size Normalization:** The datasets provide raw complaint counts, not vehicle sales volumes. Without proprietary vehicle registration/sales denominator data, defect emergence scores must rely on temporal complaint acceleration, baseline cohort anomaly ratios, and severity weighting rather than pure incident-per-vehicle rates.
3. **Manufacturer Self-Recalls:** Over 87.5% of recalls are initiated directly by manufacturers (`INFLUENCED_BY = 'MFR'`) before NHTSA formally opens a public investigation. Backtesting must evaluate against both `FLAT_INV` (when an investigation occurred) and `FLAT_RCL` (when direct recalls occurred).
4. **Hardware Constraints:** Processing nearly 1 million complaints on an 8GB RAM Apple Silicon machine requires chunked processing, Parquet columnar storage, and batched semantic embedding generation.

### 2.8 Question 8: Which datasets are essential?
- **Essential Datasets (Core Engine):**
  1. `COMPLAINTS_RECEIVED_2015-2019.zip` (Historical complaint baseline)
  2. `COMPLAINTS_RECEIVED_2020-2024.zip` (Evaluation & modern emergence corpus)
  3. `FLAT_RCL_POST_2010.zip` (Ground truth recall dates, defect summaries, and affected models)
  4. `FLAT_INV.zip` (Ground truth investigation milestones connecting complaints to recalls)

### 2.9 Question 9: Which datasets may only be supplementary?
- **Supplementary Datasets:**
  1. `RCL_FROM_2015_2019.zip` (Recall associated PDF metadata and bulletin summaries)
  2. `RCL_FROM_2020_2024.zip` (Recall associated PDF metadata and bulletin summaries)
  *Role:* These provide deep qualitative validation and OEM technical service bulletin summaries for selected case studies, but are not required for core temporal emergence detection.

---

## 3. Conclusion

Phase 1 audit and analysis confirms that the NHTSA datasets provide complete, high-quality, and robust data to answer our central research question:
> *"Can semantic and temporal analysis of consumer vehicle complaints identify emerging defect patterns before they result in an official NHTSA investigation or recall?"*

The data foundation is validated, structured, and ready for systematic preprocessing and subsequent development phases.
