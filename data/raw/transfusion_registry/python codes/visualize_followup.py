"""
Follow-Up Statistics Visualization Module

This module creates publication-quality visualizations for follow-up statistics
from transfusion registry data.

Input: followup_statistics_detailed.json
Output: PNG figures and CSV table with follow-up visualizations

Visualizations created:
- Grouped category-distribution bars for CFS and Physical Capacity (baseline vs 3-month, from the transition matrix) (PNG)
- Donut charts for categorical outcomes (PNG)
- Follow-up completion and outcomes summary table (CSV)

Author: Elina Nuerenberg-Goloub with Claude Sonnet 4.5 by Anthropic
Date: 10-20-2025
Revised on 2026-01-21 by Elina Nuerenberg-Goloub and Claude Opus 4.5
"""

import json
import os
import csv
import pandas as pd
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
    'unknown': '#b3b3b3',      # Gray - for "Unknown" or "Refused to answer"
    'background': '#fee090',   # Light yellow background
    'text': '#000000',         # Black text
    'baseline': '#d73027',     # Dark red for baseline
    'followup': '#4575b4',     # Dark blue for follow-up
}

# Full colorblind-friendly palette for donut charts (10 colors)
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


class FollowUpVisualizer:
    """Creates visualizations for follow-up descriptive statistics."""

    def __init__(self, json_path: str, output_dir: str):
        """
        Initialize the visualizer.

        Args:
            json_path: Path to followup_statistics_detailed.json
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

    def plot_baseline_followup_barcharts(self):
        """
        Baseline vs 3-month follow-up as CATEGORY DISTRIBUTIONS (grouped bars
        per category, derived from the transition matrix marginals). Both
        measures are ordinal - the physical-capacity codes index the
        categories 1, 3, 4, 10, and >10 MET - so the figure compares
        frequencies instead of averaging category codes.
        """
        comparison_data = self.data.get('3month', {}).get('baseline_followup_comparison', {})

        if not comparison_data:
            print("  Skipping baseline-followup bar charts (no data)")
            return

        CAPACITY_LABELS = {1: '1 MET', 2: '3 MET', 3: '4 MET',
                           4: '10 MET', 5: '>10 MET'}
        measures = []
        if 'physical_capacity' in comparison_data:
            measures.append({
                'name': 'Physical Capacity',
                'data': comparison_data['physical_capacity'],
                'categories': list(range(1, 6)),
                'labels': [CAPACITY_LABELS[c] for c in range(1, 6)],
                'xlabel': 'Physical capacity category',
            })
        if 'frailty_cfs' in comparison_data:
            measures.append({
                'name': 'Clinical Frailty Scale',
                'data': comparison_data['frailty_cfs'],
                'categories': list(range(1, 10)),
                'labels': [str(c) for c in range(1, 10)],
                'xlabel': 'CFS grade',
            })
        measures = [m for m in measures if m['data'].get('transition_matrix')]
        if not measures:
            print("  Skipping baseline-followup bar charts (no valid measures)")
            return

        fig, axes = plt.subplots(1, len(measures), figsize=(7.5 * len(measures), 6))
        if len(measures) == 1:
            axes = [axes]

        for ax, measure in zip(axes, measures):
            n = measure['data']['n']
            matrix = measure['data']['transition_matrix']
            cats = measure['categories']
            # marginal distributions from the transition matrix
            baseline_counts = [sum(matrix.get(str(c), {}).values()) for c in cats]
            followup_counts = [
                sum(row.get(str(c), 0) for row in matrix.values()) for c in cats]

            change_info = measure['data']['change']
            width = 0.38
            xs = list(range(len(cats)))
            ax.bar([x - width / 2 for x in xs], baseline_counts, width,
                   color=COLORS['baseline'], alpha=0.7, edgecolor='black',
                   linewidth=1.2, label='Baseline')
            ax.bar([x + width / 2 for x in xs], followup_counts, width,
                   color=COLORS['followup'], alpha=0.7, edgecolor='black',
                   linewidth=1.2, label='3-month follow-up')

            change_text = (f"Improved: {change_info['improved']}\n"
                           f"Unchanged: {change_info['unchanged']}\n"
                           f"Worsened: {change_info['worsened']}")
            ax.text(0.98, 0.78, change_text, transform=ax.transAxes,
                    fontsize=FONT_SIZE_TICK, va='top', ha='right',
                    bbox=dict(boxstyle='round', facecolor='white',
                              edgecolor='gray', alpha=0.85))

            ax.set_xticks(xs)
            rot = 30 if len(measure['labels']) <= 6 else 0
            ax.set_xticklabels(measure['labels'], fontsize=FONT_SIZE_TICK,
                               rotation=rot, ha='right' if rot else 'center')
            ax.set_xlabel(measure['xlabel'], fontsize=FONT_SIZE_LABEL)
            ax.set_ylabel('Number of patients', fontsize=FONT_SIZE_LABEL)
            top = max(baseline_counts + followup_counts + [1])
            ax.set_ylim(0, top * 1.5)
            ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
            ax.set_title(f"{measure['name']} (n = {n} paired)",
                         fontsize=FONT_SIZE_TITLE, fontweight='bold', pad=15)
            ax.legend(fontsize=FONT_SIZE_TICK, loc='upper left')
            ax.yaxis.grid(True, linestyle='--', alpha=0.3)
            ax.set_axisbelow(True)

        fig.tight_layout(w_pad=3.0)
        self._save_figure(fig, 'followup_baseline_comparison')
        plt.close(fig)

    def _sort_and_color_categories(self, distribution: Dict[str, Any]) -> Tuple[List[str], List[int], List[float], List[str]]:
        """
        Sort categories by size and assign colors.
        "Unknown", "no answer", and similar categories are always gray.

        Args:
            distribution: Dictionary of category names and their data

        Returns:
            Tuple of (sorted_labels, sorted_sizes, sorted_percentages, sorted_colors)
        """
        # Categories that should always be gray
        gray_categories = ['unknown', 'refused to answer', 'cannot answer', 'refused_to_answer', 'no answer']

        # Separate gray categories from regular ones
        gray_data = []
        regular_data = []

        for category_name, category_data in distribution.items():
            count = category_data['n']
            percent = category_data['percent']

            # Skip categories with NaN or invalid counts
            if pd.isna(count) or count is None:
                continue
            count = int(count)  # Ensure integer

            if pd.isna(percent) or percent is None:
                percent = 0.0

            # Clean up label: replace "refused_to_answer" with "no answer"
            display_name = category_name
            if category_name.lower().replace('_', ' ') == 'refused to answer':
                display_name = 'no answer'

            if category_name.lower() in gray_categories or category_name.lower().replace('_', ' ') in gray_categories:
                gray_data.append((display_name, count, percent))
            else:
                regular_data.append((display_name, count, percent))

        # Sort regular categories by size (descending)
        regular_data.sort(key=lambda x: x[1], reverse=True)

        # Add gray categories at the end
        all_data = regular_data + gray_data

        # Extract sorted data
        labels = [x[0] for x in all_data]
        sizes = [x[1] for x in all_data]
        percentages = [x[2] for x in all_data]

        # Assign colors based on size (excluding gray categories)
        colors = []
        for i, (label, _, _) in enumerate(all_data):
            if label.lower() in gray_categories:
                colors.append(COLORS['unknown'])
            else:
                # Use position in regular_data for color assignment
                regular_idx = [x[0] for x in regular_data].index(label)
                colors.append(COLOR_PALETTE_BY_SIZE[regular_idx % len(COLOR_PALETTE_BY_SIZE)])

        return labels, sizes, percentages, colors

    def plot_categorical_outcome(self, outcome_name: str, outcome_data: Dict[str, Any],
                                 timepoint: str, title_prefix: str):
        """
        Create donut chart for a categorical outcome.

        Args:
            outcome_name: Name of the outcome (for filename)
            outcome_data: Data dictionary with 'distribution' or direct category data
            timepoint: '3month' or '1year'
            title_prefix: Prefix for the chart title
        """
        # Handle different data structures
        if 'distribution' in outcome_data:
            distribution = outcome_data['distribution']
            total = outcome_data.get('total', sum(d['n'] for d in distribution.values()))
        else:
            # Direct category data (e.g., anaemia_diagnosed)
            distribution = {k: v for k, v in outcome_data.items() if k != 'total'}
            total = outcome_data.get('total', sum(d['n'] for d in distribution.values()))

        if not distribution:
            print(f"  Skipping {outcome_name} ({timepoint}) (no data)")
            return

        # Sort and color categories
        labels, sizes, percentages, colors = self._sort_and_color_categories(distribution)

        # Skip if all sizes are zero or empty
        if not sizes or sum(sizes) == 0:
            print(f"  Skipping {outcome_name} ({timepoint}) (all values are zero)")
            return

        # Add a residual wedge so the donut geometry matches the denominator
        # (total, which is also shown as n in the title). Legend percentages
        # are relative to `total`, so without this wedge the listed categories
        # would be visually inflated.
        residual_n = total - sum(sizes)
        if residual_n > 0 and total > 0:
            labels.append('No response')
            sizes.append(residual_n)
            percentages.append(residual_n / total * 100)
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

        # Title with total N
        timepoint_label = '3-Month' if timepoint == '3month' else '1-Year'
        ax.set_title(f'{title_prefix} - {timepoint_label} (n = {total})',
                     fontsize=FONT_SIZE_TITLE, fontweight='bold', pad=20)

        # Create legend with category names and percentages (already sorted)
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
        safe_filename = f'followup_{outcome_name}_{timepoint}'
        self._save_figure(fig, safe_filename)
        plt.close(fig)

    def plot_all_categorical_outcomes(self):
        """Create donut charts for all categorical outcomes."""
        # Outcomes to visualize
        outcomes = [
            {
                'name': 'anaemia_diagnosed',
                'title': 'Anaemia Diagnosed',
                'path': ['clinical_outcomes', 'anaemia_diagnosed']
            },
            {
                'name': 'past_year_transfusions',
                'title': 'Transfusions in Past Year',
                'path': ['clinical_outcomes', 'past_year_transfusions']
            },
            {
                'name': 'blood_product_problems',
                'title': 'Blood Product Problems',
                'path': ['adverse_events', 'blood_product_problems']
            }
        ]

        for timepoint in ['3month', '1year']:
            timepoint_data = self.data.get(timepoint, {})

            for outcome in outcomes:
                # Navigate to the outcome data
                data = timepoint_data
                for key in outcome['path']:
                    data = data.get(key, {})
                    if not data:
                        break

                if data:
                    print(f"  Creating {outcome['name']} chart for {timepoint}...")
                    self.plot_categorical_outcome(
                        outcome['name'],
                        data,
                        timepoint,
                        outcome['title']
                    )

    def save_followup_summary_csv(self):
        """Save comprehensive follow-up summary table as CSV."""
        # Prepare table data
        table_data = []

        # 1. Completion rates
        table_data.append(['FOLLOW-UP COMPLETION RATES', '', '', ''])
        table_data.append(['Timepoint', 'Eligible Patients', 'Completed Follow-ups', 'Completion Rate'])

        for timepoint, label in [('3month', '3-Month'), ('1year', '1-Year')]:
            comp = self.data[timepoint]['completion']
            table_data.append([
                label,
                comp['eligible_patients'],
                comp['completed_followups'],
                f"{comp['completion_rate']['percent']:.1f}%"
            ])

        table_data.append(['', '', '', ''])

        # 2. Baseline vs Follow-up Comparison (3-month)
        table_data.append(['BASELINE VS 3-MONTH FOLLOW-UP COMPARISON', '', '', ''])
        table_data.append(['Measure', 'N (Paired)', 'Baseline Median', '3-Month Median'])

        comparison = self.data['3month']['baseline_followup_comparison']

        if 'physical_capacity' in comparison:
            pc = comparison['physical_capacity']
            table_data.append([
                'Physical Capacity',
                pc['n'],
                f"{pc['baseline']['median']:.1f}",
                f"{pc['followup']['median']:.1f}"
            ])

        if 'frailty_cfs' in comparison:
            cfs = comparison['frailty_cfs']
            table_data.append([
                'Clinical Frailty Scale',
                cfs['n'],
                f"{cfs['baseline']['median']:.1f}",
                f"{cfs['followup']['median']:.1f}"
            ])

        table_data.append(['', '', '', ''])

        # 3. Clinical Outcomes Summary
        table_data.append(['CLINICAL OUTCOMES', '', '', ''])
        table_data.append(['Outcome', 'Timepoint', 'Category', 'N (%)'])

        for timepoint, label in [('3month', '3-Month'), ('1year', '1-Year')]:
            outcomes_data = self.data[timepoint]['clinical_outcomes']

            # Anaemia
            if 'anaemia_diagnosed' in outcomes_data:
                anaemia = outcomes_data['anaemia_diagnosed']
                for category in ['yes', 'no', 'refused_to_answer']:
                    if category in anaemia:
                        cat_label = category.replace('_', ' ').title()
                        table_data.append([
                            'Anaemia Diagnosed',
                            label,
                            cat_label,
                            f"{anaemia[category]['n']} ({anaemia[category]['percent']:.1f}%)"
                        ])

            # Transfusions
            if 'past_year_transfusions' in outcomes_data:
                trans = outcomes_data['past_year_transfusions']
                for category, data in trans['distribution'].items():
                    table_data.append([
                        'Past Year Transfusions',
                        label,
                        category,
                        f"{data['n']} ({data['percent']:.1f}%)"
                    ])

        # Write to CSV
        csv_path = os.path.join(self.output_dir, 'followup_summary.csv')

        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(table_data)

        print(f"  Saved: followup_summary.csv")

    def generate_all_visualizations(self):
        """Generate all follow-up visualizations."""
        print("\nGenerating follow-up visualizations...")

        print("  Creating baseline vs 3-month bar charts...")
        self.plot_baseline_followup_barcharts()

        print("  Creating categorical outcome donut charts...")
        self.plot_all_categorical_outcomes()

        print("  Creating follow-up summary CSV...")
        self.save_followup_summary_csv()

        print(f"\nAll visualizations saved to: {self.output_dir}")


def run_followup_visualization(analysis_output_dir: str, figure_output_dir: str = None):
    """
    Run follow-up visualization generation.

    Args:
        analysis_output_dir: Directory containing followup_statistics_detailed.json
        figure_output_dir: Directory where figures will be saved (default: analysis_output_dir/figures)

    Returns:
        FollowUpVisualizer instance
    """
    json_path = os.path.join(analysis_output_dir, 'followup_statistics_detailed.json')

    if not os.path.exists(json_path):
        raise FileNotFoundError(f"Could not find {json_path}")

    if figure_output_dir is None:
        figure_output_dir = os.path.join(analysis_output_dir, 'figures')

    visualizer = FollowUpVisualizer(json_path, figure_output_dir)
    visualizer.generate_all_visualizations()

    return visualizer


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python visualize_followup.py <analysis_output_dir> [figure_output_dir]")
        print("Example: python visualize_followup.py test_data_150patients test_data_150patients/figures")
        sys.exit(1)

    analysis_dir = sys.argv[1]
    figure_dir = sys.argv[2] if len(sys.argv) > 2 else None

    run_followup_visualization(analysis_dir, figure_dir)
