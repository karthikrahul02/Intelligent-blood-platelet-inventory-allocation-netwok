"""
Data Quality Analysis: Module 1 - Completeness Analysis
========================================================

Analyzes completeness of medical staff-entered data across major sections:
- Biometrics (demographics)
- Treatment (product administration)
- Indication (treatment reasons)
- Follow-up (baseline measurements)

Calculates missingness rates per variable and per section for critical variables.

Author: Elina Nuerenberg-Goloub with Claude Sonnet 4.5 by Anthropic
Date: 2025-10-22
Revised on 2026-01-20 by Elina Nuerenberg-Goloub and Claude Opus 4.5
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple
from transfusion_data_loader import TransfusionDataLoader
from transfusion_registry_mapping import PRODUCT_MAPPING, json_sanitize
import json
from pathlib import Path


class DataQualityCompleteness:
    """
    Analyze data completeness for medical staff-entered data.

    Focus areas:
    - Demographics: Age, sex, weight, blood groups with Rh
    - Treatment: Product, dosage, unit, date, indication
    - Lab values: Paired pre/post measurements
    - Follow-up: Baseline measurements (physical capacity, CFS, diagnoses)
    """

    # Critical variables by section
    DEMOGRAPHICS_VARIABLES = {
        'Age (birth year)': 'X_541_0_1',
        'Sex': 'X_433_0_4',
        'Height (cm)': 'X_433_0_2',
        'Weight (kg)': 'X_433_0_3',
        'Blood group': 'X_433_0_17',
        'Rh factor': 'X_433_0_18'
    }

    TREATMENT_VARIABLES = {
        'Product type': 'X_433_7_746',
        'Dosage amount': 'X_433_7_22',
        'Dosage unit': 'X_433_7_734',
        'Administration date': 'X_433_7_11'
    }

    # Lab value pairs (before/after) with clinically relevant products
    LAB_VALUE_PAIRS = {
        'Hemoglobin': {
            'before': 'X_433_7_614',
            'after': 'X_433_7_615',
            'unit': 'g/dl',
            'relevant_products': ['1', '1.0'],  # Red blood cell concentrate (RBC)
            'product_name': 'Red blood cell concentrate (RBC)'
        },
        'Platelets': {
            'before': 'X_433_7_37',
            'after': 'X_433_7_587',
            'unit': '/µl',
            'relevant_products': ['3', '3.0'],  # Platelet concentrate (PC)
            'product_name': 'Platelet concentrate (PC)'
        },
        "Quick's test": {
            'before': 'X_433_7_374',
            'after': 'X_433_7_596',
            'unit': '%',
            'relevant_products': ['2', '2.0', '4', '4.0'],  # FFP and PPSB
            'product_name': 'FFP + PPSB'
        },
        'Fibrinogen (lab)': {
            'before': 'X_433_7_585',
            'after': 'X_433_7_586',
            'unit': 'mg/dl',
            'relevant_products': ['5', '5.0'],  # Fibrinogen product
            'product_name': 'Fibrinogen'
        },
        'Serum albumin': {
            'before': 'X_433_7_603',
            'after': 'X_433_7_591',
            'unit': 'g/dl',
            'relevant_products': ['7', '7.0'],  # Albumin
            'product_name': 'Albumin'
        },
        'Ferritin': {
            'before': 'X_433_7_736',
            'after': 'X_433_7_735',
            'unit': 'µg/l',
            'relevant_products': ['6', '6.0'],  # Iron i.v.
            'product_name': 'Iron i.v.'
        },
        'Transferrin saturation': {
            'before': 'X_433_7_589',
            'after': 'X_433_7_590',
            'unit': '%',
            'relevant_products': ['6', '6.0'],  # Iron i.v.
            'product_name': 'Iron i.v.'
        }
    }

    # Indication columns by product with their "other"/"Sonstiges" codes
    INDICATION_COLUMNS = {
        'Red blood cell concentrate (RBC)': {'column': 'X_433_7_593', 'other_code': '5'},
        'Fresh Frozen Plasma (FFP)': {'column': 'X_433_7_604', 'other_code': '9'},
        'Platelet concentrate (PC)': {'column': 'X_433_7_605', 'other_code': '8'},
        'PPSB': {'column': 'X_433_7_606', 'other_code': '9'},
        'Fibrinogen': {'column': 'X_433_7_607', 'other_code': '9'},
        'Albumin': {'column': 'X_433_7_610', 'other_code': '3'},
        'Antithrombin III (ATIII)': {'column': 'X_433_7_612', 'other_code': '5'}
    }

    # Follow-up baseline variables
    FOLLOWUP_BASELINE_VARIABLES = {
        'Physical capacity (MET)': 'X_433_0_32',
        'Clinical Frailty Scale (CFS)': 'X_433_0_25'
    }

    # MAT (Machine Autotransfusion) specific variables
    # Note: MAT has no indication column or lab values - it uses different documentation
    MAT_SPECIFIC_VARIABLES = {
        'Recovered RBC volume': 'X_433_7_749',
        'Volume of wound blood': 'X_433_7_747',
        'Recovered hematocrit %': 'X_433_7_750',
        'Wound blood hematocrit %': 'X_433_7_748'
    }

    # Use central mapping from transfusion_registry_mapping
    PRODUCT_MAPPING = PRODUCT_MAPPING

    def __init__(self, loader: TransfusionDataLoader):
        """
        Initialize completeness analyzer.

        Args:
            loader: TransfusionDataLoader with loaded data
        """
        self.loader = loader
        self.df = loader.df_clean.copy()
        self.mapper = loader.mapper
        self.results = {}

    def calculate_all(self) -> Dict[str, Any]:
        """
        Calculate all completeness statistics.

        Returns:
            Dictionary with all completeness results
        """
        print("\nCalculating data quality: Completeness analysis...")
        print("=" * 90)

        # Calculate completeness by section
        self.results = {
            'demographics': self._analyze_demographics_completeness(),
            'treatment': self._analyze_treatment_completeness(),
            'lab_values': self._analyze_lab_values_completeness(),
            'indication': self._analyze_indication_completeness(),
            'followup_baseline': self._analyze_followup_baseline_completeness(),
            'mat': self._analyze_mat_completeness(),
            'section_summary': {}
        }

        # Calculate overall section completeness
        self.results['section_summary'] = self._calculate_section_summary()

        print("\nCompleteness analysis complete")
        print("=" * 90)

        return self.results

    def _analyze_demographics_completeness(self) -> Dict[str, Any]:
        """Analyze completeness of demographic variables at patient level."""
        print("\n1. Analyzing demographics completeness...")

        # Get patient-level data (first record per patient)
        # EXISTENCE semantics, deliberately per-column: completeness asks
        # "is this field documented ANYWHERE for the patient", so the first
        # non-missing value per column is the intended reduction here (no
        # attribute combinations are formed from the result).
        df_patient = self.df.groupby('PID').first().reset_index()
        n_patients = len(df_patient)

        variable_completeness = {}

        for var_name, col_name in self.DEMOGRAPHICS_VARIABLES.items():
            if col_name not in df_patient.columns:
                variable_completeness[var_name] = {
                    'column': col_name,
                    'n_total': n_patients,
                    'n_present': 0,
                    'n_missing': n_patients,
                    'percent_complete': 0.0,
                    'percent_missing': 100.0,
                    'note': 'Column not found in data'
                }
                continue

            values = df_patient[col_name]
            n_present = values.notna().sum()
            n_missing = values.isna().sum()

            variable_completeness[var_name] = {
                'column': col_name,
                'n_total': int(n_patients),
                'n_present': int(n_present),
                'n_missing': int(n_missing),
                'percent_complete': float(n_present / n_patients * 100) if n_patients > 0 else 0.0,
                'percent_missing': float(n_missing / n_patients * 100) if n_patients > 0 else 0.0
            }

        return {
            'level': 'patient',
            'n_patients': int(n_patients),
            'variables': variable_completeness
        }

    def _analyze_treatment_completeness(self) -> Dict[str, Any]:
        """Analyze completeness of treatment variables at administration level.

        NOTE: Only analyzes records that are actual treatment records (have product type).
        Records without product type are likely follow-up-only or baseline records.
        """
        print("2. Analyzing treatment completeness...")

        # Filter to treatment records only (records with product type)
        product_col = 'X_433_7_746'
        df_treatment = self.df[self.df[product_col].notna()].copy()
        n_administrations = len(df_treatment)
        n_excluded = len(self.df) - n_administrations

        print(f"   Total records: {len(self.df)}")
        print(f"   Treatment records (with product type): {n_administrations}")
        print(f"   Non-treatment records (excluded): {n_excluded}")

        variable_completeness = {}

        # MAT (code 11) has no generic dosage fields by design — exclude those
        # administrations from the Dosage amount/unit denominators so dosage
        # completeness is not systematically deflated (module 2 applies the
        # same policy).
        product_norm = df_treatment[product_col].astype(str).str.replace(r'\.0$', '', regex=True)
        df_dosage_relevant = df_treatment[product_norm != '11']
        n_dosage_relevant = len(df_dosage_relevant)
        dosage_vars = {'Dosage amount', 'Dosage unit'}

        for var_name, col_name in self.TREATMENT_VARIABLES.items():
            df_denom = df_dosage_relevant if var_name in dosage_vars else df_treatment
            n_denom = n_dosage_relevant if var_name in dosage_vars else n_administrations

            if col_name not in df_denom.columns:
                variable_completeness[var_name] = {
                    'column': col_name,
                    'n_total': n_denom,
                    'n_present': 0,
                    'n_missing': n_denom,
                    'percent_complete': 0.0,
                    'percent_missing': 100.0,
                    'note': 'Column not found in data'
                }
                continue

            values = df_denom[col_name]
            n_present = values.notna().sum()
            n_missing = values.isna().sum()

            variable_completeness[var_name] = {
                'column': col_name,
                'n_total': int(n_denom),
                'n_present': int(n_present),
                'n_missing': int(n_missing),
                'percent_complete': float(n_present / n_denom * 100) if n_denom > 0 else 0.0,
                'percent_missing': float(n_missing / n_denom * 100) if n_denom > 0 else 0.0
            }
            if var_name in dosage_vars:
                variable_completeness[var_name]['note'] = 'MAT (code 11) administrations excluded from denominator'

        return {
            'level': 'administration (treatment records only)',
            'n_administrations': int(n_administrations),
            'n_total_records': int(len(self.df)),
            'n_non_treatment_records': int(n_excluded),
            'variables': variable_completeness
        }

    def _analyze_lab_values_completeness(self) -> Dict[str, Any]:
        """Analyze completeness of paired lab values per clinically relevant product.

        NOTE: Calculates completeness only for administrations of products where
        the lab test is clinically relevant (e.g., hemoglobin for EK only).
        """
        print("3. Analyzing lab values completeness (per relevant product)...")

        # Filter to treatment records only
        product_col = 'X_433_7_746'
        df_treatment = self.df[self.df[product_col].notna()].copy()
        df_treatment['product_str'] = (df_treatment[product_col].astype(str)
                                       .str.replace(r'\.0$', '', regex=True))

        lab_completeness = {}

        for lab_name, lab_cols in self.LAB_VALUE_PAIRS.items():
            before_col = lab_cols['before']
            after_col = lab_cols['after']
            relevant_products = lab_cols['relevant_products']
            product_name = lab_cols['product_name']

            # Filter to relevant products only
            df_relevant = df_treatment[df_treatment['product_str'].isin(relevant_products)].copy()
            n_relevant = len(df_relevant)

            # Check if columns exist
            before_exists = before_col in df_relevant.columns
            after_exists = after_col in df_relevant.columns

            if not before_exists or not after_exists:
                lab_completeness[lab_name] = {
                    'unit': lab_cols['unit'],
                    'relevant_for': product_name,
                    'before_column': before_col,
                    'after_column': after_col,
                    'n_relevant_administrations': n_relevant,
                    'before_present': 0,
                    'before_missing': n_relevant,
                    'after_present': 0,
                    'after_missing': n_relevant,
                    'both_present': 0,
                    'both_missing': n_relevant,
                    'only_before': 0,
                    'only_after': 0,
                    'percent_paired_complete': 0.0,
                    'note': f"Column not found: before={before_exists}, after={after_exists}"
                }
                continue

            if n_relevant == 0:
                lab_completeness[lab_name] = {
                    'unit': lab_cols['unit'],
                    'relevant_for': product_name,
                    'before_column': before_col,
                    'after_column': after_col,
                    'n_relevant_administrations': 0,
                    'before_present': 0,
                    'before_missing': 0,
                    'after_present': 0,
                    'after_missing': 0,
                    'both_present': 0,
                    'both_missing': 0,
                    'only_before': 0,
                    'only_after': 0,
                    'percent_paired_complete': 0.0,
                    'note': f"No administrations of {product_name} in dataset"
                }
                continue

            before_values = df_relevant[before_col]
            after_values = df_relevant[after_col]

            before_present = before_values.notna()
            after_present = after_values.notna()

            n_before = before_present.sum()
            n_after = after_present.sum()
            n_both = (before_present & after_present).sum()
            n_neither = (~before_present & ~after_present).sum()
            n_only_before = (before_present & ~after_present).sum()
            n_only_after = (~before_present & after_present).sum()

            lab_completeness[lab_name] = {
                'unit': lab_cols['unit'],
                'relevant_for': product_name,
                'before_column': before_col,
                'after_column': after_col,
                'n_relevant_administrations': int(n_relevant),
                'before_present': int(n_before),
                'before_missing': int(n_relevant - n_before),
                'after_present': int(n_after),
                'after_missing': int(n_relevant - n_after),
                'both_present': int(n_both),
                'both_missing': int(n_neither),
                'only_before': int(n_only_before),
                'only_after': int(n_only_after),
                'percent_paired_complete': float(n_both / n_relevant * 100) if n_relevant > 0 else 0.0,
                'percent_before_only': float(n_only_before / n_relevant * 100) if n_relevant > 0 else 0.0,
                'percent_after_only': float(n_only_after / n_relevant * 100) if n_relevant > 0 else 0.0
            }

        return {
            'level': 'administration (per relevant product)',
            'note': 'Completeness calculated only for clinically relevant product-lab combinations',
            'lab_values': lab_completeness
        }

    def _analyze_indication_completeness(self) -> Dict[str, Any]:
        """
        Analyze completeness of indication field per product.

        Flags both missing indications and 'other' category as problematic.
        Note: Each product has a different code for 'other'/'Sonstiges'.
        """
        print("4. Analyzing indication completeness...")

        product_col = 'X_433_7_746'

        if product_col not in self.df.columns:
            return {
                'level': 'administration',
                'note': 'Product column not found',
                'products': {}
            }

        indication_completeness = {}

        # Analyze indication for each product that has administrations
        df_products = self.df[self.df[product_col].notna()].copy()
        df_products['product_str'] = (df_products[product_col].astype(str)
                                      .str.replace(r'\.0$', '', regex=True))

        for code, product_name in self.PRODUCT_MAPPING.items():
            if product_name not in self.INDICATION_COLUMNS:
                continue

            indication_info = self.INDICATION_COLUMNS[product_name]
            indication_col = indication_info['column']
            other_code = indication_info['other_code']

            # Filter to this product
            df_product = df_products[df_products['product_str'] == code]
            n_product_admin = len(df_product)

            if n_product_admin == 0:
                continue

            if indication_col not in df_product.columns:
                indication_completeness[product_name] = {
                    'indication_column': indication_col,
                    'n_administrations': int(n_product_admin),
                    'n_documented': 0,
                    'n_missing': int(n_product_admin),
                    'n_other': 0,
                    'n_problematic': int(n_product_admin),
                    'percent_documented': 0.0,
                    'percent_missing': 100.0,
                    'percent_other': 0.0,
                    'percent_problematic': 100.0,
                    'note': 'Indication column not found'
                }
                continue

            indications = df_product[indication_col]

            n_documented = indications.notna().sum()
            n_missing = indications.isna().sum()

            # Check for 'other'/'Sonstiges' category (product-specific code)
            indications_str = indications.astype(str)
            n_other = ((indications_str == other_code) | (indications_str == f'{other_code}.0')).sum()

            # Problematic = missing OR other
            n_problematic = n_missing + n_other

            indication_completeness[product_name] = {
                'indication_column': indication_col,
                'other_code': other_code,
                'n_administrations': int(n_product_admin),
                'n_documented': int(n_documented),
                'n_missing': int(n_missing),
                'n_other': int(n_other),
                'n_problematic': int(n_problematic),
                'percent_documented': float(n_documented / n_product_admin * 100) if n_product_admin > 0 else 0.0,
                'percent_missing': float(n_missing / n_product_admin * 100) if n_product_admin > 0 else 0.0,
                'percent_other': float(n_other / n_product_admin * 100) if n_product_admin > 0 else 0.0,
                'percent_problematic': float(n_problematic / n_product_admin * 100) if n_product_admin > 0 else 0.0
            }

        return {
            'level': 'administration',
            'note': "Problematic indications = missing OR coded as 'other'",
            'products': indication_completeness
        }

    def extract_problematic_indication_pids(self) -> pd.DataFrame:
        """
        Extract PIDs with problematic indications (missing or 'other').

        Returns DataFrame with columns:
        - PID: Patient ID
        - Admin_Date: Administration date
        - Product: Blood product name
        - Issue: 'Missing' or 'Other'
        - Indication_Code: Current indication code (for 'Other' issues)
        """
        print("Extracting problematic indication PIDs...")

        product_col = 'X_433_7_746'
        date_col = 'X_433_7_11'

        if product_col not in self.df.columns:
            return pd.DataFrame()

        problematic_records = []

        # Get administrations with product type
        df_products = self.df[self.df[product_col].notna()].copy()
        df_products['product_str'] = (df_products[product_col].astype(str)
                                      .str.replace(r'\.0$', '', regex=True))

        for code, product_name in self.PRODUCT_MAPPING.items():
            if product_name not in self.INDICATION_COLUMNS:
                continue

            indication_info = self.INDICATION_COLUMNS[product_name]
            indication_col = indication_info['column']
            other_code = indication_info['other_code']

            # Filter to this product
            df_product = df_products[df_products['product_str'] == code].copy()

            if len(df_product) == 0 or indication_col not in df_product.columns:
                continue

            # Find missing indications
            missing_mask = df_product[indication_col].isna()
            for idx, row in df_product[missing_mask].iterrows():
                problematic_records.append({
                    'PID': row['PID'],
                    'Admin_Date': row.get(date_col, ''),
                    'Product': product_name,
                    'Issue': 'Missing',
                    'Indication_Code': ''
                })

            # Find 'other' indications
            indications_str = df_product[indication_col].astype(str)
            other_mask = (indications_str == other_code) | (indications_str == f'{other_code}.0')
            for idx, row in df_product[other_mask].iterrows():
                problematic_records.append({
                    'PID': row['PID'],
                    'Admin_Date': row.get(date_col, ''),
                    'Product': product_name,
                    'Issue': 'Other',
                    'Indication_Code': other_code
                })

        df_problematic = pd.DataFrame(problematic_records)

        if len(df_problematic) > 0:
            # Sort by PID and date
            df_problematic = df_problematic.sort_values(['PID', 'Admin_Date']).reset_index(drop=True)

        print(f"  Found {len(df_problematic)} problematic indication records")
        return df_problematic

    def _analyze_followup_baseline_completeness(self) -> Dict[str, Any]:
        """Analyze completeness of baseline follow-up measurements at patient level."""
        print("5. Analyzing follow-up baseline completeness...")

        # Get patient-level data (first record per patient for baseline)
        # EXISTENCE semantics, deliberately per-column: completeness asks
        # "is this field documented ANYWHERE for the patient", so the first
        # non-missing value per column is the intended reduction here (no
        # attribute combinations are formed from the result).
        df_patient = self.df.groupby('PID').first().reset_index()
        n_patients = len(df_patient)

        variable_completeness = {}

        for var_name, col_name in self.FOLLOWUP_BASELINE_VARIABLES.items():
            if col_name not in df_patient.columns:
                variable_completeness[var_name] = {
                    'column': col_name,
                    'n_total': n_patients,
                    'n_present': 0,
                    'n_missing': n_patients,
                    'percent_complete': 0.0,
                    'percent_missing': 100.0,
                    'note': 'Column not found in data'
                }
                continue

            values = df_patient[col_name]
            n_present = values.notna().sum()
            n_missing = values.isna().sum()

            variable_completeness[var_name] = {
                'column': col_name,
                'n_total': int(n_patients),
                'n_present': int(n_present),
                'n_missing': int(n_missing),
                'percent_complete': float(n_present / n_patients * 100) if n_patients > 0 else 0.0,
                'percent_missing': float(n_missing / n_patients * 100) if n_patients > 0 else 0.0
            }

        return {
            'level': 'patient',
            'n_patients': int(n_patients),
            'variables': variable_completeness
        }

    def _analyze_mat_completeness(self) -> Dict[str, Any]:
        """
        Analyze completeness of MAT-specific variables at administration level.

        NOTE: MAT (Machine Autotransfusion, code 11) has no indication column or lab values.
        Instead, it has specific documentation fields for blood recovery during surgery.
        """
        print("6. Analyzing MAT (Machine Autotransfusion) completeness...")

        # Filter to MAT administrations only (product code 11)
        product_col = 'X_433_7_746'
        df_mat = self.df[self.df[product_col].astype(str).isin(['11', '11.0'])].copy()
        n_mat_administrations = len(df_mat)

        print(f"   Total MAT administrations: {n_mat_administrations}")

        if n_mat_administrations == 0:
            return {
                'level': 'administration (MAT only)',
                'n_administrations': 0,
                'variables': {},
                'note': 'No MAT administrations found in dataset'
            }

        variable_completeness = {}

        for var_name, col_name in self.MAT_SPECIFIC_VARIABLES.items():
            if col_name not in df_mat.columns:
                variable_completeness[var_name] = {
                    'column': col_name,
                    'n_total': n_mat_administrations,
                    'n_present': 0,
                    'n_missing': n_mat_administrations,
                    'percent_complete': 0.0,
                    'percent_missing': 100.0,
                    'note': 'Column not found in data'
                }
                continue

            values = df_mat[col_name]
            n_present = values.notna().sum()
            n_missing = values.isna().sum()

            variable_completeness[var_name] = {
                'column': col_name,
                'n_total': int(n_mat_administrations),
                'n_present': int(n_present),
                'n_missing': int(n_missing),
                'percent_complete': float(n_present / n_mat_administrations * 100) if n_mat_administrations > 0 else 0.0,
                'percent_missing': float(n_missing / n_mat_administrations * 100) if n_mat_administrations > 0 else 0.0
            }

        return {
            'level': 'administration (MAT only)',
            'n_administrations': int(n_mat_administrations),
            'variables': variable_completeness,
            'note': 'MAT has no indication column or lab values - uses specific blood recovery documentation'
        }

    def _calculate_section_summary(self) -> Dict[str, Any]:
        """Calculate overall completeness rate per major section."""
        print("7. Calculating section summary...")

        summary = {}

        # Demographics section
        if 'demographics' in self.results:
            demo = self.results['demographics']
            variables = demo['variables']
            if variables:
                avg_completeness = np.mean([v['percent_complete'] for v in variables.values()])
                n_variables = len(variables)
                n_complete_vars = sum(1 for v in variables.values() if v['percent_complete'] == 100.0)

                summary['Demographics'] = {
                    'n_variables': int(n_variables),
                    'n_fully_complete': int(n_complete_vars),
                    'avg_completeness': float(avg_completeness),
                    'level': 'patient'
                }

        # Treatment section
        if 'treatment' in self.results:
            treat = self.results['treatment']
            variables = treat['variables']
            if variables:
                avg_completeness = np.mean([v['percent_complete'] for v in variables.values()])
                n_variables = len(variables)
                n_complete_vars = sum(1 for v in variables.values() if v['percent_complete'] == 100.0)

                summary['Treatment'] = {
                    'n_variables': int(n_variables),
                    'n_fully_complete': int(n_complete_vars),
                    'avg_completeness': float(avg_completeness),
                    'level': 'administration'
                }

        # Lab values section (use paired completeness per relevant product)
        if 'lab_values' in self.results:
            lab = self.results['lab_values']
            lab_values = lab['lab_values']
            if lab_values:
                # Only include lab tests that have relevant administrations
                relevant_labs = {k: v for k, v in lab_values.items() if v['n_relevant_administrations'] > 0}

                if relevant_labs:
                    avg_paired_completeness = np.mean([v['percent_paired_complete'] for v in relevant_labs.values()])
                    n_lab_tests = len(relevant_labs)
                    n_complete_labs = sum(1 for v in relevant_labs.values() if v['percent_paired_complete'] >= 90.0)

                    summary['Lab Values (Paired)'] = {
                        'n_variables': int(n_lab_tests),
                        'n_fully_complete': int(n_complete_labs),
                        'avg_completeness': float(avg_paired_completeness),
                        'level': 'administration (per relevant product)',
                        'note': 'Completeness = both pre and post values present for clinically relevant products'
                    }
                else:
                    summary['Lab Values (Paired)'] = {
                        'n_variables': 0,
                        'n_fully_complete': 0,
                        'avg_completeness': 0.0,
                        'level': 'administration (per relevant product)',
                        'note': 'No relevant product administrations found'
                    }

        # Indication section (use non-problematic rate)
        if 'indication' in self.results:
            ind = self.results['indication']
            products = ind.get('products', {})
            if products:
                # Calculate average non-problematic rate
                non_problematic_rates = [100 - v['percent_problematic'] for v in products.values()]
                avg_completeness = np.mean(non_problematic_rates)
                n_products = len(products)
                n_complete_products = sum(1 for v in products.values() if v['percent_problematic'] == 0.0)

                summary['Indication'] = {
                    'n_products': int(n_products),
                    'n_fully_complete': int(n_complete_products),
                    'avg_completeness': float(avg_completeness),
                    'level': 'administration',
                    'note': "Completeness = indication documented AND not coded as 'other'"
                }

        # Follow-up baseline section
        if 'followup_baseline' in self.results:
            fu = self.results['followup_baseline']
            variables = fu['variables']
            if variables:
                avg_completeness = np.mean([v['percent_complete'] for v in variables.values()])
                n_variables = len(variables)
                n_complete_vars = sum(1 for v in variables.values() if v['percent_complete'] == 100.0)

                summary['Follow-up Baseline'] = {
                    'n_variables': int(n_variables),
                    'n_fully_complete': int(n_complete_vars),
                    'avg_completeness': float(avg_completeness),
                    'level': 'patient'
                }

        # MAT section
        if 'mat' in self.results:
            mat = self.results['mat']
            if mat['n_administrations'] > 0:
                variables = mat['variables']
                if variables:
                    avg_completeness = np.mean([v['percent_complete'] for v in variables.values()])
                    n_variables = len(variables)
                    n_complete_vars = sum(1 for v in variables.values() if v['percent_complete'] == 100.0)

                    summary['MAT (Machine Autotransfusion)'] = {
                        'n_variables': int(n_variables),
                        'n_fully_complete': int(n_complete_vars),
                        'avg_completeness': float(avg_completeness),
                        'level': 'administration (MAT only)',
                        'note': mat['note']
                    }

        return summary

    def create_summary_tables(self) -> Tuple[str, str, str, str, str, str, str]:
        """
        Create formatted summary tables for all completeness analyses.

        Returns:
            Tuple of (demographics_table, treatment_table, lab_values_table,
                     indication_table, followup_table, mat_table, section_summary_table)
        """
        if not self.results:
            self.calculate_all()

        # Demographics table
        demo_lines = []
        demo_lines.append("=" * 90)
        demo_lines.append("DATA QUALITY - COMPLETENESS: DEMOGRAPHICS (Patient Level)")
        demo_lines.append("=" * 90)
        demo = self.results['demographics']
        demo_lines.append(f"\nTotal patients: {demo['n_patients']}")
        demo_lines.append("")
        demo_lines.append(f"{'Variable':<30} {'Complete':>10} {'Missing':>10} {'% Complete':>12}")
        demo_lines.append("-" * 90)
        for var_name, stats in demo['variables'].items():
            demo_lines.append(f"{var_name:<30} {stats['n_present']:>10} {stats['n_missing']:>10} {stats['percent_complete']:>11.1f}%")
        demo_lines.append("=" * 90)

        # Treatment table
        treat_lines = []
        treat_lines.append("=" * 90)
        treat_lines.append("DATA QUALITY - COMPLETENESS: TREATMENT (Administration Level)")
        treat_lines.append("=" * 90)
        treat = self.results['treatment']
        treat_lines.append(f"\nTotal administrations: {treat['n_administrations']}")
        treat_lines.append("")
        treat_lines.append(f"{'Variable':<30} {'Complete':>10} {'Missing':>10} {'% Complete':>12}")
        treat_lines.append("-" * 90)
        for var_name, stats in treat['variables'].items():
            treat_lines.append(f"{var_name:<30} {stats['n_present']:>10} {stats['n_missing']:>10} {stats['percent_complete']:>11.1f}%")
        treat_lines.append("=" * 90)

        # Lab values table
        lab_lines = []
        lab_lines.append("=" * 100)
        lab_lines.append("DATA QUALITY - COMPLETENESS: LAB VALUES - PAIRED MEASUREMENTS (Per Relevant Product)")
        lab_lines.append("=" * 100)
        lab = self.results['lab_values']
        lab_lines.append(f"\nNote: {lab['note']}")
        lab_lines.append("\nPaired completeness requires BOTH pre and post values present")
        lab_lines.append("")
        lab_lines.append(f"{'Lab Test':<25} {'Relevant For':<30} {'n':>6} {'Both':>6} {'% Paired':>10}")
        lab_lines.append("-" * 100)
        for lab_name, stats in lab['lab_values'].items():
            n_rel = stats['n_relevant_administrations']
            n_both = stats['both_present']
            pct = stats['percent_paired_complete']
            relevant_for = stats['relevant_for']

            if 'note' in stats and 'No administrations' in stats['note']:
                lab_lines.append(f"{lab_name:<25} {relevant_for:<30} {n_rel:>6} {n_both:>6} {'N/A':>10}")
            else:
                lab_lines.append(f"{lab_name:<25} {relevant_for:<30} {n_rel:>6} {n_both:>6} {pct:>9.1f}%")
        lab_lines.append("=" * 100)

        # Indication table
        ind_lines = []
        ind_lines.append("=" * 90)
        ind_lines.append("DATA QUALITY - COMPLETENESS: INDICATION (Administration Level)")
        ind_lines.append("=" * 90)
        ind = self.results['indication']
        ind_lines.append(f"\nNote: {ind['note']}")
        ind_lines.append("")
        ind_lines.append(f"{'Product':<30} {'n Admin':>8} {'Missing':>8} {'Other':>8} {'Problem':>8} {'% Problem':>10}")
        ind_lines.append("-" * 90)
        for product_name, stats in ind['products'].items():
            ind_lines.append(f"{product_name:<30} {stats['n_administrations']:>8} {stats['n_missing']:>8} {stats['n_other']:>8} {stats['n_problematic']:>8} {stats['percent_problematic']:>9.1f}%")
        ind_lines.append("=" * 90)

        # Follow-up baseline table
        fu_lines = []
        fu_lines.append("=" * 90)
        fu_lines.append("DATA QUALITY - COMPLETENESS: FOLLOW-UP BASELINE (Patient Level)")
        fu_lines.append("=" * 90)
        fu = self.results['followup_baseline']
        fu_lines.append(f"\nTotal patients: {fu['n_patients']}")
        fu_lines.append("")
        fu_lines.append(f"{'Variable':<40} {'Complete':>10} {'Missing':>10} {'% Complete':>12}")
        fu_lines.append("-" * 90)
        for var_name, stats in fu['variables'].items():
            fu_lines.append(f"{var_name:<40} {stats['n_present']:>10} {stats['n_missing']:>10} {stats['percent_complete']:>11.1f}%")
        fu_lines.append("=" * 90)

        # MAT table
        mat_lines = []
        mat_lines.append("=" * 90)
        mat_lines.append("DATA QUALITY - COMPLETENESS: MAT - MACHINE AUTOTRANSFUSION (Administration Level)")
        mat_lines.append("=" * 90)
        mat = self.results['mat']
        if mat['n_administrations'] > 0:
            mat_lines.append(f"\nTotal MAT administrations: {mat['n_administrations']}")
            mat_lines.append(f"\nNote: {mat['note']}")
            mat_lines.append("")
            mat_lines.append(f"{'Variable':<40} {'Complete':>10} {'Missing':>10} {'% Complete':>12}")
            mat_lines.append("-" * 90)
            for var_name, stats in mat['variables'].items():
                mat_lines.append(f"{var_name:<40} {stats['n_present']:>10} {stats['n_missing']:>10} {stats['percent_complete']:>11.1f}%")
        else:
            mat_lines.append(f"\nNote: {mat['note']}")
        mat_lines.append("=" * 90)

        # Section summary table
        summary_lines = []
        summary_lines.append("=" * 90)
        summary_lines.append("DATA QUALITY - COMPLETENESS: SECTION SUMMARY")
        summary_lines.append("=" * 90)
        summary_lines.append("")
        summary_lines.append(f"{'Section':<30} {'Level':>15} {'Avg Complete':>15} {'n Variables':>12}")
        summary_lines.append("-" * 90)
        for section_name, stats in self.results['section_summary'].items():
            level = stats['level']
            avg_complete = stats['avg_completeness']
            if 'n_products' in stats:
                n_items = stats['n_products']
                item_label = 'products'
            else:
                n_items = stats['n_variables']
                item_label = 'variables'
            summary_lines.append(f"{section_name:<30} {level:>15} {avg_complete:>14.1f}% {n_items:>9} {item_label}")
            if 'note' in stats:
                summary_lines.append(f"  Note: {stats['note']}")
        summary_lines.append("=" * 90)

        return (
            "\n".join(demo_lines),
            "\n".join(treat_lines),
            "\n".join(lab_lines),
            "\n".join(ind_lines),
            "\n".join(fu_lines),
            "\n".join(mat_lines),
            "\n".join(summary_lines)
        )

    def export_results(self, output_dir: str = ".") -> None:
        """
        Export completeness results to files in 'data quality reporting' subfolder.

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
        json_file = output_path / "data_quality_module1_completeness.json"
        with open(json_file, 'w') as f:
            json.dump(json_sanitize(self.results), f, indent=2, allow_nan=False)
        print(f"  JSON: {json_file.name}")

        # Export formatted tables
        (demo_table, treat_table, lab_table, ind_table, fu_table, mat_table, summary_table) = self.create_summary_tables()

        # Combined TXT report
        combined_file = output_path / "data_quality_module1_completeness.txt"
        with open(combined_file, 'w') as f:
            f.write(summary_table)
            f.write("\n\n\n")
            f.write(demo_table)
            f.write("\n\n\n")
            f.write(treat_table)
            f.write("\n\n\n")
            f.write(lab_table)
            f.write("\n\n\n")
            f.write(ind_table)
            f.write("\n\n\n")
            f.write(fu_table)
            f.write("\n\n\n")
            f.write(mat_table)
        print(f"  TXT: {combined_file.name}")

        # Export CSV tables for visualization
        self._export_csv_tables(output_path)

    def _export_csv_tables(self, output_path: Path) -> None:
        """Export data in CSV format for future visualizations."""
        # Variables CSV (Demographics, Treatment, Follow-up Baseline)
        variables_data = []

        # Demographics
        demo = self.results['demographics']
        for var_name, stats in demo['variables'].items():
            variables_data.append({
                'Section': 'Demographics',
                'Variable': var_name,
                'Column': stats['column'],
                'Level': 'patient',
                'n_Total': stats['n_total'],
                'n_Present': stats['n_present'],
                'n_Missing': stats['n_missing'],
                'Percent_Complete': stats['percent_complete'],
                'Percent_Missing': stats['percent_missing']
            })

        # Treatment
        treat = self.results['treatment']
        for var_name, stats in treat['variables'].items():
            variables_data.append({
                'Section': 'Treatment',
                'Variable': var_name,
                'Column': stats['column'],
                'Level': 'administration',
                'n_Total': stats['n_total'],
                'n_Present': stats['n_present'],
                'n_Missing': stats['n_missing'],
                'Percent_Complete': stats['percent_complete'],
                'Percent_Missing': stats['percent_missing']
            })

        # Follow-up baseline
        fu = self.results['followup_baseline']
        for var_name, stats in fu['variables'].items():
            variables_data.append({
                'Section': 'Follow-up Baseline',
                'Variable': var_name,
                'Column': stats['column'],
                'Level': 'patient',
                'n_Total': stats['n_total'],
                'n_Present': stats['n_present'],
                'n_Missing': stats['n_missing'],
                'Percent_Complete': stats['percent_complete'],
                'Percent_Missing': stats['percent_missing']
            })

        # MAT (if present)
        mat = self.results['mat']
        if mat['n_administrations'] > 0:
            for var_name, stats in mat['variables'].items():
                variables_data.append({
                    'Section': 'MAT (Machine Autotransfusion)',
                    'Variable': var_name,
                    'Column': stats['column'],
                    'Level': 'administration (MAT only)',
                    'n_Total': stats['n_total'],
                    'n_Present': stats['n_present'],
                    'n_Missing': stats['n_missing'],
                    'Percent_Complete': stats['percent_complete'],
                    'Percent_Missing': stats['percent_missing']
                })

        df_variables = pd.DataFrame(variables_data)
        csv_file = output_path / "data_quality_module1_completeness_variables.csv"
        df_variables.to_csv(csv_file, index=False)
        print(f"  CSV: {csv_file.name}")

        # Lab values CSV
        lab_data = []
        lab = self.results['lab_values']
        for lab_name, stats in lab['lab_values'].items():
            lab_data.append({
                'Lab_Test': lab_name,
                'Relevant_For': stats['relevant_for'],
                'Unit': stats['unit'],
                'Level': 'administration (per relevant product)',
                'n_Relevant_Administrations': stats['n_relevant_administrations'],
                'n_Both_Present': stats['both_present'],
                'n_Only_Before': stats['only_before'],
                'n_Only_After': stats['only_after'],
                'n_Both_Missing': stats['both_missing'],
                'Percent_Paired_Complete': stats['percent_paired_complete']
            })

        df_labs = pd.DataFrame(lab_data)
        csv_file = output_path / "data_quality_module1_completeness_lab_values.csv"
        df_labs.to_csv(csv_file, index=False)
        print(f"  CSV: {csv_file.name}")

        # Indication CSV
        ind_data = []
        ind = self.results['indication']
        for product_name, stats in ind['products'].items():
            ind_data.append({
                'Product': product_name,
                'Indication_Column': stats['indication_column'],
                'Other_Code': stats['other_code'],
                'Level': 'administration',
                'n_Administrations': stats['n_administrations'],
                'n_Documented': stats['n_documented'],
                'n_Missing': stats['n_missing'],
                'n_Other': stats['n_other'],
                'n_Problematic': stats['n_problematic'],
                'Percent_Problematic': stats['percent_problematic']
            })

        df_indication = pd.DataFrame(ind_data)
        csv_file = output_path / "data_quality_module1_completeness_indication.csv"
        df_indication.to_csv(csv_file, index=False)
        print(f"  CSV: {csv_file.name}")

        # Problematic indications PID extraction CSV
        df_problematic_indications = self.extract_problematic_indication_pids()
        if len(df_problematic_indications) > 0:
            csv_file = output_path / "data_quality_module1_problematic_indications.csv"
            df_problematic_indications.to_csv(csv_file, index=False)
            print(f"  CSV: {csv_file.name} ({len(df_problematic_indications)} records)")

        # Section summary CSV
        summary_data = []
        for section_name, stats in self.results['section_summary'].items():
            summary_data.append({
                'Section': section_name,
                'Level': stats['level'],
                'Average_Completeness': stats['avg_completeness'],
                'n_Variables': stats.get('n_variables', stats.get('n_products', 0)),
                'n_Fully_Complete': stats['n_fully_complete']
            })

        df_summary = pd.DataFrame(summary_data)
        csv_file = output_path / "data_quality_module1_completeness_summary.csv"
        df_summary.to_csv(csv_file, index=False)
        print(f"  CSV: {csv_file.name}")


