import sys
import os
from visualize_treatments import run_treatment_visualization

# Check if command-line arguments provided
if len(sys.argv) < 2:
    print("Usage: python run_visualize_treatments.py <analysis_output_dir> [figure_output_dir]")
    print("Example: python run_visualize_treatments.py test_data_150patients")
    print("         python run_visualize_treatments.py test_data_150patients test_data_150patients/figures")
    sys.exit(1)

analysis_dir = sys.argv[1]
figure_dir = sys.argv[2] if len(sys.argv) > 2 else None

# Use third argument as raw data path if provided, otherwise construct from convention
if len(sys.argv) > 3:
    raw_data_path = sys.argv[3]
else:
    # Construct raw data path (convention: ../<dirname>.csv)
    raw_data_path = os.path.join('..', f'{analysis_dir}.csv')

if not os.path.exists(raw_data_path):
    print(f"Warning: Raw data file not found at {raw_data_path}")
    print("  Lab value violin plots will be skipped.")
    raw_data_path = None

# Run the treatment visualization
print(f"Generating treatment visualizations from: {analysis_dir}")
if figure_dir:
    print(f"Saving figures to: {figure_dir}")
else:
    print(f"Saving figures to: {analysis_dir}/figures")

visualizer = run_treatment_visualization(analysis_dir, figure_dir, raw_data_path)

print("\nVisualization complete!")
