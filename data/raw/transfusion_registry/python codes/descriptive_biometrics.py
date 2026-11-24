"""
Descriptive Statistics: Biometric Properties
============================================

This module calculates comprehensive descriptive statistics for patient
biometric properties including age, gender, BMI, blood group, and Rh factor.

IMPORTANT: Patients are categorized into:
- Transfusion patients: Received at least one blood product
- Non-transfusion patients: No blood product administered (reported separately)

Main statistics are calculated only for transfusion patients.

Author: Elina Nuerenberg-Goloub with Claude Sonnet 4.5 by Anthropic
Date: 2025-10-15
Revised on 2026-01-22 by Elina Nuerenberg-Goloub and Claude Opus 4.5
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional
from pathlib import Path

from transfusion_data_loader import TransfusionDataLoader, select_patient_index_rows


class BiometricDescriptives:
    """
    Calculate and present descriptive statistics for patient biometric properties.

    Statistics include:
    - Total number of patients
    - Age (years): mean, SD, median, IQR, range
    - Gender distribution: frequencies and percentages
    - BMI (kg/m²): overall and by gender - mean, SD, median, IQR, range
    - Blood group distribution: frequencies and percentages
    - Rh factor distribution: frequencies and percentages
    """

    def __init__(self, loader: TransfusionDataLoader):
        """
        Initialize with a data loader instance.

        Parameters:
        -----------
        loader : TransfusionDataLoader
            Data loader with loaded data
        """
        self.loader = loader
        self.df = loader.df_clean
        self.mapper = loader.mapper

        # Product type column for identifying transfusions
        self.product_col = 'X_433_7_746'

        # Categorize patients into transfusion vs non-transfusion
        self._categorize_patients()

        # Create patient-level dataset (one row per patient)
        # Main dataset includes only TRANSFUSION patients
        self.df_patient = self._create_patient_level_dataset()

        # Create separate dataset for non-transfusion patients
        self.df_non_transfusion = self._create_non_transfusion_dataset()

        # Results storage
        self.results = {}

    def _categorize_patients(self):
        """
        Categorize patients into transfusion and non-transfusion groups.

        Transfusion patients: Have at least one record with a blood product
        Non-transfusion patients: Have no records with blood products
        """
        # Identify patients with at least one blood product administration
        if self.product_col in self.df.columns:
            patients_with_products = self.df[self.df[self.product_col].notna()]['PID'].unique()
            self.transfusion_pids = set(patients_with_products)
        else:
            # If product column doesn't exist, treat all as transfusion patients
            self.transfusion_pids = set(self.df['PID'].unique())

        # All patients
        all_pids = set(self.df['PID'].unique())

        # Non-transfusion patients
        self.non_transfusion_pids = all_pids - self.transfusion_pids

        # Store counts
        self.n_total_patients = len(all_pids)
        self.n_transfusion_patients = len(self.transfusion_pids)
        self.n_non_transfusion_patients = len(self.non_transfusion_pids)

    def _create_patient_level_dataset(self) -> pd.DataFrame:
        """
        Create patient-level dataset with one row per TRANSFUSION patient.

        Only includes patients who received at least one blood product.
        Patient characteristics (age, gender, BMI, blood group, Rh) are
        taken from ONE real documented row per patient (the row with the
        most complete basic data, earliest episode on ties).

        Returns:
        --------
        pd.DataFrame
            Patient-level dataset for transfusion patients only
        """
        # Filter to transfusion patients only
        df_transfusion = self.df[self.df['PID'].isin(self.transfusion_pids)].copy()

        # One REAL documented row per patient (most complete basic data,
        # earliest episode) - never a per-column composite of several rows
        df_patient = select_patient_index_rows(df_transfusion).reset_index(drop=True)

        return df_patient

    def _create_non_transfusion_dataset(self) -> pd.DataFrame:
        """
        Create dataset for non-transfusion patients.

        These are patients who have records but no blood product administered.

        Returns:
        --------
        pd.DataFrame
            Dataset for non-transfusion patients
        """
        if len(self.non_transfusion_pids) == 0:
            return pd.DataFrame()

        # Filter to non-transfusion patients
        df_non = self.df[self.df['PID'].isin(self.non_transfusion_pids)].copy()

        # One REAL documented row per patient (see _create_patient_level_dataset)
        df_patient = select_patient_index_rows(df_non).reset_index(drop=True)

        return df_patient

    def calculate_all(self) -> Dict:
        """
        Calculate all biometric descriptive statistics.

        Statistics are calculated for TRANSFUSION PATIENTS only.
        Non-transfusion patients are reported separately.

        Returns:
        --------
        dict
            Dictionary containing all statistical results
        """
        print("\nCalculating biometric descriptive statistics...")
        print("="*70)

        # 1. Patient categorization and totals
        self._calculate_total_patients()

        # 2. Age statistics (transfusion patients only)
        self._calculate_age_statistics()

        # 3. Gender distribution (transfusion patients only)
        self._calculate_gender_distribution()

        # 4. BMI statistics (transfusion patients only)
        self._calculate_bmi_statistics()

        # 5. Blood group distribution (transfusion patients only)
        self._calculate_blood_group_distribution()

        # 6. Rh factor distribution (transfusion patients only)
        self._calculate_rh_factor_distribution()

        # 7. Non-transfusion patients summary
        self._calculate_non_transfusion_summary()

        # 8. Conflicting time-invariant attributes (loader data-quality finding)
        self._report_attribute_conflicts()

        print("\nCalculations complete")
        print("="*70)

        return self.results

    def _report_attribute_conflicts(self):
        """
        Surface the loader's check for conflicting time-invariant patient
        attributes (sex, height, weight, year of birth). The patient-level
        statistics use the first documented value; any patient with more than
        one distinct value is itemized here so the conflict is visible.
        """
        conflicts = getattr(self.loader, 'patient_attribute_conflicts', [])
        self.results['patient_attribute_conflicts'] = {
            'n_patients': len({c['PID'] for c in conflicts}),
            'n_conflicts': len(conflicts),
            'conflicts': [
                {'PID': str(c['PID']), 'attribute': c['attribute'],
                 'values': list(c['values'])}
                for c in conflicts
            ],
            'note': ('time-invariant attributes with more than one distinct '
                     'documented value per patient; patient-level statistics '
                     'use the first documented value')
        }
        if conflicts:
            print(f"  NOTE: {len(conflicts)} conflicting time-invariant "
                  f"attribute entrie(s) across "
                  f"{self.results['patient_attribute_conflicts']['n_patients']} "
                  f"patient(s) - see patient_attribute_conflicts in the results")

    def _calculate_total_patients(self):
        """Calculate total number of unique patients with categorization."""
        n_total = self.n_total_patients
        n_transfusion = self.n_transfusion_patients
        n_non_transfusion = self.n_non_transfusion_patients
        n_records = len(self.df)

        # Count actual blood product administrations
        if self.product_col in self.df.columns:
            n_administrations = self.df[self.product_col].notna().sum()
        else:
            n_administrations = n_records

        self.results['total_patients'] = {
            'n_total_patients': n_total,
            'n_transfusion_patients': n_transfusion,
            'n_non_transfusion_patients': n_non_transfusion,
            'n_records': n_records,
            'n_administrations': n_administrations,
            'records_per_patient_mean': n_records / n_total if n_total > 0 else 0,
            'administrations_per_transfusion_patient': n_administrations / n_transfusion if n_transfusion > 0 else 0
        }

        print(f"\n1. Patient Overview")
        print(f"   Total patients in registry: {n_total}")
        print(f"   ├─ Transfusion patients: {n_transfusion} ({n_transfusion/n_total*100:.1f}%)")
        print(f"   │  (received at least one blood product)")
        print(f"   └─ Non-transfusion patients: {n_non_transfusion} ({n_non_transfusion/n_total*100:.1f}%)")
        print(f"      (no blood product administered)")
        print(f"")
        print(f"   Total records: {n_records}")
        print(f"   Blood product administrations: {n_administrations}")
        print(f"   Mean administrations per transfusion patient: {n_administrations / n_transfusion:.1f}")
        print(f"")
        print(f"   NOTE: Statistics below calculated for TRANSFUSION PATIENTS ONLY (n={n_transfusion})")

    def _calculate_age_statistics(self):
        """Calculate age statistics at patient level."""
        # Calculate age from birth year at patient level.
        # The loader state swap is guarded by try/finally so an exception in
        # calculate_age() cannot leave the shared loader pointing at the
        # patient-level frame (which would corrupt every later module).
        temp_df = self.loader.df_clean
        try:
            self.loader.df_clean = self.df_patient
            ages = self.loader.calculate_age()
        finally:
            self.loader.df_clean = temp_df

        # Remove missing values
        ages_valid = ages.dropna()

        if len(ages_valid) == 0:
            print("\n2. Age Statistics: No valid age data available")
            self.results['age'] = None
            return

        # Calculate overall statistics
        overall_stats = {
            'n': len(ages_valid),
            'n_missing': len(ages) - len(ages_valid),
            'mean': ages_valid.mean(),
            'sd': ages_valid.std(),
            'median': ages_valid.median(),
            'q25': ages_valid.quantile(0.25),
            'q75': ages_valid.quantile(0.75),
            'min': ages_valid.min(),
            'max': ages_valid.max(),
            'iqr': ages_valid.quantile(0.75) - ages_valid.quantile(0.25)
        }

        # Calculate age by gender
        gender_col = 'X_433_0_4'
        by_gender = {}

        if gender_col in self.df_patient.columns:
            gender = self.df_patient[gender_col]

            # Add ages to patient dataframe temporarily
            self.df_patient['_temp_age'] = ages

            gender_map = {'M': 'Male', 'F': 'Female'}

            for code, label in gender_map.items():
                gender_mask = (gender == code)
                ages_gender = self.df_patient.loc[gender_mask, '_temp_age'].dropna()

                if len(ages_gender) > 0:
                    by_gender[label] = {
                        'n': len(ages_gender),
                        'mean': ages_gender.mean(),
                        'sd': ages_gender.std(),
                        'median': ages_gender.median(),
                        'q25': ages_gender.quantile(0.25),
                        'q75': ages_gender.quantile(0.75),
                        'min': ages_gender.min(),
                        'max': ages_gender.max()
                    }

            # Clean up temp column
            self.df_patient.drop('_temp_age', axis=1, inplace=True)

        self.results['age'] = {
            'overall': overall_stats,
            'by_gender': by_gender
        }

        print(f"\n2. Age Statistics")
        print(f"   n: {overall_stats['n']} (missing: {overall_stats['n_missing']})")
        print(f"   Mean (SD): {overall_stats['mean']:.1f} ({overall_stats['sd']:.1f}) years")
        print(f"   Median [IQR]: {overall_stats['median']:.1f} [{overall_stats['q25']:.1f}-{overall_stats['q75']:.1f}] years")
        print(f"   Range: {overall_stats['min']:.0f}-{overall_stats['max']:.0f} years")

        if by_gender:
            print(f"\n   By Gender:")
            for label, stats in by_gender.items():
                print(f"     {label}: n={stats['n']}, Mean (SD): {stats['mean']:.1f} ({stats['sd']:.1f}), Median: {stats['median']:.1f}, Range: {stats['min']:.0f}-{stats['max']:.0f}")

    def _calculate_gender_distribution(self):
        """Calculate gender distribution at patient level."""
        gender_col = 'X_433_0_4'

        if gender_col not in self.df_patient.columns:
            print("\n3. Gender Distribution: Column not found")
            self.results['gender'] = None
            return

        # Get gender values from patient-level data
        gender_raw = self.df_patient[gender_col]

        # Create categories including missing
        gender_categories = {
            'M': 'Male',
            'F': 'Female',
            'I': 'Intersex/Diverse',
            'missing': 'Not provided'
        }

        # Count each category
        counts = {}
        total_with_data = 0

        for code, label in gender_categories.items():
            if code == 'missing':
                count = gender_raw.isna().sum()
            else:
                count = (gender_raw == code).sum()

            counts[label] = count
            if code != 'missing':
                total_with_data += count

        total = len(gender_raw)

        # Calculate percentages (of total with data for non-missing, of total for missing)
        results = {}
        for label, count in counts.items():
            if label == 'Not provided':
                pct = (count / total) * 100 if total > 0 else 0
            else:
                pct = (count / total_with_data) * 100 if total_with_data > 0 else 0

            results[label] = {
                'n': count,
                'percent': pct
            }

        results['total'] = total
        results['total_with_data'] = total_with_data

        self.results['gender'] = results

        print(f"\n3. Gender Distribution")
        print(f"   Total: {total}")
        for label in ['Male', 'Female', 'Intersex/Diverse', 'Not provided']:
            if label in results:
                n = results[label]['n']
                pct = results[label]['percent']
                print(f"   {label}: {n} ({pct:.1f}%)")

    def _calculate_bmi_statistics(self):
        """Calculate BMI statistics overall and by gender at patient level."""
        height_col = 'X_433_0_2'  # Height in cm
        weight_col = 'X_433_0_3'  # Weight in kg
        gender_col = 'X_433_0_4'

        # Check if columns exist
        if height_col not in self.df_patient.columns or weight_col not in self.df_patient.columns:
            print("\n4. BMI Statistics: Height or weight column not found")
            self.results['bmi'] = None
            return

        # Calculate BMI from patient-level data
        height_m = pd.to_numeric(self.df_patient[height_col], errors='coerce') / 100  # Convert cm to m
        weight_kg = pd.to_numeric(self.df_patient[weight_col], errors='coerce')

        bmi = weight_kg / (height_m ** 2)

        # Remove unrealistic BMI values (< 10 or > 60)
        bmi_valid = bmi[(bmi >= 10) & (bmi <= 60)]

        if len(bmi_valid) == 0:
            print("\n4. BMI Statistics: No valid BMI data available")
            self.results['bmi'] = None
            return

        # Overall BMI statistics
        overall_stats = self._calculate_continuous_stats(bmi_valid)

        results = {
            'overall': overall_stats,
            'by_gender': {}
        }

        # BMI by gender
        if gender_col in self.df_patient.columns:
            gender = self.df_patient[gender_col]

            gender_map = {
                'M': 'Male',
                'F': 'Female',
                'I': 'Intersex/Diverse'
            }

            for code, label in gender_map.items():
                gender_mask = (gender == code) & bmi_valid.notna()
                bmi_gender = bmi_valid[gender_mask]

                if len(bmi_gender) > 0:
                    gender_stats = self._calculate_continuous_stats(bmi_gender)
                    results['by_gender'][label] = gender_stats

        self.results['bmi'] = results

        # Print results
        print(f"\n4. BMI Statistics (kg/m²)")
        print(f"   Overall:")
        self._print_continuous_stats(overall_stats, indent="     ")

        if results['by_gender']:
            print(f"\n   By Gender:")
            for gender, stats in results['by_gender'].items():
                print(f"     {gender}:")
                self._print_continuous_stats(stats, indent="       ")

    def _calculate_blood_group_distribution(self):
        """Calculate blood group distribution at patient level."""
        blood_group_col = 'X_433_0_17'  # Patient blood group

        if blood_group_col not in self.df_patient.columns:
            print("\n5. Blood Group Distribution: Column not found")
            self.results['blood_group'] = None
            return

        # Get blood group values from patient-level data
        blood_group_raw = self.df_patient[blood_group_col]

        # Define categories
        blood_group_categories = {
            'A': 'A',
            'B': 'B',
            'AB': 'AB',
            '0': '0',
            'missing': 'Not provided'
        }

        # Count each category
        counts = {}
        total_with_data = 0

        for code, label in blood_group_categories.items():
            if code == 'missing':
                count = blood_group_raw.isna().sum()
            else:
                count = (blood_group_raw == code).sum()

            counts[label] = count
            if code != 'missing':
                total_with_data += count

        total = len(blood_group_raw)

        # Calculate percentages
        results = {}
        for label, count in counts.items():
            if label == 'Not provided':
                pct = (count / total) * 100 if total > 0 else 0
            else:
                pct = (count / total_with_data) * 100 if total_with_data > 0 else 0

            results[label] = {
                'n': count,
                'percent': pct
            }

        results['total'] = total
        results['total_with_data'] = total_with_data

        self.results['blood_group'] = results

        print(f"\n5. Blood Group Distribution")
        print(f"   Total: {total}")
        for label in ['A', 'B', 'AB', '0', 'Not provided']:
            if label in results:
                n = results[label]['n']
                pct = results[label]['percent']
                print(f"   {label}: {n} ({pct:.1f}%)")

    def _calculate_rh_factor_distribution(self):
        """Calculate Rh factor distribution at patient level."""
        rh_col = 'X_433_0_18'  # Patient Rh factor

        if rh_col not in self.df_patient.columns:
            print("\n6. Rh Factor Distribution: Column not found")
            self.results['rh_factor'] = None
            return

        # Get Rh factor values from patient-level data
        rh_raw = self.df_patient[rh_col]

        # Define categories based on the permitted values
        # 1=Rh+, 2=Rh-, 0=Unknown
        # Values may be stored as '1', '1.0', or numeric 1
        rh_categories = {
            '1': 'Positive',
            '2': 'Negative',
            '0': 'Unknown',
            'missing': 'Not provided'
        }

        # Count each category
        counts = {}
        total_with_data = 0

        for code, label in rh_categories.items():
            if code == 'missing':
                count = rh_raw.isna().sum()
            else:
                # Handle both '1' and '1.0' formats
                rh_str = rh_raw.astype(str)
                count = ((rh_str == code) | (rh_str == f"{code}.0")).sum()

            counts[label] = count
            if code != 'missing':
                total_with_data += count

        total = len(rh_raw)

        # Calculate percentages
        results = {}
        for label, count in counts.items():
            if label == 'Not provided':
                pct = (count / total) * 100 if total > 0 else 0
            else:
                pct = (count / total_with_data) * 100 if total_with_data > 0 else 0

            results[label] = {
                'n': count,
                'percent': pct
            }

        results['total'] = total
        results['total_with_data'] = total_with_data

        self.results['rh_factor'] = results

        print(f"\n6. Rh Factor Distribution")
        print(f"   Total: {total}")
        for label in ['Positive', 'Negative', 'Unknown', 'Not provided']:
            if label in results:
                n = results[label]['n']
                pct = results[label]['percent']
                print(f"   {label}: {n} ({pct:.1f}%)")

    def _calculate_non_transfusion_summary(self):
        """Calculate summary for patients with no blood product administration."""
        n_non = self.n_non_transfusion_patients

        if n_non == 0:
            print(f"\n7. Patients with No Administration")
            print(f"   None (all patients received blood products)")
            self.results['non_transfusion_patients'] = {'n': 0}
            return

        results = {
            'n': n_non,
            'percent_of_total': (n_non / self.n_total_patients * 100) if self.n_total_patients > 0 else 0,
            'data_availability': {}
        }

        # Check data availability for non-transfusion patients
        data_cols = {
            'X_541_0_1': 'Year of birth',
            'X_433_0_4': 'Sex',
            'X_433_0_2': 'Height',
            'X_433_0_3': 'Weight',
            'X_433_0_17': 'Blood group',
            'X_433_0_18': 'Rh factor',
        }

        print(f"\n7. Patients with No Administration (n={n_non})")
        print(f"   These patients have registry entries but no blood product was administered.")
        print(f"   They are EXCLUDED from the statistics above.")
        print(f"")
        print(f"   Data availability for non-transfusion patients:")

        for col, name in data_cols.items():
            if col in self.df_non_transfusion.columns:
                n_with_data = self.df_non_transfusion[col].notna().sum()
                pct = (n_with_data / n_non * 100) if n_non > 0 else 0
                results['data_availability'][name] = {
                    'n': n_with_data,
                    'percent': pct
                }
                print(f"   - {name}: {n_with_data}/{n_non} ({pct:.0f}%)")
            else:
                results['data_availability'][name] = {'n': 0, 'percent': 0}
                print(f"   - {name}: Column not found")

        # Calculate age for non-transfusion patients if possible.
        # Use the same reference as the transfusion cohort (episode-date year),
        # NOT the current run date — datetime.now() would drift on every rerun
        # and make the two cohorts' ages incomparable.
        birth_year_col = 'X_541_0_1'
        if birth_year_col in self.df_non_transfusion.columns:
            episode_years = pd.to_datetime(
                self.df_non_transfusion.get('Episode date'), errors='coerce'
            ).dt.year
            if episode_years.notna().any():
                reference_year = episode_years
            else:
                # Fallback: latest episode year in the full dataset
                reference_year = pd.to_datetime(
                    self.df['Episode date'], errors='coerce'
                ).dt.year.max()
            birth_years = pd.to_numeric(self.df_non_transfusion[birth_year_col], errors='coerce')
            ages = reference_year - birth_years
            ages_valid = ages[(ages >= 0) & (ages <= 120)].dropna()

            if len(ages_valid) > 0:
                results['age'] = {
                    'n': len(ages_valid),
                    'mean': float(ages_valid.mean()),
                    'median': float(ages_valid.median()),
                    'min': float(ages_valid.min()),
                    'max': float(ages_valid.max()),
                }
                print(f"")
                print(f"   Age (if available, n={len(ages_valid)}):")
                print(f"   - Mean: {ages_valid.mean():.1f} years")
                print(f"   - Median: {ages_valid.median():.1f} years")
                print(f"   - Range: {ages_valid.min():.0f}-{ages_valid.max():.0f} years")

        self.results['non_transfusion_patients'] = results

    def _calculate_continuous_stats(self, data: pd.Series) -> Dict:
        """
        Calculate standard statistics for continuous data.

        Parameters:
        -----------
        data : pd.Series
            Continuous data

        Returns:
        --------
        dict
            Statistics dictionary
        """
        return {
            'n': len(data),
            'mean': data.mean(),
            'sd': data.std(),
            'median': data.median(),
            'q25': data.quantile(0.25),
            'q75': data.quantile(0.75),
            'min': data.min(),
            'max': data.max(),
            'iqr': data.quantile(0.75) - data.quantile(0.25)
        }

    def _print_continuous_stats(self, stats: Dict, indent: str = ""):
        """Print continuous statistics in standard format."""
        print(f"{indent}n: {stats['n']}")
        print(f"{indent}Mean (SD): {stats['mean']:.1f} ({stats['sd']:.1f})")
        print(f"{indent}Median [IQR]: {stats['median']:.1f} [{stats['q25']:.1f}-{stats['q75']:.1f}]")
        print(f"{indent}Range: {stats['min']:.1f}-{stats['max']:.1f}")

    def create_summary_table(self) -> pd.DataFrame:
        """
        Create a publication-ready summary table of all biometric statistics.

        Returns:
        --------
        pd.DataFrame
            Formatted summary table
        """
        if not self.results:
            self.calculate_all()

        rows = []

        # Patient overview
        if 'total_patients' in self.results:
            tp = self.results['total_patients']
            rows.append({
                'Variable': 'PATIENT OVERVIEW',
                'Category': '',
                'Statistic': ''
            })
            rows.append({
                'Variable': 'Total patients in registry',
                'Category': '',
                'Statistic': f"n = {tp['n_total_patients']}"
            })
            rows.append({
                'Variable': '',
                'Category': 'Transfusion patients',
                'Statistic': f"{tp['n_transfusion_patients']} ({tp['n_transfusion_patients']/tp['n_total_patients']*100:.1f}%)"
            })
            rows.append({
                'Variable': '',
                'Category': 'Non-transfusion patients',
                'Statistic': f"{tp['n_non_transfusion_patients']} ({tp['n_non_transfusion_patients']/tp['n_total_patients']*100:.1f}%)"
            })
            rows.append({
                'Variable': 'Blood product administrations',
                'Category': '',
                'Statistic': f"n = {tp['n_administrations']}"
            })
            rows.append({
                'Variable': '',
                'Category': '',
                'Statistic': ''
            })
            rows.append({
                'Variable': 'TRANSFUSION PATIENTS (n=' + str(tp['n_transfusion_patients']) + ')',
                'Category': '',
                'Statistic': 'Statistics below for transfusion patients only'
            })

        # Age
        if self.results.get('age'):
            age = self.results['age']
            overall = age.get('overall', age)  # Fallback for backwards compatibility
            rows.append({
                'Variable': 'Age (years)',
                'Category': '',
                'Statistic': f"n = {overall['n']}"
            })
            rows.append({
                'Variable': '',
                'Category': 'Mean (SD)',
                'Statistic': f"{overall['mean']:.1f} ({overall['sd']:.1f})"
            })
            rows.append({
                'Variable': '',
                'Category': 'Median [IQR]',
                'Statistic': f"{overall['median']:.1f} [{overall['q25']:.1f}-{overall['q75']:.1f}]"
            })
            rows.append({
                'Variable': '',
                'Category': 'Range',
                'Statistic': f"{overall['min']:.0f}-{overall['max']:.0f}"
            })

            # Age by gender
            if age.get('by_gender'):
                for gender_label, gender_age in age['by_gender'].items():
                    rows.append({
                        'Variable': '',
                        'Category': f'By {gender_label}',
                        'Statistic': f"n = {gender_age['n']}"
                    })
                    rows.append({
                        'Variable': '',
                        'Category': '  Mean (SD)',
                        'Statistic': f"{gender_age['mean']:.1f} ({gender_age['sd']:.1f})"
                    })
                    rows.append({
                        'Variable': '',
                        'Category': '  Median [IQR]',
                        'Statistic': f"{gender_age['median']:.1f} [{gender_age['q25']:.1f}-{gender_age['q75']:.1f}]"
                    })
                    rows.append({
                        'Variable': '',
                        'Category': '  Range',
                        'Statistic': f"{gender_age['min']:.0f}-{gender_age['max']:.0f}"
                    })

        # Gender
        if self.results.get('gender'):
            gender = self.results['gender']
            rows.append({
                'Variable': 'Gender',
                'Category': '',
                'Statistic': f"n = {gender['total_with_data']}"
            })
            for label in ['Male', 'Female', 'Intersex/Diverse', 'Not provided']:
                if label in gender:
                    n = gender[label]['n']
                    pct = gender[label]['percent']
                    rows.append({
                        'Variable': '',
                        'Category': f'  {label}',
                        'Statistic': f"{n} ({pct:.1f}%)"
                    })

        # BMI overall
        if self.results.get('bmi') and self.results['bmi']['overall']:
            bmi = self.results['bmi']['overall']
            rows.append({
                'Variable': 'BMI (kg/m²)',
                'Category': 'Overall',
                'Statistic': f"n = {bmi['n']}"
            })
            rows.append({
                'Variable': '',
                'Category': '  Mean (SD)',
                'Statistic': f"{bmi['mean']:.1f} ({bmi['sd']:.1f})"
            })
            rows.append({
                'Variable': '',
                'Category': '  Median [IQR]',
                'Statistic': f"{bmi['median']:.1f} [{bmi['q25']:.1f}-{bmi['q75']:.1f}]"
            })
            rows.append({
                'Variable': '',
                'Category': '  Range',
                'Statistic': f"{bmi['min']:.1f}-{bmi['max']:.1f}"
            })

            # BMI by gender
            if self.results['bmi'].get('by_gender'):
                for gender_label, gender_bmi in self.results['bmi']['by_gender'].items():
                    rows.append({
                        'Variable': '',
                        'Category': f'By {gender_label}',
                        'Statistic': f"n = {gender_bmi['n']}"
                    })
                    rows.append({
                        'Variable': '',
                        'Category': f'  Mean (SD)',
                        'Statistic': f"{gender_bmi['mean']:.1f} ({gender_bmi['sd']:.1f})"
                    })
                    rows.append({
                        'Variable': '',
                        'Category': f'  Median [IQR]',
                        'Statistic': f"{gender_bmi['median']:.1f} [{gender_bmi['q25']:.1f}-{gender_bmi['q75']:.1f}]"
                    })
                    rows.append({
                        'Variable': '',
                        'Category': f'  Range',
                        'Statistic': f"{gender_bmi['min']:.1f}-{gender_bmi['max']:.1f}"
                    })

        # Blood group
        if self.results.get('blood_group'):
            bg = self.results['blood_group']
            rows.append({
                'Variable': 'Blood Group',
                'Category': '',
                'Statistic': f"n = {bg['total_with_data']}"
            })
            for label in ['A', 'B', 'AB', '0', 'Not provided']:
                if label in bg:
                    n = bg[label]['n']
                    pct = bg[label]['percent']
                    rows.append({
                        'Variable': '',
                        'Category': f'  {label}',
                        'Statistic': f"{n} ({pct:.1f}%)"
                    })

        # Rh factor
        if self.results.get('rh_factor'):
            rh = self.results['rh_factor']
            rows.append({
                'Variable': 'Rh Factor',
                'Category': '',
                'Statistic': f"n = {rh['total_with_data']}"
            })
            for label in ['Positive', 'Negative', 'Unknown', 'Not provided']:
                if label in rh:
                    n = rh[label]['n']
                    pct = rh[label]['percent']
                    rows.append({
                        'Variable': '',
                        'Category': f'  {label}',
                        'Statistic': f"{n} ({pct:.1f}%)"
                    })

        # Non-transfusion patients section
        if self.results.get('non_transfusion_patients'):
            ntp = self.results['non_transfusion_patients']
            if ntp['n'] > 0:
                rows.append({
                    'Variable': '',
                    'Category': '',
                    'Statistic': ''
                })
                rows.append({
                    'Variable': 'NON-TRANSFUSION PATIENTS',
                    'Category': '',
                    'Statistic': f"n = {ntp['n']}"
                })
                rows.append({
                    'Variable': '',
                    'Category': 'Note',
                    'Statistic': 'Patients with no blood product administered'
                })
                rows.append({
                    'Variable': '',
                    'Category': 'Note',
                    'Statistic': 'Excluded from statistics above'
                })

                # Age if available
                if 'age' in ntp:
                    age = ntp['age']
                    rows.append({
                        'Variable': 'Age (years)',
                        'Category': '',
                        'Statistic': f"n = {age['n']}"
                    })
                    rows.append({
                        'Variable': '',
                        'Category': 'Mean',
                        'Statistic': f"{age['mean']:.1f}"
                    })
                    rows.append({
                        'Variable': '',
                        'Category': 'Range',
                        'Statistic': f"{age['min']:.0f}-{age['max']:.0f}"
                    })

        # Conflicting time-invariant attributes (always reported, also when 0)
        pac = self.results.get('patient_attribute_conflicts')
        if pac is not None:
            rows.append({'Variable': '', 'Category': '', 'Statistic': ''})
            rows.append({
                'Variable': 'CONFLICTING BASIC-DATA ENTRIES',
                'Category': '',
                'Statistic': f"n = {pac['n_patients']} patient(s)"
            })
            for c in pac['conflicts']:
                rows.append({
                    'Variable': '',
                    'Category': f"  PID {c['PID']} - {c['attribute']}",
                    'Statistic': ' / '.join(c['values'])
                })
            rows.append({
                'Variable': '',
                'Category': 'Note',
                'Statistic': ('Patient-level statistics use the first '
                              'documented value')
            })

        return pd.DataFrame(rows)

    def export_results(self, output_dir: str = "."):
        """
        Export results to CSV and text files.

        Parameters:
        -----------
        output_dir : str
            Directory for output files
        """
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)

        # Create summary table
        summary_table = self.create_summary_table()

        # Export to CSV
        csv_file = output_path / "biometric_descriptives.csv"
        summary_table.to_csv(csv_file, index=False)
        print(f"\nSummary table exported to: {csv_file}")

        # Export to formatted text file
        txt_file = output_path / "biometric_descriptives.txt"
        with open(txt_file, 'w') as f:
            f.write("="*70 + "\n")
            f.write("DESCRIPTIVE STATISTICS: BIOMETRIC PROPERTIES\n")
            f.write("="*70 + "\n\n")

            # Write table
            f.write(summary_table.to_string(index=False))

            f.write("\n\n" + "="*70 + "\n")
            f.write("Legend:\n")
            f.write("SD = Standard Deviation\n")
            f.write("IQR = Interquartile Range (Q1-Q3)\n")
            f.write("BMI = Body Mass Index\n")
            f.write("="*70 + "\n")

        print(f"Formatted report exported to: {txt_file}")

        # Export detailed results as JSON
        import json
        json_file = output_path / "biometric_descriptives_detailed.json"

        # Convert numpy types to native Python for JSON serialization
        results_json = self._convert_for_json(self.results)

        with open(json_file, 'w') as f:
            json.dump(results_json, f, indent=2, allow_nan=False)

        print(f"Detailed results exported to: {json_file}")

    def _convert_for_json(self, obj):
        """Convert numpy types to native Python types for JSON serialization."""
        # Delegates to the central sanitizer: NaN/Infinity -> null BEFORE any
        # float conversion (a numpy nan converted to float first would slip
        # through as literal NaN in the JSON text), numpy scalars -> native.
        from transfusion_registry_mapping import json_sanitize
        return json_sanitize(obj)


def run_biometric_analysis(data_file: str, output_dir: str = ".") -> BiometricDescriptives:
    """
    Convenience function to run complete biometric analysis.

    Parameters:
    -----------
    data_file : str
        Path to data file
    output_dir : str
        Directory for output files

    Returns:
    --------
    BiometricDescriptives
        Analysis object with results
    """
    print("="*70)
    print("BIOMETRIC DESCRIPTIVE STATISTICS ANALYSIS")
    print("="*70)

    # Load data
    print("\nLoading data...")
    loader = TransfusionDataLoader()
    loader.load_data(data_file, validate=False)

    # Create analysis object
    bio = BiometricDescriptives(loader)

    # Calculate statistics
    bio.calculate_all()

    # Export results
    print("\n" + "="*70)
    print("Exporting results...")
    bio.export_results(output_dir)

    print("\n" + "="*70)
    print("ANALYSIS COMPLETE")
    print("="*70)

    return bio


# Main execution
if __name__ == "__main__":
    # Run analysis
    bio = run_biometric_analysis("../test_data_150patients.csv", output_dir=".")

    # Display summary table
    print("\n\nSUMMARY TABLE:")
    print("="*70)
    summary = bio.create_summary_table()
    print(summary.to_string(index=False))