def run_completeness_analysis(data_file: str, output_dir: str = ".") -> DataQualityCompleteness:
    """
    Run complete data quality completeness analysis workflow.

    Args:
        data_file: Path to CSV data file
        output_dir: Directory for output files

    Returns:
        DataQualityCompleteness object with calculated results
    """
    print("=" * 90)
    print("DATA QUALITY ANALYSIS - MODULE 1: COMPLETENESS")
    print("=" * 90)

    # Load data
    print("\nLoading data...")
    loader = TransfusionDataLoader()
    loader.load_data(data_file, validate=False)

    # Calculate completeness statistics
    completeness = DataQualityCompleteness(loader)
    completeness.calculate_all()

    # Display tables
    (demo_table, treat_table, lab_table, ind_table, fu_table, mat_table, summary_table) = completeness.create_summary_tables()
    print("\n" + summary_table)
    print("\n" + demo_table)
    print("\n" + treat_table)
    print("\n" + lab_table)
    print("\n" + ind_table)
    print("\n" + fu_table)
    print("\n" + mat_table)

    # Export results
    print("\nExporting results...")
    completeness.export_results(output_dir)

    print("\nAnalysis complete!")
    return completeness


if __name__ == "__main__":
    # Example usage
    completeness = run_completeness_analysis("../test_data_150patients.csv", output_dir="test_data_150patients")
