"""
Runner script for temporal volume analysis.

Calculates total volumes (ml, IU, mg) of blood products by month and quarter.

Usage:
    python3 run_temporal_volume_analysis.py <data_file> <output_directory>

Example:
    python3 run_temporal_volume_analysis.py ../test_data_150patients.csv test_data_150patients

Author: Elina Nuerenberg-Goloub with Claude Sonnet 4.5 by Anthropic
Date: 2025-10-21
"""

import sys
from descriptive_temporal_volumes import run_temporal_volume_analysis

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python run_temporal_volume_analysis.py <data_file> <output_directory>")
        print("Example: python run_temporal_volume_analysis.py ../test_data_150patients.csv test_data_150patients")
        sys.exit(1)

    data_file = sys.argv[1]
    output_dir = sys.argv[2]

    temporal = run_temporal_volume_analysis(data_file, output_dir)

    print("\nAnalysis complete! Results saved to:")
    print(f"  - {output_dir}/temporal_volumes_detailed.json")
    print(f"  - {output_dir}/temporal_volumes_monthly.txt")
    print(f"  - {output_dir}/temporal_volumes_quarterly.txt")
    print(f"  - {output_dir}/temporal_volumes_overall.txt")
    print(f"  - {output_dir}/temporal_volumes_combined.txt")
    print(f"  - {output_dir}/temporal_volumes_monthly.csv")
    print(f"  - {output_dir}/temporal_volumes_quarterly.csv")
    print(f"  - {output_dir}/temporal_volumes_overall.csv")
