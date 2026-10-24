"""
Comprehensive dataset auditing script for DEFECTRADAR Phase 1.
Processes all 6 NHTSA raw datasets in streams/chunks to adhere to 8GB RAM constraints.
"""

import csv
import io
import os
import zipfile
from collections import Counter, defaultdict
from datetime import datetime

CMPL_COLUMNS = [
    "CMPLID", "ODINO", "MFR_NAME", "MAKETXT", "MODELTXT", "YEARTXT",
    "CRASH", "FAILDATE", "FIRE", "INJURED", "DEATHS", "COMPDESC",
    "CITY", "STATE", "VIN", "DATEA", "LDATE", "MILES", "OCCURENCES",
    "CDESCR", "CMPL_TYPE", "POLICE_RPT_YN", "PURCH_DT", "ORIG_OWNER_YN",
    "ANTI_BRAKES_YN", "CRUISE_CONT_YN", "NUM_CYLS", "DRIVE_TRAIN",
    "FUEL_SYS", "FUEL_TYPE", "TRANS_TYPE", "VEH_SPEED", "DOT", "TIRE_SIZE",
    "LOC_OF_TIRE", "TIRE_FAIL_TYPE", "ORIG_EQUIP_YN", "MANUF_DT",
    "SEAT_TYPE", "RESTRAINT_TYPE", "DEALER_NAME", "DEALER_TEL",
    "DEALER_CITY", "DEALER_STATE", "DEALER_ZIP", "PROD_TYPE",
    "REPAIRED_YN", "MEDICAL_ATTN", "VEHICLES_TOWED_YN",
    "STATE_OF_INCIDENT", "VEHICLE_OPERATOR"
]

INV_COLUMNS = [
    "NHTSA_ACTION_NUMBER", "MAKE", "MODEL", "YEAR", "COMPNAME",
    "MFR_NAME", "ODATE", "CDATE", "CAMPNO", "SUBJECT", "SUMMARY"
]

RCL_COLUMNS = [
    "RECORD_ID", "CAMPNO", "MAKETXT", "MODELTXT", "YEARTXT", "MFGCAMPNO",
    "COMPNAME", "MFGNAME", "BGMAN", "ENDMAN", "RCLTYPECD", "POTAFF",
    "ODATE", "INFLUENCED_BY", "MFGTXT", "RCDATE", "DATEA", "RPNO",
    "FMVSS", "DESC_DEFECT", "CONEQUENCE_DEFECT", "CORRECTIVE_ACTION",
    "NOTES", "RCL_CMPT_ID", "MFR_COMP_NAME", "MFR_COMP_DESC",
    "MFR_COMP_PTNO", "DO_NOT_DRIVE", "PARK_OUTSIDE"
]

def parse_date_safely(val):
    if not val or len(val) != 8 or not val.isdigit():
        return None
    try:
        y, m, d = int(val[:4]), int(val[4:6]), int(val[6:8])
        if 1900 <= y <= 2030 and 1 <= m <= 12 and 1 <= d <= 31:
            return val
    except Exception:
        pass
    return None

