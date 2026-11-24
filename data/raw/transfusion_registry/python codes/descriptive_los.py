"""
Post-Intervention Time to Discharge — Descriptive Statistics Module

Calculates the interval from the surgical intervention date to the hospital
discharge date, in days. The registry export records no hospital admission
date, so this interval is the post-intervention time to discharge, NOT the
full hospital length of stay; all human-readable outputs label it
accordingly. One episode enters the statistic per patient: the earliest row
carrying a complete same-row date pair.

Key columns:
- Intervention date: X_433_0_8 (Date of surgical intervention)
- Discharge date: X_433_0_753 (Date of discharge from hospital)

Author: Elina Nuerenberg-Goloub with Claude Opus 4.5 by Anthropic
Date: 2026-02-09
"""

import pandas as pd
import numpy as np
import json

from transfusion_registry_mapping import json_sanitize
import os
from typing import Dict, Any, Optional, List
from datetime import datetime


class LOSDescriptives:
    """
    Calculates post-intervention time-to-discharge statistics for the
    transfusion registry.

    The interval is: discharge date - intervention date (in days), from the
    same episode row. It is not the full hospital length of stay, because
    the registry export records no admission date.

    Provides:
    - Coverage statistics (how many patients have both dates)
    - Overall time-to-discharge statistics (mean, median, IQR, range)
    - Gender-stratified statistics
    - Data quality filtering (implausible values excluded), with intervals
      over the 365-day screening threshold listed individually and a
      sensitivity analysis with and without the threshold
    """

    # Column mappings
    INTERVENTION_DATE_COL = 'X_433_0_8'
    DISCHARGE_DATE_COL = 'X_433_0_753'

    # Data quality thresholds. The internal variable names keep the LOS
    # abbreviation for continuity; all human-readable output labels the
    # measure as post-intervention time to discharge.
    MIN_LOS_DAYS = 0      # Same-day discharge is valid
    MAX_LOS_DAYS = 365    # Screening threshold: intervals > 1 year are excluded
                          # from the primary statistic, listed individually, and
                          # analyzed with/without the threshold (sensitivity)

    def __init__(self, loader):
        """
        Initialize with a TransfusionDataLoader instance.

        Args:
            loader: TransfusionDataLoader with loaded data
        """
        self.loader = loader
        self.df = loader.df_clean
        self.results = {}
        self.los_data = None  # Will hold patient-level LOS data

    def _parse_dates(self) -> pd.DataFrame:
        """
        Parse intervention and discharge dates and calculate LOS.

        Returns:
            DataFrame with patient-level LOS data
        """
        # Get unique patients with their intervention and discharge dates.
        # IMPORTANT: intervention and discharge must come from the SAME row —
        # groupby('PID').first() takes the first non-null value per column
        # independently, which can pair an intervention date from one episode
        # with a discharge date from a different episode. We therefore parse
        # dates row-wise, compute LOS per row, and only then reduce to one
        # row per patient (preferring the earliest row with a complete pair).
        df_rows = self.df.copy()
        df_rows['intervention_date'] = pd.to_datetime(
            df_rows[self.INTERVENTION_DATE_COL],
            errors='coerce'
        )
        df_rows['discharge_date'] = pd.to_datetime(
            df_rows[self.DISCHARGE_DATE_COL],
            errors='coerce'
        )
        df_rows['los_days'] = (
            df_rows['discharge_date'] - df_rows['intervention_date']
        ).dt.days

        # Rank rows per patient: complete same-row date pairs first, then rows
        # with any date, then the rest; within a rank keep chronological order.
        df_rows['_has_pair'] = df_rows['intervention_date'].notna() & df_rows['discharge_date'].notna()
        df_rows['_has_any'] = df_rows['intervention_date'].notna() | df_rows['discharge_date'].notna()
        df_rows = df_rows.sort_values(
            ['PID', '_has_pair', '_has_any', 'intervention_date'],
            ascending=[True, False, False, True]
        )
        patient_df = df_rows.drop_duplicates(subset='PID', keep='first').reset_index(drop=True)
        patient_df = patient_df.drop(columns=['_has_pair', '_has_any'])

        # Add gender if available
        # X_433_0_4 is Sex: M=Male, F=Female (also handles 1=Male, 2=Female)
        if 'sex' in patient_df.columns:
            patient_df['gender'] = patient_df['sex'].map({
                'M': 'Male', 'F': 'Female',
                1: 'Male', 2: 'Female', '1': 'Male', '2': 'Female'
            })
        elif 'X_433_0_4' in patient_df.columns:
            patient_df['gender'] = patient_df['X_433_0_4'].map({
                'M': 'Male', 'F': 'Female',
                1: 'Male', 2: 'Female', '1': 'Male', '2': 'Female'
            })
        else:
            patient_df['gender'] = None

        return patient_df

    def calculate_coverage(self) -> Dict[str, Any]:
        """
        Calculate data coverage for LOS calculation.

        Returns:
            Dict with coverage statistics
        """
        patient_df = self._parse_dates()
        total_patients = len(patient_df)

        has_intervention = patient_df['intervention_date'].notna().sum()
        has_discharge = patient_df['discharge_date'].notna().sum()
        has_both = (
            patient_df['intervention_date'].notna() &
            patient_df['discharge_date'].notna()
        ).sum()

        # Valid LOS (both dates present and LOS is plausible)
        valid_los_mask = (
            patient_df['los_days'].notna() &
            (patient_df['los_days'] >= self.MIN_LOS_DAYS) &
            (patient_df['los_days'] <= self.MAX_LOS_DAYS)
        )
        valid_los = valid_los_mask.sum()

        # Check for implausible values
        negative_los = (patient_df['los_days'] < 0).sum()
        very_long_los = (patient_df['los_days'] > self.MAX_LOS_DAYS).sum()

        coverage = {
            'total_patients': int(total_patients),
            'intervention_date': {
                'column': self.INTERVENTION_DATE_COL,
                'documented': int(has_intervention),
                'missing': int(total_patients - has_intervention),
                'percent_documented': round(100 * has_intervention / total_patients, 1)
            },
            'discharge_date': {
                'column': self.DISCHARGE_DATE_COL,
                'documented': int(has_discharge),
                'missing': int(total_patients - has_discharge),
                'percent_documented': round(100 * has_discharge / total_patients, 1)
            },
            'los_calculable': {
                'both_dates_present': int(has_both),
                'percent_with_both': round(100 * has_both / total_patients, 1)
            },
            'valid_los': {
                'n': int(valid_los),
                'percent_of_total': round(100 * valid_los / total_patients, 1)
            },
            'data_quality': {
                'negative_los_excluded': int(negative_los),
                'very_long_los_excluded': int(very_long_los),
                'max_los_threshold_days': self.MAX_LOS_DAYS
            }
        }

        self.results['coverage'] = coverage
        return coverage

    def calculate_los_statistics(self) -> Dict[str, Any]:
        """
        Calculate overall LOS statistics.

        Returns:
            Dict with LOS statistics
        """
        patient_df = self._parse_dates()
        self.los_data = patient_df

        # Filter to valid LOS values
        valid_mask = (
            patient_df['los_days'].notna() &
            (patient_df['los_days'] >= self.MIN_LOS_DAYS) &
            (patient_df['los_days'] <= self.MAX_LOS_DAYS)
        )
        valid_los = patient_df.loc[valid_mask, 'los_days']

        if len(valid_los) == 0:
            stats = {
                'n': 0,
                'error': 'No valid LOS data available'
            }
        else:
            # Medians/quartiles can be half-days — keep one decimal, never truncate
            stats = {
                'n': int(len(valid_los)),
                'mean': round(float(valid_los.mean()), 1),
                'sd': round(float(valid_los.std()), 1),
                'median': round(float(valid_los.median()), 1),
                'q1': round(float(valid_los.quantile(0.25)), 1),
                'q3': round(float(valid_los.quantile(0.75)), 1),
                'iqr': f"{round(float(valid_los.quantile(0.25)), 1):g}-{round(float(valid_los.quantile(0.75)), 1):g}",
                'min': int(valid_los.min()),
                'max': int(valid_los.max()),
                'range': f"{int(valid_los.min())}-{int(valid_los.max())}"
            }

        self.results['overall'] = stats
        return stats

    def calculate_los_by_gender(self) -> Dict[str, Any]:
        """
        Calculate LOS statistics stratified by gender.

        Returns:
            Dict with gender-stratified LOS statistics
        """
        if self.los_data is None:
            self.calculate_los_statistics()

        patient_df = self.los_data

        # Filter to valid LOS values
        valid_mask = (
            patient_df['los_days'].notna() &
            (patient_df['los_days'] >= self.MIN_LOS_DAYS) &
            (patient_df['los_days'] <= self.MAX_LOS_DAYS)
        )
        valid_df = patient_df[valid_mask]

        by_gender = {}

        for gender in ['Male', 'Female']:
            gender_los = valid_df.loc[valid_df['gender'] == gender, 'los_days']

            if len(gender_los) == 0:
                by_gender[gender.lower()] = {
                    'n': 0,
                    'error': f'No valid LOS data for {gender}'
                }
            else:
                by_gender[gender.lower()] = {
                    'n': int(len(gender_los)),
                    'mean': round(float(gender_los.mean()), 1),
                    'sd': round(float(gender_los.std()), 1),
                    'median': round(float(gender_los.median()), 1),
                    'q1': round(float(gender_los.quantile(0.25)), 1),
                    'q3': round(float(gender_los.quantile(0.75)), 1),
                    'iqr': f"{round(float(gender_los.quantile(0.25)), 1):g}-{round(float(gender_los.quantile(0.75)), 1):g}",
                    'min': int(gender_los.min()),
                    'max': int(gender_los.max())
                }

        self.results['by_gender'] = by_gender
        return by_gender

    def calculate_los_distribution(self) -> Dict[str, Any]:
        """
        Calculate LOS distribution (categories).

        Returns:
            Dict with LOS distribution
        """
        if self.los_data is None:
            self.calculate_los_statistics()

        patient_df = self.los_data

        # Filter to valid LOS values
        valid_mask = (
            patient_df['los_days'].notna() &
            (patient_df['los_days'] >= self.MIN_LOS_DAYS) &
            (patient_df['los_days'] <= self.MAX_LOS_DAYS)
        )
        valid_los = patient_df.loc[valid_mask, 'los_days']

        if len(valid_los) == 0:
            distribution = {'error': 'No valid LOS data'}
        else:
            total = len(valid_los)
            distribution = {
                'same_day': {
                    'range': '0 days',
                    'n': int((valid_los == 0).sum()),
                    'percent': round(100 * (valid_los == 0).sum() / total, 1)
                },
                'short': {
                    'range': '1-5 days',
                    'n': int(((valid_los >= 1) & (valid_los <= 5)).sum()),
                    'percent': round(100 * ((valid_los >= 1) & (valid_los <= 5)).sum() / total, 1)
                },
                'typical': {
                    'range': '6-10 days',
                    'n': int(((valid_los >= 6) & (valid_los <= 10)).sum()),
                    'percent': round(100 * ((valid_los >= 6) & (valid_los <= 10)).sum() / total, 1)
                },
                'extended': {
                    'range': '11-20 days',
                    'n': int(((valid_los >= 11) & (valid_los <= 20)).sum()),
                    'percent': round(100 * ((valid_los >= 11) & (valid_los <= 20)).sum() / total, 1)
                },
                'prolonged': {
                    'range': '>20 days',
                    'n': int((valid_los > 20).sum()),
                    'percent': round(100 * (valid_los > 20).sum() / total, 1)
                }
            }

        self.results['distribution'] = distribution
        return distribution

    def calculate_discharge_by_product_status(self) -> Dict[str, Any]:
        """
        Calculate discharge documentation by blood product status.

        Compares discharge documentation rates between patients who received
        blood products and those who did not.

        Returns:
            Dict with discharge stats by product status
        """
        # Get patient-level data
        # EXISTENCE semantics, deliberately per-column: this side table only
        # asks whether a discharge date and a product are documented ANYWHERE
        # for the patient - no attribute combinations are formed.
        patient_df = self.df.groupby('PID').first().reset_index()

        # Product type column
        product_col = 'X_433_7_746'

        # Find patients with any blood product documented
        patients_with_product = self.df[self.df[product_col].notna()]['PID'].unique()

        # Split patients
        with_product = patient_df[patient_df['PID'].isin(patients_with_product)]
        without_product = patient_df[~patient_df['PID'].isin(patients_with_product)]

        # Check discharge documentation
        discharge_col = self.DISCHARGE_DATE_COL

        with_prod_has_discharge = with_product[discharge_col].notna().sum()
        without_prod_has_discharge = without_product[discharge_col].notna().sum()

        by_product_status = {
            'with_products': {
                'n_patients': int(len(with_product)),
                'with_discharge': int(with_prod_has_discharge),
                'without_discharge': int(len(with_product) - with_prod_has_discharge),
                'percent_with_discharge': round(100 * with_prod_has_discharge / len(with_product), 1) if len(with_product) > 0 else 0
            },
            'without_products': {
                'n_patients': int(len(without_product)),
                'with_discharge': int(without_prod_has_discharge),
                'without_discharge': int(len(without_product) - without_prod_has_discharge),
                'percent_with_discharge': round(100 * without_prod_has_discharge / len(without_product), 1) if len(without_product) > 0 else 0
            }
        }

        self.results['by_product_status'] = by_product_status
        return by_product_status

    def calculate_threshold_sensitivity(self) -> Dict[str, Any]:
        """
        Sensitivity analysis for the 365-day screening threshold.

        Intervals above the threshold are listed individually, and the
        summary statistics are reported both with and without the threshold
        so the effect of the exclusion on the right tail is visible.

        Returns:
            Dict with the excluded values and both sets of statistics
        """
        if self.los_data is None:
            self.calculate_los_statistics()
        patient_df = self.los_data

        def _stats(series: pd.Series) -> Dict[str, Any]:
            if len(series) == 0:
                return {'n': 0, 'error': 'No valid data'}
            q1 = round(float(series.quantile(0.25)), 1)
            q3 = round(float(series.quantile(0.75)), 1)
            return {
                'n': int(len(series)),
                'mean': round(float(series.mean()), 1),
                'sd': round(float(series.std()), 1),
                'median': round(float(series.median()), 1),
                'q1': q1,
                'q3': q3,
                'iqr': f"{q1:g}-{q3:g}",
                'min': int(series.min()),
                'max': int(series.max()),
                'range': f"{int(series.min())}-{int(series.max())}"
            }

        base_mask = (
            patient_df['los_days'].notna() &
            (patient_df['los_days'] >= self.MIN_LOS_DAYS)
        )
        over_mask = base_mask & (patient_df['los_days'] > self.MAX_LOS_DAYS)
        over_df = patient_df.loc[over_mask, ['PID', 'los_days']]

        sensitivity = {
            'threshold_days': self.MAX_LOS_DAYS,
            'threshold_rationale': (
                'screening threshold: an interval of more than one year between '
                'intervention and discharge is rare and treated as a potential '
                'documentation error; such values are excluded from the primary '
                'statistic but listed here individually and included in the '
                'without-threshold statistics'
            ),
            'n_over_threshold': int(over_mask.sum()),
            'values_over_threshold': [
                {'patient_id': str(row['PID']), 'days': int(row['los_days'])}
                for _, row in over_df.iterrows()
            ],
            'with_threshold': _stats(
                patient_df.loc[base_mask & (patient_df['los_days'] <= self.MAX_LOS_DAYS), 'los_days']
            ),
            'without_threshold': _stats(patient_df.loc[base_mask, 'los_days'])
        }

        self.results['threshold_sensitivity'] = sensitivity
        return sensitivity

    def calculate_all(self) -> Dict[str, Any]:
        """
        Calculate all time-to-discharge statistics.

        Returns:
            Complete results dictionary
        """
        self.calculate_coverage()
        self.calculate_los_statistics()
        self.calculate_los_by_gender()
        self.calculate_los_distribution()
        self.calculate_threshold_sensitivity()
        self.calculate_discharge_by_product_status()

        # Add metadata
        self.results['metadata'] = {
            'generated': datetime.now().isoformat(),
            'measure': (
                'post-intervention time to discharge (interventional-care date '
                'to discharge date; the registry export records no hospital '
                'admission date, so this is not the full hospital length of stay)'
            ),
            'episode_selection': (
                'one row per patient: the earliest row carrying a complete '
                'same-row intervention/discharge date pair'
            ),
            'total_patients': int(self.df['PID'].nunique()),
            'intervention_date_column': self.INTERVENTION_DATE_COL,
            'discharge_date_column': self.DISCHARGE_DATE_COL,
            'min_los_threshold': self.MIN_LOS_DAYS,
            'max_los_threshold': self.MAX_LOS_DAYS
        }

        return self.results

    def create_summary_table(self) -> str:
        """
        Create a formatted text summary table.

        Returns:
            Formatted string for display/export
        """
        lines = []
        lines.append("=" * 70)
        lines.append("POST-INTERVENTION TIME TO DISCHARGE")
        lines.append("=" * 70)
        lines.append("")
        lines.append("Measure: days from interventional care to hospital discharge.")
        lines.append("The registry export records no admission date; this interval is")
        lines.append("therefore NOT the full hospital length of stay.")
        lines.append("")
        lines.append(f"Total patients: {self.results['metadata']['total_patients']}")
        lines.append(f"Generated: {self.results['metadata']['generated']}")
        lines.append("")

        # Coverage section
        lines.append("-" * 70)
        lines.append("DATA COVERAGE")
        lines.append("-" * 70)
        lines.append("")

        cov = self.results['coverage']
        lines.append(f"Intervention date ({cov['intervention_date']['column']}):")
        lines.append(f"  Documented: {cov['intervention_date']['documented']}/{cov['total_patients']} ({cov['intervention_date']['percent_documented']}%)")
        lines.append("")

        lines.append(f"Discharge date ({cov['discharge_date']['column']}):")
        lines.append(f"  Documented: {cov['discharge_date']['documented']}/{cov['total_patients']} ({cov['discharge_date']['percent_documented']}%)")
        lines.append("")

        lines.append(f"Valid intervals calculable: {cov['valid_los']['n']}/{cov['total_patients']} ({cov['valid_los']['percent_of_total']}%)")

        if cov['data_quality']['negative_los_excluded'] > 0:
            lines.append(f"  (Excluded {cov['data_quality']['negative_los_excluded']} with a negative interval)")
        if cov['data_quality']['very_long_los_excluded'] > 0:
            lines.append(f"  (Excluded {cov['data_quality']['very_long_los_excluded']} with an interval > {cov['data_quality']['max_los_threshold_days']} days — see sensitivity section)")
        lines.append("")

        # Overall statistics
        lines.append("-" * 70)
        lines.append("OVERALL TIME-TO-DISCHARGE STATISTICS")
        lines.append("-" * 70)
        lines.append("")

        overall = self.results['overall']
        if 'error' in overall:
            lines.append(f"  {overall['error']}")
        else:
            lines.append(f"  N = {overall['n']} patients")
            lines.append(f"  Mean: {overall['mean']} days (SD {overall['sd']})")
            lines.append(f"  Median: {overall['median']} days [IQR {overall['iqr']}]")
            lines.append(f"  Range: {overall['range']} days")
        lines.append("")

        # By gender
        lines.append("-" * 70)
        lines.append("TIME TO DISCHARGE BY GENDER")
        lines.append("-" * 70)
        lines.append("")

        by_gender = self.results['by_gender']
        for gender in ['male', 'female']:
            gender_label = gender.capitalize()
            data = by_gender.get(gender, {})

            if 'error' in data:
                lines.append(f"  {gender_label}: {data['error']}")
            elif data.get('n', 0) > 0:
                lines.append(f"  {gender_label} (n={data['n']}):")
                lines.append(f"    Mean: {data['mean']} days (SD {data['sd']})")
                lines.append(f"    Median: {data['median']} days [IQR {data['iqr']}]")
            lines.append("")

        # Distribution
        lines.append("-" * 70)
        lines.append("TIME-TO-DISCHARGE DISTRIBUTION")
        lines.append("-" * 70)
        lines.append("")

        dist = self.results['distribution']
        if 'error' not in dist:
            lines.append(f"  {'Category':<20} {'Range':<15} {'N':>8} {'%':>8}")
            lines.append(f"  {'-'*20} {'-'*15} {'-'*8} {'-'*8}")

            for cat_key, cat_data in dist.items():
                cat_name = cat_key.replace('_', ' ').title()
                lines.append(f"  {cat_name:<20} {cat_data['range']:<15} {cat_data['n']:>8} {cat_data['percent']:>7.1f}%")
        lines.append("")

        # Threshold sensitivity
        lines.append("-" * 70)
        lines.append("SENSITIVITY: 365-DAY SCREENING THRESHOLD")
        lines.append("-" * 70)
        lines.append("")

        sens = self.results.get('threshold_sensitivity', {})
        if sens:
            lines.append(f"  Intervals over {sens['threshold_days']} days: n = {sens['n_over_threshold']}")
            for item in sens['values_over_threshold']:
                lines.append(f"    Patient {item['patient_id']}: {item['days']} days")
            lines.append("")
            for label, key in (("With threshold", 'with_threshold'),
                               ("Without threshold", 'without_threshold')):
                s = sens[key]
                if s.get('n', 0) > 0:
                    lines.append(f"  {label} (n={s['n']}): mean {s['mean']} (SD {s['sd']}), "
                                 f"median {s['median']} [IQR {s['iqr']}], range {s['range']}")
                else:
                    lines.append(f"  {label}: no valid data")
        lines.append("")

        # Discharge by product status
        lines.append("-" * 70)
        lines.append("DISCHARGE DOCUMENTATION BY PRODUCT STATUS")
        lines.append("-" * 70)
        lines.append("")

        by_prod = self.results.get('by_product_status', {})
        if by_prod:
            wp = by_prod.get('with_products', {})
            wop = by_prod.get('without_products', {})

            lines.append(f"  Patients WITH blood products (n={wp.get('n_patients', 0)}):")
            lines.append(f"    With discharge date: {wp.get('with_discharge', 0)} ({wp.get('percent_with_discharge', 0)}%)")
            lines.append(f"    Without discharge date: {wp.get('without_discharge', 0)}")
            lines.append("")
            lines.append(f"  Patients WITHOUT blood products (n={wop.get('n_patients', 0)}):")
            lines.append(f"    With discharge date: {wop.get('with_discharge', 0)} ({wop.get('percent_with_discharge', 0)}%)")
            lines.append(f"    Without discharge date: {wop.get('without_discharge', 0)}")
        lines.append("")

        return "\n".join(lines)

    def export_results(self, output_dir: str) -> None:
        """
        Export results to files.

        Creates:
        - los_analysis.json (machine-readable)
        - los_analysis.txt (human-readable summary)
        - los_patient_data.csv (patient-level LOS data)

        Args:
            output_dir: Directory to write output files
        """
        # Create LOS subdirectory
        los_dir = os.path.join(output_dir, 'LOS')
        os.makedirs(los_dir, exist_ok=True)

        # Export JSON
        json_path = os.path.join(los_dir, 'los_analysis.json')
        with open(json_path, 'w') as f:
            json.dump(json_sanitize(self.results), f, indent=2, allow_nan=False)
        print(f"  Exported: {json_path}")

        # Export text summary
        txt_path = os.path.join(los_dir, 'los_analysis.txt')
        with open(txt_path, 'w') as f:
            f.write(self.create_summary_table())
        print(f"  Exported: {txt_path}")

        # Export patient-level CSV
        if self.los_data is not None:
            csv_path = os.path.join(los_dir, 'los_patient_data.csv')
            self._export_patient_csv(csv_path)
            print(f"  Exported: {csv_path}")

    def _export_patient_csv(self, filepath: str) -> None:
        """
        Export patient-level time-to-discharge data to CSV.
        """
        export_df = self.los_data[['PID', 'intervention_date', 'discharge_date', 'los_days', 'gender']].copy()
        export_df = export_df.rename(columns={
            'PID': 'patient_id',
            'los_days': 'days_intervention_to_discharge',
        })

        days = export_df['days_intervention_to_discharge']
        export_df['in_primary_analysis'] = (
            days.notna() &
            (days >= self.MIN_LOS_DAYS) &
            (days <= self.MAX_LOS_DAYS)
        )
        export_df['exclusion_reason'] = ''
        export_df.loc[days.isna(), 'exclusion_reason'] = 'dates incomplete'
        export_df.loc[days < self.MIN_LOS_DAYS, 'exclusion_reason'] = 'negative interval'
        export_df.loc[days > self.MAX_LOS_DAYS, 'exclusion_reason'] = (
            f'over {self.MAX_LOS_DAYS}-day screening threshold (reported in sensitivity analysis)'
        )

        export_df.to_csv(filepath, index=False, date_format='%Y-%m-%d')


def run_los_analysis(data_path: str, output_dir: str) -> LOSDescriptives:
    """
    Convenience function to run complete LOS analysis.

    Args:
        data_path: Path to CSV data file
        output_dir: Directory for output files

    Returns:
        LOSDescriptives instance with results
    """
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from transfusion_data_loader import TransfusionDataLoader

    print(f"\nRunning post-intervention time-to-discharge analysis...")
    print(f"  Data: {data_path}")
    print(f"  Output: {output_dir}")

    # Load data
    loader = TransfusionDataLoader()
    loader.load_data(data_path)

    # Create analysis
    los = LOSDescriptives(loader)
    results = los.calculate_all()

    # Display summary
    print("\n" + los.create_summary_table())

    # Export
    print("\nExporting results...")
    los.export_results(output_dir)

    print("\nTime-to-discharge analysis complete.")
    print(f"Results saved to: {os.path.join(output_dir, 'LOS')}/")

    return los
