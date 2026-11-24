"""
Indication/Intervention Statistics Visualization Module

This module creates publication-quality visualizations for indication and intervention statistics
from transfusion registry data.

Input: indication_intervention_statistics_detailed.json
Output: PNG figures and CSV table with statistical visualizations

Visualizations created:
- Individual pie charts for each blood product showing indications (PNG)
- Indications summary table (CSV)

Author: Elina Nuerenberg-Goloub with Claude Sonnet 4.5 by Anthropic
Date: 10-20-2025
Revised on 2026-01-21 by Elina Nuerenberg-Goloub and Claude Opus 4.5
"""

import json
import os
import csv
import matplotlib
matplotlib.use('Agg')  # Headless-safe backend; must be set before importing pyplot
import matplotlib.pyplot as plt
from typing import Dict, Any, List, Tuple

# Colorblind-friendly color scheme (diverging warm-to-cold palette)
COLORS = {
    'primary': '#4575b4',      # Dark blue
    'secondary': '#74add1',    # Medium blue
    'highlight': '#d73027',    # Dark red
    'alternate': '#f46d43',    # Orange
    'color5': '#fdae61',       # Light orange
    'color6': '#abd9e9',       # Light blue 2
    'color7': '#e0f3f8',       # Light blue 1
    'color8': '#fee090',       # Yellow
    'unknown': '#b3b3b3',      # Gray - for "Other" category
    'background': '#fee090',   # Light yellow background
    'text': '#000000',         # Black text
}

# Full colorblind-friendly palette for charts with many categories (10 colors)
# "Other" is always gray regardless of size
COLOR_PALETTE_BY_SIZE = [
    '#a50026',  # 1st largest: Very dark red
    '#d73027',  # 2nd largest: Dark red
    '#f46d43',  # 3rd largest: Orange
    '#fdae61',  # 4th largest: Light orange
    '#fee090',  # 5th largest: Yellow
    '#e0f3f8',  # 6th largest: Light blue 1
    '#abd9e9',  # 7th largest: Light blue 2
    '#74add1',  # 8th largest: Medium blue
    '#4575b4',  # 9th largest: Dark blue
    '#313695',  # 10th largest: Very dark blue
]

# Consistent product colors across all visualizations
PRODUCT_COLORS = {
    'Red blood cell concentrate (RBC)': '#a50026',   # Very dark red
    'Fresh Frozen Plasma (FFP)': '#fee090',          # Yellow
    'Platelet concentrate (PC)': '#f46d43',          # Orange
    'PPSB': '#74add1',                               # Medium blue
    'Fibrinogen': '#4575b4',                         # Dark blue
    'Albumin': '#abd9e9',                            # Light blue 2
    'Antithrombin III (ATIII)': '#fdae61',           # Light orange
    'Iron i.v.': '#e0f3f8',                          # Light blue 1
    'Oral iron': '#b3b3b3',                          # Gray
    'EPO': '#313695',                                # Very dark blue
    'Machine Autotransfusion (Cell Salvage)': '#d73027',  # Dark red
}

# Figure settings
FIGURE_DPI = 300
FONT_FAMILY = 'Arial'
FONT_SIZE_TITLE = 24
FONT_SIZE_LABEL = 20
FONT_SIZE_TICK = 18
FONT_SIZE_LEGEND = 18