def audit_complaint_file(zip_path, file_label):
    print(f"\n--- Auditing Complaint Dataset: {file_label} ({zip_path}) ---")
    file_size_bytes = os.path.getsize(zip_path)
    
    total_rows = 0
    missing_counts = defaultdict(int)
    unique_cmplids = set()
    odino_counts = Counter()
    odino_comp_map = defaultdict(set)
    
    min_ldate, max_ldate = "99999999", "00000000"
    min_faildate, max_faildate = "99999999", "00000000"
    min_datea, max_datea = "99999999", "00000000"
    
    valid_ldate_count = 0
    valid_faildate_count = 0
    valid_datea_count = 0
    
    crash_counter = Counter()
    fire_counter = Counter()
    injuries_total = 0
    deaths_total = 0
    prod_type_counter = Counter()
    top_makes = Counter()
    top_components = Counter()
    
    narrative_lengths = []
    zero_narrative_count = 0
    
    with zipfile.ZipFile(zip_path) as z:
        inner_name = z.namelist()[0]
        uncompressed_size = z.getinfo(inner_name).file_size
        with z.open(inner_name) as f:
            reader = io.BufferedReader(f, buffer_size=1024*1024)
            for line_b in reader:
                line = line_b.decode('latin-1', errors='replace').rstrip('\r\n')
                if not line:
                    continue
                total_rows += 1
                parts = line.split('\t')
                
                # Check column count
                col_len = len(parts)
                if col_len < len(CMPL_COLUMNS):
                    parts.extend([''] * (len(CMPL_COLUMNS) - col_len))
                
                cmpl_id = parts[0].strip()
                odino = parts[1].strip()
                mfr = parts[2].strip()
                make = parts[3].strip()
                model = parts[4].strip()
                year = parts[5].strip()
                crash = parts[6].strip()
                faildate = parts[7].strip()
                fire = parts[8].strip()
                inj = parts[9].strip()
                death = parts[10].strip()
                comp = parts[11].strip()
                city = parts[12].strip()
                state = parts[13].strip()
                vin = parts[14].strip()
                datea = parts[15].strip()
                ldate = parts[16].strip()
                miles = parts[17].strip()
                cdescr = parts[19].strip()
                prod_type = parts[45].strip()
                
                # Missing counts
                for i, col_name in enumerate(CMPL_COLUMNS):
                    val = parts[i].strip() if i < len(parts) else ''
                    if not val:
                        missing_counts[col_name] += 1
                
                if cmpl_id:
                    unique_cmplids.add(cmpl_id)
                if odino:
                    odino_counts[odino] += 1
                    if comp:
                        odino_comp_map[odino].add(comp)
                        
                # Date audits
                pd_ldate = parse_date_safely(ldate)
                if pd_ldate:
                    valid_ldate_count += 1
                    if pd_ldate < min_ldate: min_ldate = pd_ldate
                    if pd_ldate > max_ldate: max_ldate = pd_ldate
                
                pd_fail = parse_date_safely(faildate)
                if pd_fail:
                    valid_faildate_count += 1
                    if pd_fail < min_faildate: min_faildate = pd_fail
                    if pd_fail > max_faildate: max_faildate = pd_fail
                    
                pd_datea = parse_date_safely(datea)
                if pd_datea:
                    valid_datea_count += 1
                    if pd_datea < min_datea: min_datea = pd_datea
                    if pd_datea > max_datea: max_datea = pd_datea
                
                crash_counter[crash] += 1
                fire_counter[fire] += 1
                if inj.isdigit(): injuries_total += int(inj)
                if death.isdigit(): deaths_total += int(death)
                prod_type_counter[prod_type] += 1
                
                if make: top_makes[make] += 1
                if comp: top_components[comp] += 1
                
                n_len = len(cdescr)
                if n_len == 0:
                    zero_narrative_count += 1
                # Sample 10000 lengths for narrative percentiles to save memory
                if total_rows % 50 == 0:
                    narrative_lengths.append(n_len)
                    
    # Multi-component stats
    multi_comp_odinos = sum(1 for od, comps in odino_comp_map.items() if len(comps) > 1)
    max_comps_per_odino = max((len(comps) for comps in odino_comp_map.values()), default=0)
    odinos_with_multiple_rows = sum(1 for count in odino_counts.values() if count > 1)
    
    narrative_lengths.sort()
    p50_len = narrative_lengths[len(narrative_lengths)//2] if narrative_lengths else 0
    p90_len = narrative_lengths[int(len(narrative_lengths)*0.9)] if narrative_lengths else 0
    avg_len = sum(narrative_lengths)/len(narrative_lengths) if narrative_lengths else 0
    
    result = {
        "file_label": file_label,
        "zip_size_bytes": file_size_bytes,
        "uncompressed_bytes": uncompressed_size,
        "total_rows": total_rows,
        "columns_count": len(CMPL_COLUMNS),
        "unique_cmplids": len(unique_cmplids),
        "unique_odinos": len(odino_counts),
        "odinos_with_multiple_rows": odinos_with_multiple_rows,
        "multi_component_odinos": multi_comp_odinos,
        "max_components_per_odino": max_comps_per_odino,
        "ldate_range": (min_ldate, max_ldate),
        "valid_ldate_pct": (valid_ldate_count / total_rows) * 100 if total_rows else 0,
        "faildate_range": (min_faildate, max_faildate),
        "valid_faildate_pct": (valid_faildate_count / total_rows) * 100 if total_rows else 0,
        "crash_breakdown": dict(crash_counter),
        "fire_breakdown": dict(fire_counter),
        "injuries_total": injuries_total,
        "deaths_total": deaths_total,
        "prod_types": dict(prod_type_counter),
        "top_5_makes": top_makes.most_common(5),
        "top_5_components": top_components.most_common(5),
        "zero_narrative_count": zero_narrative_count,
        "narrative_len_p50": p50_len,
        "narrative_len_p90": p90_len,
        "narrative_len_avg": avg_len,
        "missing_counts": {k: missing_counts[k] for k in CMPL_COLUMNS}
    }
    return result

def audit_investigation_file(zip_path):
    print(f"\n--- Auditing Investigation Dataset ({zip_path}) ---")
    file_size_bytes = os.path.getsize(zip_path)
    total_rows = 0
    unique_actions = set()
    campno_count = 0
    unique_campnos = set()
    missing_counts = defaultdict(int)
    
    min_odate, max_odate = "99999999", "00000000"
    min_cdate, max_cdate = "99999999", "00000000"
    top_makes = Counter()
    top_components = Counter()
    prefix_counter = Counter()
    
    with zipfile.ZipFile(zip_path) as z:
        inner_name = z.namelist()[0]
        uncompressed_size = z.getinfo(inner_name).file_size
        with z.open(inner_name) as f:
            reader = io.BufferedReader(f, buffer_size=1024*1024)
            for line_b in reader:
                line = line_b.decode('latin-1', errors='replace').rstrip('\r\n')
                if not line:
                    continue
                total_rows += 1
                parts = line.split('\t')
                if len(parts) < len(INV_COLUMNS):
                    parts.extend([''] * (len(INV_COLUMNS) - len(parts)))
                    
                action = parts[0].strip()
                make = parts[1].strip()
                model = parts[2].strip()
                year = parts[3].strip()
                comp = parts[4].strip()
                mfr = parts[5].strip()
                odate = parts[6].strip()
                cdate = parts[7].strip()
                campno = parts[8].strip()
                subject = parts[9].strip()
                summary = parts[10].strip()
                
                for i, col_name in enumerate(INV_COLUMNS):
                    val = parts[i].strip() if i < len(parts) else ''
                    if not val:
                        missing_counts[col_name] += 1
                        
                if action:
                    unique_actions.add(action)
                    # Extract investigation type prefix (e.g. PE, EA, RQ, DP, AQ)
                    prefix = ''.join([c for c in action if c.isalpha()])
                    prefix_counter[prefix] += 1
                    
                if campno:
                    campno_count += 1
                    unique_campnos.add(campno)
                    
                pd_o = parse_date_safely(odate)
                if pd_o:
                    if pd_o < min_odate: min_odate = pd_o
                    if pd_o > max_odate: max_odate = pd_o
                pd_c = parse_date_safely(cdate)
                if pd_c:
                    if pd_c < min_cdate: min_cdate = pd_c
                    if pd_c > max_cdate: max_cdate = pd_c
                    
                if make: top_makes[make] += 1
                if comp: top_components[comp] += 1

    return {
        "zip_size_bytes": file_size_bytes,
        "uncompressed_bytes": uncompressed_size,
        "total_rows": total_rows,
        "columns_count": len(INV_COLUMNS),
        "unique_actions": len(unique_actions),
        "rows_with_campno": campno_count,
        "unique_campnos": len(unique_campnos),
        "odate_range": (min_odate, max_odate),
        "cdate_range": (min_cdate, max_cdate),
        "inv_types": dict(prefix_counter.most_common(10)),
        "top_5_makes": top_makes.most_common(5),
        "top_5_components": top_components.most_common(5),
        "missing_counts": {k: missing_counts[k] for k in INV_COLUMNS}
    }

def audit_flat_rcl_file(zip_path):
    print(f"\n--- Auditing FLAT_RCL Dataset ({zip_path}) ---")
    file_size_bytes = os.path.getsize(zip_path)
    total_rows = 0
    unique_record_ids = set()
    campno_counter = Counter()
    missing_counts = defaultdict(int)
    
    min_rcdate, max_rcdate = "99999999", "00000000"
    min_odate, max_odate = "99999999", "00000000"
    top_makes = Counter()
    top_components = Counter()
    influenced_by_counter = Counter()
    rcl_type_counter = Counter()
    
    campaign_vehicle_map = defaultdict(set)
    
    with zipfile.ZipFile(zip_path) as z:
        inner_name = z.namelist()[0]
        uncompressed_size = z.getinfo(inner_name).file_size
        with z.open(inner_name) as f:
            reader = io.BufferedReader(f, buffer_size=1024*1024)
            for line_b in reader:
                line = line_b.decode('latin-1', errors='replace').rstrip('\r\n')
                if not line:
                    continue
                total_rows += 1
                parts = line.split('\t')
                if len(parts) < len(RCL_COLUMNS):
                    parts.extend([''] * (len(RCL_COLUMNS) - len(parts)))
                    
                rec_id = parts[0].strip()
                campno = parts[1].strip()
                make = parts[2].strip()
                model = parts[3].strip()
                year = parts[4].strip()
                comp = parts[6].strip()
                mfg = parts[7].strip()
                rcl_type = parts[10].strip()
                odate = parts[12].strip()
                inf_by = parts[13].strip()
                rcdate = parts[15].strip()
                
                for i, col_name in enumerate(RCL_COLUMNS):
                    val = parts[i].strip() if i < len(parts) else ''
                    if not val:
                        missing_counts[col_name] += 1
                        
                if rec_id:
                    unique_record_ids.add(rec_id)
                if campno:
                    campno_counter[campno] += 1
                    if make and model and year:
                        campaign_vehicle_map[campno].add(f"{make}|{model}|{year}")
                        
                pd_rc = parse_date_safely(rcdate)
                if pd_rc:
                    if pd_rc < min_rcdate: min_rcdate = pd_rc
                    if pd_rc > max_rcdate: max_rcdate = pd_rc
                    
                pd_o = parse_date_safely(odate)
                if pd_o:
                    if pd_o < min_odate: min_odate = pd_o
                    if pd_o > max_odate: max_odate = pd_o
                    
                if make: top_makes[make] += 1
                if comp: top_components[comp] += 1
                if inf_by: influenced_by_counter[inf_by] += 1
                if rcl_type: rcl_type_counter[rcl_type] += 1

    multi_model_campaigns = sum(1 for c, v in campaign_vehicle_map.items() if len(v) > 1)
    max_models_in_campaign = max((len(v) for v in campaign_vehicle_map.values()), default=0)
    
    return {
        "zip_size_bytes": file_size_bytes,
        "uncompressed_bytes": uncompressed_size,
        "total_rows": total_rows,
        "columns_count": len(RCL_COLUMNS),
        "unique_record_ids": len(unique_record_ids),
        "unique_campnos": len(campno_counter),
        "multi_model_campaigns": multi_model_campaigns,
        "max_models_in_campaign": max_models_in_campaign,
        "rcdate_range": (min_rcdate, max_rcdate),
        "odate_range": (min_odate, max_odate),
        "influenced_by": dict(influenced_by_counter),
        "rcl_types": dict(rcl_type_counter),
        "top_5_makes": top_makes.most_common(5),
        "top_5_components": top_components.most_common(5),
        "missing_counts": {k: missing_counts[k] for k in RCL_COLUMNS}
    }

def audit_rcl_csv_file(zip_path, file_label):
    print(f"\n--- Auditing RCL CSV Dataset: {file_label} ({zip_path}) ---")
    file_size_bytes = os.path.getsize(zip_path)
    total_rows = 0
    unique_nhtsa_ids = set()
    unique_doc_names = set()
    missing_counts = defaultdict(int)
    top_makes = Counter()
    doc_prefix_counter = Counter()
    
    with zipfile.ZipFile(zip_path) as z:
        inner_name = z.namelist()[0]
        uncompressed_size = z.getinfo(inner_name).file_size
        with z.open(inner_name) as f:
            text_stream = io.TextIOWrapper(f, encoding='utf-8', errors='replace')
            reader = csv.reader(text_stream)
            headers = next(reader)
            for row in reader:
                if not row:
                    continue
                total_rows += 1
                nhtsa_id = row[0].strip() if len(row) > 0 else ''
                doc_name = row[1].strip() if len(row) > 1 else ''
                make = row[2].strip() if len(row) > 2 else ''
                model = row[3].strip() if len(row) > 3 else ''
                year = row[4].strip() if len(row) > 4 else ''
                summary = row[5].strip() if len(row) > 5 else ''
                
                for idx, h in enumerate(headers):
                    val = row[idx].strip() if idx < len(row) else ''
                    if not val:
                        missing_counts[h] += 1
                        
                if nhtsa_id: unique_nhtsa_ids.add(nhtsa_id)
                if doc_name:
                    unique_doc_names.add(doc_name)
                    doc_prefix = doc_name.split('-')[0] if '-' in doc_name else 'OTHER'
                    doc_prefix_counter[doc_prefix] += 1
                if make: top_makes[make] += 1

    return {
        "file_label": file_label,
        "zip_size_bytes": file_size_bytes,
        "uncompressed_bytes": uncompressed_size,
        "total_rows": total_rows,
        "headers": headers,
        "unique_nhtsa_ids": len(unique_nhtsa_ids),
        "unique_doc_names": len(unique_doc_names),
        "doc_types": dict(doc_prefix_counter.most_common(10)),
        "top_5_makes": top_makes.most_common(5),
        "missing_counts": dict(missing_counts)
    }

if __name__ == '__main__':
    import json
    results = {}
    results['cmpl_2015_2019'] = audit_complaint_file('data/raw/COMPLAINTS_RECEIVED_2015-2019.zip', 'Complaints 2015-2019')
    results['cmpl_2020_2024'] = audit_complaint_file('data/raw/COMPLAINTS_RECEIVED_2020-2024.zip', 'Complaints 2020-2024')
    results['inv'] = audit_investigation_file('data/raw/FLAT_INV.zip')
    results['flat_rcl'] = audit_flat_rcl_file('data/raw/FLAT_RCL_POST_2010.zip')
    results['rcl_csv_2015_2019'] = audit_rcl_csv_file('data/raw/RCL_FROM_2015_2019.zip', 'Recall Docs 2015-2019')
    results['rcl_csv_2020_2024'] = audit_rcl_csv_file('data/raw/RCL_FROM_2020_2024.zip', 'Recall Docs 2020-2024')
    
    with open('data/audit_summary.json', 'w') as out:
        json.dump(results, out, indent=2)
    print("\nAudit completed successfully! Saved to data/audit_summary.json")
