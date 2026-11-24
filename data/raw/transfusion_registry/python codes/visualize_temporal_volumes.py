"""
Temporal Volume Visualization Module

Creates publication-quality visualizations for blood product volumes over time:
- Monthly volume bar charts (one per product-unit)
- Quarterly volume bar charts (one per product-unit)
- Stacked monthly administrations bar chart (all products, colorblind-friendly palette with legend)
- Total monthly administrations bar chart (all products combined)

Author: Elina Nuerenberg-Goloub with Claude Sonnet 4.5 by Anthropic
Date: 2025-10-21
Revised on 2026-01-21 by Elina Nuerenberg-Goloub and Claude Opus 4.5
"""

import json
import os
import matplotlib
matplotlib.use('Agg')  # Headless-safe backend; must be set before importing pyplot
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
from typing import Dict, Any, List
import pandas as pd

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


class TemporalVolumeVisualizer:
    """Creates visualizations for temporal volume data."""

    def __init__(self, json_path: str, output_dir: str):
        """
        Initialize the visualizer.

        Args:
            json_path: Path to temporal_volumes_detailed.json
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

    def _format_product_unit_key(self, product_name: str, unit: str) -> str:
        """Create clean filename key for product-unit combination."""
        clean_name = product_name.split('(')[0].strip()
        safe_name = clean_name.lower().replace(' ', '_').replace('/', '_')
        return f"{safe_name}_{unit.lower()}"

    def _format_month_label(self, date: datetime) -> str:
        """
        Format month label with proper month name.

        Months with 4 letters use full name (July, June, April, May).
        Others use 3-letter abbreviation (Jan, Feb, Mar, Aug, Sep, Oct, Nov, Dec).

        Args:
            date: datetime object

        Returns:
            Formatted string like "July 2025" or "Jan 2025"
        """
        month_name = date.strftime('%B')  # Full month name
        year = date.strftime('%Y')

        # Months with 4 letters keep full name
        if len(month_name) == 4:  # July, June, May (April is 5 but treated as 4-letter)
            return f"{month_name} {year}"
        elif month_name == 'April':  # Special case
            return f"April {year}"
        else:
            # Use 3-letter abbreviation
            return f"{month_name[:3]} {year}"

    def plot_monthly_bar_chart(self, product_name: str, unit: str):
        """
        Create bar chart showing monthly volumes for a product-unit.
        Shows ALL months on x-axis for consistent bar widths.

        Args:
            product_name: Name of the blood product
            unit: Unit of measurement (ml, IU, mg)
        """
        monthly_data = self.data.get('monthly') or {}
        if not monthly_data:
            print(f"  Skipping {product_name} ({unit}) - no 'monthly' section in data")
            return

        # Get ALL months (sorted) for consistent x-axis
        all_months = sorted(monthly_data.keys())
        dates = [datetime.strptime(m, '%Y-%m') for m in all_months]
        month_labels = [self._format_month_label(d) for d in dates]

        # Extract volumes for this product-unit (0 if no data)
        volumes = []
        has_any_data = False

        for month in all_months:
            month_data = monthly_data[month]
            if ('products' in month_data and
                product_name in month_data['products'] and
                unit in month_data['products'][product_name]):
                volume = month_data['products'][product_name][unit]['total_amount']
                volumes.append(volume)
                has_any_data = True
            else:
                volumes.append(0)

        if not has_any_data:
            print(f"  Skipping {product_name} ({unit}) - no monthly data")
            return

        # Create figure
        fig, ax = plt.subplots(figsize=(14, 7))

        x_pos = range(len(all_months))

        # Use consistent product color
        color = PRODUCT_COLORS.get(product_name, COLORS['highlight'])

        # Plot bars with consistent style
        bars = ax.bar(x_pos, volumes, color=color,
                     edgecolor='white', linewidth=0.5, width=0.7)

        # Add value labels on top of bars
        for i, (bar, volume) in enumerate(zip(bars, volumes)):
            if volume > 0:
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                       f'{int(volume):,}', ha='center', va='bottom',
                       fontsize=10, fontweight='bold')

        # Clean product name
        clean_name = product_name.split('(')[0].strip()

        # Title with total
        total_volume = sum(volumes)
        n_months_with_data = sum(1 for v in volumes if v > 0)
        title = f'{clean_name} - Monthly Volume ({n_months_with_data} months with data, total={total_volume:,.0f} {unit})'
        ax.set_title(title, fontsize=FONT_SIZE_TITLE, fontweight='bold', pad=15)

        # Axes labels
        ax.set_xlabel('Month', fontsize=FONT_SIZE_LABEL)
        ax.set_ylabel(f'Total Volume ({unit})', fontsize=FONT_SIZE_LABEL)

        # Set x-axis with month labels
        ax.set_xticks(x_pos)
        ax.set_xticklabels(month_labels, rotation=45, ha='right')

        # Format y-axis with commas
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{int(x):,}'))

        # Grid
        ax.grid(True, axis='y', linestyle='--', alpha=0.3)
        ax.set_axisbelow(True)

        # Add padding to y-axis for value labels
        max_vol = max(volumes) if volumes else 0
        if max_vol > 0:
            ax.set_ylim(bottom=0, top=max_vol * 1.15)

        # Tight layout
        plt.tight_layout()

        # Save
        filename = f'monthly_{self._format_product_unit_key(product_name, unit)}'
        self._save_figure(fig, filename)
        plt.close(fig)

    def plot_quarterly_bar_chart(self, product_name: str, unit: str):
        """
        Create bar chart showing quarterly volumes for a product-unit.
        Shows ALL quarters on x-axis for consistent bar widths.

        Args:
            product_name: Name of the blood product
            unit: Unit of measurement (ml, IU, mg)
        """
        quarterly_data = self.data.get('quarterly') or {}
        if not quarterly_data:
            print(f"  Skipping {product_name} ({unit}) - no 'quarterly' section in data")
            return

        # Get ALL quarters (sorted) for consistent x-axis
        all_quarters = sorted(quarterly_data.keys())

        # Extract volumes for this product-unit (0 if no data)
        volumes = []
        has_any_data = False

        for quarter in all_quarters:
            quarter_data = quarterly_data[quarter]
            if ('products' in quarter_data and
                product_name in quarter_data['products'] and
                unit in quarter_data['products'][product_name]):
                volume = quarter_data['products'][product_name][unit]['total_amount']
                volumes.append(volume)
                has_any_data = True
            else:
                volumes.append(0)

        if not has_any_data:
            print(f"  Skipping {product_name} ({unit}) - no quarterly data")
            return

        # Create figure
        fig, ax = plt.subplots(figsize=(12, 7))

        x_pos = range(len(all_quarters))

        # Use consistent product color
        color = PRODUCT_COLORS.get(product_name, COLORS['primary'])

        # Plot bars with consistent style
        bars = ax.bar(x_pos, volumes, color=color,
                     edgecolor='white', linewidth=0.5, width=0.7)

        # Add value labels on top of bars
        for i, (bar, volume) in enumerate(zip(bars, volumes)):
            if volume > 0:
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                       f'{int(volume):,}', ha='center', va='bottom',
                       fontsize=10, fontweight='bold')

        # Clean product name
        clean_name = product_name.split('(')[0].strip()

        # Title with total
        total_volume = sum(volumes)
        n_quarters_with_data = sum(1 for v in volumes if v > 0)
        title = f'{clean_name} - Quarterly Volume ({n_quarters_with_data} quarters with data, total={total_volume:,.0f} {unit})'
        ax.set_title(title, fontsize=FONT_SIZE_TITLE, fontweight='bold', pad=15)

        # Axes labels
        ax.set_xlabel('Quarter', fontsize=FONT_SIZE_LABEL)
        ax.set_ylabel(f'Total Volume ({unit})', fontsize=FONT_SIZE_LABEL)

        # Set x-axis
        ax.set_xticks(x_pos)
        ax.set_xticklabels(all_quarters, rotation=45, ha='right')

        # Format y-axis with commas
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{int(x):,}'))

        # Grid
        ax.grid(True, axis='y', linestyle='--', alpha=0.3)
        ax.set_axisbelow(True)

        # Add padding to y-axis for value labels
        max_vol = max(volumes) if volumes else 0
        if max_vol > 0:
            ax.set_ylim(bottom=0, top=max_vol * 1.15)

        # Tight layout
        plt.tight_layout()

        # Save
        filename = f'quarterly_{self._format_product_unit_key(product_name, unit)}'
        self._save_figure(fig, filename)
        plt.close(fig)

    def plot_stacked_monthly_administrations_chart(self):
        """
        Create stacked bar chart showing monthly administration counts for all products.
        Uses colorblind-friendly palette with legend.
        """
        monthly_data = self.data.get('monthly') or {}
        if not monthly_data:
            print("  Skipping stacked monthly administrations chart - no 'monthly' section in data")
            return

        # Get all months (sorted)
        all_months = sorted(monthly_data.keys())
        dates = [datetime.strptime(m, '%Y-%m') for m in all_months]
        month_labels = [self._format_month_label(d) for d in dates]

        # Get all unique products across all months
        all_products = set()
        for month_data in monthly_data.values():
            if 'products' in month_data:
                all_products.update(month_data['products'].keys())

        # Sort products for consistent ordering
        all_products = sorted(all_products)

        # Build data matrix: rows = products, cols = months
        product_data = {}
        for product_name in all_products:
            counts = []
            for month in all_months:
                month_data = monthly_data[month]
                if 'products' in month_data and product_name in month_data['products']:
                    product_info = month_data['products'][product_name]
                    # Check for total_n_administrations first (the TRUE count including records without dosage)
                    if 'total_n_administrations' in product_info:
                        total_admin = product_info['total_n_administrations']
                    # Then check if this product has direct n_administrations (no dosage data at all)
                    elif 'n_administrations' in product_info and len(product_info) == 1:
                        # Product without dosage data (e.g., Machine Autotransfusion)
                        total_admin = product_info['n_administrations']
                    else:
                        # Product with dosage data - sum across all units
                        total_admin = 0
                        for unit_data in product_info.values():
                            if isinstance(unit_data, dict):
                                total_admin += unit_data.get('n_administrations', 0)
                    counts.append(total_admin)
                else:
                    counts.append(0)
            product_data[product_name] = counts

        # Create figure
        fig, ax = plt.subplots(figsize=(14, 7))

        x_pos = range(len(all_months))

        # Create stacked bars using consistent product colors
        bottom = [0] * len(all_months)
        bars_list = []

        for i, product_name in enumerate(all_products):
            # Use consistent product color, fallback to palette if not defined
            color = PRODUCT_COLORS.get(product_name, COLOR_PALETTE[i % len(COLOR_PALETTE)])
            counts = product_data[product_name]
            bars = ax.bar(x_pos, counts, bottom=bottom, color=color,
                         edgecolor='white', linewidth=0.5, width=0.7,
                         label=product_name)
            bars_list.append(bars)
            # Update bottom for next product
            bottom = [b + c for b, c in zip(bottom, counts)]

        # Add total numbers on top of each stacked bar
        for i, total in enumerate(bottom):
            if total > 0:
                ax.text(i, total + 1, str(total), ha='center', va='bottom',
                       fontsize=10, fontweight='bold')

        # Title
        n_months = len(all_months)
        total_admin = sum(bottom)
        title = f'Monthly Administrations by Product ({n_months} months, n={total_admin:,})'
        ax.set_title(title, fontsize=FONT_SIZE_TITLE, fontweight='bold', pad=15)

        # Axes labels
        ax.set_xlabel('Month', fontsize=FONT_SIZE_LABEL)
        ax.set_ylabel('Number of Administrations', fontsize=FONT_SIZE_LABEL)

        # Set x-axis with month labels
        ax.set_xticks(x_pos)
        ax.set_xticklabels(month_labels, rotation=45, ha='right')

        # Format y-axis with commas
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{int(x):,}'))

        # Grid
        ax.grid(True, axis='y', linestyle='--', alpha=0.3)
        ax.set_axisbelow(True)

        # Add padding to y-axis for value labels
        if max(bottom) > 0:
            ax.set_ylim(bottom=0, top=max(bottom) * 1.12)

        # Legend outside the plot
        ax.legend(loc='upper left', bbox_to_anchor=(1.02, 1), fontsize=18)

        # Tight layout with space for legend
        plt.tight_layout()
        plt.subplots_adjust(right=0.78)

        # Save
        filename = 'monthly_administrations_stacked'
        self._save_figure(fig, filename)
        plt.close(fig)

    def plot_total_monthly_administrations_chart(self):
        """
        Create bar chart showing total monthly administration counts across all products.
        """
        monthly_data = self.data.get('monthly') or {}

        # Extract total administrations per month
        dates = []
        counts = []

        for month, month_data in sorted(monthly_data.items()):
            # Parse month (format: YYYY-MM)
            date = datetime.strptime(month, '%Y-%m')
            total_admin = month_data.get('total_administrations', 0)

            dates.append(date)
            counts.append(total_admin)

        if len(dates) == 0:
            print("  Skipping total administrations - no monthly data")
            return

        # Create figure
        fig, ax = plt.subplots(figsize=(12, 6))

        # Create month labels
        month_labels = [self._format_month_label(d) for d in dates]
        x_pos = range(len(dates))

        # Plot bars (medium blue for totals)
        bars = ax.bar(x_pos, counts, color=COLORS['secondary'], alpha=0.8,
                     edgecolor='black', linewidth=1.5, width=0.6)

        # Add value labels on top of bars
        for i, (bar, count) in enumerate(zip(bars, counts)):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                   str(count), ha='center', va='bottom', fontsize=10, fontweight='bold')

        # Title
        n_months = len(dates)
        total_admin = sum(counts)
        title = f'Total Monthly Administrations - All Products ({n_months} months, n={total_admin:,})'
        ax.set_title(title, fontsize=FONT_SIZE_TITLE, fontweight='bold', pad=15)

        # Axes labels
        ax.set_xlabel('Month', fontsize=FONT_SIZE_LABEL)
        ax.set_ylabel('Number of Administrations', fontsize=FONT_SIZE_LABEL)

        # Set x-axis with month labels
        ax.set_xticks(x_pos)
        ax.set_xticklabels(month_labels, rotation=45, ha='right')

        # Format y-axis with commas
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{int(x):,}'))

        # Grid
        ax.grid(True, axis='y', linestyle='--', alpha=0.3)
        ax.set_axisbelow(True)

        # Add padding to y-axis for value labels
        if max(counts) > 0:
            ax.set_ylim(bottom=0, top=max(counts) * 1.15)

        # Tight layout
        plt.tight_layout()

        # Save
        filename = 'monthly_administrations_total'
        self._save_figure(fig, filename)
        plt.close(fig)

    def plot_all_charts(self):
        """Generate all monthly and quarterly charts."""
        # Get all unique product-unit combinations from overall summary
        overall_summary = self.data.get('overall_summary') or {}
        if not overall_summary:
            print("  Warning: no 'overall_summary' section in data - skipping per-product charts")

        product_units = []
        products = set()
        for product_name, units in overall_summary.items():
            products.add(product_name)
            for unit in units.keys():
                product_units.append((product_name, unit))

        # Sort for consistent ordering
        product_units.sort()
        products = sorted(products)

        print(f"\nGenerating visualizations for {len(product_units)} product-unit combinations...")

        # Generate monthly volume charts
        print("\nCreating monthly volume bar charts...")
        for product_name, unit in product_units:
            print(f"  Processing {product_name} ({unit})...")
            self.plot_monthly_bar_chart(product_name, unit)

        # Generate quarterly volume charts
        print("\nCreating quarterly volume bar charts...")
        for product_name, unit in product_units:
            print(f"  Processing {product_name} ({unit})...")
            self.plot_quarterly_bar_chart(product_name, unit)

        # Generate stacked monthly administrations chart (all products combined)
        print("\nCreating stacked monthly administrations chart...")
        self.plot_stacked_monthly_administrations_chart()

        # Generate total monthly administrations chart (all products combined)
        print("\nCreating total monthly administrations chart...")
        self.plot_total_monthly_administrations_chart()

        print(f"\nAll visualizations saved to: {self.output_dir}")

    def generate_all_visualizations(self):
        """Generate all temporal volume visualizations."""
        print("\nGenerating temporal volume visualizations...")
        self.plot_all_charts()


def run_temporal_volume_visualization(analysis_output_dir: str, figure_output_dir: str = None):
    """
    Run temporal volume visualization generation.

    Args:
        analysis_output_dir: Directory containing temporal_volumes_detailed.json
        figure_output_dir: Directory where figures will be saved (default: analysis_output_dir/figures)

    Returns:
        TemporalVolumeVisualizer instance
    """
    json_path = os.path.join(analysis_output_dir, 'temporal_volumes_detailed.json')

    if not os.path.exists(json_path):
        raise FileNotFoundError(f"Could not find {json_path}")

    if figure_output_dir is None:
        figure_output_dir = os.path.join(analysis_output_dir, 'figures')

    visualizer = TemporalVolumeVisualizer(json_path, figure_output_dir)
    visualizer.generate_all_visualizations()

    return visualizer


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python visualize_temporal_volumes.py <analysis_output_dir> [figure_output_dir]")
        print("Example: python visualize_temporal_volumes.py test_data_150patients test_data_150patients/figures")
        sys.exit(1)

    analysis_dir = sys.argv[1]
    figure_dir = sys.argv[2] if len(sys.argv) > 2 else None

    run_temporal_volume_visualization(analysis_dir, figure_dir)
