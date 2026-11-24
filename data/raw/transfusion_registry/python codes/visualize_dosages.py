"""
Dosage Statistics Visualization Module

This module creates publication-quality visualizations for dosage statistics
from transfusion registry data.

Input: treatment_statistics_detailed.json + raw CSV data
Output: PNG figures and CSV table with dosage visualizations

Visualizations created:
- Horizontal histograms for each product-unit (PNG)
  Note: Histograms are used instead of violin plots because blood products
  come in standard doses, making the data discrete rather than continuous.
- Dosage summary table (CSV)

Author: Elina Nuerenberg-Goloub with Claude Sonnet 4.5 by Anthropic
Date: 10-20-2025
Revised on 2026-01-21 by Elina Nuerenberg-Goloub and Claude Opus 4.5
"""

import json
import os
import csv
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Headless-safe backend; must be set before importing pyplot
import matplotlib.pyplot as plt
from typing import Dict, Any, List, Optional

# Minimum observations required for violin plot
MIN_OBSERVATIONS_VIOLIN = 15

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
    'unknown': '#b3b3b3',      # Gray
    'background': '#fee090',   # Light yellow background
    'text': '#000000',         # Black text
}

# Full colorblind-friendly palette for charts with many categories (10 colors)
COLOR_PALETTE = [
    '#a50026',  # Very dark red
    '#d73027',  # Dark red
    '#f46d43',  # Orange
    '#fdae61',  # Light orange
    '#fee090',  # Yellow
    '#e0f3f8',  # Light blue 1
    '#abd9e9',  # Light blue 2
    '#74add1',  # Medium blue
    '#4575b4',  # Dark blue
    '#313695',  # Very dark blue
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


class DosageVisualizer:
    """Creates visualizations for dosage statistics."""

    def __init__(self, json_path: str, output_dir: str, raw_data_path: Optional[str] = None):
        """
        Initialize the visualizer.

        Args:
            json_path: Path to treatment_statistics_detailed.json
            output_dir: Directory where visualizations will be saved
            raw_data_path: Path to raw CSV data file for violin plots
        """
        self.json_path = json_path
        self.output_dir = output_dir
        self.raw_data_path = raw_data_path
        self.raw_df = None

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Load JSON summary data
        with open(json_path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)

        # Load raw data if path provided (needed for violin plots)
        if raw_data_path:
            self._load_raw_data()

        # Set matplotlib defaults
        plt.rcParams['font.family'] = FONT_FAMILY
        plt.rcParams['font.size'] = FONT_SIZE_LABEL
        plt.rcParams['axes.labelsize'] = FONT_SIZE_LABEL
        plt.rcParams['axes.titlesize'] = FONT_SIZE_TITLE
        plt.rcParams['xtick.labelsize'] = FONT_SIZE_TICK
        plt.rcParams['ytick.labelsize'] = FONT_SIZE_TICK
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

    def _load_raw_data(self):
        """Load raw data through the standard loader so figures use the SAME
        cohort as the statistics (test-site exclusion, typing, cleaning)."""
        try:
            from transfusion_data_loader import TransfusionDataLoader
            _loader = TransfusionDataLoader()
            _loader.load_data(self.raw_data_path)
            self.raw_df = _loader.df_clean
            print(f"  Loaded raw data via standard loader: {len(self.raw_df)} records")
        except Exception as e:
            print(f"  Warning: Could not load raw data: {e}")
            self.raw_df = None

    def _get_raw_dosages(self, product_name: str, unit: str) -> Optional[np.ndarray]:
        """
        Get raw dosage values for a specific product-unit combination.

        Args:
            product_name: Full product name with abbreviation
            unit: Unit of measurement

        Returns:
            numpy array of dosage values or None if not available
        """
        if self.raw_df is None:
            return None

        # Column names for dosage data
        dose_col = 'X_433_7_22'
        unit_col = 'X_433_7_734'
        product_col = 'X_433_7_746'

        # Check if columns exist
        if dose_col not in self.raw_df.columns:
            return None

        # Reverse product mapping (name to codes)
        product_codes = {
            'Red blood cell concentrate (RBC)': ['1', '1.0'],
            'Fresh Frozen Plasma (FFP)': ['2', '2.0'],
            'Platelet concentrate (PC)': ['3', '3.0'],
            'PPSB': ['4', '4.0'],
            'Fibrinogen': ['5', '5.0'],
            'Iron i.v.': ['6', '6.0'],
            'Albumin': ['7', '7.0'],
            'EPO': ['8', '8.0'],
            'Antithrombin III (ATIII)': ['9', '9.0'],
            'Oral iron': ['10', '10.0'],
            'Machine Autotransfusion (Cell Salvage)': ['11', '11.0'],
        }

        # Reverse unit mapping (name to codes)
        unit_codes = {
            'ml': ['1', '1.0'],
            'IU': ['2', '2.0'],
            'mg': ['3', '3.0'],
        }

        p_codes = product_codes.get(product_name)
        u_codes = unit_codes.get(unit)

        if not p_codes or not u_codes:
            return None

        # Filter data
        df = self.raw_df.copy()
        df['product_str'] = df[product_col].astype(str)
        df['unit_str'] = df[unit_col].astype(str)

        # Filter by product and unit
        mask = df['product_str'].isin(p_codes) & df['unit_str'].isin(u_codes)
        doses = df.loc[mask, dose_col].dropna()

        # Apply data quality filters (same as descriptive_treatments.py)
        # Filter 1: PPSB ml - clinically implausible
        if product_name == 'PPSB' and unit == 'ml':
            print(f"    DATA QUALITY: PPSB ml excluded (reconstituted product)")
            return None

        # Filter 2: Fibrinogen IU - non-standard unit
        if product_name == 'Fibrinogen' and unit == 'IU':
            print(f"    DATA QUALITY: Fibrinogen IU excluded (non-standard unit)")
            return None

        # Filter 3: Fibrinogen mg < 500 - implausibly low
        if product_name == 'Fibrinogen' and unit == 'mg':
            excluded = (doses < 500).sum()
            if excluded > 0:
                print(f"    DATA QUALITY: Excluded {excluded} Fibrinogen records with dose < 500 mg")
            doses = doses[doses >= 500]

        # Filter out zeros
        doses = doses[doses > 0]

        if len(doses) == 0:
            return None

        return doses.values

    def _get_product_color(self, product_name: str) -> str:
        """Get the color for a specific product."""
        return PRODUCT_COLORS.get(product_name, COLORS['primary'])

    def _create_box_data(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create box plot data structure from summary statistics.

        Args:
            stats: Dictionary with median, q25, q75, min, max

        Returns:
            Dictionary suitable for matplotlib bxp()
        """
        return {
            'med': stats['median'],
            'q1': stats['q25'],
            'q3': stats['q75'],
            'whislo': stats['min'],
            'whishi': stats['max'],
            'fliers': []
        }

    def plot_dosage_histogram(self, product_name: str, unit: str, stats: Dict[str, Any]) -> bool:
        """
        Create horizontal histogram for a specific product-unit dosage.

        Histograms are more appropriate than violin plots for blood product dosages
        because they honestly represent the discrete nature of standard dosing
        (products come in fixed volumes/units).

        Args:
            product_name: Name of the blood product
            unit: Unit of measurement (ml, IU, mg)
            stats: Statistics dictionary with n, mean, sd, median, q25, q75, min, max

        Returns:
            True if plot was created, False if skipped due to insufficient data
        """
        n = stats['n']

        # Skip if insufficient observations
        if n < MIN_OBSERVATIONS_VIOLIN:
            print(f"  Skipping histogram for {product_name} ({unit}) - only {n} observation(s), need {MIN_OBSERVATIONS_VIOLIN}")
            return False

        # Try to get raw data
        data = self._get_raw_dosages(product_name, unit)
        if data is None:
            print(f"  Skipping histogram for {product_name} ({unit}) - no raw data available")
            return False

        if len(data) < MIN_OBSERVATIONS_VIOLIN:
            print(f"  Skipping histogram for {product_name} ({unit}) - only {len(data)} valid values")
            return False

        # Get product color
        product_color = self._get_product_color(product_name)

        # Clean product name (remove abbreviations)
        clean_name = product_name.split('(')[0].strip()

        # Create figure
        fig, ax = plt.subplots(figsize=(6, 5))

        # Get unique values and their counts
        unique_values, counts = np.unique(data, return_counts=True)

        # Sort by value for proper display
        sort_idx = np.argsort(unique_values)
        unique_values = unique_values[sort_idx]
        counts = counts[sort_idx]

        # Determine if we should use bar chart (few unique values) or histogram (many)
        if len(unique_values) <= 30:
            # Use bar chart with consistent bar height for discrete data
            # Calculate bar positions and height
            bar_height = 0.8  # Relative height within each position

            # Create evenly spaced positions for bars
            positions = np.arange(len(unique_values))

            # Create horizontal bar chart
            bars = ax.barh(positions, counts, height=bar_height,
                          color=product_color, edgecolor='white',
                          linewidth=1, alpha=0.8)

            # Set y-ticks to show actual dose values
            ax.set_yticks(positions)
            ax.set_yticklabels([f'{int(v)}' for v in unique_values])

            # Store for later use in statistics overlay
            use_bar_chart = True
            data_min, data_max = unique_values[0], unique_values[-1]
        else:
            # Many unique values - use traditional histogram
            data_min, data_max = np.min(data), np.max(data)
            n_bins = min(25, max(15, len(unique_values) // 5))
            bins = np.linspace(data_min - 0.5, data_max + 0.5, n_bins + 1)

            counts, bin_edges, patches = ax.hist(data, bins=bins, orientation='horizontal',
                                                  color=product_color, edgecolor='white',
                                                  linewidth=1, alpha=0.8)
            use_bar_chart = False

        # Calculate statistics for annotation
        median_val = np.median(data)
        q1 = np.percentile(data, 25)
        q3 = np.percentile(data, 75)

        # For bar charts, we don't add median line/IQR shading on the plot
        # (the y-axis is categorical, not continuous)
        # Statistics are shown in the annotation box only

        # X-axis label (counts)
        ax.set_xlabel('Frequency', fontsize=FONT_SIZE_LABEL)

        # Y-axis label with unit
        ylabel = f'Dosage ({unit})'
        ax.set_ylabel(ylabel, fontsize=FONT_SIZE_LABEL)

        # Set axis limits
        if use_bar_chart:
            ax.set_ylim(-0.5, len(unique_values) - 0.5)
        else:
            data_range = data_max - data_min
            y_padding = data_range * 0.05
            ax.set_ylim(data_min - y_padding, data_max + y_padding)

        # Title with product name and n
        title = f'{clean_name} (n = {len(data)})'
        ax.set_title(title, fontsize=FONT_SIZE_TITLE, fontweight='bold', pad=15)

        # Grid on x-axis only
        ax.xaxis.grid(True, linestyle='--', alpha=0.3)
        ax.set_axisbelow(True)

        # Tight layout
        fig.tight_layout()

        # Save with clean filename
        safe_product = clean_name.lower().replace(' ', '_').replace('/', '_')
        safe_filename = f'dosage_{safe_product}_{unit.lower()}'
        self._save_figure(fig, safe_filename)
        plt.close(fig)

        return True

    def plot_all_dosages(self) -> Dict[str, bool]:
        """
        Create histograms for all product-unit combinations with sufficient data.

        Histograms are used instead of violin plots because blood products come
        in standard doses, making the data discrete rather than continuous.

        Returns:
            Dictionary mapping product-unit to whether plot was created
        """
        dosages_data = self.data['administration_level']['dosages']
        plot_status = {}

        if not dosages_data:
            print("  Skipping dosage histograms (no data)")
            return plot_status

        if self.raw_df is None:
            print("  Warning: No raw data loaded - cannot create histograms")
            return plot_status

        for product_name, units in dosages_data.items():
            for unit, stats in units.items():
                key = f"{product_name} ({unit})"
                print(f"  Processing {key}...")
                plot_status[key] = self.plot_dosage_histogram(product_name, unit, stats)

        # Summary
        created = sum(1 for v in plot_status.values() if v)
        skipped = sum(1 for v in plot_status.values() if not v)
        print(f"\n  Histograms created: {created}, skipped (insufficient data): {skipped}")

        return plot_status

    def save_dosage_summary_csv(self, plot_status: Optional[Dict[str, bool]] = None):
        """
        Save dosage summary table as CSV.

        Args:
            plot_status: Dictionary indicating which product-units have violin plots
        """
        dosages_data = self.data['administration_level']['dosages']

        if not dosages_data:
            print("  Skipping dosage summary CSV (no data)")
            return

        # Prepare table data
        table_data = []
        table_data.append(['Product', 'Unit', 'N', 'Mean', 'SD', 'Median', 'Q25', 'Q75', 'Min', 'Max', 'Histogram'])

        for product_name, units in dosages_data.items():
            # Clean product name (remove abbreviations)
            clean_name = product_name.split('(')[0].strip()

            for unit, stats in units.items():
                # Check if plot was created
                key = f"{product_name} ({unit})"
                has_plot = 'Yes' if plot_status and plot_status.get(key, False) else 'No'

                table_data.append([
                    clean_name,
                    unit,
                    stats['n'],
                    f"{stats['mean']:.1f}",
                    f"{stats['sd']:.1f}",
                    f"{stats['median']:.0f}",
                    f"{stats['q25']:.0f}",
                    f"{stats['q75']:.0f}",
                    f"{stats['min']:.0f}",
                    f"{stats['max']:.0f}",
                    has_plot
                ])

        # Write to CSV
        csv_path = os.path.join(self.output_dir, 'dosage_summary.csv')

        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(table_data)

        print(f"  Saved: dosage_summary.csv")

    def generate_all_visualizations(self):
        """Generate all dosage visualizations."""
        print("\nGenerating dosage visualizations...")

        print("  Creating dosage histograms...")
        plot_status = self.plot_all_dosages()

        print("  Creating dosage summary CSV...")
        self.save_dosage_summary_csv(plot_status)

        print(f"\nAll visualizations saved to: {self.output_dir}")


def run_dosage_visualization(analysis_output_dir: str, figure_output_dir: str = None,
                              raw_data_path: str = None):
    """
    Run dosage visualization generation.

    Args:
        analysis_output_dir: Directory containing treatment_statistics_detailed.json
        figure_output_dir: Directory where figures will be saved (default: analysis_output_dir/figures)
        raw_data_path: Path to raw CSV data file for violin plots

    Returns:
        DosageVisualizer instance
    """
    json_path = os.path.join(analysis_output_dir, 'treatment_statistics_detailed.json')

    if not os.path.exists(json_path):
        raise FileNotFoundError(f"Could not find {json_path}")

    if figure_output_dir is None:
        figure_output_dir = os.path.join(analysis_output_dir, 'figures')

    visualizer = DosageVisualizer(json_path, figure_output_dir, raw_data_path)
    visualizer.generate_all_visualizations()

    return visualizer


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python visualize_dosages.py <analysis_output_dir> [figure_output_dir] [raw_data_path]")
        print("Example: python visualize_dosages.py test_data_150patients test_data_150patients/figures ../test_data_150patients.csv")
        sys.exit(1)

    analysis_dir = sys.argv[1]
    figure_dir = sys.argv[2] if len(sys.argv) > 2 else None
    raw_data = sys.argv[3] if len(sys.argv) > 3 else None

    run_dosage_visualization(analysis_dir, figure_dir, raw_data)
