# DEFECTRADAR — Phase 1: Data Dictionary

This document details the field-level definitions, physical types, NHTSA layout mappings, semantic roles, and data considerations across the NHTSA datasets used in **DEFECTRADAR**.

## Source attribution and authorship boundary

NHTSA source material includes raw field names, positions, official definitions, and source-file layouts. Refer to the NHTSA [Datasets and APIs inventory](https://www.nhtsa.gov/nhtsa-datasets-and-apis), the official [complaint layout (`CMPL.txt`)](https://static.nhtsa.gov/odi/ffdd/cmpl/CMPL.txt), [investigation layout (`INV.txt`)](https://static.nhtsa.gov/odi/ffdd/inv/INV.txt), [recall layout (`RCL.txt`)](https://static.nhtsa.gov/odi/ffdd/rcl/RCL.txt), and [recall import instructions](https://static.nhtsa.gov/odi/ffdd/rcl/Import_Instructions_Recalls.pdf). The inventory lists `RCL.txt` as a recall variable list. Browser/web previews did not render its direct endpoint, but a direct `curl` retrieval succeeded on 2026-10-25 (see [data audit](data_audit.md)); the retrieved layout is marked `Last Updated May 2025` and is the primary source for `FLAT_RCL` widths. The import-instructions PDF is an older corroborating NHTSA reference. Source field names, positions, and documented widths are attributed to these NHTSA materials. Local missingness statistics, canonical mappings, normalization notes, and interpretations are project-authored. Recall-document CSV value descriptions are project-authored summaries of source-supplied fields. This is schema documentation only: no complaint row values or narratives are reproduced. These links provide provenance, not a license or redistribution grant for NHTSA material.

---

## 1. Complaint Dataset Mapping & Field Dictionary

The raw complaint files (`COMPLAINTS_RECEIVED_2015-2019.txt` and `COMPLAINTS_RECEIVED_2020-2024.txt`) follow NHTSA's 51-column tab-delimited flat file specification (`FLAT_CMPL`).

### 1.1 Core Concept to NHTSA Column Mapping

| Conceptual Field | Actual NHTSA Column Name | Field # | Raw Type | Missing % (2015-2024) | Description & Value Domain |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Complaint ID** | `CMPLID` | 1 | `CHAR(9)` | 0.00% | NHTSA internal sequence identifier. Unique for each `(Complaint, Component)` physical row. |
| **ODI Number** | `ODINO` | 2 | `CHAR(9)` | 0.00% | NHTSA case reference number. Identifies the distinct complaint report. One `ODINO` can have multiple rows (one per failed component). |
| **Manufacturer** | `MFR_NAME` | 3 | `CHAR(40)` | <0.002% | Official corporate manufacturer name as supplied by NHTSA. |
| **Make** | `MAKETXT` | 4 | `CHAR(25)` | <0.002% | Vehicle make/brand as supplied in uppercase. |
| **Model** | `MODELTXT` | 5 | `CHAR(256)` | <0.002% | Vehicle model text; may contain trim/submodel tokens. |
| **Model Year** | `YEARTXT` | 6 | `CHAR(4)` | <0.002% | Model year (`YYYY`). Note: `9999` denotes unknown or not applicable. |
| **Crash Flag** | `CRASH` | 7 | `CHAR(1)` | 0.00% | Crash involvement: `'Y'` (Yes) or `'N'` (No). 5.2% are `'Y'`. |
| **Incident/Failure Date** | `FAILDATE` | 8 | `CHAR(8)` | 0.00% | Date failure occurred (`YYYYMMDD`). Occasional historical typographical errors require sanity filtering. |
| **Fire Flag** | `FIRE` | 9 | `CHAR(1)` | 0.00% | Fire involvement: `'Y'` (Yes) or `'N'` (No). 2.1% are `'Y'`. |
| **Injuries** | `INJURED` | 10 | `NUMBER(2)` | 0.00% | Number of persons injured in the incident ($0$ if none). |
| **Deaths** | `DEATHS` | 11 | `NUMBER(2)` | 0.00% | Number of fatalities in the incident ($0$ if none). |
| **Component** | `COMPDESC` | 12 | `CHAR(128)` | <0.001% | NHTSA-supplied standardized component taxonomy string, often hierarchical and colon-delimited. |
| **City** | `CITY` | 13 | `CHAR(30)` | 0.00% | Complainant city of residence. |
| **State** | `STATE` | 14 | `CHAR(2)` | 0.00% | Complainant US state postal code (e.g., `CA`, `TX`, `FL`). |
| **VIN** | `VIN` | 15 | `CHAR(11)` | 6.06% | First 11 characters of vehicle VIN (WMI + VDS), anonymized by NHTSA to omit serial number. |
| **Date Added** | `DATEA` | 16 | `CHAR(8)` | 0.00% | Internal date record was entered into the NHTSA database (`YYYYMMDD`). |
| **Received Date** | `LDATE` | 17 | `CHAR(8)` | 0.00% | Date complaint was formally received by NHTSA (`YYYYMMDD`). **Critical timestamp for temporal simulation**. |
| **Mileage** | `MILES` | 18 | `NUMBER(7)` | 42.58% | Vehicle odometer mileage at the time of failure. |
| **Complaint Narrative** | `CDESCR` | 20 | `CHAR(2048)`| <0.001% | Full consumer free-text narrative describing the failure symptom, driving speed, warning lights, and consequences. |
| **Complaint Source** | `CMPL_TYPE` | 21 | `CHAR(4)` | 0.00% | Intake channel code: `IVOQ` (Web), `EVOQ` (Hotline), `MAVQ`/`MIVQ` (Mobile App), `VOQ` (Paper Form), `RC` (Recall Petition). |
| **Police Report** | `POLICE_RPT_YN` | 22 | `CHAR(1)` | 0.00% | `'Y'` or `'N'` indicating if a formal police report was filed. |
| **Purchase Date** | `PURCH_DT` | 23 | `CHAR(8)` | 98.51% | Date vehicle was purchased (`YYYYMMDD`). |
| **Original Owner** | `ORIG_OWNER_YN` | 24 | `CHAR(1)` | 1.14% | `'Y'` or `'N'` indicating original vehicle ownership. |
| **Anti-Lock Brakes** | `ANTI_BRAKES_YN`| 25 | `CHAR(1)` | 1.14% | `'Y'` or `'N'` indicating presence of ABS. |
| **Cruise Control** | `CRUISE_CONT_YN`| 26 | `CHAR(1)` | 1.14% | `'Y'` or `'N'` indicating presence of cruise control. |
| **Vehicle Speed** | `VEH_SPEED` | 32 | `NUMBER(3)` | 42.18% | Approximate vehicle speed (MPH) when failure occurred. |
| **Product Type** | `PROD_TYPE` | 46 | `CHAR(4)` | <0.002% | Product category: `'V'` (Vehicle: 98.8%), `'T'` (Tire), `'E'` (Equipment), `'C'` (Child Restraint). |
| **Medical Attention**| `MEDICAL_ATTN` | 48 | `CHAR(1)` | 0.00% | `'Y'` or `'N'` indicating whether medical attention was required. |
| **Vehicle Towed** | `VEHICLES_TOWED_YN`| 49| `CHAR(1)` | 1.14% | `'Y'` or `'N'` indicating if the vehicle was towed from the scene. |
| **State of Incident**| `STATE_OF_INCIDENT`| 50 | `CHAR(2)` | 100.0% | Added in April 2026 NHTSA schema update; blank in historical 2015-2024 dumps. |
| **Vehicle Operator** | `VEHICLE_OPERATOR` | 51 | `CHAR(40)`| 100.0% | Added in April 2026 NHTSA schema update; blank in historical 2015-2024 dumps. |

---

## 2. Investigation Dataset Dictionary (`FLAT_INV`)

The defect investigations file records official NHTSA investigations opened since 1972 (154,401 records, 11 tab-delimited columns).

**Source-specific campaign-number widths:** NHTSA's [investigation layout](https://static.nhtsa.gov/odi/ffdd/inv/INV.txt) defines `FLAT_INV.CAMPNO` as `CHAR(9)`. The current [recall layout (`RCL.txt`)](https://static.nhtsa.gov/odi/ffdd/rcl/RCL.txt), marked `Last Updated May 2025`, defines `FLAT_RCL.CAMPNO` as `CHAR(12)`; direct retrieval succeeded on 2026-10-25 after browser/web previews did not render it. The older [recall import instructions](https://static.nhtsa.gov/odi/ffdd/rcl/Import_Instructions_Recalls.pdf), Appendix A, corroborate `CHAR(12)` (field list dated March 14, 2008; instructions document dated February 2014). These are distinct source-file schemas, not a type contradiction. The local archive's exact source version was not independently compared, so this records the official layout rather than a local archive width measurement.

| Field # | Column Name | Type | Key Role | Description |
| :--- | :--- | :--- | :--- | :--- |
| 1 | `NHTSA_ACTION_NUMBER` | `CHAR(10)` | **PK** (Investigation ID) | Unique case action identifier. Prefix denotes phase:<br>• `PE`: Preliminary Evaluation (initial defect query)<br>• `EA`: Engineering Analysis (in-depth engineering probe)<br>• `DP`: Defect Petition<br>• `RQ`: Recall Query (investigation into recall adequacy)<br>• `AQ`: Audit Query |
| 2 | `MAKE` | `CHAR(25)` | Dimension | Vehicle make under investigation. |
| 3 | `MODEL` | `CHAR(256)` | Dimension | Vehicle model under investigation. |
| 4 | `YEAR` | `CHAR(4)` | Dimension | Vehicle model year under investigation. |
| 5 | `COMPNAME` | `CHAR(256)` | Dimension | Primary vehicle component under investigation. |
| 6 | `MFR_NAME` | `CHAR(40)` | Dimension | Vehicle manufacturer name. |
| 7 | `ODATE` | `CHAR(8)` | **Validation Milestone** | Date investigation was formally **Opened** (`YYYYMMDD`). Core milestone for early detection backtesting. |
| 8 | `CDATE` | `CHAR(8)` | Temporal | Date investigation was **Closed** (`YYYYMMDD`). Blank if investigation remains open. |
| 9 | `CAMPNO` | `CHAR(9)` | **FK** $\to$ Recall | NHTSA Recall Campaign Number resulting from this investigation (if a defect was confirmed and recall ordered). |
| 10 | `SUBJECT` | `CHAR(200)` | Text | NHTSA-supplied short title or subject for the investigation. |
| 11 | `SUMMARY` | `CHAR(6000)`| Text | Comprehensive investigation summary outlining defect mechanics, consumer failure reports received, engineering tests, and closing action. |

---

## 3. Safety Recall Dataset Dictionary (`FLAT_RCL_POST_2010`)

The post-2010 recalls file details safety-related defect and non-compliance campaigns (245,651 records, 29 tab-delimited columns).

For `FLAT_RCL`, the directly retrieved NHTSA `RCL.txt` layout (last updated May 2025) lists `CAMPNO CHAR(12)`, corroborated by the older import instructions. This is distinct from `FLAT_INV.CAMPNO CHAR(9)`. Preprocessing stores each source value as a trimmed, uppercase string without padding or truncating it to either declared width.

| Field # | Column Name | Type | Key Role | Description |
| :--- | :--- | :--- | :--- | :--- |
| 1 | `RECORD_ID` | `NUMBER(9)` | Row ID | Unique sequence identifier for each record row. |
| 2 | `CAMPNO` | `CHAR(12)` | **PK** (Campaign ID) | NHTSA Safety Recall Campaign Number, repeated across multiple affected models. |
| 3 | `MAKETXT` | `CHAR(25)` | Dimension | Affected vehicle make. |
| 4 | `MODELTXT` | `CHAR(256)` | Dimension | Affected vehicle model. |
| 5 | `YEARTXT` | `CHAR(4)` | Dimension | Affected model year (`YYYY`). |
| 6 | `MFGCAMPNO` | `CHAR(20)` | Dimension | Internal manufacturer recall campaign code (synthetic format example: `XXV-NNN`). |
| 7 | `COMPNAME` | `CHAR(256)` | Dimension | Component description affected by the recall. |
| 8 | `MFGNAME` | `CHAR(40)` | Dimension | Name of entity filing Part 573 Defect/Noncompliance report. |
| 9 | `BGMAN` | `CHAR(8)` | Temporal | Begin date of manufacturing of affected population (`YYYYMMDD`). |
| 10 | `ENDMAN` | `CHAR(8)` | Temporal | End date of manufacturing of affected population (`YYYYMMDD`). |
| 11 | `RCLTYPECD` | `CHAR(4)` | Dimension | Recall classification: `'V'` (Vehicle), `'E'` (Equipment), `'T'` (Tire), `'C'` (Child Restraint). |
| 12 | `POTAFF` | `NUMBER(9)` | Severity Metric | Potential number of units affected in the United States. |
| 13 | `ODATE` | `CHAR(8)` | Temporal | Date manufacturer officially notified owners (`YYYYMMDD`). |
| 14 | `INFLUENCED_BY` | `CHAR(36)` | Metadata | Originator: `'MFR'` (Manufacturer: 87.6%), `'ODI'` (NHTSA ODI Investigation: 11.7%), `'OVSC'` (Compliance: 0.8%). |
| 15 | `MFGTXT` | `CHAR(40)` | Dimension | Detailed manufacturer string. |
| 16 | `RCDATE` | `CHAR(8)` | **Validation Milestone** | Date Part 573 Defect Report was received by NHTSA (`YYYYMMDD`). **Ground truth date of recall**. |
| 17 | `DATEA` | `CHAR(8)` | Temporal | Date recall record was entered into NHTSA database. |
| 20 | `DESC_DEFECT` | `CHAR(6000)`| **Semantic Ground Truth** | Source field containing the official defect description. |
| 21 | `CONEQUENCE_DEFECT`| `CHAR(2000)`| Text | Source field containing the stated safety consequences. |
| 22 | `CORRECTIVE_ACTION`| `CHAR(6000)`| Text | Source field containing the stated corrective action. |
| 24 | `RCL_CMPT_ID` | `CHAR(27)` | Sub-ID | Unique identifier for the recalled component. |
| 28 | `DO_NOT_DRIVE` | `CHAR(3)` | Severity Flag | Urgent safety advisory: `'Yes'` or `'No'`. |
| 29 | `PARK_OUTSIDE` | `CHAR(3)` | Severity Flag | Urgent fire hazard advisory: `'Yes'` or `'No'`. |

---

## 4. Recall Associated Documents Dictionary (`RCL_FROM_...`)

CSV files containing document-level metadata for associated technical service bulletins, manufacturer notices, and remedy procedures.

| Column Header | Type | Description |
| :--- | :--- | :--- |
| `NHTSA ID` | `STRING` | Shortened campaign identifier supplied in the recall-document metadata; concrete campaign values are omitted. Its separate prefix mapping to `FLAT_RCL.CAMPNO` is not the exact investigation-to-recall matching used in historical evaluation. |
| `DOCUMENT NAME` | `STRING` | Source-supplied PDF docket filename; concrete filenames are omitted. |
| `MAKE` | `STRING` | Vehicle/Equipment Make. |
| `MODEL` | `STRING` | Vehicle/Equipment Model. |
| `MODEL YEAR` | `STRING` | Vehicle/Equipment Model Year (`9999` if across all years or equipment). |
| `SUMMARY` | `STRING` | Source-supplied document abstract. It may contain NHTSA- or manufacturer-authored text and is not reproduced here. |
