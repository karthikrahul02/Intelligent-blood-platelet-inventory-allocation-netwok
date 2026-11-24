"""
Runner script for dosage visualization.

Usage:
    python run_visualize_dosages.py <analysis_output_dir> [figure_output_dir] [raw_data_path]

The raw_data_path is required for histogram generation. If not provided,
the script will look for a CSV file in the parent directory matching
the analysis_output_dir name (e.g., ../test_data_150patients.csv for test_data_150patients/).
"""

import sys
import os
from visualize_dosages import run_dosage_visualization

# Check if command-line arguments provided
if len(sys.argv) < 2:
    print("Usage: python run_visualize_dosages.py <analysis_output_dir> [figure_output_dir] [raw_data_path]")
    print("Example: python run_visualize_dosages.py test_data_150patients")
    print("         python run_visualize_dosages.py test_data_150patients test_data_150patients/figures ../test_data_150patients.csv")
    sys.exit(1)

analysis_dir = sys.argv[1]
figure_dir = sys.argv[2] if len(sys.argv) > 2 else None
raw_data_path = sys.argv[3] if len(sys.argv) > 3 else None

# Auto-detect raw data path if not provided
if raw_data_path is None:
    # Try to find CSV in parent directory matching analysis_dir name
    potential_path = os.path.join('..', f'{analysis_dir}.csv')
    if os.path.exists(potential_path):
        raw_data_path = potential_path
        print(f"Auto-detected raw data file: {raw_data_path}")
    else:
        print(f"Warning: Raw data file not found at {potential_path}")
        print("Histograms require raw data. Provide path as third argument.")

# Run the dosage visualization
print(f"Generating dosage visualizations from: {analysis_dir}")
if figure_dir:
    print(f"Saving figures to: {figure_dir}")
else:
    print(f"Saving figures to: {analysis_dir}/figures")

visualizer = run_dosage_visualization(analysis_dir, figure_dir, raw_data_path)

print("\nVisualization complete!")
