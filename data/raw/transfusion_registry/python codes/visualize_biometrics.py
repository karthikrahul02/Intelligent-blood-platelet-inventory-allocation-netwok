"""
Biometric Data Visualization Module

This module creates publication-quality visualizations for biometric descriptive statistics
from transfusion registry data.

Input: biometric_descriptives_detailed.json
Output: PNG figures and CSV table with statistical visualizations

Visualizations created:
- Gender distribution pie chart (PNG)
- Biometric measurements box plots (Age, BMI) (PNG)
- Statistical summary table (CSV)

Author: Elina Nuerenberg-Goloub with Claude Sonnet 4.5 by Anthropic
Date: 10-20-2025
Revised on 2026-01-25 by Elina Nuerenberg-Goloub and Claude Opus 4.5
"""

import json
import os
import csv
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Headless-safe backend; must be set before importing pyplot
import matplotlib.pyplot as plt
from typing import Dict, Any, Tuple, Optional

# Colorblind-friendly color scheme (diverging warm-to-cold palette)
COLORS = {
    'primary': '#4575b4',      # Dark blue - main data
    'secondary': '#74add1',    # Medium blue - accents
    'highlight': '#d73027',    # Dark red - overlays, female
    'alternate': '#f46d43',    # Orange - alternative
    'color5': '#fdae61',       # Light orange
    'color6': '#abd9e9',       # Light blue 2
    'color7': '#e0f3f8',       # Light blue 1
    'color8': '#fee090',       # Yellow
    'unknown': '#b3b3b3',      # Gray - missing/unknown/other
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
FONT_SIZE_LEGEND = 18


class BiometricVisualizer:
    """Creates visualizations for biometric descriptive statistics."""

    def __init__(self, json_path: str, output_dir: str, raw_data_path: Optional[str] = None):
        """
        Initialize the visualizer.

        Args:
            json_path: Path to biometric_descriptives_detailed.json
            output_dir: Directory where visualizations will be saved
            raw_data_path: Optional path to raw CSV for violin plots
        """
        self.json_path = json_path
        self.output_dir = output_dir
        self.raw_data_path = raw_data_path
        self.raw_data = None
        self.loader = None

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Load summary data
        with open(json_path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)

        # Load raw data if path provided (for violin plots)
        if raw_data_path and os.path.exists(raw_data_path):
            self._load_raw_data(raw_data_path)

    def _load_raw_data(self, csv_path: str):
        """Load raw data from CSV for violin plots."""
        try:
            import pandas as pd
            # Load with the transfusion data loader to handle the 7-row header
            from transfusion_data_loader import TransfusionDataLoader
            loader = TransfusionDataLoader()
            loader.load_data(csv_path)
            self.raw_data = loader.df_clean
            self.loader = loader
            print(f"  Loaded raw data: {len(self.raw_data)} records")
        except Exception as e:
            print(f"  Warning: Could not load raw data for violin plots: {e}")
            self.raw_data = None
            self.loader = None

    # BMI plausibility limits in kg/m² (must match the descriptive statistics module)
    BMI_PLAUSIBLE_RANGE = (10, 60)

    def _get_patient_level_biometrics(self):
        """
        Build a patient-level dataframe (one row per PID) with calculated
        '_age' and '_bmi' columns.

        Age is calculated the same way as in the descriptive statistics module
        (loader.calculate_age: episode-date year minus birth year, valid range
        0-120 years). BMI uses the plausibility filter 10-60 kg/m².

        As in the descriptive statistics module, only TRANSFUSION patients
        (at least one blood product administration) are included, and the
        first record per patient (chronological) is used.

        Returns:
            Patient-level DataFrame or None if no raw data is available.
        """
        import pandas as pd

        if self.raw_data is None:
            return None

        df = self.raw_data

        # Restrict to transfusion patients (same as the descriptive statistics
        # module); if the product column is missing, keep all patients
        product_col = 'X_433_7_746'
        if product_col in df.columns:
            transfusion_pids = df.loc[df[product_col].notna(), 'PID'].unique()
            df = df[df['PID'].isin(transfusion_pids)]

        # One REAL row per patient (same rule as the descriptive statistics
        # module: most complete basic data, earliest episode - never a
        # per-column composite of several rows)
        from transfusion_data_loader import select_patient_index_rows
        df_patient = select_patient_index_rows(df).reset_index(drop=True)

        # Age: use the loader's calculate_age as the reference implementation
        ages = None
        if self.loader is not None:
            try:
                original_df = self.loader.df_clean
                try:
                    self.loader.df_clean = df_patient
                    ages = self.loader.calculate_age()
                finally:
                    self.loader.df_clean = original_df
            except Exception as e:
                print(f"  Warning: Could not calculate age via data loader: {e}")
                ages = None

        if ages is None:
            # Fallback: replicate loader.calculate_age
            # (episode-date year minus birth year, valid range 0-120)
            birth_year_col = 'X_541_0_1'
            if birth_year_col in df_patient.columns:
                birth_years = pd.to_numeric(df_patient[birth_year_col], errors='coerce')
                if 'Episode date' in df_patient.columns:
                    ref_year = pd.to_datetime(df_patient['Episode date'], errors='coerce').dt.year
                else:
                    ref_year = pd.Timestamp.now().year
                ages = ref_year - birth_years
                ages = ages.where((ages >= 0) & (ages <= 120))

        if ages is not None:
            df_patient['_age'] = ages

        # BMI from height (cm) and weight (kg)
        height_col = 'X_433_0_2'
        weight_col = 'X_433_0_3'
        if height_col in df_patient.columns and weight_col in df_patient.columns:
            heights = pd.to_numeric(df_patient[height_col], errors='coerce') / 100  # cm to m
            weights = pd.to_numeric(df_patient[weight_col], errors='coerce')
            bmi = weights / (heights ** 2)
            bmi_min, bmi_max = self.BMI_PLAUSIBLE_RANGE
            df_patient['_bmi'] = bmi.where((bmi >= bmi_min) & (bmi <= bmi_max))

        return df_patient

    def _set_matplotlib_defaults(self):
        """Set matplotlib defaults for consistent styling."""
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


    def plot_sex_distribution(self):
        """Create gender distribution pie chart."""
        gender_data = self.data.get('gender')

        if not gender_data:
            print("  Skipping gender distribution (no data)")
            return

        # Prepare data
        labels = []
        sizes = []
        colors = []

        if gender_data['Male']['n'] > 0:
            labels.append("Male")
            sizes.append(gender_data['Male']['n'])
            colors.append(COLORS['primary'])

        if gender_data['Female']['n'] > 0:
            labels.append("Female")
            sizes.append(gender_data['Female']['n'])
            colors.append(COLORS['highlight'])

        if gender_data.get('Intersex/Diverse', {}).get('n', 0) > 0:
            labels.append("Intersex/Diverse")
            sizes.append(gender_data['Intersex/Diverse']['n'])
            colors.append(COLORS['secondary'])

        if gender_data.get('Not provided', {}).get('n', 0) > 0:
            labels.append("Not provided")
            sizes.append(gender_data['Not provided']['n'])
            colors.append(COLORS['unknown'])

        if not sizes:
            print("  Skipping gender distribution (no data)")
            return

        total_n = sum(sizes)

        # Create figure
        fig, ax = plt.subplots(figsize=(8, 6))

        # Create pie chart without percentages on slices
        wedges, texts = ax.pie(
            sizes,
            colors=colors,
            startangle=90
        )

        # Equal aspect ratio ensures circular pie
        ax.axis('equal')

        # Title with total N
        ax.set_title(f'Gender Distribution (n = {total_n})', fontsize=FONT_SIZE_TITLE, fontweight='bold', pad=20)

        # Create legend with only name and percent
        legend_labels = []
        for label, size in zip(labels, sizes):
            percent = (size / sum(sizes)) * 100
            legend_labels.append(f'{label} ({percent:.1f}%)')

        ax.legend(legend_labels,
                  loc='center left',
                  bbox_to_anchor=(1, 0.5),
                  fontsize=FONT_SIZE_LEGEND,
                  frameon=True,
                  facecolor='white',
                  edgecolor='gray')

        self._save_figure(fig, 'biometric_gender_distribution')
        plt.close(fig)


    def plot_anthropometric_violins(self):
        """Create violin plots with embedded box plots for continuous biometric measures.

        Violin plots are only ever rendered from real (raw) patient-level data.
        If no raw data is available for a variable, that violin is skipped with
        a prominent warning - simulated distributions are never plotted.
        """
        # Determine which variables are available
        # (JSON structure: age = {'overall': {...}, 'by_gender': {...}})
        variables = []

        # Age
        age_overall = (self.data.get('age') or {}).get('overall') or {}
        if age_overall.get('n', 0) > 0:
            variables.append(('age', 'Age (years)', 'Age', age_overall))

        # BMI
        if self.data.get('bmi') and 'overall' in self.data['bmi']:
            bmi_data = self.data['bmi']['overall']
            if bmi_data.get('n', 0) > 0:
                variables.append(('bmi', 'BMI (kg/m²)', 'BMI', bmi_data))

        if not variables:
            print("  Skipping violin plots (no continuous data available)")
            return

        # Get raw patient-level data (one row per patient - same dedup as the
        # by-gender plots, so multi-transfused patients are not overweighted)
        raw_values = {}
        df_patient = self._get_patient_level_biometrics()
        if df_patient is not None:
            if '_age' in df_patient.columns:
                raw_values['age'] = df_patient['_age'].dropna().values
            if '_bmi' in df_patient.columns:
                raw_values['bmi'] = df_patient['_bmi'].dropna().values

        # Only variables with real raw data are plotted
        plottable = []
        for var in variables:
            var_key, _, var_title, _ = var
            if var_key in raw_values and len(raw_values[var_key]) > 10:
                plottable.append(var)
            else:
                missing_input = self.raw_data_path or 'raw data CSV (no raw_data_path provided)'
                print(f"  WARNING: Skipping '{var_title}' violin plot - no raw data available "
                      f"(missing input: {missing_input}). "
                      f"Simulated data is never rendered as a distribution.")

        if not plottable:
            print("  Skipping violin plots (no raw data available for any variable)")
            return

        # Create figure with appropriate number of subplots
        n_vars = len(plottable)
        fig, axes = plt.subplots(1, n_vars, figsize=(4 * n_vars, 6))

        # Make axes iterable even if only one subplot
        if n_vars == 1:
            axes = [axes]

        # Grey color for demographics (not attributed to blood products)
        violin_color = '#808080'  # Medium grey
        violin_color_light = '#b0b0b0'  # Light grey for violin body

        for ax, (var_key, ylabel, title, var_data) in zip(axes, plottable):
            n = var_data['n']
            data = raw_values[var_key]

            # Create violin plot
            vp = ax.violinplot([data], positions=[1], showmeans=False,
                               showmedians=False, showextrema=False, widths=0.8)

            # Style the violin
            for body in vp['bodies']:
                body.set_facecolor(violin_color_light)
                body.set_edgecolor(violin_color)
                body.set_alpha(0.7)
                body.set_linewidth(1.5)

            # Add box plot inside (thin)
            bp = ax.boxplot([data], positions=[1], widths=0.15,
                           showfliers=True, patch_artist=True,
                           flierprops=dict(marker='o', markersize=4,
                                          markerfacecolor=violin_color,
                                          markeredgecolor=violin_color,
                                          alpha=0.6))

            # Style the box plot
            for patch in bp['boxes']:
                patch.set_facecolor('white')
                patch.set_edgecolor(violin_color)
                patch.set_linewidth(1.5)

            for element in ['whiskers', 'caps']:
                for item in bp[element]:
                    item.set_color(violin_color)
                    item.set_linewidth(1.5)

            for item in bp['medians']:
                item.set_color('#d73027')  # Red median line
                item.set_linewidth(2)

            # Add mean marker
            mean_val = var_data['mean']
            ax.scatter([1], [mean_val], color='#d73027', marker='D', s=50, zorder=5,
                      edgecolor='white', linewidth=1, label=f'Mean: {mean_val:.1f}')

            # Labels
            ax.set_ylabel(ylabel, fontsize=FONT_SIZE_LABEL)
            ax.set_title(f'{title} (n = {n})', fontsize=FONT_SIZE_TITLE, fontweight='bold', pad=15)
            ax.set_xticks([])
            ax.set_xlim(0.4, 1.6)

            # Grid
            ax.grid(axis='y', alpha=0.3, linestyle='--', linewidth=0.5)
            ax.set_axisbelow(True)

        plt.tight_layout()
        self._save_figure(fig, 'biometric_violins')
        plt.close(fig)

    def plot_biometrics_by_gender(self):
        """Create violin plots for age and BMI stratified by sex."""
        if self.raw_data is None:
            print("  Skipping gender-stratified biometric plots (no raw data)")
            return

        # Colors for gender (orange and light blue)
        male_color = '#f46d43'    # Orange
        female_color = '#74add1'  # Light blue

        # Gender column
        gender_col = 'X_433_0_4'
        if gender_col not in self.raw_data.columns:
            print("  Skipping gender-stratified biometric plots (no gender column)")
            return

        # Get patient-level data with calculated age and BMI (same dedup,
        # age calculation, and plausibility filters as the overall violins)
        df_patient = self._get_patient_level_biometrics()
        if df_patient is None:
            print("  Skipping gender-stratified biometric plots (no raw data)")
            return

        # Prepare data for plots
        plot_data = {}

        # Age (episode-date year minus birth year, via loader.calculate_age)
        if '_age' in df_patient.columns:
            male_ages = df_patient.loc[df_patient[gender_col] == 'M', '_age'].dropna().values
            female_ages = df_patient.loc[df_patient[gender_col] == 'F', '_age'].dropna().values

            if len(male_ages) >= 5 and len(female_ages) >= 5:
                plot_data['age'] = {
                    'Male': male_ages,
                    'Female': female_ages,
                    'label': 'Age (years)',
                    'title': 'Age'
                }

        # BMI (calculated from height and weight, plausibility filter 10-60)
        if '_bmi' in df_patient.columns:
            male_bmi = df_patient.loc[df_patient[gender_col] == 'M', '_bmi'].dropna().values
            female_bmi = df_patient.loc[df_patient[gender_col] == 'F', '_bmi'].dropna().values

            if len(male_bmi) >= 5 and len(female_bmi) >= 5:
                plot_data['bmi'] = {
                    'Male': male_bmi,
                    'Female': female_bmi,
                    'label': 'BMI (kg/m²)',
                    'title': 'BMI'
                }

        if not plot_data:
            print("  Skipping gender-stratified biometric plots (insufficient data)")
            return

        # Create individual plots for each variable
        for var_key, var_info in plot_data.items():
            male_data = var_info['Male']
            female_data = var_info['Female']

            fig, ax = plt.subplots(figsize=(6, 6))

            # Positions for violins
            positions = [1, 2]

            # Create violin plots
            vp = ax.violinplot([male_data, female_data], positions=positions,
                              showmeans=False, showmedians=False, showextrema=False, widths=0.7)

            # Style violins
            colors = [male_color, female_color]
            for i, body in enumerate(vp['bodies']):
                body.set_facecolor(colors[i])
                body.set_edgecolor(colors[i])
                body.set_alpha(0.7)
                body.set_linewidth(1.5)

            # Add box plots inside with outliers
            bp = ax.boxplot([male_data, female_data], positions=positions, widths=0.15,
                           showfliers=True, patch_artist=True,
                           flierprops=dict(marker='o', markersize=4, alpha=0.6))

            for i, (patch, color) in enumerate(zip(bp['boxes'], colors)):
                patch.set_facecolor('white')
                patch.set_edgecolor(color)
                patch.set_linewidth(1.5)

            for element in ['whiskers', 'caps']:
                for j, item in enumerate(bp[element]):
                    item.set_color(colors[j // 2])
                    item.set_linewidth(1.5)

            for j, item in enumerate(bp['medians']):
                item.set_color(colors[j])
                item.set_linewidth(2)

            # Style outlier points with matching colors
            for j, flier in enumerate(bp['fliers']):
                flier.set_markerfacecolor(colors[j])
                flier.set_markeredgecolor(colors[j])

            # Add mean diamond markers (red for visibility)
            male_mean = np.mean(male_data)
            female_mean = np.mean(female_data)
            ax.scatter([1], [male_mean], color='#d73027', marker='D', s=60, zorder=5,
                      edgecolor='white', linewidth=1)
            ax.scatter([2], [female_mean], color='#d73027', marker='D', s=60, zorder=5,
                      edgecolor='white', linewidth=1)

            # Labels and title
            ax.set_ylabel(var_info['label'], fontsize=FONT_SIZE_LABEL)
            ax.set_title(f"{var_info['title']} by Sex",
                        fontsize=FONT_SIZE_TITLE, fontweight='bold', pad=15)
            ax.set_xticks(positions)
            ax.set_xticklabels([f'Male\n(n={len(male_data)})', f'Female\n(n={len(female_data)})'])
            ax.set_xlim(0.4, 2.6)

            # Grid
            ax.grid(axis='y', alpha=0.3, linestyle='--', linewidth=0.5)
            ax.set_axisbelow(True)

            plt.tight_layout()
            self._save_figure(fig, f'biometric_{var_key}_by_gender')
            plt.close(fig)

    def plot_anthropometric_boxplots(self):
        """Legacy method - redirects to violin plots."""
        self.plot_anthropometric_violins()

    def save_summary_table_csv(self):
        """Save statistical summary table as CSV file."""
        table_data = []

        # Add gender row
        if 'gender' in self.data:
            gender_data = self.data['gender']
            male_n = gender_data.get('Male', {}).get('n', 0)
            female_n = gender_data.get('Female', {}).get('n', 0)
            other_n = gender_data.get('Intersex/Diverse', {}).get('n', 0)
            not_prov_n = gender_data.get('Not provided', {}).get('n', 0)

            gender_row = [
                'Gender',
                f"{male_n} M, {female_n} F, {other_n} D, {not_prov_n} NP",
                f"{gender_data['Male']['percent']:.1f}% M, {gender_data['Female']['percent']:.1f}% F",
                '-',
                '-'
            ]
            table_data.append(gender_row)

        # Add age (JSON structure: age = {'overall': {...}, 'by_gender': {...}})
        age_data = (self.data.get('age') or {}).get('overall') or {}
        if age_data:
            if age_data.get('n', 0) > 0:
                n = age_data['n']
                mean = age_data['mean']
                sd = age_data['sd']
                median = age_data['median']
                q1 = age_data.get('q25', age_data.get('q1'))
                q3 = age_data.get('q75', age_data.get('q3'))
                min_val = age_data['min']
                max_val = age_data['max']

                row = [
                    'Age (years)',
                    str(n),
                    f"{mean:.1f}±{sd:.1f}",
                    f"{median:.1f} ({q1:.1f}-{q3:.1f})",
                    f"{min_val:.1f}-{max_val:.1f}"
                ]
                table_data.append(row)

        # Add BMI
        if 'bmi' in self.data and 'overall' in self.data['bmi']:
            bmi_data = self.data['bmi']['overall']
            if bmi_data.get('n', 0) > 0:
                n = bmi_data['n']
                mean = bmi_data['mean']
                sd = bmi_data['sd']
                median = bmi_data['median']
                q1 = bmi_data.get('q25', bmi_data.get('q1'))
                q3 = bmi_data.get('q75', bmi_data.get('q3'))
                min_val = bmi_data['min']
                max_val = bmi_data['max']

                row = [
                    'BMI (kg/m²)',
                    str(n),
                    f"{mean:.1f}±{sd:.1f}",
                    f"{median:.1f} ({q1:.1f}-{q3:.1f})",
                    f"{min_val:.1f}-{max_val:.1f}"
                ]
                table_data.append(row)

        # Add blood group
        if 'blood_group' in self.data:
            bg_data = self.data['blood_group']
            a_n = bg_data.get('A', {}).get('n', 0)
            b_n = bg_data.get('B', {}).get('n', 0)
            ab_n = bg_data.get('AB', {}).get('n', 0)
            o_n = bg_data.get('0', {}).get('n', 0)
            np_n = bg_data.get('Not provided', {}).get('n', 0)

            bg_row = [
                'Blood Group',
                f"{a_n} A, {b_n} B, {ab_n} AB, {o_n} 0",
                f"{np_n} not provided",
                '-',
                '-'
            ]
            table_data.append(bg_row)

        if not table_data:
            print("  Skipping summary table (no data available)")
            return

        # Write to CSV
        csv_path = os.path.join(self.output_dir, 'biometric_summary_table.csv')
        headers = ['Variable', 'N', 'Mean±SD', 'Median (IQR)', 'Range']

        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(table_data)

        print(f"  Saved: biometric_summary_table.csv")

    def generate_all_visualizations(self):
        """Generate all biometric visualizations."""
        print("\nGenerating biometric visualizations...")
        self._set_matplotlib_defaults()

        print("  Creating gender distribution...")
        self.plot_sex_distribution()

        print("  Creating biometric violin plots...")
        self.plot_anthropometric_violins()

        print("  Creating biometric plots by gender...")
        self.plot_biometrics_by_gender()

        print("  Creating summary table CSV...")
        self.save_summary_table_csv()

        print(f"\nAll visualizations saved to: {self.output_dir}")


def run_biometric_visualization(analysis_output_dir: str, figure_output_dir: str = None,
                                raw_data_path: str = None):
    """
    Run biometric visualization generation.

    Args:
        analysis_output_dir: Directory containing biometric_descriptives_detailed.json
        figure_output_dir: Directory where figures will be saved (default: analysis_output_dir/figures)
        raw_data_path: Optional path to raw CSV data for violin plots

    Returns:
        BiometricVisualizer instance
    """
    json_path = os.path.join(analysis_output_dir, 'biometric_descriptives_detailed.json')

    if not os.path.exists(json_path):
        raise FileNotFoundError(f"Could not find {json_path}")

    if figure_output_dir is None:
        figure_output_dir = os.path.join(analysis_output_dir, 'figures')

    # Try to find raw data if not provided: derive '<analysis_dir_name>.csv'
    # from the analysis directory name (never a hardcoded filename)
    if raw_data_path is None:
        analysis_dir_abs = os.path.abspath(analysis_output_dir)
        analysis_dir_name = os.path.basename(os.path.normpath(analysis_dir_abs))
        candidates = [
            os.path.join(os.path.dirname(analysis_dir_abs), f'{analysis_dir_name}.csv'),
            os.path.join(os.path.dirname(os.path.dirname(analysis_dir_abs)), f'{analysis_dir_name}.csv'),
        ]
        for path in candidates:
            if os.path.exists(path):
                raw_data_path = path
                break
        if raw_data_path is None:
            print(f"  Warning: No raw data CSV found (tried: {', '.join(candidates)}). "
                  f"Violin plots requiring raw data will be skipped.")

    visualizer = BiometricVisualizer(json_path, figure_output_dir, raw_data_path)
    visualizer.generate_all_visualizations()

    return visualizer


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python visualize_biometrics.py <analysis_output_dir> [figure_output_dir] [raw_data_csv]")
        print("Example: python visualize_biometrics.py test_data_150patients test_data_150patients/figures ../test_data_150patients.csv")
        sys.exit(1)

    analysis_dir = sys.argv[1]
    figure_dir = sys.argv[2] if len(sys.argv) > 2 else None
    raw_csv = sys.argv[3] if len(sys.argv) > 3 else None

    run_biometric_visualization(analysis_dir, figure_dir, raw_csv)
