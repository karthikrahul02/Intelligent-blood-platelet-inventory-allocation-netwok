"""
Runner script for lab value data quality checks.

Usage:
    python3 run_lab_value_quality.py <raw_data_path> <output_dir>

Example:
    python3 run_lab_value_quality.py ../test_data_150patients.csv test_data_150patients

This will:
1. Load the raw data file
2. Run unit detection for all configured lab parameters
3. Generate lab_value_quality_report.txt (human-readable report)
4. Export lab_value_unit_issues.csv (problematic records for manual review)
"""

import sys
import os
from lab_value_quality import run_lab_value_quality_check

if len(sys.argv) < 3:
    print("Usage: python3 run_lab_value_quality.py <raw_data_path> <output_dir>")
    print("Example: python3 run_lab_value_quality.py ../test_data_150patients.csv test_data_150patients")
    sys.exit(1)

raw_data_path = sys.argv[1]
output_dir = sys.argv[2]

if not os.path.exists(raw_data_path):
    print(f"Error: Raw data file not found: {raw_data_path}")
    sys.exit(1)

print(f"Running lab value quality check...")
print(f"  Input: {raw_data_path}")
print(f"  Output: {output_dir}")

checker = run_lab_value_quality_check(raw_data_path, output_dir)

print("\nQuality check complete!")
print(f"  Review: {output_dir}/lab_value_quality_report.txt")
print(f"  Problem records: {output_dir}/lab_value_unit_issues.csv")
