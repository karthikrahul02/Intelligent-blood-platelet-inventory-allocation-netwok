"""
Runner script for Data Quality Module 3: Follow-up Duplicates.

Analyzes follow-up survey duplicates and completion rates.

Usage:
    python3 run_data_quality_module3_followup_duplicates.py <data_file> <output_directory>

Example:
    python3 run_data_quality_module3_followup_duplicates.py ../test_data_150patients.csv test_data_150patients

Author: Elina Nuerenberg-Goloub with Claude Sonnet 4.5 by Anthropic
Date: 2025-10-22
"""

import sys
from data_quality_module3_followup_duplicates import run_followup_duplicates_analysis

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 run_data_quality_module3_followup_duplicates.py <data_file> <output_directory>")
        print("Example: python3 run_data_quality_module3_followup_duplicates.py ../test_data_150patients.csv test_data_150patients")
        sys.exit(1)

    data_file = sys.argv[1]
    output_dir = sys.argv[2]

    print(f"Running Data Quality Module 3: Follow-up Duplicates")
    print(f"Input file: {data_file}")
    print(f"Output directory: {output_dir}")
    print()

    analyzer = run_followup_duplicates_analysis(data_file, output_dir)

    print("\nModule 3 (Follow-up Duplicates) analysis complete!")
