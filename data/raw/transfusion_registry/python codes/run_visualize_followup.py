import sys
import os
from visualize_followup import run_followup_visualization

# Check if command-line arguments provided
if len(sys.argv) < 2:
    print("Usage: python run_visualize_followup.py <analysis_output_dir> [figure_output_dir]")
    print("Example: python run_visualize_followup.py test_data_150patients")
    print("         python run_visualize_followup.py test_data_150patients test_data_150patients/figures")
    sys.exit(1)

analysis_dir = sys.argv[1]
figure_dir = sys.argv[2] if len(sys.argv) > 2 else None

# Run the follow-up visualization
print(f"Generating follow-up visualizations from: {analysis_dir}")
if figure_dir:
    print(f"Saving figures to: {figure_dir}")
else:
    print(f"Saving figures to: {analysis_dir}/figures")

visualizer = run_followup_visualization(analysis_dir, figure_dir)

print("\nVisualization complete!")
