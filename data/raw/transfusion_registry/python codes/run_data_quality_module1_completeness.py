"""
Runner script for Data Quality Module 1: Completeness Analysis.

Analyzes completeness of medical staff-entered data across all major sections.

Usage:
    python3 run_data_quality_module1_completeness.py <data_file> <output_directory>

Example:
    python3 run_data_quality_module1_completeness.py ../test_data_150patients.csv test_data_150patients

Author: Elina Nuerenberg-Goloub with Claude Sonnet 4.5 by Anthropic
Date: 2025-10-22
"""

import sys
from data_quality_module1_completeness import run_completeness_analysis

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 run_data_quality_module1_completeness.py <data_file> <output_directory>")
        print("Example: python3 run_data_quality_module1_completeness.py ../test_data_150patients.csv test_data_150patients")
        sys.exit(1)

    data_file = sys.argv[1]
    output_dir = sys.argv[2]

    print(f"Running Data Quality Module 1: Completeness Analysis")
    print(f"Input file: {data_file}")
    print(f"Output directory: {output_dir}")
    print()

    completeness = run_completeness_analysis(data_file, output_dir)

    print("\nModule 1 (Completeness) analysis complete!")
