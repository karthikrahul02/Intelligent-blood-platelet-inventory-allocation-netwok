#!/usr/bin/env python3
"""
SNOMED Code Analysis Runner Script

Runs SNOMED code analysis on transfusion registry data.

Usage:
    python3 run_snomed_analysis.py <output_directory>

Example:
    python3 run_snomed_analysis.py test_data_150patients

This will:
1. Load data from ../test_data_150patients.csv
2. Calculate SNOMED coverage and frequency statistics
3. Create output directory test_data_150patients/SNOMED/ if it doesn't exist
4. Export results to that directory

Author: Elina Nuerenberg-Goloub with Claude Opus 4.5 by Anthropic
Date: 2026-02-08
"""

import sys
import os

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from descriptive_snomed import run_snomed_analysis


def main():
    """Main entry point."""
    # Check arguments
    if len(sys.argv) < 2:
        print("Usage: python3 run_snomed_analysis.py <output_directory>")
        print("")
        print("Example: python3 run_snomed_analysis.py test_data_150patients")
        print("")
        print("This will:")
        print("  1. Load data from ../test_data_150patients.csv")
        print("  2. Calculate SNOMED coverage and frequency statistics")
        print("  3. Export results to test_data_150patients/SNOMED/")
        sys.exit(1)

    output_dir = sys.argv[1]

    # Derive data path from output directory name
    # Convention: output_dir is like "test_data_150patients", data is at "../test_data_150patients.csv"
    data_filename = os.path.basename(output_dir) + ".csv"
    data_path = os.path.join("..", data_filename)

    # Check if data file exists
    if not os.path.exists(data_path):
        # Try alternative: data file in same directory structure
        alt_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), data_filename)
        if os.path.exists(alt_path):
            data_path = alt_path
        else:
            print(f"Error: Data file not found: {data_path}")
            print(f"Also tried: {alt_path}")
            sys.exit(1)

    # Create output directory if needed
    os.makedirs(output_dir, exist_ok=True)

    # Run analysis
    snomed = run_snomed_analysis(
        data_path=data_path,
        output_dir=output_dir,
        top_n=5
    )

    print("\nDone!")
    print(f"\nNext steps:")
    print(f"  1. Open {output_dir}/SNOMED/snomed_codes_for_lookup.csv")
    print(f"  2. Look up each code at https://browser.ihtsdotools.org/")
    print(f"  3. Add descriptions to the 'description' column")
    print(f"  4. Save the file for documentation")


if __name__ == "__main__":
    main()
