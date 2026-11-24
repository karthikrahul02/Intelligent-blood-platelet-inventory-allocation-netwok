"""
Treatment Statistics Visualization Module

This module creates publication-quality visualizations for treatment descriptive statistics
from transfusion registry data.

Input: treatment_statistics_detailed.json + raw CSV data
Output: PNG figures and CSV tables with statistical visualizations

Visualizations created:
- Product distribution bar chart (PNG)
- Temporal trends line chart (PNG)
- Lab values before/after violin plots - one per lab parameter (PNG)
- Administration frequency bar chart (PNG)
- Summary tables (CSV)

Author: Elina Nuerenberg-Goloub with Claude Sonnet 4.5 by Anthropic
Date: 10-20-2025
Revised on 2026-01-25 by Elina Nuerenberg-Goloub and Claude Opus 4.5
"""

import json
import os
import csv
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Headless-safe backend; must be set before importing pyplot
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

# Import lab value quality checker for unit detection and cleaning
from lab_value_quality import LabValueQualityChecker, LAB_VALUE_CONFIG

# Colorblind-friendly color scheme (diverging warm-to-cold palette)
COLORS = {
    'primary': '#4575b4',      # Dark blue - main data
    'secondary': '#74add1',    # Medium blue - accents
    'highlight': '#d73027',    # Dark red - overlays
    'alternate': '#f46d43',    # Orange - alternative
    'color5': '#fdae61',       # Light orange
    'color6': '#abd9e9',       # Light blue 2
    'color7': '#e0f3f8',       # Light blue 1
    'color8': '#fee090',       # Yellow
    'unknown': '#b3b3b3',      # Gray - missing/unknown/other
    'background': '#fee090',   # Light yellow background
    'text': '#000000',         # Black text
    'before': '#d73027',       # Dark red for "before"
    'after': '#4575b4',        # Dark blue for "after"
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

# Mapping of lab parameters to blood products (must match PRODUCT_COLORS keys)
LAB_TO_PRODUCT = {
    'Hemoglobin': 'Red blood cell concentrate (RBC)',
    'Platelets': 'Platelet concentrate (PC)',
    "Quick's test": 'PPSB',
    'Fibrinogen': 'Fibrinogen',
    'Serum albumin': 'Albumin',
    'Ferritin': 'Iron i.v.',
    'Transferrin saturation': 'Iron i.v.',
    'Antithrombin activity': 'Antithrombin III (ATIII)',
}

# Lab value column mappings (before and after treatment)
LAB_COLUMNS = {
    'Hemoglobin': {
        'before': 'X_433_7_614',
        'after': 'X_433_7_615',
        'unit': 'g/dl',
    },
    'Platelets': {
        'before': 'X_433_7_37',
        'after': 'X_433_7_587',
        'unit': '/µl',
    },
    "Quick's test": {
        'before': 'X_433_7_374',
        'after': 'X_433_7_596',
        'unit': '%',
    },
    'Fibrinogen': {
        'before': 'X_433_7_585',
        'after': 'X_433_7_586',
        'unit': 'mg/dl',
    },
    'Serum albumin': {
        'before': 'X_433_7_603',
        'after': 'X_433_7_591',
        'unit': 'g/dl',
    },
    'Ferritin': {
        'before': 'X_433_7_736',
        'after': 'X_433_7_735',
        'unit': 'µg/l',
    },
    'Transferrin saturation': {
        'before': 'X_433_7_589',
        'after': 'X_433_7_590',
        'unit': '%',
    },
    'Antithrombin activity': {
        'before': 'X_433_7_601',
        'after': 'X_433_7_602',
        'unit': '%',
    },
}

# Minimum observations required for violin plot
MIN_OBSERVATIONS_VIOLIN = 15

# Figure settings
FIGURE_DPI = 300
FONT_FAMILY = 'Arial'
FONT_SIZE_TITLE = 24
FONT_SIZE_LABEL = 20
FONT_SIZE_TICK = 18
FONT_SIZE_LEGEND = 18


class TreatmentVisualizer:
    """Creates visualizations for treatment descriptive statistics."""

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
        plt.rcParams['legend.fontsize'] = FONT_SIZE_LEGEND
        plt.rcParams['figure.dpi'] = FIGURE_DPI
        plt.rcParams['savefig.dpi'] = FIGURE_DPI
        plt.rcParams['savefig.bbox'] = 'tight'

    def _load_raw_data(self):
        """Load raw data through the standard loader so figures use the SAME
        cohort as the statistics (test-site exclusion, typing, cleaning)."""
        try:
            from transfusion_data_loader import TransfusionDataLoader
            _loader = TransfusionDataLoader()
            _loader.load_data(self.raw_data_path)
            self.raw_df = _loader.df_clean
            print(f"  Loaded raw data via standard loader: {len(self.raw_df)} records")

            # Central lab normalization on the SAME cohort as the statistics
            self.lab_quality_checker = LabValueQualityChecker(self.raw_df)
        except Exception as e:
            print(f"  Warning: Could not load raw data: {e}")
            self.raw_df = None
            self.lab_quality_checker = None

    def _save_figure(self, fig, filename: str):
        """Save figure in PNG format only."""
        base_name = os.path.splitext(filename)[0]
        png_path = os.path.join(self.output_dir, f"{base_name}.png")

        fig.savefig(png_path, format='png', dpi=FIGURE_DPI, bbox_inches='tight',
                    facecolor='white', edgecolor='none')

        print(f"  Saved: {base_name}.png")

    def plot_product_distribution(self):
        """Create horizontal bar chart for product distribution with consistent product colors."""
        products_section = (self.data.get('administration_level') or {}).get('products') or {}
        products_data = products_section.get('products') or {}
        total = products_section.get('total', 0)

        if not products_data:
            print("  Skipping product distribution (no data)")
            return

        # Sort products by count (descending)
        sorted_products = sorted(products_data.items(), key=lambda x: x[1]['n'], reverse=True)

        # Build labels and colors for each product
        labels = []
        colors = []
        for name, _ in sorted_products:
            # Remove text in parentheses for display (e.g., "(RBC)", "(PC)")
            clean_name = name.split('(')[0].strip()
            labels.append(clean_name)
            # Get color from PRODUCT_COLORS, fallback to primary color
            colors.append(PRODUCT_COLORS.get(name, COLORS['primary']))

        counts = [data['n'] for _, data in sorted_products]
        percentages = [data['percent'] for _, data in sorted_products]

        # Create figure
        fig, ax = plt.subplots(figsize=(10, 6))

        # Create horizontal bars with product-specific colors
        y_pos = range(len(labels))
        bars = ax.barh(y_pos, counts, color=colors, edgecolor='white', linewidth=0.5)

        # Add count and percentage labels on bars
        max_count = max(counts)
        for i, (count, pct) in enumerate(zip(counts, percentages)):
            ax.text(count + max_count*0.01, i, f'{count} ({pct:.1f}%)',
                    va='center', fontsize=11)

        # Labels and formatting
        ax.set_yticks(y_pos)
        ax.set_yticklabels(labels, fontsize=FONT_SIZE_TICK)
        ax.set_xlabel('Number of Administrations', fontsize=FONT_SIZE_LABEL)
        ax.set_title(f'Blood Product Distribution (n = {total})', fontsize=FONT_SIZE_TITLE, fontweight='bold', pad=15)

        # Extend x-axis to accommodate text labels
        ax.set_xlim(0, max_count * 1.25)

        # Grid
        ax.grid(axis='x', alpha=0.3, linestyle='--', linewidth=0.5)
        ax.set_axisbelow(True)

        plt.tight_layout()
        self._save_figure(fig, 'treatment_product_distribution')
        plt.close(fig)

    def plot_temporal_trends(self):
        """Create line chart for temporal trends."""
        temporal_data = (self.data.get('administration_level') or {}).get('temporal') or {}
        monthly_dist = temporal_data.get('monthly_distribution', {})

        if not monthly_dist:
            print("  Skipping temporal trends (no data)")
            return

        # Parse dates and counts
        dates = []
        counts = []
        for month_str, count in sorted(monthly_dist.items()):
            try:
                date = datetime.strptime(month_str, '%Y-%m')
                dates.append(date)
                counts.append(count)
            except ValueError:
                continue

        if not dates:
            print("  Skipping temporal trends (no valid dates)")
            return

        # Create figure
        fig, ax = plt.subplots(figsize=(12, 6))

        # Plot line
        ax.plot(dates, counts, color=COLORS['primary'], linewidth=2, marker='o', markersize=6,
                markerfacecolor=COLORS['highlight'], markeredgecolor='black', markeredgewidth=0.5)

        # Labels and formatting
        ax.set_xlabel('Month', fontsize=FONT_SIZE_LABEL)
        ax.set_ylabel('Number of Administrations', fontsize=FONT_SIZE_LABEL)
        ax.set_title('Temporal Trends in Blood Product Administration', fontsize=FONT_SIZE_TITLE, fontweight='bold', pad=15)

        # Format x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')

        # Grid
        ax.grid(axis='both', alpha=0.3, linestyle='--', linewidth=0.5)
        ax.set_axisbelow(True)

        plt.tight_layout()
        self._save_figure(fig, 'treatment_temporal_trends')
        plt.close(fig)

    def plot_lab_value_violin(self, lab_name: str, lab_info: Dict[str, Any]) -> bool:
        """
        Create paired violin plot for a single lab parameter (before/after treatment).

        Uses the LabValueQualityChecker to get cleaned data with outliers
        (values in minority/wrong unit) excluded.

        Args:
            lab_name: Name of the lab parameter
            lab_info: Dictionary with before/after statistics and unit

        Returns:
            True if plot was created, False if skipped
        """
        if self.lab_quality_checker is None:
            print(f"  Skipping violin plot for {lab_name} - no quality checker available")
            return False

        # Use quality checker to get cleaned data (outliers excluded)
        before_data, after_data, unit = self.lab_quality_checker.get_cleaned_data(
            lab_name, exclude_outliers=True
        )

        if len(before_data) == 0 or len(after_data) == 0:
            print(f"  Skipping violin plot for {lab_name} - no valid data after cleaning")
            return False

        n_paired = len(before_data)

        if n_paired < MIN_OBSERVATIONS_VIOLIN:
            print(f"  Skipping violin plot for {lab_name} - only {n_paired} paired observations, need {MIN_OBSERVATIONS_VIOLIN}")
            return False

        # Get product color
        product_name = LAB_TO_PRODUCT.get(lab_name, lab_name)
        product_color = PRODUCT_COLORS.get(product_name, COLORS['primary'])

        # Create figure
        fig, ax = plt.subplots(figsize=(5, 6))

        # Create violin plots for before and after
        positions = [0.8, 1.2]
        data_sets = [before_data, after_data]

        for i, (pos, data, label) in enumerate(zip(positions, data_sets, ['Before', 'After'])):
            # Create violin
            vp = ax.violinplot([data], positions=[pos], showmeans=False,
                               showmedians=False, showextrema=False, widths=0.35)

            # Style the violin with product color
            for body in vp['bodies']:
                body.set_facecolor(product_color)
                body.set_alpha(0.3 if i == 0 else 0.5)  # Before lighter, After darker
                body.set_edgecolor(product_color)
                body.set_linewidth(1.5)

            # Add thin box plot inside
            bp = ax.boxplot([data], positions=[pos], widths=0.1,
                           showfliers=True, patch_artist=True,
                           flierprops=dict(marker='o', markerfacecolor=product_color,
                                          markeredgecolor=product_color, markersize=3, alpha=0.5))

            # Style the box plot
            for patch in bp['boxes']:
                patch.set_facecolor('white')
                patch.set_alpha(0.9)
                patch.set_edgecolor(product_color)
                patch.set_linewidth(1.5)

            # Red median line
            for item in bp['medians']:
                item.set_color('#d73027')
                item.set_linewidth(2)

            # Whiskers and caps in product color
            for item in bp['whiskers']:
                item.set_color(product_color)
                item.set_linewidth(1.5)

            for item in bp['caps']:
                item.set_color(product_color)
                item.set_linewidth(1.5)

            # Add mean as diamond marker
            mean_val = np.mean(data)
            ax.scatter([pos], [mean_val], color='#d73027', marker='D', s=40, zorder=10,
                       edgecolors='white', linewidths=0.5)

        # Calculate statistics for annotation
        before_median = np.median(before_data)
        before_iqr = (np.percentile(before_data, 25), np.percentile(before_data, 75))
        after_median = np.median(after_data)
        after_iqr = (np.percentile(after_data, 25), np.percentile(after_data, 75))

        # X-axis labels
        ax.set_xticks(positions)
        ax.set_xticklabels(['Before', 'After'], fontsize=FONT_SIZE_LABEL)
        ax.set_xlim(0.4, 1.6)

        # Y-axis label with unit
        ylabel = f'{lab_name} ({unit})' if unit else lab_name
        ax.set_ylabel(ylabel, fontsize=FONT_SIZE_LABEL)

        # Title with lab name and n
        ax.set_title(f'{lab_name} (n = {n_paired} paired)', fontsize=FONT_SIZE_TITLE, fontweight='bold', pad=15)

        # Grid
        ax.yaxis.grid(True, linestyle='--', alpha=0.3)
        ax.set_axisbelow(True)

        # Tight layout
        fig.tight_layout()

        # Save with clean filename
        safe_name = lab_name.lower().replace(' ', '_').replace("'", '').replace('/', '_')
        self._save_figure(fig, f'lab_value_{safe_name}')
        plt.close(fig)

        return True

    def plot_all_lab_values(self) -> Dict[str, bool]:
        """
        Create individual violin plots for all lab parameters with sufficient data.

        Returns:
            Dictionary mapping lab name to whether plot was created
        """
        lab_data = (self.data.get('administration_level') or {}).get('lab_values') or {}
        plot_status = {}

        if not lab_data:
            print("  Skipping lab value violin plots (no data in JSON)")
            return plot_status

        if self.raw_df is None:
            print("  Warning: No raw data loaded - cannot create violin plots")
            return plot_status

        for lab_name, lab_info in lab_data.items():
            print(f"  Processing {lab_name}...")
            plot_status[lab_name] = self.plot_lab_value_violin(lab_name, lab_info)

        # Summary
        created = sum(1 for v in plot_status.values() if v)
        skipped = sum(1 for v in plot_status.values() if not v)
        print(f"\n  Lab value violin plots created: {created}, skipped: {skipped}")

        return plot_status

    def plot_lab_values_by_gender(self) -> Dict[str, bool]:
        """
        Create violin plots for lab values before administration, stratified by gender.

        Creates one plot per lab parameter showing Male vs Female distributions.

        Returns:
            Dictionary of lab_name: bool indicating which plots were created
        """
        # Check if gender-stratified data exists
        by_gender = self.data.get('by_gender', {})
        lab_values_data = by_gender.get('lab_values_before', {})

        if not lab_values_data:
            print("  Skipping gender-stratified lab values (no data)")
            return {}

        plot_status = {}

        # Get lab values that have data for at least one gender
        all_lab_names = set()
        for gender in ['Male', 'Female']:
            if gender in lab_values_data:
                all_lab_names.update(lab_values_data[gender].keys())

        for lab_name in sorted(all_lab_names):
            # Get data for each gender
            male_data = None
            female_data = None
            unit = None
            normal_range = None

            if 'Male' in lab_values_data and lab_name in lab_values_data['Male']:
                male_info = lab_values_data['Male'][lab_name]
                male_data = male_info.get('values', [])
                unit = male_info.get('unit', '')
                normal_range = male_info.get('normal_range', '')

            if 'Female' in lab_values_data and lab_name in lab_values_data['Female']:
                female_info = lab_values_data['Female'][lab_name]
                female_data = female_info.get('values', [])
                if not unit:
                    unit = female_info.get('unit', '')
                if not normal_range:
                    normal_range = female_info.get('normal_range', '')

            # Skip if insufficient data
            has_male = male_data is not None and len(male_data) >= MIN_OBSERVATIONS_VIOLIN
            has_female = female_data is not None and len(female_data) >= MIN_OBSERVATIONS_VIOLIN

            if not has_male and not has_female:
                print(f"  Skipping gender violin for {lab_name} - insufficient data")
                plot_status[lab_name] = False
                continue

            # Create figure
            fig, ax = plt.subplots(figsize=(6, 6))

            # Colors for gender (orange and light blue)
            male_color = '#f46d43'    # Orange
            female_color = '#74add1'  # Light blue

            positions = []
            data_sets = []
            labels = []
            colors = []

            if has_male:
                positions.append(0.8)
                data_sets.append(male_data)
                labels.append(f'Male\n(n={len(male_data)})')
                colors.append(male_color)

            if has_female:
                positions.append(1.2)
                data_sets.append(female_data)
                labels.append(f'Female\n(n={len(female_data)})')
                colors.append(female_color)

            for i, (pos, data, color) in enumerate(zip(positions, data_sets, colors)):
                # Create violin
                vp = ax.violinplot([data], positions=[pos], showmeans=False,
                                   showmedians=False, showextrema=False, widths=0.35)

                # Style the violin
                for body in vp['bodies']:
                    body.set_facecolor(color)
                    body.set_alpha(0.4)
                    body.set_edgecolor(color)
                    body.set_linewidth(1.5)

                # Add box plot inside
                bp = ax.boxplot([data], positions=[pos], widths=0.1,
                               showfliers=True, patch_artist=True,
                               flierprops=dict(marker='o', markerfacecolor=color,
                                              markeredgecolor=color, markersize=3, alpha=0.5))

                # Style the box plot
                for patch in bp['boxes']:
                    patch.set_facecolor('white')
                    patch.set_alpha(0.9)
                    patch.set_edgecolor(color)
                    patch.set_linewidth(1.5)

                for item in bp['medians']:
                    item.set_color(color)  # Same color as group
                    item.set_linewidth(2)

                for item in bp['whiskers']:
                    item.set_color(color)
                    item.set_linewidth(1.5)

                for item in bp['caps']:
                    item.set_color(color)
                    item.set_linewidth(1.5)

                # Add mean as diamond marker (red for visibility)
                mean_val = np.mean(data)
                ax.scatter([pos], [mean_val], color='#d73027', marker='D', s=40, zorder=10,
                           edgecolors='white', linewidths=0.5)

            # X-axis labels
            ax.set_xticks(positions)
            ax.set_xticklabels(labels, fontsize=FONT_SIZE_LABEL)
            ax.set_xlim(0.4, 1.6)

            # Y-axis label with unit
            ylabel = f'{lab_name} ({unit})' if unit else lab_name
            ax.set_ylabel(ylabel, fontsize=FONT_SIZE_LABEL)

            # Title
            total_n = (len(male_data) if has_male else 0) + (len(female_data) if has_female else 0)
            ax.set_title(f'{lab_name} by Sex\n(before administration)', fontsize=FONT_SIZE_TITLE, fontweight='bold', pad=15)

            # Grid
            ax.yaxis.grid(True, linestyle='--', alpha=0.3)
            ax.set_axisbelow(True)

            # Tight layout
            fig.tight_layout()

            # Save
            safe_name = lab_name.lower().replace(' ', '_').replace("'", '').replace('/', '_')
            self._save_figure(fig, f'lab_value_{safe_name}_by_gender')
            plt.close(fig)

            plot_status[lab_name] = True
            print(f"  Saved: lab_value_{safe_name}_by_gender.png")

        return plot_status

    def plot_administration_frequency(self):
        """Create bar chart for administration frequency distribution."""
        freq_data = (self.data.get('patient_level') or {}).get('administration_frequency') or {}
        distribution = freq_data.get('distribution') or {}

        if not distribution:
            print("  Skipping administration frequency (no data)")
            return

        total_patients = (freq_data.get('statistics') or {}).get('n_patients', 0)
        if not total_patients:
            print("  Skipping administration frequency (no patient count in statistics)")
            return

        # Group into categories
        categories = {
            '1': 0, '2': 0, '3': 0, '4': 0, '5': 0,
            '6-10': 0, '11-20': 0, '>20': 0
        }

        for key, value in distribution.items():
            n_admin = int(key.split()[0])
            count = value['n_patients']

            if n_admin == 1:
                categories['1'] += count
            elif n_admin == 2:
                categories['2'] += count
            elif n_admin == 3:
                categories['3'] += count
            elif n_admin == 4:
                categories['4'] += count
            elif n_admin == 5:
                categories['5'] += count
            elif 6 <= n_admin <= 10:
                categories['6-10'] += count
            elif 11 <= n_admin <= 20:
                categories['11-20'] += count
            else:
                categories['>20'] += count

        # Prepare data
        labels = list(categories.keys())
        counts = list(categories.values())
        percentages = [(c / total_patients * 100) for c in counts]

        # Create figure
        fig, ax = plt.subplots(figsize=(10, 6))

        # Create bars
        x_pos = range(len(labels))
        bars = ax.bar(x_pos, counts, color=COLORS['primary'], alpha=0.8,
                      edgecolor='black', linewidth=0.5)

        # Add count and percentage labels on bars
        max_count = max(counts) if counts else 0
        for i, (count, pct) in enumerate(zip(counts, percentages)):
            if count > 0:
                ax.text(i, count + max_count*0.02, f'{count}\n({pct:.1f}%)',
                        ha='center', va='bottom', fontsize=11)

        # Labels and formatting
        ax.set_xticks(x_pos)
        ax.set_xticklabels(labels, fontsize=FONT_SIZE_TICK)
        ax.set_xlabel('Number of Administrations per Patient', fontsize=FONT_SIZE_LABEL)
        ax.set_ylabel('Number of Patients', fontsize=FONT_SIZE_LABEL)
        ax.set_title(f'Administration Frequency Distribution (n = {total_patients} patients)',
                     fontsize=FONT_SIZE_TITLE, fontweight='bold', pad=15)

        # Extend y-axis to accommodate text labels
        ax.set_ylim(0, max_count * 1.2)

        # Grid
        ax.grid(axis='y', alpha=0.3, linestyle='--', linewidth=0.5)
        ax.set_axisbelow(True)

        plt.tight_layout()
        self._save_figure(fig, 'treatment_administration_frequency')
        plt.close(fig)

    def plot_administration_frequency_by_gender(self):
        """Create grouped bar chart for administration frequency by gender."""
        if self.raw_df is None:
            print("  Skipping administration frequency by gender (no raw data)")
            return

        # Gender column
        gender_col = 'X_433_0_4'
        if gender_col not in self.raw_df.columns:
            print("  Skipping administration frequency by gender (no gender column)")
            return

        # Colors for gender (orange and light blue)
        male_color = '#f46d43'    # Orange
        female_color = '#74add1'  # Light blue

        # Calculate administrations per patient by gender
        df = self.raw_df.copy()

        # Filter to only records with blood product (product type column)
        product_col = 'X_433_7_746'
        if product_col in df.columns:
            df = df[df[product_col].notna() & (df[product_col] != '')]

        # Gender from the SAME per-patient index row as the statistics
        # (most complete basic data, earliest episode) - a per-column first()
        # could disagree with the statistics when a patient has conflicting rows
        from transfusion_data_loader import select_patient_index_rows
        index_gender = select_patient_index_rows(self.raw_df).set_index('PID')[gender_col]
        patient_admin = df.groupby('PID').size().rename('n_admin').reset_index()
        patient_admin[gender_col] = patient_admin['PID'].map(index_gender)

        # Separate by gender
        male_patients = patient_admin[patient_admin[gender_col] == 'M']
        female_patients = patient_admin[patient_admin[gender_col] == 'F']

        if len(male_patients) < 5 or len(female_patients) < 5:
            print("  Skipping administration frequency by gender (insufficient data)")
            return

        # Group into categories
        categories = ['1', '2', '3', '4', '5', '6-10', '11-20', '>20']

        def categorize_admins(n_admin):
            if n_admin == 1:
                return '1'
            elif n_admin == 2:
                return '2'
            elif n_admin == 3:
                return '3'
            elif n_admin == 4:
                return '4'
            elif n_admin == 5:
                return '5'
            elif 6 <= n_admin <= 10:
                return '6-10'
            elif 11 <= n_admin <= 20:
                return '11-20'
            else:
                return '>20'

        male_patients['category'] = male_patients['n_admin'].apply(categorize_admins)
        female_patients['category'] = female_patients['n_admin'].apply(categorize_admins)

        # Count by category
        male_counts = {cat: 0 for cat in categories}
        female_counts = {cat: 0 for cat in categories}

        for cat, count in male_patients['category'].value_counts().items():
            male_counts[cat] = count
        for cat, count in female_patients['category'].value_counts().items():
            female_counts[cat] = count

        male_values = [male_counts[cat] for cat in categories]
        female_values = [female_counts[cat] for cat in categories]

        total_male = len(male_patients)
        total_female = len(female_patients)

        # Create figure
        fig, ax = plt.subplots(figsize=(12, 6))

        # Bar positions
        x = np.arange(len(categories))
        width = 0.35

        # Create grouped bars
        bars_male = ax.bar(x - width/2, male_values, width, label=f'Male (n={total_male})',
                          color=male_color, alpha=0.8, edgecolor='black', linewidth=0.5)
        bars_female = ax.bar(x + width/2, female_values, width, label=f'Female (n={total_female})',
                            color=female_color, alpha=0.8, edgecolor='black', linewidth=0.5)

        # Add count and percentage labels on bars
        max_count = max(max(male_values), max(female_values)) if male_values and female_values else 0

        for i, (m_count, f_count) in enumerate(zip(male_values, female_values)):
            if m_count > 0:
                m_pct = m_count / total_male * 100
                ax.text(i - width/2, m_count + max_count*0.02, f'{m_count}\n({m_pct:.1f}%)',
                        ha='center', va='bottom', fontsize=10, color=male_color)
            if f_count > 0:
                f_pct = f_count / total_female * 100
                ax.text(i + width/2, f_count + max_count*0.02, f'{f_count}\n({f_pct:.1f}%)',
                        ha='center', va='bottom', fontsize=10, color='#555555')

        # Labels and formatting
        ax.set_xticks(x)
        ax.set_xticklabels(categories, fontsize=FONT_SIZE_TICK)
        ax.set_xlabel('Number of Administrations per Patient', fontsize=FONT_SIZE_LABEL)
        ax.set_ylabel('Number of Patients', fontsize=FONT_SIZE_LABEL)
        ax.set_title(f'Administration Frequency by Sex (n={total_male} Male, {total_female} Female)',
                     fontsize=FONT_SIZE_TITLE, fontweight='bold', pad=15)

        # Extend y-axis to accommodate text labels
        ax.set_ylim(0, max_count * 1.25)

        # Legend
        ax.legend(loc='upper right', fontsize=FONT_SIZE_LEGEND)

        # Grid
        ax.grid(axis='y', alpha=0.3, linestyle='--', linewidth=0.5)
        ax.set_axisbelow(True)

        plt.tight_layout()
        self._save_figure(fig, 'treatment_administration_frequency_by_gender')
        plt.close(fig)

    def plot_administration_frequency_by_gender_percent(self):
        """Create grouped bar chart for administration frequency by gender using percentages.

        Uses percentages on y-axis for fair comparison between groups with different sample sizes.
        This also helps protect privacy by not showing small absolute numbers.
        """
        if self.raw_df is None:
            print("  Skipping administration frequency by gender (percent) (no raw data)")
            return

        # Gender column
        gender_col = 'X_433_0_4'
        if gender_col not in self.raw_df.columns:
            print("  Skipping administration frequency by gender (percent) (no gender column)")
            return

        # Colors for gender (orange and light blue)
        male_color = '#f46d43'    # Orange
        female_color = '#74add1'  # Light blue

        # Calculate administrations per patient by gender
        df = self.raw_df.copy()

        # Filter to only records with blood product (product type column)
        product_col = 'X_433_7_746'
        if product_col in df.columns:
            df = df[df[product_col].notna() & (df[product_col] != '')]

        # Gender from the SAME per-patient index row as the statistics
        # (most complete basic data, earliest episode) - a per-column first()
        # could disagree with the statistics when a patient has conflicting rows
        from transfusion_data_loader import select_patient_index_rows
        index_gender = select_patient_index_rows(self.raw_df).set_index('PID')[gender_col]
        patient_admin = df.groupby('PID').size().rename('n_admin').reset_index()
        patient_admin[gender_col] = patient_admin['PID'].map(index_gender)

        # Separate by gender
        male_patients = patient_admin[patient_admin[gender_col] == 'M']
        female_patients = patient_admin[patient_admin[gender_col] == 'F']

        if len(male_patients) < 5 or len(female_patients) < 5:
            print("  Skipping administration frequency by gender (percent) (insufficient data)")
            return

        # Group into categories
        categories = ['1', '2', '3', '4', '5', '6-10', '11-20', '>20']

        def categorize_admins(n_admin):
            if n_admin == 1:
                return '1'
            elif n_admin == 2:
                return '2'
            elif n_admin == 3:
                return '3'
            elif n_admin == 4:
                return '4'
            elif n_admin == 5:
                return '5'
            elif 6 <= n_admin <= 10:
                return '6-10'
            elif 11 <= n_admin <= 20:
                return '11-20'
            else:
                return '>20'

        male_patients = male_patients.copy()
        female_patients = female_patients.copy()
        male_patients['category'] = male_patients['n_admin'].apply(categorize_admins)
        female_patients['category'] = female_patients['n_admin'].apply(categorize_admins)

        # Count by category
        male_counts = {cat: 0 for cat in categories}
        female_counts = {cat: 0 for cat in categories}

        for cat, count in male_patients['category'].value_counts().items():
            male_counts[cat] = count
        for cat, count in female_patients['category'].value_counts().items():
            female_counts[cat] = count

        total_male = len(male_patients)
        total_female = len(female_patients)

        # Calculate percentages
        male_pct = [(male_counts[cat] / total_male * 100) for cat in categories]
        female_pct = [(female_counts[cat] / total_female * 100) for cat in categories]

        # Create figure
        fig, ax = plt.subplots(figsize=(12, 6))

        # Bar positions
        x = np.arange(len(categories))
        width = 0.35

        # Create grouped bars with percentages
        bars_male = ax.bar(x - width/2, male_pct, width, label=f'Male (n={total_male})',
                          color=male_color, alpha=0.8, edgecolor='black', linewidth=0.5)
        bars_female = ax.bar(x + width/2, female_pct, width, label=f'Female (n={total_female})',
                            color=female_color, alpha=0.8, edgecolor='black', linewidth=0.5)

        # Add percentage labels on bars
        max_pct = max(max(male_pct), max(female_pct)) if male_pct and female_pct else 0

        for i, (m_pct, f_pct) in enumerate(zip(male_pct, female_pct)):
            if m_pct > 0:
                ax.text(i - width/2, m_pct + max_pct*0.02, f'{m_pct:.1f}%',
                        ha='center', va='bottom', fontsize=11, color=male_color, fontweight='bold')
            if f_pct > 0:
                ax.text(i + width/2, f_pct + max_pct*0.02, f'{f_pct:.1f}%',
                        ha='center', va='bottom', fontsize=11, color='#555555', fontweight='bold')

        # Labels and formatting
        ax.set_xticks(x)
        ax.set_xticklabels(categories, fontsize=FONT_SIZE_TICK)
        ax.set_xlabel('Number of Administrations per Patient', fontsize=FONT_SIZE_LABEL)
        ax.set_ylabel('Percentage of Patients (%)', fontsize=FONT_SIZE_LABEL)
        ax.set_title(f'Administration Frequency by Sex (n={total_male} Male, {total_female} Female)',
                     fontsize=FONT_SIZE_TITLE, fontweight='bold', pad=15)

        # Extend y-axis to accommodate text labels
        ax.set_ylim(0, max_pct * 1.2)

        # Legend
        ax.legend(loc='upper right', fontsize=FONT_SIZE_LEGEND)

        # Grid
        ax.grid(axis='y', alpha=0.3, linestyle='--', linewidth=0.5)
        ax.set_axisbelow(True)

        plt.tight_layout()
        self._save_figure(fig, 'treatment_administration_frequency_by_gender_percent')
        plt.close(fig)

    def save_product_summary_csv(self):
        """Save product summary table as CSV."""
        products_section = (self.data.get('administration_level') or {}).get('products') or {}
        products_data = products_section.get('products') or {}
        total = products_section.get('total', 0)

        if not products_data:
            print("  Skipping product summary CSV (no data)")
            return

        # Sort products by count
        sorted_products = sorted(products_data.items(), key=lambda x: x[1]['n'], reverse=True)

        # Prepare table data
        table_data = []
        for name, data in sorted_products:
            # Remove abbreviations in parentheses from product names
            clean_name = name.split('(')[0].strip()
            table_data.append([
                clean_name,
                data['n'],
                f"{data['percent']:.1f}%"
            ])

        # Add total
        table_data.append(['TOTAL', total, '100.0%'])

        # Write to CSV
        csv_path = os.path.join(self.output_dir, 'treatment_product_summary.csv')
        headers = ['Product', 'Administrations', 'Percentage']

        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(table_data)

        print(f"  Saved: treatment_product_summary.csv")

    def save_lab_values_summary_csv(self):
        """Save lab values summary table as CSV."""
        lab_data = (self.data.get('administration_level') or {}).get('lab_values') or {}

        if not lab_data:
            print("  Skipping lab values summary CSV (no data)")
            return

        # Prepare table data
        table_data = []

        for lab_name, lab_info in lab_data.items():
            if 'before' not in lab_info or 'after' not in lab_info:
                continue

            before = lab_info['before']
            after = lab_info['after']
            change = lab_info.get('change', {})
            unit = lab_info.get('unit', '')
            normal_range = lab_info.get('normal_range', '-')
            n_before_only = lab_info.get('n_before_only', 0)
            n_after_only = lab_info.get('n_after_only', 0)

            if before.get('n', 0) == 0:
                continue

            n_paired = before['n']
            before_mean_sd = f"{before['mean']:.1f}±{before['sd']:.1f}"
            after_mean_sd = f"{after['mean']:.1f}±{after['sd']:.1f}"
            change_mean_sd = f"{change['mean']:.1f}±{change['sd']:.1f}" if change else '-'

            table_data.append([
                f"{lab_name} ({unit})" if unit else lab_name,
                n_paired,
                n_before_only,
                n_after_only,
                before_mean_sd,
                after_mean_sd,
                change_mean_sd,
                normal_range
            ])

        if not table_data:
            print("  Skipping lab values summary CSV (no valid data)")
            return

        # Write to CSV
        csv_path = os.path.join(self.output_dir, 'treatment_lab_values_summary.csv')
        headers = ['Lab Parameter', 'N (Paired)', 'N (Before only)', 'N (After only)',
                   'Before (Mean±SD)', 'After (Mean±SD)', 'Change (Mean±SD)', 'Normal Range']

        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(table_data)

        print(f"  Saved: treatment_lab_values_summary.csv")

    def plot_rbc_dose_per_ebv_by_gender(self):
        """
        Create violin plot for RBC dose normalized by estimated blood volume (Nadler),
        stratified by gender.
        """
        by_gender = self.data.get('by_gender', {})
        dosages_data = by_gender.get('dosages_normalized', {})

        if not dosages_data:
            print("  Skipping RBC dose/EBV plot (no normalized dosage data)")
            return

        rbc_name = 'Red blood cell concentrate (RBC)'

        # Get raw values for each gender
        male_data = None
        female_data = None

        if 'Male' in dosages_data and rbc_name in dosages_data['Male']:
            male_info = dosages_data['Male'][rbc_name]
            male_data = male_info.get('values', [])

        if 'Female' in dosages_data and rbc_name in dosages_data['Female']:
            female_info = dosages_data['Female'][rbc_name]
            female_data = female_info.get('values', [])

        has_male = male_data is not None and len(male_data) >= MIN_OBSERVATIONS_VIOLIN
        has_female = female_data is not None and len(female_data) >= MIN_OBSERVATIONS_VIOLIN

        if not has_male and not has_female:
            print("  Skipping RBC dose/EBV plot - insufficient data")
            return

        fig, ax = plt.subplots(figsize=(6, 6))

        male_color = '#f46d43'
        female_color = '#74add1'

        positions = []
        data_sets = []
        labels = []
        colors = []

        if has_male:
            positions.append(0.8)
            data_sets.append(male_data)
            labels.append(f'Male\n(n={len(male_data)})')
            colors.append(male_color)

        if has_female:
            positions.append(1.2)
            data_sets.append(female_data)
            labels.append(f'Female\n(n={len(female_data)})')
            colors.append(female_color)

        for i, (pos, data, color) in enumerate(zip(positions, data_sets, colors)):
            vp = ax.violinplot([data], positions=[pos], showmeans=False,
                               showmedians=False, showextrema=False, widths=0.35)

            for body in vp['bodies']:
                body.set_facecolor(color)
                body.set_alpha(0.4)
                body.set_edgecolor(color)
                body.set_linewidth(1.5)

            bp = ax.boxplot([data], positions=[pos], widths=0.1,
                           showfliers=True, patch_artist=True,
                           flierprops=dict(marker='o', markerfacecolor=color,
                                          markeredgecolor=color, markersize=3, alpha=0.5))

            for patch in bp['boxes']:
                patch.set_facecolor('white')
                patch.set_alpha(0.9)
                patch.set_edgecolor(color)
                patch.set_linewidth(1.5)

            for item in bp['medians']:
                item.set_color(color)
                item.set_linewidth(2)

            for item in bp['whiskers']:
                item.set_color(color)
                item.set_linewidth(1.5)

            for item in bp['caps']:
                item.set_color(color)
                item.set_linewidth(1.5)

            mean_val = np.mean(data)
            ax.scatter([pos], [mean_val], color='#d73027', marker='D', s=40, zorder=10,
                       edgecolors='white', linewidths=0.5)

        ax.set_xticks(positions)
        ax.set_xticklabels(labels, fontsize=FONT_SIZE_LABEL)
        ax.set_xlim(0.4, 1.6)

        ax.set_ylabel('RBC dose (ml/L EBV)', fontsize=FONT_SIZE_LABEL)
        ax.set_title('RBC dose per estimated blood volume', fontsize=FONT_SIZE_TITLE, fontweight='bold', pad=15)

        ax.yaxis.grid(True, linestyle='--', alpha=0.3)
        ax.set_axisbelow(True)

        fig.tight_layout()
        self._save_figure(fig, 'rbc_dose_per_ebv_by_gender')
        plt.close(fig)
        print("  Saved: rbc_dose_per_ebv_by_gender.png")

    def generate_all_visualizations(self):
        """Generate all treatment visualizations."""
        print("\nGenerating treatment visualizations...")

        print("  Creating product distribution...")
        self.plot_product_distribution()

        print("  Creating temporal trends...")
        self.plot_temporal_trends()

        print("  Creating lab value violin plots (before/after)...")
        self.plot_all_lab_values()

        print("  Creating lab value violin plots by gender...")
        self.plot_lab_values_by_gender()

        print("  Creating RBC dose per EBV by gender...")
        self.plot_rbc_dose_per_ebv_by_gender()

        print("  Creating administration frequency distribution...")
        self.plot_administration_frequency()

        print("  Creating administration frequency by gender...")
        self.plot_administration_frequency_by_gender()

        print("  Creating administration frequency by gender (percentages)...")
        self.plot_administration_frequency_by_gender_percent()

        print("  Creating product summary CSV...")
        self.save_product_summary_csv()

        print("  Creating lab values summary CSV...")
        self.save_lab_values_summary_csv()

        print(f"\nAll visualizations saved to: {self.output_dir}")


def run_treatment_visualization(analysis_output_dir: str, figure_output_dir: str = None,
                                 raw_data_path: str = None):
    """
    Run treatment visualization generation.

    Args:
        analysis_output_dir: Directory containing treatment_statistics_detailed.json
        figure_output_dir: Directory where figures will be saved (default: analysis_output_dir/figures)
        raw_data_path: Path to raw CSV data file for violin plots

    Returns:
        TreatmentVisualizer instance
    """
    json_path = os.path.join(analysis_output_dir, 'treatment_statistics_detailed.json')

    if not os.path.exists(json_path):
        raise FileNotFoundError(f"Could not find {json_path}")

    if figure_output_dir is None:
        figure_output_dir = os.path.join(analysis_output_dir, 'figures')

    visualizer = TreatmentVisualizer(json_path, figure_output_dir, raw_data_path)
    visualizer.generate_all_visualizations()

    return visualizer


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python visualize_treatments.py <analysis_output_dir> [figure_output_dir] [raw_data_path]")
        print("Example: python visualize_treatments.py test_data_150patients test_data_150patients/figures ../test_data_150patients.csv")
        sys.exit(1)

    analysis_dir = sys.argv[1]
    figure_dir = sys.argv[2] if len(sys.argv) > 2 else None
    raw_data = sys.argv[3] if len(sys.argv) > 3 else None

    run_treatment_visualization(analysis_dir, figure_dir, raw_data)
