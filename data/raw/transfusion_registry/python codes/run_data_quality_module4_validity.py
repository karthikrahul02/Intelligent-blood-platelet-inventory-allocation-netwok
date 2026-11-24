"""
Runner script for Data Quality Module 4: Data Validity.

Checks if values fall within clinically plausible ranges.

Usage:
    python3 run_data_quality_module4_validity.py <data_file> <output_directory>

Example:
    python3 run_data_quality_module4_validity.py ../test_data_150patients.csv test_data_150patients

Author: Elina Nuerenberg-Goloub with Claude Sonnet 4.5 by Anthropic
Date: 2025-10-23
"""

import sys
from data_quality_module4_validity import run_validity_analysis

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 run_data_quality_module4_validity.py <data_file> <output_directory>")
        print("Example: python3 run_data_quality_module4_validity.py ../test_data_150patients.csv test_data_150patients")
        sys.exit(1)

    data_file = sys.argv[1]
    output_dir = sys.argv[2]

    print(f"Running Data Quality Module 4: Data Validity")
    print(f"Input file: {data_file}")
    print(f"Output directory: {output_dir}")
    print()

    validity = run_validity_analysis(data_file, output_dir)

    print("\nModule 4 (Data Validity) analysis complete!")
