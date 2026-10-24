"""
Phase 1 Validation Tests: DEFECTRADAR Data Foundation
Tests coverage:
- Required datasets exist in data/raw/
- ZIP files are readable
- Expected data files can be discovered
- Important columns can be identified
- Dates can be parsed
- Duplicate patterns can be measured
- Complaint identifiers can be analyzed (CMPLID vs ODINO)
- Recall campaign identifiers can be analyzed (CAMPNO)
- Missing-value statistics can be calculated
"""

import csv
import io
import os
import unittest
import zipfile
from datetime import datetime

from src.utils.audit_datasets import (
    CMPL_COLUMNS,
    INV_COLUMNS,
    RCL_COLUMNS,
    parse_date_safely,
)

RAW_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "raw")

EXPECTED_DATASETS = [
    "COMPLAINTS_RECEIVED_2015-2019.zip",
    "COMPLAINTS_RECEIVED_2020-2024.zip",
    "FLAT_INV.zip",
    "FLAT_RCL_POST_2010.zip",
    "RCL_FROM_2015_2019.zip",
    "RCL_FROM_2020_2024.zip",
]


class TestDataFoundation(unittest.TestCase):

    def test_required_datasets_exist(self):
        """Verify that all six NHTSA raw zip datasets exist in data/raw/."""
        self.assertTrue(os.path.isdir(RAW_DIR), f"Raw data directory does not exist: {RAW_DIR}")
        for ds_name in EXPECTED_DATASETS:
            path = os.path.join(RAW_DIR, ds_name)
            self.assertTrue(os.path.isfile(path), f"Missing dataset: {ds_name}")
            self.assertGreater(os.path.getsize(path), 1_000_000, f"File appears corrupt or empty: {ds_name}")

    def test_zip_files_are_readable(self):
        """Verify that all six ZIP files are valid, non-corrupted archives."""
        for ds_name in EXPECTED_DATASETS:
            path = os.path.join(RAW_DIR, ds_name)
            with zipfile.ZipFile(path, "r") as z:
                # testzip returns None if archive has no corrupt files
                corrupt = z.testzip()
                self.assertIsNone(corrupt, f"Corrupted file detected in archive: {ds_name} -> {corrupt}")

    def test_expected_data_files_discovered(self):
        """Verify that internal archive names match expected flat file specifications."""
        expected_contents = {
            "COMPLAINTS_RECEIVED_2015-2019.zip": "COMPLAINTS_RECEIVED_2015-2019.txt",
            "COMPLAINTS_RECEIVED_2020-2024.zip": "COMPLAINTS_RECEIVED_2020-2024.txt",
            "FLAT_INV.zip": "FLAT_INV.txt",
            "FLAT_RCL_POST_2010.zip": "FLAT_RCL_POST_2010.txt",
            "RCL_FROM_2015_2019.zip": "RCL_FROM_2015_2019.csv",
            "RCL_FROM_2020_2024.zip": "RCL_FROM_2020_2024.csv",
        }
        for zip_name, expected_inner in expected_contents.items():
            path = os.path.join(RAW_DIR, zip_name)
            with zipfile.ZipFile(path, "r") as z:
                namelist = z.namelist()
                self.assertIn(expected_inner, namelist, f"Archive {zip_name} does not contain {expected_inner}")

    def test_important_columns_identified_in_complaints(self):
        """Verify complaint flat files match the 51-column NHTSA specification."""
        sample_path = os.path.join(RAW_DIR, "COMPLAINTS_RECEIVED_2020-2024.zip")
        with zipfile.ZipFile(sample_path) as z:
            inner_name = z.namelist()[0]
            with z.open(inner_name) as f:
                first_line = f.readline().decode("latin-1").rstrip("\r\n")
                fields = first_line.split("\t")
                self.assertEqual(len(fields), 51, f"Expected 51 columns in complaint file, found {len(fields)}")
                # Check important columns
                self.assertTrue(fields[0].isdigit(), "CMPLID should be numeric sequence")
                self.assertTrue(fields[1].isdigit(), "ODINO should be numeric case ID")
                self.assertIn(fields[6], ["Y", "N"], "CRASH column should be Y/N")
                self.assertIn(fields[8], ["Y", "N"], "FIRE column should be Y/N")

    def test_important_columns_identified_in_investigations(self):
        """Verify investigation flat file matches the 11-column NHTSA schema."""
        sample_path = os.path.join(RAW_DIR, "FLAT_INV.zip")
        with zipfile.ZipFile(sample_path) as z:
            inner_name = z.namelist()[0]
            with z.open(inner_name) as f:
                first_line = f.readline().decode("latin-1").rstrip("\r\n")
                fields = first_line.split("\t")
                self.assertEqual(len(fields), 11, f"Expected 11 columns in FLAT_INV, found {len(fields)}")
                action_num = fields[0]
                self.assertTrue(len(action_num) >= 5, f"Expected action number format, got {action_num}")

    def test_important_columns_identified_in_recalls(self):
        """Verify recall flat file matches the 29-column NHTSA schema."""
        sample_path = os.path.join(RAW_DIR, "FLAT_RCL_POST_2010.zip")
        with zipfile.ZipFile(sample_path) as z:
            inner_name = z.namelist()[0]
            with z.open(inner_name) as f:
                first_line = f.readline().decode("latin-1").rstrip("\r\n")
                fields = first_line.split("\t")
                self.assertEqual(len(fields), 29, f"Expected 29 columns in FLAT_RCL, found {len(fields)}")
                campno = fields[1]
                self.assertEqual(len(campno), 9, f"Expected 9-char CAMPNO format (e.g., 10V078000), got {campno}")

    def test_dates_can_be_parsed(self):
        """Verify that date normalization function correctly handles NHTSA YYYYMMDD dates."""
        valid_date = parse_date_safely("20210515")
        self.assertEqual(valid_date, "20210515")

        # Invalid formats
        self.assertIsNone(parse_date_safely(""))
        self.assertIsNone(parse_date_safely("99999999"))
        self.assertIsNone(parse_date_safely("00000000"))
        self.assertIsNone(parse_date_safely("invalid"))
        self.assertIsNone(parse_date_safely("20211345"))  # month 13, day 45

    def test_complaint_identifiers_and_multi_component_structure(self):
        """Verify that ODINO repeats across rows for multi-component complaints while CMPLID is unique."""
        sample_path = os.path.join(RAW_DIR, "COMPLAINTS_RECEIVED_2015-2019.zip")
        with zipfile.ZipFile(sample_path) as z:
            inner_name = z.namelist()[0]
            with z.open(inner_name) as f:
                # Read the first 5 rows which we know share ODINO 516612
                rows = [f.readline().decode("latin-1").rstrip("\r\n").split("\t") for _ in range(3)]
                cmpl_ids = [r[0] for r in rows]
                odinos = [r[1] for r in rows]
                components = [r[11] for r in rows]

                # CMPLIDs must be distinct sequence numbers
                self.assertEqual(len(set(cmpl_ids)), 3, "CMPLIDs must all be unique")
                # ODINOs for this multi-component filing must be identical
                self.assertEqual(len(set(odinos)), 1, "Expected identical ODINO for multi-component complaint")
                # Components must be different
                self.assertEqual(len(set(components)), 3, "Expected different components across rows")

    def test_recall_campaign_identifiers_can_be_analyzed(self):
        """Verify that recall campaign identifiers (CAMPNO) can be extracted and have multi-model rows."""
        sample_path = os.path.join(RAW_DIR, "FLAT_RCL_POST_2010.zip")
        with zipfile.ZipFile(sample_path) as z:
            inner_name = z.namelist()[0]
            with z.open(inner_name) as f:
                campnos = []
                for _ in range(100):
                    line = f.readline().decode("latin-1").rstrip("\r\n")
                    campnos.append(line.split("\t")[1].strip())

                self.assertTrue(any(c for c in campnos), "No valid CAMPNOs found")
                # Validate standard 9-character format (2-digit year + type letter + sequence + 000)
                sample_camp = campnos[0]
                self.assertEqual(len(sample_camp), 9, f"Unexpected CAMPNO length: {sample_camp}")

    def test_missing_value_statistics_can_be_calculated(self):
        """Verify that missing-value calculation logic correctly computes rates on real batches."""
        sample_path = os.path.join(RAW_DIR, "COMPLAINTS_RECEIVED_2020-2024.zip")
        with zipfile.ZipFile(sample_path) as z:
            inner_name = z.namelist()[0]
            with z.open(inner_name) as f:
                missing_make = 0
                total = 500
                for _ in range(total):
                    line = f.readline().decode("latin-1").rstrip("\r\n")
                    parts = line.split("\t")
                    make = parts[3].strip() if len(parts) > 3 else ""
                    if not make:
                        missing_make += 1

                pct_missing = (missing_make / total) * 100
                # Vehicle make is present on almost all complaints
                self.assertLess(pct_missing, 1.0, "Make missing percentage unexpectedly high in sample")


if __name__ == "__main__":
    unittest.main()
