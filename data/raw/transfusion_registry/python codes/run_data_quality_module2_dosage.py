"""
Runner script for Data Quality Module 2: Dosage Consistency.

Checks dosage data for unit consistency and identifies anomalies.

Usage:
    python3 run_data_quality_module2_dosage.py <data_file> <output_directory>

Example:
    python3 run_data_quality_module2_dosage.py ../test_data_150patients.csv test_data_150patients

Author: Elina Nuerenberg-Goloub with Claude Sonnet 4.5 by Anthropic
Date: 2025-10-23
"""

import sys
from data_quality_module2_dosage import run_dosage_analysis

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 run_data_quality_module2_dosage.py <data_file> <output_directory>")
        print("Example: python3 run_data_quality_module2_dosage.py ../test_data_150patients.csv test_data_150patients")
        sys.exit(1)

    data_file = sys.argv[1]
    output_dir = sys.argv[2]

    print(f"Running Data Quality Module 2: Dosage Consistency")
    print(f"Input file: {data_file}")
    print(f"Output directory: {output_dir}")
    print()

    dosage = run_dosage_analysis(data_file, output_dir)

    print("\nModule 2 (Dosage Consistency) analysis complete!")