class IndicationVisualizer:
    """Creates visualizations for indication/intervention descriptive statistics."""

    def __init__(self, json_path: str, output_dir: str):
        """
        Initialize the visualizer.

        Args:
            json_path: Path to indication_intervention_statistics_detailed.json
            output_dir: Directory where visualizations will be saved
        """
        self.json_path = json_path
        self.output_dir = output_dir

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Load data
        with open(json_path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)

        # Set matplotlib defaults
        plt.rcParams['font.family'] = FONT_FAMILY
        plt.rcParams['font.size'] = FONT_SIZE_LABEL
        plt.rcParams['axes.labelsize'] = FONT_SIZE_LABEL
        plt.rcParams['axes.titlesize'] = FONT_SIZE_TITLE
        plt.rcParams['xtick.labelsize'] = FONT_SIZE_TICK
        plt.rcParams['ytick.labelsize'] = FONT_SIZE_TICK
        plt.rcParams['legend.fontsize'] = FONT_SIZE_LEGEND
        plt.rcParams['figure.dpi'] = FIGURE_DPI
        plt.rcParams['savefig.dpi'] = FIGURE_DPI
        plt.rcParams['savefig.bbox'] = 'tight'

    def _save_figure(self, fig, filename: str):
        """Save figure in PNG format only."""
        base_name = os.path.splitext(filename)[0]
        png_path = os.path.join(self.output_dir, f"{base_name}.png")

        fig.savefig(png_path, format='png', dpi=FIGURE_DPI, bbox_inches='tight',
                    facecolor='white', edgecolor='none')

        print(f"  Saved: {base_name}.png")

    def _sort_and_color_indications(self, indications: Dict[str, Any]) -> Tuple[List[str], List[int], List[float], List[str]]:
        """
        Sort indications by size and assign colors.
        "Other" is always gray and placed at the end of legend.

        Args:
            indications: Dictionary of indication names and their data

        Returns:
            Tuple of (sorted_labels, sorted_sizes, sorted_percentages, sorted_colors)
        """
        # Separate "Other" from rest
        other_data = None
        regular_indications = []

        for indication_name, indication_data in indications.items():
            if indication_name.lower() == 'other':
                other_data = (indication_name, indication_data['n'], indication_data['percent_of_documented'])
            else:
                regular_indications.append((indication_name, indication_data['n'], indication_data['percent_of_documented']))

        # Sort regular indications by size (descending)
        regular_indications.sort(key=lambda x: x[1], reverse=True)

        # Add "Other" at the end if it exists
        if other_data:
            regular_indications.append(other_data)

        # Extract sorted data
        labels = [x[0] for x in regular_indications]
        sizes = [x[1] for x in regular_indications]
        percentages = [x[2] for x in regular_indications]

        # Assign colors based on size (excluding "Other")
        colors = []
        non_other_count = len(regular_indications) - (1 if other_data else 0)

        for i, label in enumerate(labels):
            if label.lower() == 'other':
                colors.append(COLORS['unknown'])
            else:
                colors.append(COLOR_PALETTE_BY_SIZE[i % len(COLOR_PALETTE_BY_SIZE)])

        return labels, sizes, percentages, colors

    def plot_product_indications(self, product_name: str, product_data: Dict[str, Any]):
        """
        Create pie chart for a specific product's indications.
        Largest slice starts at south (270°) and goes clockwise.

        Args:
            product_name: Name of the blood product
            product_data: Data dictionary for this product
        """
        # Use documented_indications count, not total_administrations
        # This ensures the n shown matches the actual data in the chart
        documented_n = product_data['documented_indications']
        indications = product_data['indications']

        if not indications:
            print(f"  Skipping {product_name} (no indications)")
            return

        # Sort and color indications
        labels, sizes, percentages, colors = self._sort_and_color_indications(indications)

        # Add a residual wedge so the donut geometry matches the denominator
        # (documented_n). Legend percentages are relative to documented_n, so
        # without this wedge small categories would be visually inflated.
        classified_n = sum(sizes)
        residual_n = documented_n - classified_n
        if residual_n > 0 and documented_n > 0:
            labels.append('Not classified')
            sizes.append(residual_n)
            percentages.append(residual_n / documented_n * 100)
            colors.append('#d9d9d9')  # Neutral light gray

        # Create figure
        fig, ax = plt.subplots(figsize=(10, 6))

        # Create donut chart without percentages on slices
        # Start at 270° (south) and go clockwise (negative direction)
        wedges, texts = ax.pie(
            sizes,
            colors=colors,
            startangle=270,
            counterclock=False,
            wedgeprops={'edgecolor': 'white', 'linewidth': 0.5, 'width': 0.6}
        )

        # Add white circle in center to create donut effect
        centre_circle = plt.Circle((0, 0), 0.40, fc='white', linewidth=0)
        ax.add_artist(centre_circle)

        # Equal aspect ratio ensures circular pie
        ax.axis('equal')

        # Remove abbreviations from product name
        clean_product_name = product_name.split('(')[0].strip()

        # Title with documented indications N
        ax.set_title(f'{clean_product_name} (n = {documented_n})',
                     fontsize=FONT_SIZE_TITLE, fontweight='bold', pad=20)

        # Create legend with indication names and percentages (already sorted)
        legend_labels = []
        for label, pct in zip(labels, percentages):
            legend_labels.append(f'{label} ({pct:.1f}%)')

        ax.legend(legend_labels,
                  loc='center left',
                  bbox_to_anchor=(1.0, 0.5),
                  fontsize=FONT_SIZE_LEGEND,
                  frameon=True,
                  facecolor='white',
                  edgecolor='gray')

        # Save with clean filename
        safe_filename = clean_product_name.lower().replace(' ', '_').replace('/', '_')
        self._save_figure(fig, f'indication_{safe_filename}')
        plt.close(fig)

    def plot_all_product_indications(self):
        """Create pie charts for all products."""
        indications_data = self.data['administration_level']['indications_by_product']

        if not indications_data:
            print("  Skipping product indications (no data)")
            return

        for product_name, product_data in indications_data.items():
            print(f"  Creating indication chart for {product_name}...")
            self.plot_product_indications(product_name, product_data)

    def save_indications_summary_csv(self):
        """Save comprehensive indications summary table as CSV (sorted by size)."""
        indications_data = self.data['administration_level']['indications_by_product']

        if not indications_data:
            print("  Skipping indications summary CSV (no data)")
            return

        # Prepare table data
        table_data = []

        for product_name, product_data in indications_data.items():
            # Remove abbreviations from product name
            clean_product_name = product_name.split('(')[0].strip()
            total_n = product_data['total_administrations']
            indications = product_data['indications']

            # Sort indications (same as pie charts)
            labels, sizes, percentages, colors = self._sort_and_color_indications(indications)

            for label, size, pct in zip(labels, sizes, percentages):
                table_data.append([
                    clean_product_name,
                    label,
                    size,
                    f"{pct:.1f}%"
                ])

        if not table_data:
            print("  Skipping indications summary CSV (no valid data)")
            return

        # Write to CSV
        csv_path = os.path.join(self.output_dir, 'indication_summary.csv')
        headers = ['Product', 'Indication', 'Count', 'Percentage']

        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(table_data)

        print(f"  Saved: indication_summary.csv")

    def generate_all_visualizations(self):
        """Generate all indication visualizations."""
        print("\nGenerating indication/intervention visualizations...")

        print("  Creating product indication pie charts...")
        self.plot_all_product_indications()

        print("  Creating indications summary CSV...")
        self.save_indications_summary_csv()

        print(f"\nAll visualizations saved to: {self.output_dir}")


def run_indication_visualization(analysis_output_dir: str, figure_output_dir: str = None):
    """
    Run indication/intervention visualization generation.

    Args:
        analysis_output_dir: Directory containing indication_intervention_statistics_detailed.json
        figure_output_dir: Directory where figures will be saved (default: analysis_output_dir/figures)

    Returns:
        IndicationVisualizer instance
    """
    json_path = os.path.join(analysis_output_dir, 'indication_intervention_statistics_detailed.json')

    if not os.path.exists(json_path):
        raise FileNotFoundError(f"Could not find {json_path}")

    if figure_output_dir is None:
        figure_output_dir = os.path.join(analysis_output_dir, 'figures')

    visualizer = IndicationVisualizer(json_path, figure_output_dir)
    visualizer.generate_all_visualizations()

    return visualizer


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python visualize_indications.py <analysis_output_dir> [figure_output_dir]")
        print("Example: python visualize_indications.py test_data_150patients test_data_150patients/figures")
        sys.exit(1)

    analysis_dir = sys.argv[1]
    figure_dir = sys.argv[2] if len(sys.argv) > 2 else None

    run_indication_visualization(analysis_dir, figure_dir)
