"""
Descriptive Follow-Up Statistics Module

Calculates comprehensive descriptive statistics for follow-up data at two timepoints:
- First follow-up (3-month): 68-113 days post-first-transfusion
- Second follow-up (1-year): 273-455 days post-first-transfusion

IMPORTANT: Only TRANSFUSION PATIENTS are included (patients who received at least one
blood product). Non-transfusion patients are excluded as follow-up is only initiated
for those who received a transfusion.

Includes completion rates, patient-reported outcomes, adverse events, and
baseline-follow-up comparisons for each timepoint.

Author: Elina Nuerenberg-Goloub with Claude Sonnet 4.5 by Anthropic
Date: 2025-10-17
Revised on 2026-01-22 by Elina Nuerenberg-Goloub and Claude Opus 4.5
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List, Tuple
from transfusion_data_loader import TransfusionDataLoader
import json

from transfusion_registry_mapping import json_sanitize
from pathlib import Path
from datetime import datetime, timedelta


class FollowUpDescriptives:
    """
    Calculate descriptive statistics for follow-up data at two timepoints.

    Timepoints:
    - First follow-up (3-month): 68-113 days from first blood product
    - Second follow-up (1-year): 273-455 days from first blood product

    All statistics calculated at patient level. Correctly accounts for
    timepoint-specific eligibility criteria.
    """

    def __init__(self, loader: TransfusionDataLoader, data_end_date: Optional[datetime] = None):
        """
        Initialize follow-up descriptives calculator.

        Args:
            loader: TransfusionDataLoader with loaded data
            data_end_date: End date for data collection (default: latest date in data)
        """
        self.loader = loader
        self.mapper = loader.mapper

        # Filter to TRANSFUSION PATIENTS only (those who received at least one blood product)
        # Non-transfusion patients are excluded as follow-up is only initiated for transfusion patients
        product_col = 'X_433_7_746'
        df_all = loader.df_clean.copy()

        # Identify transfusion patients (those with at least one blood product)
        transfusion_pids = df_all[df_all[product_col].notna()]['PID'].unique()
        self.n_transfusion_patients = len(transfusion_pids)
        self.n_non_transfusion_patients = df_all['PID'].nunique() - self.n_transfusion_patients

        # Filter to only transfusion patients
        self.df = df_all[df_all['PID'].isin(transfusion_pids)].copy()

        # Determine data end date
        if data_end_date is None:
            # Use latest date in the data. NOTE: a derived end date makes
            # eligibility denominators depend on the observed events; for
            # reportable follow-up rates pass the explicit export/censoring
            # date instead.
            admin_dates = pd.to_datetime(self.df['X_433_7_11'], errors='coerce')
            followup_dates = pd.to_datetime(self.df['X_435_0_751'], errors='coerce')
            all_dates = pd.concat([admin_dates, followup_dates])
            self.data_end_date = all_dates.max()
            self.data_end_date_source = 'derived from data (latest administration or follow-up date)'
            print(f"  NOTE: data end date derived from the data "
                  f"({self.data_end_date.date() if pd.notna(self.data_end_date) else 'n/a'}); "
                  f"pass an explicit export date for reportable follow-up rates")
        else:
            self.data_end_date = pd.to_datetime(data_end_date)
            self.data_end_date_source = 'explicit'

        # Timing windows for follow-up classification (based on protocol)
        # LOCKED TO MANUSCRIPT METHODS TEXT — single source of truth for this module.
        # Must match data_quality_module3_followup_duplicates.py and the Methods:
        # 3-month window: 68-113 days; 1-year window: 273-455 days.
        # First follow-up: 3 months ± 3 weeks from first blood product
        self.followup_3month_min_days = 68   # 90 - 22 days
        self.followup_3month_max_days = 113  # 90 + 23 days
        # Second follow-up: 1 year ± 3 months from first blood product
        self.followup_1year_min_days = 273   # 365 - 92 days
        self.followup_1year_max_days = 455   # 365 + 90 days

        # Eligibility cutoffs: patients eligible if first transfusion was at least
        # [min of window] days before data end (when they first enter the window)
        self.eligibility_cutoff_3month = self.data_end_date - timedelta(days=self.followup_3month_min_days)
        self.eligibility_cutoff_1year = self.data_end_date - timedelta(days=self.followup_1year_min_days)

        self.results = {}

        # Track conflicting duplicates (different values in same window)
        self.conflicting_duplicates = []  # List of dicts with PID, window, and differences
        self.resolved_duplicates = []  # List of dicts with PID, window (identical duplicates)

        self._prepare_patient_data()

    def _are_followups_identical(self, records: pd.DataFrame, followup_cols: List[str]) -> Tuple[bool, List[str]]:
        """
        Check if multiple follow-up records have identical values.

        Args:
            records: DataFrame with multiple follow-up records for same patient/window
            followup_cols: List of follow-up column names to compare

        Returns:
            Tuple of (are_identical: bool, differing_columns: List[str])
        """
        if len(records) <= 1:
            return True, []

        differing_cols = []

        for col in followup_cols:
            if col not in records.columns:
                continue

            values = records[col].tolist()
            # Normalize values: treat NaN, None, empty string as equivalent
            normalized = []
            for v in values:
                if pd.isna(v) or v == '' or v is None:
                    normalized.append(None)
                else:
                    normalized.append(v)

            # Check if all normalized values are the same
            first_val = normalized[0]
            if not all(v == first_val for v in normalized):
                differing_cols.append(col)

        return len(differing_cols) == 0, differing_cols

    def _resolve_duplicates(self, patient_followups: pd.DataFrame, followup_cols: List[str],
                            pid: int, window: str) -> Tuple[Optional[pd.DataFrame], bool]:
        """
        Resolve duplicate follow-ups for a patient in same timeframe.

        Logic:
        1. If only 1 record: keep it
        2. If multiple records with IDENTICAL values: keep one (resolved duplicate)
        3. If multiple records with DIFFERENT values: exclude all (conflicting duplicate)

        Args:
            patient_followups: DataFrame with all follow-ups for this patient in this timeframe
            followup_cols: List of follow-up column names
            pid: Patient ID
            window: Window name ('3month' or '1year')

        Returns:
            Tuple of (selected_record or None, was_conflict: bool)
        """
        if len(patient_followups) == 1:
            return patient_followups, False

        # Check if all records are identical
        are_identical, differing_cols = self._are_followups_identical(patient_followups, followup_cols)

        if are_identical:
            # Identical duplicates - keep first one and log as resolved
            self.resolved_duplicates.append({
                'PID': int(pid),
                'window': window,
                'n_duplicates': len(patient_followups),
                'status': 'resolved_identical'
            })
            return patient_followups.iloc[[0]], False
        else:
            # Conflicting duplicates - exclude all and log for review
            # Collect the actual differing values for export
            conflict_details = {
                'PID': int(pid),
                'window': window,
                'n_duplicates': len(patient_followups),
                'differing_columns': differing_cols,
                'records': []
            }

            for idx, row in patient_followups.iterrows():
                # Convert followup_date to string for JSON serialization
                followup_date = row.get('followup_date', None)
                if pd.notna(followup_date):
                    followup_date = str(followup_date.date()) if hasattr(followup_date, 'date') else str(followup_date)

                record_info = {
                    'followup_date': followup_date,
                    'days_from_first': int(row.get('days_from_first')) if pd.notna(row.get('days_from_first')) else None
                }
                for col in differing_cols:
                    if col in row.index:
                        val = row[col]
                        # Convert any non-JSON-serializable types
                        if pd.isna(val):
                            val = None
                        elif hasattr(val, 'item'):  # numpy types
                            val = val.item()
                        record_info[col] = val
                conflict_details['records'].append(record_info)

            self.conflicting_duplicates.append(conflict_details)
            return None, True  # Exclude these records

    def _prepare_patient_data(self):
        """Prepare patient-level dataset with eligibility and follow-up status for both timepoints."""
        # Determine first administration date per patient
        # Time anchor is the ADMINISTRATION date only. X_433_0_753 is the
        # date of discharge per the data dictionary and is NOT a valid
        # substitute for exposure start; patients without any administration
        # date are not classifiable on the follow-up time axis and are
        # counted separately.
        self.df['admin_date'] = pd.to_datetime(self.df['X_433_7_11'], errors='coerce')

        # Get first administration per patient
        first_admin = self.df.groupby('PID')['admin_date'].min().reset_index()
        first_admin.columns = ['PID', 'first_administration_date']
        self.n_patients_no_time_anchor = int(
            first_admin['first_administration_date'].isna().sum())
        if self.n_patients_no_time_anchor:
            print(f"  NOTE: {self.n_patients_no_time_anchor} patient(s) have no "
                  f"administration date and cannot be classified on the "
                  f"follow-up time axis (reported separately)")

        # Determine eligibility for both timepoints
        # <= so that a patient exactly at the window minimum counts as eligible ("≥68 days")
        first_admin['eligible_for_3month'] = first_admin['first_administration_date'] <= self.eligibility_cutoff_3month
        first_admin['eligible_for_1year'] = first_admin['first_administration_date'] <= self.eligibility_cutoff_1year

        # Get baseline data: restrict to each patient's FIRST episode before aggregating.
        # groupby().first() takes the first non-null value per column, which could
        # otherwise silently pull "baseline" values from a later episode.
        df_sorted = self.df.sort_values(['PID', 'admin_date']).copy()
        first_dates = df_sorted.groupby('PID')['admin_date'].transform('min')
        same_first = (df_sorted['admin_date'] == first_dates) | (first_dates.isna())
        baseline_data = df_sorted[same_first].groupby('PID').first().reset_index()

        # Get ALL follow-up data (not just first per patient, as patients may have multiple)
        # NOTE: the follow-up date (X_435_0_751) is deliberately EXCLUDED from the
        # duplicate-value comparison — two records with identical answers but different
        # completion dates within the same window are identical duplicates (keep one),
        # per the documented duplicate policy.
        followup_cols = [col for col in self.df.columns
                         if col.startswith('X_435_') and col != 'X_435_0_751']
        all_followup_cols = [col for col in self.df.columns if col.startswith('X_435_')]
        # Select with ALL follow-up columns (incl. the date, needed below);
        # only the duplicate-value comparison uses the date-free followup_cols.
        all_followups = self.df[self.df['X_435_0_751'].notna()][['PID'] + all_followup_cols].copy()

        # Calculate days from first transfusion to follow-up for each follow-up record
        all_followups = all_followups.merge(first_admin[['PID', 'first_administration_date']], on='PID', how='left')
        all_followups['followup_date'] = pd.to_datetime(all_followups['X_435_0_751'], errors='coerce')
        all_followups['days_from_first'] = (all_followups['followup_date'] - all_followups['first_administration_date']).dt.days

        # Classify each follow-up by timepoint
        all_followups['timepoint'] = 'unclassified'
        all_followups.loc[
            (all_followups['days_from_first'] >= self.followup_3month_min_days) &
            (all_followups['days_from_first'] <= self.followup_3month_max_days),
            'timepoint'
        ] = '3month'
        all_followups.loc[
            (all_followups['days_from_first'] >= self.followup_1year_min_days) &
            (all_followups['days_from_first'] <= self.followup_1year_max_days),
            'timepoint'
        ] = '1year'

        # Assign "intended timeframe" to all follow-ups (including unclassified)
        # This helps identify unclassified follow-ups that are clearly meant for a specific timeframe
        def get_intended_timeframe(days):
            if 60 < days < 120:  # Around 3 months (±30 days tolerance)
                return "3month_intended"
            elif 250 < days < 480:  # Around 1 year (±115 days tolerance)
                return "1year_intended"
            else:
                return "other"

        all_followups['intended_timeframe'] = all_followups['days_from_first'].apply(get_intended_timeframe)

        # Separate 3-month and 1-year follow-ups, resolving duplicates
        # Duplicates with IDENTICAL values: keep one (resolved)
        # Duplicates with DIFFERENT values: exclude all (conflicting - flagged for review)

        # For 3-month: only follow-ups within the documented protocol window
        # (68-113 days) enter the analysis; 'intended_timeframe' is reporting-only.
        followup_3month_list = []
        self.excluded_3month_pids = []  # Track PIDs excluded due to conflicting duplicates
        patients_with_3month = all_followups[
            (all_followups['timepoint'] == '3month')
        ]['PID'].unique()

        for pid in patients_with_3month:
            patient_3month = all_followups[
                (all_followups['PID'] == pid) &
                (all_followups['timepoint'] == '3month')
            ]
            resolved, was_conflict = self._resolve_duplicates(patient_3month, followup_cols, pid, '3-month')
            if resolved is not None:
                followup_3month_list.append(resolved)
            else:
                self.excluded_3month_pids.append(pid)

        followup_3month = pd.concat(followup_3month_list) if followup_3month_list else pd.DataFrame(columns=all_followups.columns)

        # For 1-year: only follow-ups within the documented protocol window
        # (273-455 days) enter the analysis; 'intended_timeframe' is reporting-only.
        followup_1year_list = []
        self.excluded_1year_pids = []  # Track PIDs excluded due to conflicting duplicates
        patients_with_1year = all_followups[
            (all_followups['timepoint'] == '1year')
        ]['PID'].unique()

        for pid in patients_with_1year:
            patient_1year = all_followups[
                (all_followups['PID'] == pid) &
                (all_followups['timepoint'] == '1year')
            ]
            resolved, was_conflict = self._resolve_duplicates(patient_1year, followup_cols, pid, '1-year')
            if resolved is not None:
                followup_1year_list.append(resolved)
            else:
                self.excluded_1year_pids.append(pid)

        followup_1year = pd.concat(followup_1year_list) if followup_1year_list else pd.DataFrame(columns=all_followups.columns)

        # Create patient-level datasets for each timepoint
        # 3-month follow-up dataset
        self.patient_df_3month = first_admin.copy()
        self.patient_df_3month = self.patient_df_3month.merge(
            baseline_data[['PID', 'X_433_0_2', 'X_433_0_3', 'X_433_0_4', 'X_433_0_32', 'X_433_0_25', 'X_541_0_1']],
            on='PID', how='left'
        )
        # Add 3-month follow-up data with suffix (ALL follow-up columns incl.
        # the completion date; only the duplicate comparison excludes the date)
        followup_3month_cols = {col: f"{col}_3month" for col in all_followup_cols}
        followup_3month_rename = followup_3month[['PID'] + all_followup_cols].rename(columns=followup_3month_cols)
        self.patient_df_3month = self.patient_df_3month.merge(followup_3month_rename, on='PID', how='left')
        self.patient_df_3month['has_followup_3month'] = self.patient_df_3month[f'X_435_0_751_3month'].notna()

        # 1-year follow-up dataset
        self.patient_df_1year = first_admin.copy()
        self.patient_df_1year = self.patient_df_1year.merge(
            baseline_data[['PID', 'X_433_0_2', 'X_433_0_3', 'X_433_0_4', 'X_433_0_32', 'X_433_0_25', 'X_541_0_1']],
            on='PID', how='left'
        )
        # Add 1-year follow-up data with suffix (ALL follow-up columns incl.
        # the completion date; only the duplicate comparison excludes the date)
        followup_1year_cols = {col: f"{col}_1year" for col in all_followup_cols}
        followup_1year_rename = followup_1year[['PID'] + all_followup_cols].rename(columns=followup_1year_cols)
        self.patient_df_1year = self.patient_df_1year.merge(followup_1year_rename, on='PID', how='left')
        self.patient_df_1year['has_followup_1year'] = self.patient_df_1year[f'X_435_0_751_1year'].notna()

        # Store raw follow-up data for reference
        self.all_followups = all_followups

    def calculate_all(self) -> Dict[str, Any]:
        """
        Calculate all follow-up statistics for both timepoints.

        Returns:
            Dictionary with all calculated statistics for 3-month and 1-year follow-ups
        """
        print("\nCalculating follow-up statistics for both timepoints...")

        self.results = {
            '3month': {
                'completion': self._calculate_completion_statistics('3month'),
                'respondent_demographics': self._calculate_respondent_demographics('3month'),
                'patient_reported_outcomes': self._calculate_patient_reported_outcomes('3month'),
                'adverse_events': self._calculate_adverse_events('3month'),
                'clinical_outcomes': self._calculate_clinical_outcomes('3month'),
                'baseline_followup_comparison': self._calculate_baseline_followup_comparison('3month')
            },
            '1year': {
                'completion': self._calculate_completion_statistics('1year'),
                'respondent_demographics': self._calculate_respondent_demographics('1year'),
                'patient_reported_outcomes': self._calculate_patient_reported_outcomes('1year'),
                'adverse_events': self._calculate_adverse_events('1year'),
                'clinical_outcomes': self._calculate_clinical_outcomes('1year'),
                'baseline_followup_comparison': self._calculate_baseline_followup_comparison('1year')
            },
            'timing_summary': self._calculate_timing_summary(),
            'duplicate_resolution': self._calculate_duplicate_resolution_summary()
        }

        print("Follow-up statistics calculated successfully for both timepoints")
        self.results['time_axis'] = {
            'data_end_date': str(self.data_end_date.date()) if pd.notna(self.data_end_date) else None,
            'data_end_date_source': self.data_end_date_source,
            'n_patients_without_administration_date': self.n_patients_no_time_anchor,
        }
        return self.results

    def _calculate_timing_summary(self) -> Dict[str, Any]:
        """Calculate summary of follow-up timing and classification."""
        return {
            'total_followup_records': int(len(self.all_followups)),
            'classified_3month': int((self.all_followups['timepoint'] == '3month').sum()),
            'classified_1year': int((self.all_followups['timepoint'] == '1year').sum()),
            'unclassified': int((self.all_followups['timepoint'] == 'unclassified').sum()),
            'timing_windows': {
                '3month': f"{self.followup_3month_min_days}-{self.followup_3month_max_days} days",
                '1year': f"{self.followup_1year_min_days}-{self.followup_1year_max_days} days"
            }
        }

    def _calculate_duplicate_resolution_summary(self) -> Dict[str, Any]:
        """Calculate summary of how duplicate follow-ups were resolved."""
        # Count resolved (identical) duplicates by window
        resolved_3month = sum(1 for r in self.resolved_duplicates if r['window'] == '3-month')
        resolved_1year = sum(1 for r in self.resolved_duplicates if r['window'] == '1-year')

        # Count conflicting duplicates by window
        conflicting_3month = sum(1 for c in self.conflicting_duplicates if c['window'] == '3-month')
        conflicting_1year = sum(1 for c in self.conflicting_duplicates if c['window'] == '1-year')

        return {
            'resolved_identical_duplicates': {
                'total': len(self.resolved_duplicates),
                '3month': resolved_3month,
                '1year': resolved_1year,
                'pids': [r['PID'] for r in self.resolved_duplicates]
            },
            'excluded_conflicting_duplicates': {
                'total': len(self.conflicting_duplicates),
                '3month': conflicting_3month,
                '1year': conflicting_1year,
                'pids_3month': [int(p) for p in self.excluded_3month_pids],
                'pids_1year': [int(p) for p in self.excluded_1year_pids],
                'note': 'Detailed conflict records exported to conflicting_followup_duplicates.csv'
            }
        }

    def _calculate_completion_statistics(self, timepoint: str) -> Dict[str, Any]:
        """Calculate follow-up completion statistics with correct eligibility for specified timepoint."""
        if timepoint == '3month':
            patient_df = self.patient_df_3month
            eligible_col = 'eligible_for_3month'
            has_followup_col = 'has_followup_3month'
            eligibility_cutoff = self.eligibility_cutoff_3month
            timing_window = f"{self.followup_3month_min_days}-{self.followup_3month_max_days} days"
        else:  # 1year
            patient_df = self.patient_df_1year
            eligible_col = 'eligible_for_1year'
            has_followup_col = 'has_followup_1year'
            eligibility_cutoff = self.eligibility_cutoff_1year
            timing_window = f"{self.followup_1year_min_days}-{self.followup_1year_max_days} days"

        total_patients = len(patient_df)
        eligible_patients = patient_df[patient_df[eligible_col] == True]
        n_eligible = len(eligible_patients)
        n_not_yet_eligible = total_patients - n_eligible

        # Completed follow-ups among eligible
        eligible_completed = eligible_patients[eligible_patients[has_followup_col] == True]
        n_completed = len(eligible_completed)
        n_pending = n_eligible - n_completed

        return {
            'timepoint': timepoint,
            'timing_window': timing_window,
            'data_end_date': str(self.data_end_date.date()),
            'eligibility_cutoff_date': str(eligibility_cutoff.date()),
            'total_patients': int(total_patients),
            'eligible_patients': int(n_eligible),
            'not_yet_eligible': int(n_not_yet_eligible),
            'completed_followups': int(n_completed),
            'pending_followups': int(n_pending),
            'completion_rate': {
                'n': int(n_completed),
                'denominator': int(n_eligible),
                'percent': float(n_completed / n_eligible * 100) if n_eligible > 0 else 0
            }
        }

    def _calculate_respondent_demographics(self, timepoint: str) -> Dict[str, Any]:
        """Calculate demographics of follow-up respondents vs non-respondents for specified timepoint."""
        if timepoint == '3month':
            patient_df = self.patient_df_3month
            eligible_col = 'eligible_for_3month'
            has_followup_col = 'has_followup_3month'
        else:  # 1year
            patient_df = self.patient_df_1year
            eligible_col = 'eligible_for_1year'
            has_followup_col = 'has_followup_1year'

        eligible = patient_df[patient_df[eligible_col] == True].copy()
        respondents = eligible[eligible[has_followup_col] == True].copy()
        non_respondents = eligible[eligible[has_followup_col] == False].copy()

        # Calculate age at first administration
        for df_subset in [respondents, non_respondents]:
            birth_year = pd.to_numeric(df_subset['X_541_0_1'], errors='coerce')
            admin_year = df_subset['first_administration_date'].dt.year
            df_subset['age'] = admin_year - birth_year

        # Respondent demographics
        resp_stats = {}

        # Age
        resp_ages = respondents['age'].dropna()
        if len(resp_ages) > 0:
            resp_stats['age'] = {
                'n': int(len(resp_ages)),
                'mean': float(resp_ages.mean()),
                'sd': float(resp_ages.std()) if len(resp_ages) > 1 else 0,
                'median': float(resp_ages.median()),
                'q25': float(resp_ages.quantile(0.25)),
                'q75': float(resp_ages.quantile(0.75)),
                'min': int(resp_ages.min()),
                'max': int(resp_ages.max())
            }

        # Gender
        resp_gender = respondents['X_433_0_4'].copy()
        if resp_gender.notna().any():
            gender_counts = {}
            for code, label in [('M', 'Male'), ('F', 'Female'), ('I', 'Intersex/Diverse')]:
                count = (resp_gender == code).sum()
                if count > 0 or code in ['M', 'F']:
                    gender_counts[label] = {
                        'n': int(count),
                        'percent': float(count / len(respondents) * 100)
                    }
            resp_stats['gender'] = gender_counts

        # Non-respondent demographics (for comparison)
        non_resp_stats = {}

        # Age
        non_resp_ages = non_respondents['age'].dropna()
        if len(non_resp_ages) > 0:
            non_resp_stats['age'] = {
                'n': int(len(non_resp_ages)),
                'mean': float(non_resp_ages.mean()),
                'sd': float(non_resp_ages.std()) if len(non_resp_ages) > 1 else 0,
                'median': float(non_resp_ages.median())
            }

        # Gender
        non_resp_gender = non_respondents['X_433_0_4'].copy()
        if non_resp_gender.notna().any():
            gender_counts = {}
            for code, label in [('M', 'Male'), ('F', 'Female')]:
                count = (non_resp_gender == code).sum()
                gender_counts[label] = {
                    'n': int(count),
                    'percent': float(count / len(non_respondents) * 100)
                }
            non_resp_stats['gender'] = gender_counts

        return {
            'respondents': resp_stats,
            'non_respondents': non_resp_stats
        }

    def _calculate_patient_reported_outcomes(self, timepoint: str) -> Dict[str, Any]:
        """Calculate patient-reported outcomes from follow-up for specified timepoint."""
        if timepoint == '3month':
            patient_df = self.patient_df_3month
            has_followup_col = 'has_followup_3month'
            suffix = '_3month'
        else:  # 1year
            patient_df = self.patient_df_1year
            has_followup_col = 'has_followup_1year'
            suffix = '_1year'

        respondents = patient_df[patient_df[has_followup_col] == True].copy()

        results = {}

        # Physical capacity (X_435_0_741)
        phys_cap_col = f'X_435_0_741{suffix}'
        if phys_cap_col in respondents.columns:
            phys_cap = respondents[phys_cap_col].dropna()
            if len(phys_cap) > 0:
                phys_cap_num = pd.to_numeric(phys_cap, errors='coerce')
                # Code 0 = "Kann / möchte ich nicht beantworten" (refusal), NOT a
                # scale value — shown in the distribution but excluded from mean/median.
                phys_cap_scale = phys_cap_num[phys_cap_num >= 1]
                capacity_dist = {}
                for val in sorted(phys_cap.unique()):
                    count = (phys_cap == val).sum()
                    code = int(float(val))
                    label = "Refused to answer" if code == 0 else f"Level {code}"
                    capacity_dist[label] = {
                        'n': int(count),
                        'percent': float(count / len(phys_cap) * 100)
                    }

                results['physical_capacity'] = {
                    'n': int(len(phys_cap)),
                    'n_scale': int(len(phys_cap_scale)),
                    'n_refused': int((phys_cap_num == 0).sum()),
                    'distribution': capacity_dist,
                    'median': float(phys_cap_scale.median()) if len(phys_cap_scale) > 0 else None,
                    'q25': float(phys_cap_scale.quantile(0.25)) if len(phys_cap_scale) > 0 else None,
                    'q75': float(phys_cap_scale.quantile(0.75)) if len(phys_cap_scale) > 0 else None,
                    'mean': float(phys_cap_scale.mean()) if len(phys_cap_scale) > 0 else None,
                    'scale_note': (
                        'ordinal scale; codes 1-5 index the categories 1, 3, 4, 10 '
                        'and >10 MET and are not MET values. The distribution and '
                        'median/IQR are the primary summaries; the mean of the '
                        'category codes is exploratory (unequal category spacing).'
                    )
                }

        # Frailty CFS (X_435_0_742)
        cfs_col = f'X_435_0_742{suffix}'
        if cfs_col in respondents.columns:
            cfs = respondents[cfs_col].dropna()
            if len(cfs) > 0:
                cfs_num = pd.to_numeric(cfs, errors='coerce')
                # Code 0 = refusal, not a CFS grade (scale is 1-9) — excluded from stats.
                cfs_scale = cfs_num[cfs_num >= 1]
                cfs_dist = {}
                for val in sorted(cfs.unique()):
                    count = (cfs == val).sum()
                    code = int(float(val))
                    label = "Refused to answer" if code == 0 else f"CFS {code}"
                    cfs_dist[label] = {
                        'n': int(count),
                        'percent': float(count / len(cfs) * 100)
                    }

                results['frailty_cfs'] = {
                    'n': int(len(cfs)),
                    'n_scale': int(len(cfs_scale)),
                    'n_refused': int((cfs_num == 0).sum()),
                    'distribution': cfs_dist,
                    'median': float(cfs_scale.median()) if len(cfs_scale) > 0 else None,
                    'q25': float(cfs_scale.quantile(0.25)) if len(cfs_scale) > 0 else None,
                    'q75': float(cfs_scale.quantile(0.75)) if len(cfs_scale) > 0 else None,
                    'mean': float(cfs_scale.mean()) if len(cfs_scale) > 0 else None,
                    'scale_note': (
                        'ordinal scale (CFS grades 1-9). The distribution and '
                        'median/IQR are the primary summaries; the mean of the '
                        'grades is exploratory (ordinal, not interval-scaled).'
                    )
                }

        return results

    def _calculate_adverse_events(self, timepoint: str) -> Dict[str, Any]:
        """Calculate adverse events related to blood products for specified timepoint."""
        if timepoint == '3month':
            patient_df = self.patient_df_3month
            has_followup_col = 'has_followup_3month'
            suffix = '_3month'
        else:  # 1year
            patient_df = self.patient_df_1year
            has_followup_col = 'has_followup_1year'
            suffix = '_1year'

        respondents = patient_df[patient_df[has_followup_col] == True].copy()

        results = {}

        # Blood product problems (X_435_0_737)
        problems_col = f'X_435_0_737{suffix}'
        if problems_col in respondents.columns:
            problems = respondents[problems_col].dropna()

            yes_count = (problems == 'Y').sum()
            no_count = (problems == 'N').sum()
            unknown_count = (problems == 'U').sum()
            total = len(problems)

            results['blood_product_problems'] = {
                'yes': {
                    'n': int(yes_count),
                    'percent': float(yes_count / total * 100) if total > 0 else 0
                },
                'no': {
                    'n': int(no_count),
                    'percent': float(no_count / total * 100) if total > 0 else 0
                },
                'refused_to_answer': {
                    'n': int(unknown_count),
                    'percent': float(unknown_count / total * 100) if total > 0 else 0
                },
                'total': int(total)
            }

        return results

    def _calculate_clinical_outcomes(self, timepoint: str) -> Dict[str, Any]:
        """Calculate clinical outcomes from follow-up for specified timepoint."""
        if timepoint == '3month':
            patient_df = self.patient_df_3month
            has_followup_col = 'has_followup_3month'
            suffix = '_3month'
        else:  # 1year
            patient_df = self.patient_df_1year
            has_followup_col = 'has_followup_1year'
            suffix = '_1year'

        respondents = patient_df[patient_df[has_followup_col] == True].copy()

        results = {}

        # Anaemia diagnosed (X_435_0_740)
        anaemia_col = f'X_435_0_740{suffix}'
        if anaemia_col in respondents.columns:
            anaemia = respondents[anaemia_col].dropna()

            yes_count = (anaemia == 'Y').sum()
            no_count = (anaemia == 'N').sum()
            unknown_count = (anaemia == 'U').sum()
            total = len(anaemia)

            results['anaemia_diagnosed'] = {
                'yes': {
                    'n': int(yes_count),
                    'percent': float(yes_count / total * 100) if total > 0 else 0
                },
                'no': {
                    'n': int(no_count),
                    'percent': float(no_count / total * 100) if total > 0 else 0
                },
                'refused_to_answer': {
                    'n': int(unknown_count),
                    'percent': float(unknown_count / total * 100) if total > 0 else 0
                },
                'total': int(total)
            }

        # Past year transfusions (X_435_0_752)
        transfusions_col = f'X_435_0_752{suffix}'
        if transfusions_col in respondents.columns:
            transfusions = respondents[transfusions_col].dropna()

            transfusion_dist = {}
            # Permitted values for element 752: 0=none, 1=one, 2=more than one,
            # 3="Kann / möchte ich nicht beantworten" (cannot/will not answer)
            labels = {
                '0': 'None',
                '1': 'One',
                '2': 'More than one',
                '3': 'Cannot answer',
            }

            counted = 0
            trans_str = transfusions.astype(str).str.replace(r'\.0$', '', regex=True)
            for code, label in labels.items():
                count = (trans_str == code).sum()
                if count > 0:
                    counted += int(count)
                    transfusion_dist[label] = {
                        'n': int(count),
                        'percent': float(count / len(transfusions) * 100)
                    }
            # Any unexpected codes are reported, not silently dropped, so the
            # distribution always sums to the total
            n_other = int(len(transfusions)) - counted
            if n_other > 0:
                transfusion_dist['Other/unexpected code'] = {
                    'n': n_other,
                    'percent': float(n_other / len(transfusions) * 100)
                }

            results['past_year_transfusions'] = {
                'distribution': transfusion_dist,
                'total': int(len(transfusions))
            }

        return results

    @staticmethod
    def _transition_matrix(baseline_vals, followup_vals) -> Dict[str, Dict[str, int]]:
        """
        Cross-tabulate baseline vs. follow-up category codes.

        Returns {baseline_code: {followup_code: n}} with string keys, the
        ordinal-safe primary presentation of paired change (no arithmetic on
        the codes).
        """
        matrix: Dict[str, Dict[str, int]] = {}
        for b, f in zip(baseline_vals, followup_vals):
            if pd.isna(b) or pd.isna(f):
                continue
            row = matrix.setdefault(str(int(b)), {})
            key = str(int(f))
            row[key] = row.get(key, 0) + 1
        return matrix

    def _calculate_baseline_followup_comparison(self, timepoint: str) -> Dict[str, Any]:
        """Compare baseline and follow-up measures for respondents at specified timepoint."""
        if timepoint == '3month':
            patient_df = self.patient_df_3month
            has_followup_col = 'has_followup_3month'
            suffix = '_3month'
        else:  # 1year
            patient_df = self.patient_df_1year
            has_followup_col = 'has_followup_1year'
            suffix = '_1year'

        respondents = patient_df[patient_df[has_followup_col] == True].copy()

        results = {}

        # Physical capacity: baseline (X_433_0_32) vs follow-up (X_435_0_741)
        baseline_phys = 'X_433_0_32'
        followup_phys = f'X_435_0_741{suffix}'

        if baseline_phys in respondents.columns and followup_phys in respondents.columns:
            paired = respondents[(respondents[baseline_phys].notna()) &
                                (respondents[followup_phys].notna())].copy()
            # Exclude refusal code 0 at follow-up (not a scale value) from paired analysis
            paired = paired[pd.to_numeric(paired[followup_phys], errors='coerce') >= 1]

            if len(paired) > 0:
                baseline_vals = pd.to_numeric(paired[baseline_phys], errors='coerce')
                followup_vals = pd.to_numeric(paired[followup_phys], errors='coerce')
                change_vals = followup_vals - baseline_vals

                results['physical_capacity'] = {
                    'n': int(len(paired)),
                    'baseline': {
                        'mean': float(baseline_vals.mean()),
                        'sd': float(baseline_vals.std()) if len(baseline_vals) > 1 else 0,
                        'median': float(baseline_vals.median()),
                        'q25': float(baseline_vals.quantile(0.25)),
                        'q75': float(baseline_vals.quantile(0.75))
                    },
                    'followup': {
                        'mean': float(followup_vals.mean()),
                        'sd': float(followup_vals.std()) if len(followup_vals) > 1 else 0,
                        'median': float(followup_vals.median()),
                        'q25': float(followup_vals.quantile(0.25)),
                        'q75': float(followup_vals.quantile(0.75))
                    },
                    'change': {
                        'mean': float(change_vals.mean()),
                        'median': float(change_vals.median()),
                        'improved': int((change_vals > 0).sum()),
                        'unchanged': int((change_vals == 0).sum()),
                        'worsened': int((change_vals < 0).sum())
                    },
                    'transition_matrix': self._transition_matrix(baseline_vals, followup_vals),
                    'scale_note': (
                        'ordinal scale; codes index the categories 1, 3, 4, 10 and '
                        '>10 MET. Primary summaries: transition matrix, '
                        'improved/unchanged/worsened counts, and median/IQR. '
                        'Means and mean changes of the category codes are '
                        'exploratory (unequal category spacing).'
                    )
                }

        # Frailty CFS: baseline (X_433_0_25) vs follow-up (X_435_0_742)
        baseline_cfs = 'X_433_0_25'
        followup_cfs = f'X_435_0_742{suffix}'

        if baseline_cfs in respondents.columns and followup_cfs in respondents.columns:
            paired = respondents[(respondents[baseline_cfs].notna()) &
                                (respondents[followup_cfs].notna())].copy()
            # Exclude refusal code 0 at follow-up (CFS scale is 1-9) from paired analysis
            paired = paired[pd.to_numeric(paired[followup_cfs], errors='coerce') >= 1]

            if len(paired) > 0:
                baseline_vals = pd.to_numeric(paired[baseline_cfs], errors='coerce')
                followup_vals = pd.to_numeric(paired[followup_cfs], errors='coerce')
                change_vals = followup_vals - baseline_vals

                results['frailty_cfs'] = {
                    'n': int(len(paired)),
                    'baseline': {
                        'mean': float(baseline_vals.mean()),
                        'sd': float(baseline_vals.std()) if len(baseline_vals) > 1 else 0,
                        'median': float(baseline_vals.median()),
                        'q25': float(baseline_vals.quantile(0.25)),
                        'q75': float(baseline_vals.quantile(0.75))
                    },
                    'followup': {
                        'mean': float(followup_vals.mean()),
                        'sd': float(followup_vals.std()) if len(followup_vals) > 1 else 0,
                        'median': float(followup_vals.median()),
                        'q25': float(followup_vals.quantile(0.25)),
                        'q75': float(followup_vals.quantile(0.75))
                    },
                    'change': {
                        'mean': float(change_vals.mean()),
                        'median': float(change_vals.median()),
                        'improved': int((change_vals < 0).sum()),  # Lower CFS is better
                        'unchanged': int((change_vals == 0).sum()),
                        'worsened': int((change_vals > 0).sum())
                    },
                    'transition_matrix': self._transition_matrix(baseline_vals, followup_vals),
                    'scale_note': (
                        'ordinal scale (CFS grades 1-9). Primary summaries: '
                        'transition matrix, improved/unchanged/worsened counts, '
                        'and median/IQR. Means and mean changes of the grades '
                        'are exploratory (ordinal, not interval-scaled).'
                    )
                }

        return results

    def _format_timepoint_section(self, timepoint: str, label: str) -> List[str]:
        """Helper method to format statistics for a single timepoint."""
        lines = []
        results = self.results[timepoint]

        lines.append("=" * 110)
        lines.append(f"FOLLOW-UP STATISTICS - {label}")
        lines.append("=" * 110)
        lines.append("")

        # Completion statistics
        lines.append("-" * 110)
        lines.append("FOLLOW-UP COMPLETION RATE")
        lines.append("-" * 110)
        comp = results['completion']
        lines.append(f"Timing window: {comp['timing_window']} from first blood product")
        lines.append(f"Data collection end date: {comp['data_end_date']}")
        lines.append(f"Eligibility cutoff: {comp['eligibility_cutoff_date']}")
        lines.append("")
        lines.append(f"Transfusion patients: {comp['total_patients']}")
        lines.append(f"  (Note: Non-transfusion patients excluded - follow-up only for those who received blood products)")
        lines.append(f"Eligible for follow-up: {comp['eligible_patients']}")
        lines.append(f"Not yet eligible: {comp['not_yet_eligible']}")
        lines.append("")
        lines.append(f"Among {comp['eligible_patients']} eligible patients:")
        lines.append(f"  Completed follow-up:  {comp['completed_followups']:3d} ({comp['completion_rate']['percent']:5.1f}%)")
        lines.append(f"  Pending:              {comp['pending_followups']:3d} ({100-comp['completion_rate']['percent']:5.1f}%)")
        lines.append("")

        # Respondent demographics
        lines.append("-" * 110)
        lines.append("RESPONDENT DEMOGRAPHICS")
        lines.append("-" * 110)
        resp_demo = results['respondent_demographics']['respondents']

        if 'age' in resp_demo:
            age = resp_demo['age']
            lines.append(f"\nAge (n={age['n']}):")
            lines.append(f"  Mean (SD): {age['mean']:.1f} ({age['sd']:.1f}) years")
            lines.append(f"  Median [IQR]: {age['median']:.0f} [{age['q25']:.0f}-{age['q75']:.0f}] years")
            lines.append(f"  Range: {age['min']}-{age['max']} years")

        if 'gender' in resp_demo:
            lines.append(f"\nGender:")
            for gender, data in resp_demo['gender'].items():
                lines.append(f"  {gender:20s} {data['n']:3d} ({data['percent']:5.1f}%)")

        # Comparison with non-respondents
        non_resp_demo = results['respondent_demographics']['non_respondents']
        if 'age' in non_resp_demo and 'age' in resp_demo:
            lines.append(f"\nComparison with non-respondents:")
            lines.append(f"  Mean age (respondents):     {resp_demo['age']['mean']:5.1f} years")
            lines.append(f"  Mean age (non-respondents): {non_resp_demo['age']['mean']:5.1f} years")
        lines.append("")

        # Patient-reported outcomes
        lines.append("-" * 110)
        lines.append("PATIENT-REPORTED OUTCOMES AT FOLLOW-UP")
        lines.append("-" * 110)
        pro = results['patient_reported_outcomes']

        lines.append("(Ordinal scales: distribution and median/IQR are the primary")
        lines.append(" summaries; means of the category codes are exploratory.)")

        if 'physical_capacity' in pro:
            pc = pro['physical_capacity']
            lines.append(f"\nPhysical Capacity (n={pc['n']}; categories index 1, 3, 4, 10, >10 MET):")
            lines.append(f"  Distribution:")
            for level, data in sorted(pc['distribution'].items()):
                lines.append(f"    {level:15s} {data['n']:3d} ({data['percent']:5.1f}%)")
            if pc['median'] is not None:
                lines.append(f"  Median [IQR]: {pc['median']:.1f} [{pc['q25']:.1f}-{pc['q75']:.1f}]")
                lines.append(f"  Mean (exploratory): {pc['mean']:.1f}")
            else:
                lines.append("  No scale values (all answers refused)")

        if 'frailty_cfs' in pro:
            cfs = pro['frailty_cfs']
            lines.append(f"\nClinical Frailty Scale (n={cfs['n']}; ordinal grades 1-9):")
            lines.append(f"  Distribution:")
            for level, data in sorted(cfs['distribution'].items()):
                lines.append(f"    {level:15s} {data['n']:3d} ({data['percent']:5.1f}%)")
            if cfs['median'] is not None:
                lines.append(f"  Median [IQR]: {cfs['median']:.1f} [{cfs['q25']:.1f}-{cfs['q75']:.1f}]")
                lines.append(f"  Mean (exploratory): {cfs['mean']:.1f}")
            else:
                lines.append("  No scale values (all answers refused)")

        if not pro:
            lines.append("\nNo patient-reported outcomes available for this timepoint.")
        lines.append("")

        # Adverse events
        lines.append("-" * 110)
        lines.append("ADVERSE EVENTS")
        lines.append("-" * 110)
        ae = results['adverse_events']

        if 'blood_product_problems' in ae:
            bp = ae['blood_product_problems']
            lines.append(f"\nProblems related to blood product (n={bp['total']}):")
            lines.append(f"  Yes:                {bp['yes']['n']:3d} ({bp['yes']['percent']:5.1f}%)")
            lines.append(f"  No:                 {bp['no']['n']:3d} ({bp['no']['percent']:5.1f}%)")
            lines.append(f"  Refused to answer:  {bp['refused_to_answer']['n']:3d} ({bp['refused_to_answer']['percent']:5.1f}%)")
        else:
            lines.append("\nNo adverse event data available for this timepoint.")
        lines.append("")

        # Clinical outcomes
        lines.append("-" * 110)
        lines.append("CLINICAL OUTCOMES")
        lines.append("-" * 110)
        co = results['clinical_outcomes']

        if 'anaemia_diagnosed' in co:
            an = co['anaemia_diagnosed']
            lines.append(f"\nAnaemia diagnosed (n={an['total']}):")
            lines.append(f"  Yes:                {an['yes']['n']:3d} ({an['yes']['percent']:5.1f}%)")
            lines.append(f"  No:                 {an['no']['n']:3d} ({an['no']['percent']:5.1f}%)")
            lines.append(f"  Refused to answer:  {an['refused_to_answer']['n']:3d} ({an['refused_to_answer']['percent']:5.1f}%)")

        if 'past_year_transfusions' in co:
            pt = co['past_year_transfusions']
            lines.append(f"\nBlood transfusions in past year (n={pt['total']}):")
            for category, data in sorted(pt['distribution'].items()):
                lines.append(f"  {category:20s} {data['n']:3d} ({data['percent']:5.1f}%)")

        if not co:
            lines.append("\nNo clinical outcome data available for this timepoint.")
        lines.append("")

        # Baseline vs follow-up comparison
        lines.append("-" * 110)
        lines.append("BASELINE VS. FOLLOW-UP COMPARISON")
        lines.append("-" * 110)
        comp = results['baseline_followup_comparison']

        if comp:
            lines.append("(Ordinal scales: the transition matrix, the improved/unchanged/")
            lines.append(" worsened counts, and median/IQR are the primary summaries;")
            lines.append(" means of the category codes are exploratory.)")

        def _matrix_lines(matrix: Dict[str, Dict[str, int]], row_label: str) -> List[str]:
            out = []
            cols = sorted({c for row in matrix.values() for c in row}, key=int)
            out.append(f"    {row_label + ' v / follow-up >':<24}" + "".join(f"{c:>6}" for c in cols))
            for b in sorted(matrix, key=int):
                out.append(f"    {b:<24}" + "".join(f"{matrix[b].get(c, 0):>6}" for c in cols))
            return out

        if 'physical_capacity' in comp:
            pc = comp['physical_capacity']
            lines.append(f"\nPhysical Capacity (n={pc['n']} paired; categories index 1, 3, 4, 10, >10 MET):")
            lines.append(f"  Transition matrix (baseline category -> follow-up category):")
            lines.extend(_matrix_lines(pc['transition_matrix'], 'baseline'))
            lines.append(f"  Improved:  {pc['change']['improved']:3d} patients")
            lines.append(f"  Unchanged: {pc['change']['unchanged']:3d} patients")
            lines.append(f"  Worsened:  {pc['change']['worsened']:3d} patients")
            lines.append(f"  Baseline:  Median [IQR] = {pc['baseline']['median']:.1f} [{pc['baseline']['q25']:.1f}-{pc['baseline']['q75']:.1f}]")
            lines.append(f"  Follow-up: Median [IQR] = {pc['followup']['median']:.1f} [{pc['followup']['q25']:.1f}-{pc['followup']['q75']:.1f}]")
            lines.append(f"  Exploratory means: baseline {pc['baseline']['mean']:.2f} (SD {pc['baseline']['sd']:.2f}), "
                         f"follow-up {pc['followup']['mean']:.2f} (SD {pc['followup']['sd']:.2f}), "
                         f"change {pc['change']['mean']:+.2f}")

        if 'frailty_cfs' in comp:
            cfs = comp['frailty_cfs']
            lines.append(f"\nClinical Frailty Scale (n={cfs['n']} paired; ordinal grades 1-9):")
            lines.append(f"  Transition matrix (baseline grade -> follow-up grade):")
            lines.extend(_matrix_lines(cfs['transition_matrix'], 'baseline'))
            lines.append(f"  Improved (lower CFS):  {cfs['change']['improved']:3d} patients")
            lines.append(f"  Unchanged:             {cfs['change']['unchanged']:3d} patients")
            lines.append(f"  Worsened (higher CFS): {cfs['change']['worsened']:3d} patients")
            lines.append(f"  Baseline:  Median [IQR] = {cfs['baseline']['median']:.1f} [{cfs['baseline']['q25']:.1f}-{cfs['baseline']['q75']:.1f}]")
            lines.append(f"  Follow-up: Median [IQR] = {cfs['followup']['median']:.1f} [{cfs['followup']['q25']:.1f}-{cfs['followup']['q75']:.1f}]")
            lines.append(f"  Exploratory means: baseline {cfs['baseline']['mean']:.2f} (SD {cfs['baseline']['sd']:.2f}), "
                         f"follow-up {cfs['followup']['mean']:.2f} (SD {cfs['followup']['sd']:.2f}), "
                         f"change {cfs['change']['mean']:+.2f}")

        if not comp:
            lines.append("\nNo paired baseline-followup data available for this timepoint.")

        lines.append("")
        return lines

    def create_summary_table(self) -> str:
        """
        Create formatted summary table for follow-up statistics at both timepoints.

        Returns:
            Formatted string with complete follow-up statistics
        """
        if not self.results:
            self.calculate_all()

        lines = []

        # Overall header
        lines.append("=" * 110)
        lines.append("FOLLOW-UP STATISTICS - COMPREHENSIVE ANALYSIS")
        lines.append("=" * 110)
        lines.append("")

        # Timing summary
        timing = self.results['timing_summary']
        lines.append("FOLLOW-UP CLASSIFICATION SUMMARY")
        lines.append(f"Total follow-up records: {timing['total_followup_records']}")
        lines.append(f"  Classified as 3-month ({timing['timing_windows']['3month']}): {timing['classified_3month']}")
        lines.append(f"  Classified as 1-year ({timing['timing_windows']['1year']}):  {timing['classified_1year']}")
        lines.append(f"  Unclassified (outside windows):                                      {timing['unclassified']}")
        lines.append("")

        # Duplicate resolution summary
        dup_res = self.results['duplicate_resolution']
        lines.append("DUPLICATE FOLLOW-UP RESOLUTION")
        lines.append("-" * 60)

        resolved = dup_res['resolved_identical_duplicates']
        if resolved['total'] > 0:
            lines.append(f"Resolved identical duplicates (kept one): {resolved['total']} patients")
            lines.append(f"  3-month: {resolved['3month']} patients")
            lines.append(f"  1-year:  {resolved['1year']} patients")
        else:
            lines.append("Resolved identical duplicates: 0")

        excluded = dup_res['excluded_conflicting_duplicates']
        if excluded['total'] > 0:
            lines.append(f"\nEXCLUDED conflicting duplicates (different values): {excluded['total']} patients")
            lines.append(f"  3-month: {excluded['3month']} patients (PIDs: {', '.join(map(str, excluded['pids_3month']))})")
            lines.append(f"  1-year:  {excluded['1year']} patients (PIDs: {', '.join(map(str, excluded['pids_1year']))})")
            lines.append("")
            lines.append("  NOTE: These patients had multiple follow-ups in the same window with")
            lines.append("        DIFFERENT values. They are excluded from analysis and exported")
            lines.append("        to conflicting_followup_duplicates.csv for manual review.")
        else:
            lines.append("\nExcluded conflicting duplicates: 0")
        lines.append("")
        lines.append("")

        # 3-month follow-up section
        lines.extend(self._format_timepoint_section('3month', 'FIRST FOLLOW-UP (3-MONTH)'))
        lines.append("")
        lines.append("")

        # 1-year follow-up section
        lines.extend(self._format_timepoint_section('1year', 'SECOND FOLLOW-UP (1-YEAR)'))

        lines.append("")
        lines.append("=" * 110)

        return "\n".join(lines)

    def export_results(self, output_dir: str = ".") -> None:
        """
        Export results to files.

        Args:
            output_dir: Directory to save output files
        """
        if not self.results:
            self.calculate_all()

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Export detailed JSON
        json_file = output_path / "followup_statistics_detailed.json"
        with open(json_file, 'w') as f:
            json.dump(json_sanitize(self.results), f, indent=2, allow_nan=False)
        print(f"Detailed results exported to: {json_file}")

        # Export formatted table
        table = self.create_summary_table()
        txt_file = output_path / "followup_statistics.txt"
        with open(txt_file, 'w') as f:
            f.write(table)
        print(f"Summary table exported to: {txt_file}")

        # Export conflicting duplicates for manual review (if any)
        if self.conflicting_duplicates:
            self._export_conflicting_duplicates(output_path)

    def _export_conflicting_duplicates(self, output_path: Path) -> None:
        """Export conflicting duplicate follow-ups for manual review."""
        # Create a detailed CSV with all differing values
        rows = []
        for conflict in self.conflicting_duplicates:
            pid = conflict['PID']
            window = conflict['window']
            differing_cols = conflict['differing_columns']

            for i, record in enumerate(conflict['records']):
                row = {
                    'PID': pid,
                    'window': window,
                    'record_number': i + 1,
                    'followup_date': record.get('followup_date', ''),
                    'days_from_first': record.get('days_from_first', ''),
                    'differing_columns': '; '.join(differing_cols)
                }
                # Add the differing values
                for col in differing_cols:
                    if col in record:
                        # Use readable column name if available
                        readable_name = col  # Could be enhanced with mapper
                        row[readable_name] = record[col]
                rows.append(row)

        df_conflicts = pd.DataFrame(rows)
        csv_file = output_path / "conflicting_followup_duplicates.csv"
        df_conflicts.to_csv(csv_file, index=False)
        print(f"Conflicting duplicates exported to: {csv_file}")
        print(f"  -> {len(self.conflicting_duplicates)} patients with conflicting follow-ups need manual review")


def run_followup_analysis(data_file: str, output_dir: str = ".",
                          data_end_date: Optional[datetime] = None) -> FollowUpDescriptives:
    """
    Run complete follow-up analysis workflow.

    Args:
        data_file: Path to CSV data file
        output_dir: Directory for output files
        data_end_date: End date for data collection (default: latest in data)

    Returns:
        FollowUpDescriptives object with calculated results
    """
    print("=" * 90)
    print("FOLLOW-UP STATISTICS ANALYSIS")
    print("=" * 90)

    # Load data
    print("\nLoading data...")
    loader = TransfusionDataLoader()
    loader.load_data(data_file, validate=False)

    # Calculate statistics
    followup = FollowUpDescriptives(loader, data_end_date)
    followup.calculate_all()

    # Display table
    table = followup.create_summary_table()
    print("\n" + table)

    # Export results
    print("\nExporting results...")
    followup.export_results(output_dir)

    print("\nAnalysis complete!")
    return followup


if __name__ == "__main__":
    # Example usage
    followup = run_followup_analysis("../test_data_150patients.csv", output_dir=".")
