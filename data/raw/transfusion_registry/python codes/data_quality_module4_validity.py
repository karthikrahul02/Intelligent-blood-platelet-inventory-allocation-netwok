"""
Data Quality Analysis: Module 4 - Data Validity
================================================

Checks if values fall within clinically plausible ranges.

Author: Elina Nuerenberg-Goloub with Claude Sonnet 4.5 by Anthropic
Date: 2025-10-22
Revised on 2026-01-21 by Elina Nuerenberg-Goloub and Claude Opus 4.5
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple
from transfusion_data_loader import TransfusionDataLoader
import json
from pathlib import Path
from datetime import datetime

from transfusion_registry_mapping import clinical_range as _registry_range
from transfusion_registry_mapping import json_sanitize


class DataValidity:
    """
    Analyze data validity by checking if values fall within clinically plausible ranges.

    Checks:
    - Demographics: height, weight, age
    - Lab values (before/after): Hb, albumin, ferritin, transferrin, fibrinogen, Quick's test, platelets
    - Identical before/after values: flags potential copy-paste errors
    - MAT values: wound blood volume, recovered RBC volume, recovered hematocrit
    """

    # Validity ranges for each parameter - all bounds come from the central
    # physician range registry (transfusion_registry_mapping), the single
    # versioned source. Only the derived age parameter is defined locally.
    RANGES = {
        # Demographics
        'height_cm': _registry_range('height_cm'),
        'weight_kg': _registry_range('weight_kg'),
        'age_years': (0, 120, 'years'),  # derived parameter, not part of the physician table

        # Lab values (before and after; canonical units)
        'hemoglobin': _registry_range('hemoglobin'),
        'serum_albumin': _registry_range('serum_albumin'),
        'ferritin': _registry_range('ferritin'),
        'transferrin': _registry_range('transferrin'),
        'fibrinogen': _registry_range('fibrinogen'),
        'quicks_test': _registry_range('quicks_test'),
        'platelets': _registry_range('platelets'),
        'epo_plasma': _registry_range('epo_plasma'),
        'atiii_activity': _registry_range('atiii_activity'),

        # MAT values
        'mat_wound_blood': _registry_range('mat_wound_blood'),
        'mat_wound_hematocrit': _registry_range('mat_wound_hematocrit'),
        'recovered_rbc_volume': _registry_range('recovered_rbc_volume'),
        'recovered_hematocrit': _registry_range('recovered_hematocrit'),
    }

    # Field mappings
    FIELD_MAP = {
        # Administration
        'admin_date': 'X_433_7_11',

        # Demographics
        'height_cm': 'X_433_0_2',
        'weight_kg': 'X_433_0_3',
        'age_birth_year': 'X_541_0_1',

        # Lab values - before
        'hemoglobin_before': 'X_433_7_614',
        'serum_albumin_before': 'X_433_7_603',
        'ferritin_before': 'X_433_7_736',
        'transferrin_before': 'X_433_7_589',
        'fibrinogen_before': 'X_433_7_585',
        'quicks_test_before': 'X_433_7_374',
        'platelets_before': 'X_433_7_37',
        'epo_plasma_before': 'X_433_7_597',  # Erythropoietin (Plasma), before
        'atiii_activity_before': 'X_433_7_601',  # Antithrombin III activity (before)

        # Lab values - after
        'hemoglobin_after': 'X_433_7_615',
        'serum_albumin_after': 'X_433_7_591',
        'ferritin_after': 'X_433_7_735',
        'transferrin_after': 'X_433_7_590',
        'fibrinogen_after': 'X_433_7_586',
        'quicks_test_after': 'X_433_7_596',
        'platelets_after': 'X_433_7_587',
        'epo_plasma_after': 'X_433_7_599',  # Erythropoietin (Plasma), after
        'atiii_activity_after': 'X_433_7_602',  # Antithrombin III activity (after)

        # MAT values
        'mat_wound_blood': 'X_433_7_747',
        'mat_wound_hematocrit': 'X_433_7_748',  # Hematocrit of wound blood
        'recovered_rbc_volume': 'X_433_7_749',
        'recovered_hematocrit': 'X_433_7_750',
    }

    # Before/after pairs to check for identical values
    BEFORE_AFTER_PAIRS = [
        ('hemoglobin', 'Hemoglobin', 'g/dl'),
        ('serum_albumin', 'Serum Albumin', 'g/dl'),
        ('ferritin', 'Ferritin', 'μg/L'),
        ('transferrin', 'Transferrin', '%'),
        ('fibrinogen', 'Fibrinogen', 'mg/dl'),
        ('quicks_test', 'Quick\'s Test', '%'),
        ('platelets', 'Platelets', '/μL'),
        ('epo_plasma', 'EPO (Plasma)', 'U/L'),
        ('atiii_activity', 'Antithrombin III activity', '%'),
    ]

    def __init__(self, loader: TransfusionDataLoader):
        """
        Initialize data validity analyzer.

        Args:
            loader: TransfusionDataLoader with loaded data
        """
        self.loader = loader
        self.df = loader.df_clean.copy()
        self.mapper = loader.mapper
        self.results = {}
        # Reference date derived from the data (max episode date), NOT hardcoded —
        # a fixed export date silently mis-ages every later export.
        episode_dates = pd.to_datetime(self.df.get('Episode date'), errors='coerce', dayfirst=True)
        self.export_date = episode_dates.max() if episode_dates.notna().any() else pd.Timestamp.now()

    @staticmethod
    def _norm_code(series: pd.Series) -> pd.Series:
        """Normalize product/unit code strings: '11.0' -> '11'. Robust against
        int-parsed or plain-string exports (the float form only arises from
        NaN-induced float parsing)."""
        return series.astype(str).str.replace(r'\.0$', '', regex=True)

    def calculate_all(self) -> Dict[str, Any]:
        """
        Calculate all data validity statistics.

        Returns:
            Dictionary with all analysis results
        """
        print("\nCalculating data quality: Data validity analysis...")
        print("=" * 90)

        # Step 1: Check demographics
        print("\n1. Checking demographics validity...")
        self._check_demographics()

        # Step 2: Check lab values
        print("2. Checking lab values validity...")
        self._check_lab_values()

        # Step 3: Check identical before/after values
        print("3. Checking for identical before/after values...")
        self._check_identical_before_after()

        # Step 4: Check MAT values
        print("4. Checking MAT values validity...")
        self._check_mat_values()

        # Step 5: Create summary
        print("5. Creating summary statistics...")
        self._create_summary()

        print("\nData validity analysis complete")
        print("=" * 90)

        return self.results

    def _check_demographics(self) -> None:
        """Check validity of demographic data."""
        # Calculate age from birth year
        current_year = self.export_date.year
        birth_year_col = self.FIELD_MAP['age_birth_year']

        if birth_year_col in self.df.columns:
            self.df['calculated_age'] = current_year - pd.to_numeric(self.df[birth_year_col], errors='coerce')

        demographics_checks = []

        # Height
        height_col = self.FIELD_MAP['height_cm']
        min_val, max_val, unit = self.RANGES['height_cm']
        height_check = self._check_range(height_col, 'Height', min_val, max_val, unit, level='patient')
        demographics_checks.append(height_check)

        # Weight
        weight_col = self.FIELD_MAP['weight_kg']
        min_val, max_val, unit = self.RANGES['weight_kg']
        weight_check = self._check_range(weight_col, 'Weight', min_val, max_val, unit, level='patient')
        demographics_checks.append(weight_check)

        # Age
        if 'calculated_age' in self.df.columns:
            min_val, max_val, unit = self.RANGES['age_years']
            age_check = self._check_range('calculated_age', 'Age', min_val, max_val, unit, level='patient')
            demographics_checks.append(age_check)

        invalid_dfs = [check['invalid_records'] for check in demographics_checks if len(check['invalid_records']) > 0]
        self.demographics_df = pd.concat(invalid_dfs) if invalid_dfs else pd.DataFrame()
        self.results['demographics'] = {
            'checks': demographics_checks,
            'n_total_checks': len(demographics_checks),
            'n_with_invalid': sum(1 for check in demographics_checks if check['n_invalid'] > 0)
        }

        # Print summary
        for check in demographics_checks:
            if check['n_invalid'] > 0:
                print(f"   {check['parameter']}: {check['n_invalid']} invalid values (out of {check['n_present']})")

    def _check_lab_values(self) -> None:
        """Check validity of lab values."""
        lab_checks = []

        # Check each lab parameter (before and after)
        lab_params = ['hemoglobin', 'serum_albumin', 'ferritin', 'transferrin',
                      'fibrinogen', 'quicks_test', 'platelets', 'epo_plasma',
                      'atiii_activity']

        # work on an instance copy so the class-level FIELD_MAP is untouched
        self.FIELD_MAP = dict(self.FIELD_MAP)
        # Bring mixed-scale entries onto the canonical unit before range
        # screening (same rules as the central lab normalization in
        # lab_value_quality: positive platelet values < 1000 are thousands/µl;
        # albumin values >= 100 are mg/dl). Non-positive values stay unscaled
        # and fail the range check as impossible.
        for fld, kind in (('serum_albumin_before', 'alb'), ('serum_albumin_after', 'alb'),
                          ('platelets_before', 'plt'), ('platelets_after', 'plt')):
            col = self.FIELD_MAP[fld]
            if col in self.df.columns:
                vals = pd.to_numeric(self.df[col], errors='coerce')
                if kind == 'plt':
                    m = vals.notna() & (vals > 0) & (vals < 1000)
                    vals = vals.mask(m, vals * 1000)
                else:
                    m = vals.notna() & (vals >= 100)
                    vals = vals.mask(m, vals / 1000)
                self.df[col + '_screening'] = vals
                self.FIELD_MAP[fld] = col + '_screening'

        for param in lab_params:
            min_val, max_val, unit = self.RANGES[param]

            # Before
            before_field = f'{param}_before'
            if before_field in self.FIELD_MAP:
                before_col = self.FIELD_MAP[before_field]
                before_check = self._check_range(
                    before_col, f'{param.replace("_", " ").title()} (before)',
                    min_val, max_val, unit, level='administration',
                    nonpositive_invalid=True
                )
                lab_checks.append(before_check)

            # After
            after_field = f'{param}_after'
            if after_field in self.FIELD_MAP:
                after_col = self.FIELD_MAP[after_field]
                after_check = self._check_range(
                    after_col, f'{param.replace("_", " ").title()} (after)',
                    min_val, max_val, unit, level='administration',
                    nonpositive_invalid=True
                )
                lab_checks.append(after_check)

        invalid_dfs = [check['invalid_records'] for check in lab_checks if len(check['invalid_records']) > 0]
        self.lab_df = pd.concat(invalid_dfs) if invalid_dfs else pd.DataFrame()
        self.results['lab_values'] = {
            'checks': lab_checks,
            'n_total_checks': len(lab_checks),
            'n_with_invalid': sum(1 for check in lab_checks if check['n_invalid'] > 0)
        }

        # Print summary
        for check in lab_checks:
            if check['n_invalid'] > 0:
                print(f"   {check['parameter']}: {check['n_invalid']} invalid values (out of {check['n_present']})")

    def _check_identical_before_after(self) -> None:
        """Check for identical before/after lab values (potential copy-paste errors)."""
        identical_records = []

        for param_key, param_name, unit in self.BEFORE_AFTER_PAIRS:
            before_field = f'{param_key}_before'
            after_field = f'{param_key}_after'

            if before_field not in self.FIELD_MAP or after_field not in self.FIELD_MAP:
                continue

            before_col = self.FIELD_MAP[before_field]
            after_col = self.FIELD_MAP[after_field]

            if before_col not in self.df.columns or after_col not in self.df.columns:
                continue

            # Get numeric values
            before_vals = pd.to_numeric(self.df[before_col], errors='coerce')
            after_vals = pd.to_numeric(self.df[after_col], errors='coerce')

            # Find records where both are present and exactly identical
            both_present = before_vals.notna() & after_vals.notna()
            identical_mask = both_present & (before_vals == after_vals)

            n_both_present = both_present.sum()
            n_identical = identical_mask.sum()

            if n_identical > 0:
                print(f"   {param_name}: {n_identical} identical before/after values (out of {n_both_present} pairs)")

                # Collect records
                admin_date_col = self.FIELD_MAP['admin_date']
                for idx in self.df[identical_mask].index:
                    admin_date = ''
                    if admin_date_col in self.df.columns:
                        admin_val = self.df.loc[idx, admin_date_col]
                        admin_date = str(admin_val)[:10] if pd.notna(admin_val) else ''
                    identical_records.append({
                        'PID': str(self.df.loc[idx, 'PID']),
                        'admin_date': admin_date,
                        'parameter': param_name,
                        'before_value': float(before_vals[idx]),
                        'after_value': float(after_vals[idx]),
                        'unit': unit
                    })

        self.identical_df = pd.DataFrame(identical_records) if identical_records else pd.DataFrame()
        self.results['identical_before_after'] = {
            'n_total_identical': len(identical_records),
            'records': identical_records
        }

    def _check_mat_values(self) -> None:
        """Check validity of MAT values."""
        mat_checks = []

        # Filter to MAT records only (code 11), normalized against float-string forms
        mat_df = (self.df[self._norm_code(self.df['X_433_7_746']) == '11'].copy()
                  if 'X_433_7_746' in self.df.columns else pd.DataFrame())

        if len(mat_df) > 0:
            # Wound blood volume
            min_val, max_val, unit = self.RANGES['mat_wound_blood']
            wound_check = self._check_range(
                self.FIELD_MAP['mat_wound_blood'], 'MAT wound blood volume',
                min_val, max_val, unit, level='administration', subset_df=mat_df
            )
            mat_checks.append(wound_check)

            # Recovered RBC volume
            min_val, max_val, unit = self.RANGES['recovered_rbc_volume']
            rbc_check = self._check_range(
                self.FIELD_MAP['recovered_rbc_volume'], 'Recovered RBC volume',
                min_val, max_val, unit, level='administration', subset_df=mat_df
            )
            mat_checks.append(rbc_check)

            # Wound blood hematocrit
            min_val, max_val, unit = self.RANGES['mat_wound_hematocrit']
            wound_hct_check = self._check_range(
                self.FIELD_MAP['mat_wound_hematocrit'], 'Wound blood hematocrit',
                min_val, max_val, unit, level='administration', subset_df=mat_df
            )
            mat_checks.append(wound_hct_check)

            # Recovered hematocrit
            min_val, max_val, unit = self.RANGES['recovered_hematocrit']
            hct_check = self._check_range(
                self.FIELD_MAP['recovered_hematocrit'], 'Recovered hematocrit',
                min_val, max_val, unit, level='administration', subset_df=mat_df
            )
            mat_checks.append(hct_check)

        invalid_dfs = [check['invalid_records'] for check in mat_checks if len(check['invalid_records']) > 0]
        self.mat_df = pd.concat(invalid_dfs) if invalid_dfs else pd.DataFrame()
        self.results['mat'] = {
            'checks': mat_checks,
            'n_total_checks': len(mat_checks),
            'n_with_invalid': sum(1 for check in mat_checks if check['n_invalid'] > 0)
        }

        # Print summary
        for check in mat_checks:
            if check['n_invalid'] > 0:
                print(f"   {check['parameter']}: {check['n_invalid']} invalid values (out of {check['n_present']})")

    def _check_range(self, column: str, parameter: str, min_val: float, max_val: float,
                     unit: str, level: str = 'patient', subset_df: pd.DataFrame = None,
                     nonpositive_invalid: bool = False) -> Dict[str, Any]:
        """
        Check if values in a column fall within valid range.

        Args:
            column: Column name to check
            parameter: Human-readable parameter name
            min_val: Minimum valid value
            max_val: Maximum valid value
            unit: Unit of measurement
            level: Level of analysis ('patient' or 'administration')
            subset_df: Optional subset of data to check (e.g., MAT records only)

        Returns:
            Dictionary with check results
        """
        df_to_check = subset_df if subset_df is not None else self.df

        if column not in df_to_check.columns:
            return {
                'parameter': parameter,
                'column': column,
                'unit': unit,
                'valid_range': f'{min_val}-{max_val}',
                'n_total': 0,
                'n_present': 0,
                'n_invalid': 0,
                'n_valid': 0,
                'percent_invalid': 0.0,
                'invalid_records': pd.DataFrame(),
                'level': level
            }

        # Get non-null values - EVERY documented value is checked (a later
        # impossible entry must not be hidden by an earlier valid one)
        values = pd.to_numeric(df_to_check[column], errors='coerce')
        present_mask = values.notna()
        invalid_mask = present_mask & ((values < min_val) | (values > max_val))
        if nonpositive_invalid:
            # laboratory parameters: documented values <= 0 are impossible
            # even when the table floor is 0 (entry floor, not a measured
            # value) - counted as findings, distinct from missing values
            invalid_mask = invalid_mask | (present_mask & (values <= 0))

        if level == 'patient' and 'PID' in df_to_check.columns:
            # patient-level counting: unique patients, not rows; the offending
            # rows themselves are itemized in invalid_records
            pids = df_to_check['PID']
            n_total_units = int(pids.nunique())
            n_present = int(pids[present_mask].nunique())
            n_invalid = int(pids[invalid_mask].nunique())
        else:
            n_total_units = len(df_to_check)
            n_present = int(present_mask.sum())
            n_invalid = int(invalid_mask.sum())
        n_valid = n_present - n_invalid

        # Get invalid records
        admin_date_col = self.FIELD_MAP['admin_date']
        cols_to_get = ['PID', column]
        if admin_date_col in df_to_check.columns:
            cols_to_get.append(admin_date_col)
        invalid_records = df_to_check[invalid_mask][cols_to_get].copy()
        invalid_records['parameter'] = parameter
        invalid_records['value'] = values[invalid_mask]
        invalid_records['valid_range'] = f'{min_val}-{max_val} {unit}'
        # Add admin_date column
        if admin_date_col in invalid_records.columns:
            invalid_records['admin_date'] = invalid_records[admin_date_col].apply(
                lambda x: str(x)[:10] if pd.notna(x) else ''
            )
            invalid_records.drop(columns=[admin_date_col], inplace=True)
        else:
            invalid_records['admin_date'] = ''

        # For patient-level data, get unique patients
        if level == 'patient' and 'PID' in invalid_records.columns:
            n_invalid_patients = invalid_records['PID'].nunique()
        else:
            n_invalid_patients = n_invalid

        # Calculate actual range in data
        actual_min = float(values[present_mask].min()) if n_present > 0 else None
        actual_max = float(values[present_mask].max()) if n_present > 0 else None
        actual_range = f'{actual_min}-{actual_max}' if actual_min is not None else 'N/A'

        return {
            'parameter': parameter,
            'column': column,
            'unit': unit,
            'valid_range': f'{min_val}-{max_val}',
            'actual_range': actual_range,
            'actual_min': actual_min,
            'actual_max': actual_max,
            'n_total': n_total_units,
            'n_present': int(n_present),
            'n_invalid': int(n_invalid),
            'n_valid': int(n_valid),
            'percent_invalid': float(n_invalid / n_present * 100) if n_present > 0 else 0.0,
            'invalid_records': invalid_records,
            'level': level,
            'n_invalid_unique': int(n_invalid_patients) if level == 'patient' else int(n_invalid)
        }

    def _create_summary(self) -> None:
        """Create summary statistics."""
        total_checks = (
            self.results['demographics']['n_total_checks'] +
            self.results['lab_values']['n_total_checks'] +
            self.results['mat']['n_total_checks']
        )

        total_with_invalid = (
            self.results['demographics']['n_with_invalid'] +
            self.results['lab_values']['n_with_invalid'] +
            self.results['mat']['n_with_invalid']
        )

        # Get total invalid values
        total_invalid_demographics = sum(check['n_invalid'] for check in self.results['demographics']['checks'])
        total_invalid_lab = sum(check['n_invalid'] for check in self.results['lab_values']['checks'])
        total_invalid_mat = sum(check['n_invalid'] for check in self.results['mat']['checks'])
        total_identical = self.results['identical_before_after']['n_total_identical']

        self.results['summary'] = {
            'n_total_checks': total_checks,
            'n_checks_with_invalid': total_with_invalid,
            'n_checks_all_valid': total_checks - total_with_invalid,
            'demographics_invalid': total_invalid_demographics,
            'lab_values_invalid': total_invalid_lab,
            'identical_before_after': total_identical,
            'mat_invalid': total_invalid_mat,
            'total_invalid_values': total_invalid_demographics + total_invalid_lab + total_invalid_mat
        }

    def create_summary_tables(self) -> Tuple[str, str, str, str, str]:
        """
        Create formatted summary tables.

        Returns:
            Tuple of (summary_table, demographics_table, lab_table, identical_table, mat_table)
        """
        if not self.results:
            self.calculate_all()

        # Summary table
        summary_lines = []
        summary_lines.append("=" * 120)
        summary_lines.append("DATA QUALITY - VALIDITY: SUMMARY")
        summary_lines.append("=" * 120)
        summary_lines.append("")
        summary = self.results['summary']
        summary_lines.append(f"Total validity checks performed: {summary['n_total_checks']}")
        summary_lines.append(f"Checks with invalid values: {summary['n_checks_with_invalid']}")
        summary_lines.append(f"Checks with all valid values: {summary['n_checks_all_valid']}")
        summary_lines.append("")
        summary_lines.append(f"Total invalid values found: {summary['total_invalid_values']}")
        summary_lines.append(f"  Demographics: {summary['demographics_invalid']}")
        summary_lines.append(f"  Lab values: {summary['lab_values_invalid']}")
        summary_lines.append(f"  MAT values: {summary['mat_invalid']}")
        summary_lines.append("")
        summary_lines.append(f"Identical before/after values (potential copy-paste errors): {summary['identical_before_after']}")
        summary_lines.append("=" * 120)

        # Demographics table
        demographics_lines = self._create_section_table("Demographics", self.results['demographics']['checks'])

        # Lab values table
        lab_lines = self._create_section_table("Lab Values", self.results['lab_values']['checks'])

        # Identical before/after table
        identical_lines = []
        identical_lines.append("=" * 120)
        identical_lines.append("DATA QUALITY - VALIDITY: IDENTICAL BEFORE/AFTER VALUES")
        identical_lines.append("=" * 120)
        identical_lines.append("")
        identical_data = self.results['identical_before_after']
        if identical_data['n_total_identical'] == 0:
            identical_lines.append("No identical before/after values found")
        else:
            identical_lines.append(f"Found {identical_data['n_total_identical']} records with identical before/after values")
            identical_lines.append("(These may indicate copy-paste errors during data entry)")
            identical_lines.append("")
            identical_lines.append(f"{'Parameter':<25} {'Value':<15} {'Unit':<15} {'N Records':>10}")
            identical_lines.append("-" * 120)

            # Group by parameter
            from collections import Counter
            param_counts = Counter((r['parameter'], r['before_value'], r['unit']) for r in identical_data['records'])
            for (param, value, unit), count in sorted(param_counts.items()):
                identical_lines.append(f"{param:<25} {value:<15} {unit:<15} {count:>10}")
        identical_lines.append("=" * 120)

        # MAT table
        mat_lines = self._create_section_table("MAT Values", self.results['mat']['checks'])

        return (
            "\n".join(summary_lines),
            "\n".join(demographics_lines),
            "\n".join(lab_lines),
            "\n".join(identical_lines),
            "\n".join(mat_lines)
        )

    def _create_section_table(self, section_name: str, checks: List[Dict]) -> List[str]:
        """Create formatted table for a section."""
        lines = []
        lines.append("=" * 120)
        lines.append(f"DATA QUALITY - VALIDITY: {section_name.upper()}")
        lines.append("=" * 120)
        lines.append("")

        if len(checks) == 0:
            lines.append("No checks performed for this section")
        else:
            lines.append(f"{'Parameter':<30} {'Valid Range':<18} {'Actual Range':<18} {'Present':>9} {'Invalid':>9} {'%Invalid':>9}")
            lines.append("-" * 120)

            for check in checks:
                if check['n_present'] > 0:
                    lines.append(
                        f"{check['parameter']:<30} "
                        f"{check['valid_range']:<18} "
                        f"{check['actual_range']:<18} "
                        f"{check['n_present']:>9} "
                        f"{check['n_invalid']:>9} "
                        f"{check['percent_invalid']:>8.1f}%"
                    )

        lines.append("=" * 120)
        return lines

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

        # Prepare JSON export (without DataFrame objects, but include actual ranges)
        json_results = {
            'demographics': {
                'n_total_checks': self.results['demographics']['n_total_checks'],
                'n_with_invalid': self.results['demographics']['n_with_invalid'],
                'checks': [{k: v for k, v in check.items() if k != 'invalid_records'}
                          for check in self.results['demographics']['checks']]
            },
            'lab_values': {
                'n_total_checks': self.results['lab_values']['n_total_checks'],
                'n_with_invalid': self.results['lab_values']['n_with_invalid'],
                'checks': [{k: v for k, v in check.items() if k != 'invalid_records'}
                          for check in self.results['lab_values']['checks']]
            },
            'mat': {
                'n_total_checks': self.results['mat']['n_total_checks'],
                'n_with_invalid': self.results['mat']['n_with_invalid'],
                'checks': [{k: v for k, v in check.items() if k != 'invalid_records'}
                          for check in self.results['mat']['checks']]
            },
            'identical_before_after': self.results['identical_before_after'],
            'summary': self.results['summary'],
            'note': 'Actual range shows min-max values found in the data. Valid range shows clinically acceptable limits.'
        }

        # Export detailed JSON
        json_file = output_path / "data_quality_module4_validity.json"
        with open(json_file, 'w') as f:
            json.dump(json_sanitize(json_results), f, indent=2, allow_nan=False)
        print(f"  JSON: {json_file.name}")

        # Export formatted tables
        (summary_table, demographics_table, lab_table, identical_table, mat_table) = self.create_summary_tables()

        # Combined TXT report
        combined_file = output_path / "data_quality_module4_validity.txt"
        with open(combined_file, 'w') as f:
            f.write(summary_table)
            f.write("\n\n\n")
            f.write(demographics_table)
            f.write("\n\n\n")
            f.write(lab_table)
            f.write("\n\n\n")
            f.write(identical_table)
            f.write("\n\n\n")
            f.write(mat_table)
        print(f"  TXT: {combined_file.name}")

        # Export CSV tables
        self._export_csv_tables(output_path)

    def _export_csv_tables(self, output_path: Path) -> None:
        """Export invalid records in CSV format for clinic follow-up."""
        # Create consolidated list of all invalid values
        invalid_records = []

        # Demographics (patient-level, no admin_date)
        for check in self.results['demographics']['checks']:
            if check['n_invalid'] > 0:
                for _, row in check['invalid_records'].iterrows():
                    invalid_records.append({
                        'PID': row['PID'],
                        'Admin_Date': '',
                        'Section': 'Demographics',
                        'Parameter': check['parameter'],
                        'Value': row['value'],
                        'Valid_Range': check['valid_range'],
                        'Unit': check['unit'],
                        'Issue': f"Value {row['value']} outside valid range {check['valid_range']} {check['unit']}"
                    })

        # Lab values
        for check in self.results['lab_values']['checks']:
            if check['n_invalid'] > 0:
                for _, row in check['invalid_records'].iterrows():
                    invalid_records.append({
                        'PID': row['PID'],
                        'Admin_Date': row.get('admin_date', ''),
                        'Section': 'Lab Values',
                        'Parameter': check['parameter'],
                        'Value': row['value'],
                        'Valid_Range': check['valid_range'],
                        'Unit': check['unit'],
                        'Issue': f"Value {row['value']} outside valid range {check['valid_range']} {check['unit']}"
                    })

        # MAT
        for check in self.results['mat']['checks']:
            if check['n_invalid'] > 0:
                for _, row in check['invalid_records'].iterrows():
                    invalid_records.append({
                        'PID': row['PID'],
                        'Admin_Date': row.get('admin_date', ''),
                        'Section': 'MAT',
                        'Parameter': check['parameter'],
                        'Value': row['value'],
                        'Valid_Range': check['valid_range'],
                        'Unit': check['unit'],
                        'Issue': f"Value {row['value']} outside valid range {check['valid_range']} {check['unit']}"
                    })

        # Identical before/after values
        for record in self.results['identical_before_after']['records']:
            invalid_records.append({
                'PID': record['PID'],
                'Admin_Date': record.get('admin_date', ''),
                'Section': 'Identical Before/After',
                'Parameter': record['parameter'],
                'Value': record['before_value'],
                'Valid_Range': 'before ≠ after',
                'Unit': record['unit'],
                'Issue': f"Before and after values identical ({record['before_value']} {record['unit']}) - potential copy-paste error"
            })

        # Export single consolidated CSV for clinic follow-up
        if invalid_records:
            invalid_df = pd.DataFrame(invalid_records)
            csv_file = output_path / "data_quality_module4_invalid_values.csv"
            invalid_df.to_csv(csv_file, index=False)
            print(f"  CSV: {csv_file.name} ({len(invalid_df)} records for clinic review)")


def run_validity_analysis(data_file: str, output_dir: str = ".") -> DataValidity:
    """
    Run complete data validity analysis workflow.

    Args:
        data_file: Path to CSV data file
        output_dir: Directory for output files

    Returns:
        DataValidity object with calculated results
    """
    print("=" * 90)
    print("DATA QUALITY ANALYSIS - MODULE 4: DATA VALIDITY")
    print("=" * 90)

    # Load data
    print("\nLoading data...")
    loader = TransfusionDataLoader()
    loader.load_data(data_file, validate=False)

    # Calculate statistics
    analyzer = DataValidity(loader)
    analyzer.calculate_all()

    # Display tables
    (summary_table, demographics_table, lab_table, identical_table, mat_table) = analyzer.create_summary_tables()
    print("\n" + summary_table)
    print("\n" + demographics_table)
    print("\n" + lab_table)
    print("\n" + identical_table)
    print("\n" + mat_table)

    # Export results
    print("\nExporting results...")
    analyzer.export_results(output_dir)

    print("\nAnalysis complete!")
    return analyzer


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python3 data_quality_module4_validity.py <data_file.csv> <output_directory>")
        print("Example: python3 data_quality_module4_validity.py ../test_data_150patients.csv test_data_150patients")
        sys.exit(1)

    data_file = sys.argv[1]
    output_dir = sys.argv[2]

    analyzer = run_validity_analysis(data_file, output_dir=output_dir)
