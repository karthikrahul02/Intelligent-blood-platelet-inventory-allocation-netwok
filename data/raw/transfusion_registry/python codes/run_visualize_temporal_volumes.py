"""
Runner script for temporal volume visualizations.

Generates monthly line charts and quarterly bar charts for blood product volumes.

Usage:
    python3 run_visualize_temporal_volumes.py <analysis_output_directory>

Example:
    python3 run_visualize_temporal_volumes.py test_data_150patients

Author: Elina Nuerenberg-Goloub with Claude Sonnet 4.5 by Anthropic
Date: 2025-10-21
"""

import sys
from visualize_temporal_volumes import run_temporal_volume_visualization

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_visualize_temporal_volumes.py <analysis_output_directory>")
        print("Example: python run_visualize_temporal_volumes.py test_data_150patients")
        sys.exit(1)

    analysis_dir = sys.argv[1]
    figure_dir = sys.argv[2] if len(sys.argv) > 2 else None

    print(f"Generating temporal volume visualizations from: {analysis_dir}")
    if figure_dir:
        print(f"Saving figures to: {figure_dir}")
    else:
        print(f"Saving figures to: {analysis_dir}/figures")

    visualizer = run_temporal_volume_visualization(analysis_dir, figure_dir)

    print("\nVisualization complete!")
