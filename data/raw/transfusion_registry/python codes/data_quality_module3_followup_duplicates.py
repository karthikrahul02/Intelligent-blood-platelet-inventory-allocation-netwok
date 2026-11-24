"""
Data Quality Analysis: Module 3 - Follow-up Duplicates
=======================================================

Analyzes follow-up survey duplicates and completion rates.

Follow-up Windows:
- 3-month: 68-113 days (3 months ± 3 weeks, expanded)
- 1-year: 273-455 days (1 year ± 3 months)

Expected: 1 follow-up per window per patient
Flags: Multiple follow-ups in same window, follow-ups outside windows

Author: Elina Nuerenberg-Goloub with Claude Sonnet 4.5 by Anthropic
Date: 2025-10-22
Revised on 2026-01-21 by Elina Nuerenberg-Goloub and Claude Opus 4.5
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple
from transfusion_data_loader import TransfusionDataLoader
import json

from transfusion_registry_mapping import json_sanitize
from pathlib import Path
from datetime import datetime, timedelta


class FollowUpDuplicates:
    """
    Analyze follow-up survey duplicates and completion patterns.

    Identifies:
    - Multiple follow-ups within the same time window
    - Follow-ups outside expected windows
    - Completion rates per window
    """

    # Follow-up time windows (in days from first treatment)
    # LOCKED TO MANUSCRIPT METHODS TEXT — must match descriptive_followup.py:
    # 3-month window 68-113 days, 1-year window 273-455 days.
    WINDOW_3MONTH_MIN = 68   # 90 - 22 days
    WINDOW_3MONTH_MAX = 113  # 90 + 23 days
    WINDOW_1YEAR_MIN = 273   # 365 - 92 days
    WINDOW_1YEAR_MAX = 455   # 365 + 90 days

    def __init__(self, loader: TransfusionDataLoader, data_end_date=None):
        """
        Initialize follow-up duplicates analyzer.

        Args:
            loader: TransfusionDataLoader with loaded data
        """
        self.loader = loader
        self.df = loader.df_clean.copy()
        self.explicit_data_end_date = pd.to_datetime(data_end_date) if data_end_date is not None else None
        self.mapper = loader.mapper
        self.results = {}

    def calculate_all(self) -> Dict[str, Any]:
        """
        Calculate all follow-up duplicate statistics.

        Returns:
            Dictionary with all analysis results
        """
        print("\nCalculating data quality: Follow-up duplicates analysis...")
        print("=" * 90)

        # Step 1: Identify follow-up records and treatment baseline
        print("\n1. Identifying follow-up records and treatment baseline...")
        self._identify_followups_and_baseline()

        # Step 2: Categorize follow-ups into windows
        print("2. Categorizing follow-ups into time windows...")
        self._categorize_followups_into_windows()

        # Step 3: Detect duplicates within windows
        print("3. Detecting duplicate follow-ups within same window...")
        self._detect_duplicates()

        # Step 4: Calculate completion rates
        print("4. Calculating follow-up eligibility and completion rates...")
        self._calculate_completion_rates()

        # Step 5: Create summary statistics
        print("5. Creating summary statistics...")
        self._create_summary()

        print("\nFollow-up duplicates analysis complete")
        print("=" * 90)

        return self.results

    def _identify_followups_and_baseline(self) -> None:
        """Identify follow-up records and establish baseline dates for each patient."""
        product_col = 'X_433_7_746'
        episode_date_col = 'Episode date'
        followup_form_col = 'FormStatus_435'  # Follow-up form indicator
        followup_completion_col = 'X_435_0_751'  # Date of completion field

        # Identify follow-up records (FormStatus_435 = "open")
        self.df['is_followup'] = self.df[followup_form_col].notna()
        self.df['is_treatment'] = self.df[product_col].notna()

        # Parse dates
        self.df['episode_date_parsed'] = pd.to_datetime(self.df[episode_date_col], errors='coerce', dayfirst=True)
        # unified follow-up time anchor: the ADMINISTRATION date (same anchor
        # as descriptive_followup.py) - not the episode date
        self.df['admin_date_parsed'] = pd.to_datetime(self.df['X_433_7_11'], errors='coerce')
        self.df['followup_completion_date'] = pd.to_datetime(self.df[followup_completion_col], errors='coerce', dayfirst=True)

        # For each patient, find baseline date = FIRST treatment date
        patient_baseline = []

        for pid in self.df['PID'].unique():
            patient_data = self.df[self.df['PID'] == pid].copy()

            # Get treatment data
            treatment_data = patient_data[patient_data['is_treatment']].copy()

            # Baseline = FIRST administration date (same anchor as the
            # follow-up statistics module); may be missing if no
            # administration carries a date
            if len(treatment_data) > 0:
                first_treatment = treatment_data['admin_date_parsed'].min()
                has_treatment = True
            else:
                first_treatment = None
                has_treatment = False

            patient_baseline.append({
                'PID': pid,
                'baseline_date': first_treatment,
                'first_treatment_date': first_treatment,
                'n_treatments': len(treatment_data),
                'has_treatment': has_treatment
            })

        self.patient_baseline_df = pd.DataFrame(patient_baseline)

        # Merge baseline date back to main dataframe
        self.df = self.df.merge(
            self.patient_baseline_df[['PID', 'baseline_date', 'has_treatment']],
            on='PID',
            how='left'
        )

        # Calculate days from baseline for follow-up records
        # Use completion date from follow-up form, not episode date
        followup_data = self.df[self.df['is_followup']].copy()
        followup_data['days_from_baseline'] = (
            followup_data['followup_completion_date'] - followup_data['baseline_date']
        ).dt.days

        self.followup_df = followup_data

        n_total_patients = len(self.patient_baseline_df)
        n_patients_with_treatment = self.patient_baseline_df['has_treatment'].sum()
        n_followup_records = len(self.followup_df)
        n_patients_with_followup = self.followup_df['PID'].nunique()

        print(f"   Total patients: {n_total_patients}")
        print(f"   Patients with treatment: {n_patients_with_treatment}")
        print(f"   Follow-up records: {n_followup_records}")
        print(f"   Patients with at least one follow-up: {n_patients_with_followup}")

    def _categorize_followups_into_windows(self) -> None:
        """Categorize each follow-up into time windows."""
        def categorize_window(days):
            if pd.isna(days):
                return 'Unknown'
            elif self.WINDOW_3MONTH_MIN <= days <= self.WINDOW_3MONTH_MAX:
                return '3-month'
            elif self.WINDOW_1YEAR_MIN <= days <= self.WINDOW_1YEAR_MAX:
                return '1-year'
            elif days < self.WINDOW_3MONTH_MIN:
                return 'Too early (<68 days)'
            elif self.WINDOW_3MONTH_MAX < days < self.WINDOW_1YEAR_MIN:
                return 'Between windows (114-272 days)'
            else:  # days > self.WINDOW_1YEAR_MAX
                return 'Too late (>455 days)'

        self.followup_df['window'] = self.followup_df['days_from_baseline'].apply(categorize_window)

        # Summary by window
        window_counts = self.followup_df['window'].value_counts().to_dict()

        print(f"   3-month window: {window_counts.get('3-month', 0)} follow-ups")
        print(f"   1-year window: {window_counts.get('1-year', 0)} follow-ups")
        print(f"   Outside windows: {sum([window_counts.get(k, 0) for k in window_counts if k not in ['3-month', '1-year', 'Unknown']])}")

    def _detect_duplicates(self) -> None:
        """Detect patients with multiple follow-ups in the same window."""
        # Group by patient and window — only the two REAL protocol windows.
        # Labels like 'Unknown', 'Too early' or 'Between windows' are not
        # windows; two unparseable-date follow-ups must not be flagged as
        # same-window duplicates.
        real_windows = self.followup_df[self.followup_df['window'].isin(['3-month', '1-year'])]
        window_counts = real_windows.groupby(['PID', 'window']).size().reset_index(name='n_followups')

        # Identify duplicates (>1 follow-up in same window)
        duplicates_same_window = window_counts[window_counts['n_followups'] > 1].copy()

        # Also check for patients with follow-ups in BOTH windows (expected, not a problem)
        patient_window_counts = self.followup_df.groupby('PID')['window'].apply(
            lambda x: x[x.isin(['3-month', '1-year'])].nunique()
        ).reset_index(name='n_different_windows')
        patients_both_windows = patient_window_counts[patient_window_counts['n_different_windows'] == 2]

        self.duplicates_same_window_df = duplicates_same_window
        self.patients_both_windows_df = patients_both_windows

        n_patients_duplicates_same_window = len(duplicates_same_window['PID'].unique())
        n_patients_both_windows = len(patients_both_windows)

        print(f"   Patients with DUPLICATE follow-ups in SAME window: {n_patients_duplicates_same_window}")
        print(f"   Patients with follow-ups in BOTH windows (3-month + 1-year): {n_patients_both_windows} (expected)")

        if len(duplicates_same_window) > 0:
            print(f"\n   Duplicates in same window (PROBLEMATIC):")
            for _, row in duplicates_same_window.iterrows():
                print(f"      PID {row['PID']}: {row['n_followups']} follow-ups in {row['window']} window")

    def _calculate_completion_rates(self) -> None:
        """Calculate follow-up completion rates per window and current eligibility."""
        # Reference date derived from the data itself (max of treatment and
        # follow-up dates) — a hardcoded export date silently corrupts
        # eligibility for every later export.
        candidate_dates = pd.concat([
            self.patient_baseline_df['baseline_date'],
            self.followup_df['followup_completion_date']
            if 'followup_completion_date' in self.followup_df.columns else pd.Series(dtype='datetime64[ns]'),
        ])
        if self.explicit_data_end_date is not None:
            export_date = self.explicit_data_end_date
            self.results['reference_date_source'] = 'explicit'
        else:
            export_date = candidate_dates.max()
            self.results['reference_date_source'] = 'derived from data'
        self.results['reference_date'] = str(export_date.date()) if pd.notna(export_date) else None
        print(f"   Reference date ({self.results['reference_date_source']}): {self.results['reference_date']}")

        # All patients with treatment
        eligible_df = self.patient_baseline_df[
            self.patient_baseline_df['has_treatment']
        ].copy()

        n_total_eligible = len(eligible_df)

        # Calculate days since first treatment for each patient (as of export date)
        eligible_df['days_since_baseline'] = (
            export_date - eligible_df['baseline_date']
        ).dt.days

        # Current eligibility status as of export date
        # 3-month window: 68-113 days (WINDOW_3MONTH_MIN/MAX)
        currently_eligible_3month = eligible_df[
            (eligible_df['days_since_baseline'] >= self.WINDOW_3MONTH_MIN) &
            (eligible_df['days_since_baseline'] <= self.WINDOW_3MONTH_MAX)
        ]

        # 1-year window: 273-455 days (WINDOW_1YEAR_MIN/MAX)
        currently_eligible_1year = eligible_df[
            (eligible_df['days_since_baseline'] >= self.WINDOW_1YEAR_MIN) &
            (eligible_df['days_since_baseline'] <= self.WINDOW_1YEAR_MAX)
        ]

        # Patients with completed follow-ups in each window
        followup_3month_pids = self.followup_df[
            self.followup_df['window'] == '3-month'
        ]['PID'].unique()

        followup_1year_pids = self.followup_df[
            self.followup_df['window'] == '1-year'
        ]['PID'].unique()

        # Completion among currently eligible
        n_currently_eligible_3month = len(currently_eligible_3month)
        n_completed_3month_of_current = sum(currently_eligible_3month['PID'].isin(followup_3month_pids))

        n_currently_eligible_1year = len(currently_eligible_1year)
        n_completed_1year_of_current = sum(currently_eligible_1year['PID'].isin(followup_1year_pids))

        # Overall completion (all time)
        n_completed_3month_total = len(followup_3month_pids)
        n_completed_1year_total = len(followup_1year_pids)

        self.completion_rates = {
            'export_date': str(export_date.date()),
            'n_total_eligible_patients': int(n_total_eligible),
            '3_month': {
                'n_currently_eligible': int(n_currently_eligible_3month),
                'n_completed_of_current': int(n_completed_3month_of_current),
                'n_completed_total': int(n_completed_3month_total),
                'percent_completed_of_current': float(n_completed_3month_of_current / n_currently_eligible_3month * 100) if n_currently_eligible_3month > 0 else 0
            },
            '1_year': {
                'n_currently_eligible': int(n_currently_eligible_1year),
                'n_completed_of_current': int(n_completed_1year_of_current),
                'n_completed_total': int(n_completed_1year_total),
                'percent_completed_of_current': float(n_completed_1year_of_current / n_currently_eligible_1year * 100) if n_currently_eligible_1year > 0 else 0
            }
        }

        self.currently_eligible_df = {
            '3_month': currently_eligible_3month,
            '1_year': currently_eligible_1year
        }

        print(f"   Total patients with treatment: {n_total_eligible}")
        print(f"\n   WINDOW CURRENTLY OPEN (as of {export_date.date()}):")
        print(f"      3-month window: {n_currently_eligible_3month} patients currently eligible")
        print(f"      1-year window: {n_currently_eligible_1year} patients currently eligible")
        print(f"\n   COMPLETION AMONG CURRENTLY ELIGIBLE:")
        print(f"      3-month: {n_completed_3month_of_current}/{n_currently_eligible_3month} ({n_completed_3month_of_current / n_currently_eligible_3month * 100 if n_currently_eligible_3month > 0 else 0:.1f}%)")
        print(f"      1-year: {n_completed_1year_of_current}/{n_currently_eligible_1year} ({n_completed_1year_of_current / n_currently_eligible_1year * 100 if n_currently_eligible_1year > 0 else 0:.1f}%)")
        print(f"\n   TOTAL COMPLETION (all time):")
        print(f"      3-month: {n_completed_3month_total} completed")
        print(f"      1-year: {n_completed_1year_total} completed")

    def _create_summary(self) -> None:
        """Create summary statistics."""
        n_total_patients = len(self.patient_baseline_df)
        n_patients_with_treatment = self.patient_baseline_df['has_treatment'].sum()
        n_followup_records = len(self.followup_df)
        n_patients_with_any_followup = self.followup_df['PID'].nunique()

        window_distribution = self.followup_df['window'].value_counts().to_dict()

        n_outside_windows = sum([
            window_distribution.get(k, 0)
            for k in window_distribution
            if k not in ['3-month', '1-year', 'Unknown']
        ])

        # Get PIDs with same-window duplicates
        pids_with_same_window_duplicates = self.duplicates_same_window_df['PID'].unique().tolist() if len(self.duplicates_same_window_df) > 0 else []
        pids_with_both_windows = self.patients_both_windows_df['PID'].tolist() if len(self.patients_both_windows_df) > 0 else []

        # preserve the reference-date provenance set in step 4 — the export
        # must document the censoring date and whether it was explicit
        self.results = {
            'reference_date': self.results.get('reference_date'),
            'reference_date_source': self.results.get('reference_date_source'),
            'summary': {
                'n_total_patients': int(n_total_patients),
                'n_patients_with_treatment': int(n_patients_with_treatment),
                'n_followup_records': int(n_followup_records),
                'n_patients_with_any_followup': int(n_patients_with_any_followup),
                'n_patients_with_same_window_duplicates': int(len(pids_with_same_window_duplicates)),
                'n_patients_with_both_windows': int(len(pids_with_both_windows)),
                'n_followups_outside_windows': int(n_outside_windows)
            },
            'window_distribution': window_distribution,
            'completion_rates': self.completion_rates,
            'same_window_duplicates': self.duplicates_same_window_df.to_dict('records') if len(self.duplicates_same_window_df) > 0 else [],
            'pids_with_same_window_duplicates': pids_with_same_window_duplicates,
            'pids_with_both_windows': pids_with_both_windows
        }

    def create_summary_tables(self) -> Tuple[str, str, str]:
        """
        Create formatted summary tables.

        Returns:
            Tuple of (summary_table, completion_table, duplicates_table)
        """
        if not self.results:
            self.calculate_all()

        # Summary table
        summary_lines = []
        summary_lines.append("=" * 90)
        summary_lines.append("DATA QUALITY - FOLLOW-UP DUPLICATES: SUMMARY")
        summary_lines.append("=" * 90)
        summary_lines.append("")
        summary = self.results['summary']
        summary_lines.append(f"Total patients: {summary['n_total_patients']}")
        summary_lines.append(f"Patients with treatment (eligible for follow-up): {summary['n_patients_with_treatment']}")
        summary_lines.append(f"Total follow-up records: {summary['n_followup_records']}")
        summary_lines.append(f"Patients with at least one follow-up: {summary['n_patients_with_any_followup']}")
        summary_lines.append("")
        summary_lines.append(f"Follow-ups in defined windows:")
        window_dist = self.results['window_distribution']
        summary_lines.append(f"  3-month window (68-113 days): {window_dist.get('3-month', 0)}")
        summary_lines.append(f"  1-year window (273-455 days): {window_dist.get('1-year', 0)}")
        summary_lines.append("")
        summary_lines.append(f"Follow-ups OUTSIDE defined windows: {summary['n_followups_outside_windows']}")
        summary_lines.append(f"  Too early (<68 days): {window_dist.get('Too early (<68 days)', 0)}")
        summary_lines.append(f"  Between windows (114-272 days): {window_dist.get('Between windows (114-272 days)', 0)}")
        summary_lines.append(f"  Too late (>455 days): {window_dist.get('Too late (>455 days)', 0)}")
        summary_lines.append("")
        summary_lines.append(f"DUPLICATE FOLLOW-UPS (>1 in SAME window): {summary['n_patients_with_same_window_duplicates']} patients (PROBLEMATIC)")
        summary_lines.append(f"Patients with follow-ups in BOTH windows (3-month + 1-year): {summary['n_patients_with_both_windows']} patients (EXPECTED)")
        summary_lines.append("=" * 90)

        # Completion rates table
        completion_lines = []
        completion_lines.append("=" * 90)
        completion_lines.append("DATA QUALITY - FOLLOW-UP DUPLICATES: COMPLETION RATES")
        completion_lines.append("=" * 90)
        completion_lines.append("")
        comp = self.results['completion_rates']
        completion_lines.append(f"Export date: {comp['export_date']}")
        completion_lines.append(f"Total eligible patients (with treatment): {comp['n_total_eligible_patients']}")
        completion_lines.append("")
        _ref_src = self.results.get('reference_date_source', 'derived from data')
        completion_lines.append(f"WINDOW CURRENTLY OPEN (reference date {comp['export_date']}, {_ref_src}):")
        completion_lines.append("(operational list: patients whose follow-up window is open ON the")
        completion_lines.append(" reference date; NOT a completion rate - the analytic completion")
        completion_lines.append(" rates with full eligibility denominators are in the follow-up")
        completion_lines.append(" statistics module)")
        completion_lines.append(f"{'Window':<25} {'Currently Eligible':>20} {'Completed':>12} {'% Completed':>15}")
        completion_lines.append("-" * 90)
        completion_lines.append(f"{'3-month (68-113d)':<25} {comp['3_month']['n_currently_eligible']:>20} {comp['3_month']['n_completed_of_current']:>12} {comp['3_month']['percent_completed_of_current']:>14.1f}%")
        completion_lines.append(f"{'1-year (273-455d)':<25} {comp['1_year']['n_currently_eligible']:>20} {comp['1_year']['n_completed_of_current']:>12} {comp['1_year']['percent_completed_of_current']:>14.1f}%")
        completion_lines.append("")
        completion_lines.append("TOTAL COMPLETION (all time, regardless of current eligibility):")
        completion_lines.append(f"  3-month window: {comp['3_month']['n_completed_total']} patients completed")
        completion_lines.append(f"  1-year window: {comp['1_year']['n_completed_total']} patients completed")
        completion_lines.append("=" * 90)

        # Duplicates table
        duplicates_lines = []
        duplicates_lines.append("=" * 90)
        duplicates_lines.append("DATA QUALITY - FOLLOW-UP DUPLICATES: DUPLICATE SITUATIONS")
        duplicates_lines.append("=" * 90)
        duplicates_lines.append("")
        duplicates_lines.append("SAME-WINDOW DUPLICATES (PROBLEMATIC - Which one to use?):")
        duplicates_lines.append("")
        if len(self.duplicates_same_window_df) > 0:
            duplicates_lines.append(f"{'PID':<15} {'Window':<30} {'Number of Follow-ups':>20}")
            duplicates_lines.append("-" * 90)
            for _, row in self.duplicates_same_window_df.iterrows():
                duplicates_lines.append(f"{row['PID']:<15} {row['window']:<30} {row['n_followups']:>20}")
            duplicates_lines.append("")
            duplicates_lines.append(f"PIDs with same-window duplicates: {', '.join(map(str, self.results['pids_with_same_window_duplicates']))}")
        else:
            duplicates_lines.append("No same-window duplicates detected!")
            duplicates_lines.append("Each patient has at most 1 follow-up per window.")
        duplicates_lines.append("")
        duplicates_lines.append("-" * 90)
        duplicates_lines.append("")
        duplicates_lines.append("PATIENTS WITH BOTH WINDOWS (EXPECTED - Not a problem):")
        duplicates_lines.append("")
        if len(self.patients_both_windows_df) > 0:
            duplicates_lines.append(f"Number of patients with follow-ups in BOTH 3-month and 1-year windows: {len(self.patients_both_windows_df)}")
            duplicates_lines.append(f"PIDs: {', '.join(map(str, self.results['pids_with_both_windows']))}")
        else:
            duplicates_lines.append("No patients have completed follow-ups in both windows yet.")
        duplicates_lines.append("=" * 90)

        return (
            "\n".join(summary_lines),
            "\n".join(completion_lines),
            "\n".join(duplicates_lines)
        )

    def export_results(self, output_dir: str = ".") -> None:
        """
        Export results to files in 'data quality reporting' subfolder.

        Args:
            output_dir: Base directory (e.g., 'test_data_150patients')
        """
        if not self.results:
            self.calculate_all()

        # Create 'data quality reporting' subfolder
        base_path = Path(output_dir)
        output_path = base_path / "data quality reporting"
        output_path.mkdir(parents=True, exist_ok=True)

        print(f"\nExporting to: {output_path}")

        # Export detailed JSON
        json_file = output_path / "data_quality_module3_followup_duplicates.json"
        with open(json_file, 'w') as f:
            json.dump(json_sanitize(self.results), f, indent=2, allow_nan=False)
        print(f"  JSON: {json_file.name}")

        # Export formatted tables
        (summary_table, completion_table, duplicates_table) = self.create_summary_tables()

        # Combined TXT report
        combined_file = output_path / "data_quality_module3_followup_duplicates.txt"
        with open(combined_file, 'w') as f:
            f.write(summary_table)
            f.write("\n\n\n")
            f.write(completion_table)
            f.write("\n\n\n")
            f.write(duplicates_table)
        print(f"  TXT: {combined_file.name}")

        # Export CSV tables
        self._export_csv_tables(output_path)

    def _export_csv_tables(self, output_path: Path) -> None:
        """Export data in CSV format."""
        # All follow-ups with window categorization (using completion date)
        followup_export = self.followup_df[[
            'PID', 'followup_completion_date', 'baseline_date',
            'days_from_baseline', 'window'
        ]].copy()
        followup_export.columns = [
            'PID', 'Completion_Date', 'Baseline_Date',
            'Days_From_Baseline', 'Window'
        ]
        csv_file = output_path / "data_quality_module3_all_followups.csv"
        followup_export.to_csv(csv_file, index=False)
        print(f"  CSV: {csv_file.name}")

        # Same-window duplicates (PROBLEMATIC)
        if len(self.duplicates_same_window_df) > 0:
            csv_file = output_path / "data_quality_module3_same_window_duplicates.csv"
            self.duplicates_same_window_df.to_csv(csv_file, index=False)
            print(f"  CSV: {csv_file.name}")

        # Patients with both windows (EXPECTED)
        if len(self.patients_both_windows_df) > 0:
            csv_file = output_path / "data_quality_module3_patients_both_windows.csv"
            self.patients_both_windows_df.to_csv(csv_file, index=False)
            print(f"  CSV: {csv_file.name}")

        # Follow-ups outside windows
        outside_followups = self.followup_df[
            ~self.followup_df['window'].isin(['3-month', '1-year', 'Unknown'])
        ][['PID', 'followup_completion_date', 'days_from_baseline', 'window']].copy()
        outside_followups.columns = ['PID', 'Completion_Date', 'Days_From_Baseline', 'Window']

        if len(outside_followups) > 0:
            csv_file = output_path / "data_quality_module3_outside_windows.csv"
            outside_followups.to_csv(csv_file, index=False)
            print(f"  CSV: {csv_file.name}")


def run_followup_duplicates_analysis(data_file: str, output_dir: str = ".",
                                     data_end_date=None) -> FollowUpDuplicates:
    """
    Run complete follow-up duplicates analysis workflow.

    Args:
        data_file: Path to CSV data file
        output_dir: Directory for output files

    Returns:
        FollowUpDuplicates object with calculated results
    """
    print("=" * 90)
    print("DATA QUALITY ANALYSIS - MODULE 3: FOLLOW-UP DUPLICATES")
    print("=" * 90)

    # Load data
    print("\nLoading data...")
    loader = TransfusionDataLoader()
    loader.load_data(data_file, validate=False)

    # Calculate statistics
    analyzer = FollowUpDuplicates(loader, data_end_date=data_end_date)
    analyzer.calculate_all()

    # Display tables
    (summary_table, completion_table, duplicates_table) = analyzer.create_summary_tables()
    print("\n" + summary_table)
    print("\n" + completion_table)
    print("\n" + duplicates_table)

    # Export results
    print("\nExporting results...")
    analyzer.export_results(output_dir)

    print("\nAnalysis complete!")
    return analyzer


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python3 data_quality_module3_followup_duplicates.py <data_file.csv> <output_directory>")
        print("Example: python3 data_quality_module3_followup_duplicates.py ../test_data_150patients.csv test_data_150patients")
        sys.exit(1)

    data_file = sys.argv[1]
    output_dir = sys.argv[2]

    analyzer = run_followup_duplicates_analysis(data_file, output_dir=output_dir)
