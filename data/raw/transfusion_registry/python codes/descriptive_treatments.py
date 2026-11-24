"""
Descriptive Treatment Statistics Module

Calculates comprehensive descriptive statistics for haematologic treatment details
at both administration level and patient level.

Author: Elina Nuerenberg-Goloub with Claude Sonnet 4.5 by Anthropic
Date: 2025-10-15
Revised on 2026-01-27 by Elina Nuerenberg-Goloub and Claude Opus 4.5
Revised on 2026-01-27: Added weight-adjusted dosage (dose/kg) calculation
Revised on 2026-02-04: Replaced dose/kg with dose/L EBV (Nadler) for RBC and FFP
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List, Tuple
from transfusion_data_loader import TransfusionDataLoader, select_patient_index_rows
from transfusion_registry_mapping import TransfusionRegistryMapper, PRODUCT_MAPPING, UNIT_MAPPING
import json
import math
from pathlib import Path


def _json_sanitize(obj):
    """RFC 8259 conformance - delegates to the central sanitizer."""
    from transfusion_registry_mapping import json_sanitize
    return json_sanitize(obj)


class TreatmentDescriptives:
    """
    Calculate descriptive statistics for treatment details.

    Calculates statistics at two levels:
    - Administration level: All product administrations (records)
    - Patient level: Aggregated by patient
    """

    # Use central mappings from transfusion_registry_mapping
    PRODUCT_MAPPING = PRODUCT_MAPPING
    UNIT_MAPPING = UNIT_MAPPING

    # Statistical minima for stratified cells (predefined; distinct from any
    # publication-level privacy suppression, which is applied when results are
    # reported, not in these closed-environment outputs). Cells below the
    # minimum are not summarized but are listed with their n, status, and
    # reason in 'suppressed_cells'.
    MIN_N_DOSAGE_STATS = 3
    MIN_N_LAB_STATS = 5

    # Lab value columns (before/after pairs)
    LAB_COLUMNS = {
        'Hemoglobin': {
            'before': 'X_433_7_614',
            'after': 'X_433_7_615',
            'unit': 'g/dl',
            'normal_range': 'M: 13.5-17.5, F: 12-16'
        },
        'Platelets': {
            'before': 'X_433_7_37',
            'after': 'X_433_7_587',
            'unit': '/µl',
            'normal_range': '150,000-400,000'
        },
        "Quick's test": {
            'before': 'X_433_7_374',
            'after': 'X_433_7_596',
            'unit': '%',
            'normal_range': '70-120'
        },
        'Fibrinogen': {
            'before': 'X_433_7_585',
            'after': 'X_433_7_586',
            'unit': 'mg/dl',
            'normal_range': '200-400'
        },
        'Serum albumin': {
            'before': 'X_433_7_603',
            'after': 'X_433_7_591',
            'unit': 'g/dl',
            'normal_range': '3.5-5.0'
        },
        'Ferritin': {
            'before': 'X_433_7_736',
            'after': 'X_433_7_735',
            'unit': 'µg/l',
            'normal_range': 'M: 20-250, F: 10-120'
        },
        'Transferrin saturation': {
            'before': 'X_433_7_589',
            'after': 'X_433_7_590',
            'unit': '%',
            'normal_range': '20-50'
        },
        'Antithrombin activity': {
            'before': 'X_433_7_601',
            'after': 'X_433_7_602',
            'unit': '%',
            'normal_range': '80-120'
        }
    }

    # Indication columns by product
    INDICATION_COLUMNS = {
        'Red blood cell concentrate (RBC)': 'X_433_7_593',
        'Fresh Frozen Plasma (FFP)': 'X_433_7_604',
        'Platelet concentrate (PC)': 'X_433_7_605',
        'PPSB': 'X_433_7_606',
        'Fibrinogen': 'X_433_7_607',
        'Iron i.v.': 'X_433_7_608',
        'Albumin': 'X_433_7_610',
        'Antithrombin III (ATIII)': 'X_433_7_612'
    }

    # Primary lab value for each product (for data completeness table)
    PRODUCT_LAB_MAPPING = {
        'Red blood cell concentrate (RBC)': 'Hemoglobin',
        'Platelet concentrate (PC)': 'Platelets',
        'Fresh Frozen Plasma (FFP)': None,  # No lab values in eCRF for FFP
        'PPSB': "Quick's test",
        'Fibrinogen': 'Fibrinogen',
        'Albumin': 'Serum albumin',
        'Iron i.v.': 'Ferritin',
        'Machine Autotransfusion (Cell Salvage)': None,  # Separate table with specific parameters
        'Antithrombin III (ATIII)': 'Antithrombin activity',
        'EPO': None,
        'Oral iron': 'Ferritin'
    }

    # Autotransfusion (Cell Salvage) specific columns
    AUTOTRANSFUSION_COLUMNS = {
        'wound_blood_volume': {
            'column': 'X_433_7_747',
            'name': 'Volume of wound blood',
            'unit': 'ml'
        },
        'wound_blood_hematocrit': {
            'column': 'X_433_7_748',
            'name': 'Hematocrit of wound blood',
            'unit': '%'
        },
        'recovered_rbc_volume': {
            'column': 'X_433_7_749',
            'name': 'Recovered RBC volume',
            'unit': 'ml'
        },
        'recovered_hematocrit': {
            'column': 'X_433_7_750',
            'name': 'Recovered hematocrit',
            'unit': '%'
        }
    }

    # Blood type columns
    BLOOD_TYPE_COLUMNS = {
        'patient_abo': 'X_433_0_17',      # Blood group patient (A, B, AB, 0)
        'patient_rh': 'X_433_0_18',        # Rhesus factor patient (1=Rh+, 2=Rh-, 0=Unknown)
        'product_abo': 'X_433_7_19',       # Blood group of product (A, B, AB, 0)
        'product_rh': 'X_433_7_20'         # Rhesus factor of product (1=Rh+, 2=Rh-, 0=Unknown)
    }

    # Products where blood type compatibility is clinically important
    BLOOD_TYPE_PRODUCTS = {
        '1': 'Red blood cell concentrate (RBC)',      # ABO and Rh critical
        '2': 'Fresh Frozen Plasma (FFP)',             # ABO important (reverse rules)
        '3': 'Platelet concentrate (PC)'              # ABO preferred
    }

    # ABO compatibility rules: recipient ABO -> set of compatible donor/product ABO groups.
    # Registry code for blood group O is '0' (zero).
    # RBC: recipient isoagglutinins against donor RBC antigens matter (O = universal RBC donor).
    ABO_COMPAT_RBC = {
        '0': {'0'},
        'A': {'A', '0'},
        'B': {'B', '0'},
        'AB': {'A', 'B', 'AB', '0'},
    }
    # Plasma (FFP): rules are REVERSED - donor plasma antibodies against recipient
    # RBC antigens matter (AB = universal plasma donor, O recipients can receive any plasma).
    ABO_COMPAT_PLASMA = {
        '0': {'0', 'A', 'B', 'AB'},
        'A': {'A', 'AB'},
        'B': {'B', 'AB'},
        'AB': {'AB'},
    }
    # Product class used for ABO compatibility assessment per product name
    ABO_PRODUCT_CLASS = {
        'Red blood cell concentrate (RBC)': 'RBC',
        'Fresh Frozen Plasma (FFP)': 'plasma',
        'Platelet concentrate (PC)': 'PC',
    }
    # Products where RhD is checked (RhD-positive product to RhD-negative patient flagged)
    RHD_CHECK_PRODUCTS = {'Red blood cell concentrate (RBC)', 'Platelet concentrate (PC)'}

    @staticmethod
    def _normalize_code(code) -> str:
        """Normalize a registry code to canonical string form ('1.0' -> '1')."""
        s = str(code).strip()
        if s.endswith('.0'):
            s = s[:-2]
        return s

    @classmethod
    def _canonical_products(cls) -> Dict[str, str]:
        """PRODUCT_MAPPING deduplicated to canonical code form ('1.0' collapsed into '1')."""
        canonical = {}
        for code, name in cls.PRODUCT_MAPPING.items():
            canonical[cls._normalize_code(code)] = name
        return canonical

    @classmethod
    def _canonical_units(cls) -> Dict[str, str]:
        """UNIT_MAPPING deduplicated to canonical code form ('1.0' collapsed into '1')."""
        canonical = {}
        for code, name in cls.UNIT_MAPPING.items():
            canonical[cls._normalize_code(code)] = name
        return canonical

    @staticmethod
    def _normalize_abo(value) -> Optional[str]:
        """Normalize an ABO value to '0'/'A'/'B'/'AB'; returns None if not interpretable."""
        if pd.isna(value):
            return None
        s = str(value).strip().upper()
        if s.endswith('.0'):
            s = s[:-2]
        return s if s in ('0', 'A', 'B', 'AB') else None

    @staticmethod
    def _normalize_rh(value) -> Optional[str]:
        """Normalize an Rh code to '1' (Rh+) or '2' (Rh-); '0'/unknown -> None."""
        if pd.isna(value):
            return None
        s = str(value).strip()
        if s.endswith('.0'):
            s = s[:-2]
        return s if s in ('1', '2') else None

    @classmethod
    def _classify_abo_compatibility(cls, patient_abo, product_abo, product_class: str) -> str:
        """
        Classify the ABO status of a transfusion using real compatibility rules.

        Args:
            patient_abo: recipient ABO group (registry coding, O = '0')
            product_abo: product/donor ABO group
            product_class: 'RBC', 'plasma' or 'PC'

        Returns:
            'identical', 'compatible' (compatible but non-identical, RBC/plasma),
            'incompatible' (RBC/plasma), 'non_identical' (PC only - neutral category,
            ABO-identical PC is preferred but not mandatory), or 'not_assessable'.
        """
        p = cls._normalize_abo(patient_abo)
        d = cls._normalize_abo(product_abo)
        if p is None or d is None:
            return 'not_assessable'
        if p == d:
            return 'identical'
        if product_class == 'PC':
            # ABO-identical PC transfusion is preferred but not mandatory:
            # non-identical PC is reported as a neutral category, not a mismatch.
            return 'non_identical'
        rules = cls.ABO_COMPAT_RBC if product_class == 'RBC' else cls.ABO_COMPAT_PLASMA
        return 'compatible' if d in rules[p] else 'incompatible'

    def __init__(self, loader: TransfusionDataLoader):
        """
        Initialize treatment descriptives calculator.

        Args:
            loader: TransfusionDataLoader with loaded data
        """
        self.loader = loader
        self.df_all = loader.df_clean.copy()  # All records
        self.mapper = loader.mapper
        self.results = {}

        # Identify records with and without products
        product_col = 'X_433_7_746'
        self.df = self.df_all[self.df_all[product_col].notna()].copy()  # Only records with products
        self.df_no_product = self.df_all[self.df_all[product_col].isna()].copy()  # Records without products

    def calculate_all(self) -> Dict[str, Any]:
        """
        Calculate all treatment statistics.

        Returns:
            Dictionary with all calculated statistics
        """
        print("\nCalculating treatment statistics...")
        print(f"  Total records in dataset: {len(self.df_all)}")
        print(f"  Records with product (administrations): {len(self.df)}")
        print(f"  Records without product: {len(self.df_no_product)}")

        # Administration-level statistics (only records WITH products)
        self.results['administration_level'] = {
            'total_count': self._calculate_total_administrations(),
            'products': self._calculate_product_distribution(),
            'temporal': self._calculate_temporal_distribution(),
            'dosages': self._calculate_dosage_statistics(),
            'indications': self._calculate_indication_statistics(),
            'lab_values': self._calculate_lab_value_statistics()
        }

        # Patient-level statistics
        self.results['patient_level'] = {
            'patient_count': self._calculate_patient_statistics(),
            'products_per_patient': self._calculate_products_per_patient(),
            'administration_frequency': self._calculate_administration_frequency()
        }

        # Records without products (for manual review)
        self.results['records_without_product'] = self._get_records_without_product()

        # Comprehensive patient summary
        self.results['patient_summary'] = self._calculate_patient_summary()

        # Data completeness by product
        self.results['data_completeness'] = self._calculate_data_completeness_by_product()

        # Autotransfusion (Cell Salvage) statistics
        self.results['autotransfusion'] = self._calculate_autotransfusion_statistics()

        # Blood type documentation and compatibility
        self.results['blood_type'] = self._calculate_blood_type_statistics()

        # Gender-stratified statistics
        self.results['by_gender'] = self._calculate_gender_stratified_statistics()

        print("Treatment statistics calculated successfully")
        return self.results

    def _get_records_without_product(self) -> Dict[str, Any]:
        """Get information about records without a product for manual review."""
        if len(self.df_no_product) == 0:
            return {'count': 0, 'patient_ids': []}

        # Get unique patient IDs
        patient_ids = sorted(self.df_no_product['PID'].unique().tolist())

        return {
            'count': len(self.df_no_product),
            'unique_patients': len(patient_ids),
            'patient_ids': patient_ids
        }

    def _calculate_patient_summary(self) -> Dict[str, Any]:
        """
        Calculate comprehensive patient summary including record types.

        Categorizes patients by:
        - With/without product administrations
        - With/without follow-up data
        - With/without baseline data
        """
        # Define column groups
        followup_cols = [c for c in self.df_all.columns if c.startswith('X_435_')]
        baseline_cols = [c for c in self.df_all.columns if c.startswith('X_433_0_')]
        product_col = 'X_433_7_746'

        # All patients
        all_patients = set(self.df_all['PID'].unique())

        # Patients with at least one product administration
        patients_with_product = set(self.df[self.df[product_col].notna()]['PID'].unique())

        # Patients without any products
        patients_without_product = all_patients - patients_with_product

        # For patients WITH products, check if they have follow-up
        df_product_patients = self.df_all[self.df_all['PID'].isin(patients_with_product)]
        has_followup = df_product_patients[followup_cols].notna().any(axis=1)
        patients_with_product_and_followup = set(df_product_patients[has_followup]['PID'].unique())

        # For patients WITHOUT products, categorize by what data they have
        df_no_product_patients = self.df_all[self.df_all['PID'].isin(patients_without_product)]

        # Check follow-up and baseline for patients without products
        has_followup_no_prod = df_no_product_patients[followup_cols].notna().any(axis=1)
        has_baseline_no_prod = df_no_product_patients[baseline_cols].notna().any(axis=1)

        patients_followup_only = set(df_no_product_patients[has_followup_no_prod]['PID'].unique())
        patients_baseline_only = set(df_no_product_patients[has_baseline_no_prod]['PID'].unique()) - patients_followup_only

        # Patients with follow-up but no baseline (should not happen - error cases)
        followup_no_baseline = patients_followup_only - set(df_no_product_patients[has_baseline_no_prod]['PID'].unique())

        # Patients with only basic demographics
        patients_demographics_only = patients_without_product - patients_followup_only - patients_baseline_only

        return {
            'total_patients': len(all_patients),
            'patients_with_product': {
                'total': len(patients_with_product),
                'with_followup': len(patients_with_product_and_followup),
                'without_followup': len(patients_with_product) - len(patients_with_product_and_followup)
            },
            'patients_without_product': {
                'total': len(patients_without_product),
                'followup_only_ERROR': len(followup_no_baseline),
                'baseline_only': len(patients_baseline_only),
                'demographics_only': len(patients_demographics_only),
                'patient_ids': sorted(list(patients_without_product))
            }
        }

    def _calculate_total_administrations(self) -> Dict[str, Any]:
        """Calculate total number of administrations with detailed statistics."""
        total = len(self.df)
        unique_patients = self.df['PID'].nunique()

        # Calculate administrations per patient statistics
        admin_counts = self.df.groupby('PID').size()

        return {
            'total_administrations': total,
            'unique_patients': unique_patients,
            'administrations_per_patient': {
                'mean': float(admin_counts.mean()),
                'sd': float(admin_counts.std()) if len(admin_counts) > 1 else 0,
                'median': float(admin_counts.median()),
                'q25': float(admin_counts.quantile(0.25)),
                'q75': float(admin_counts.quantile(0.75)),
                'min': int(admin_counts.min()),
                'max': int(admin_counts.max())
            }
        }

    def _calculate_product_distribution(self) -> Dict[str, Any]:
        """Calculate product type distribution (only records with products)."""
        product_col = 'X_433_7_746'

        if product_col not in self.df.columns:
            return {'error': 'Product column not found'}

        # Get counts (self.df already filtered to only records with products)
        # Codes are normalized first ('1.0' -> '1') so both string forms are
        # aggregated instead of the second form overwriting the first.
        product_series = self.df[product_col].map(self._normalize_code)
        total = len(self.df)

        products = {}
        for code, name in self._canonical_products().items():
            count = (product_series == code).sum()
            if count > 0:
                products[name] = {
                    'n': int(count),
                    'percent': float(count / total * 100) if total > 0 else 0
                }

        return {
            'products': products,
            'total': total
        }

    def _calculate_temporal_distribution(self) -> Dict[str, Any]:
        """Calculate temporal distribution by month."""
        date_col = 'X_433_7_11'

        if date_col not in self.df.columns:
            return {'error': 'Date column not found'}

        dates = pd.to_datetime(self.df[date_col], errors='coerce')

        # Monthly distribution
        months = dates.dt.to_period('M')
        monthly_counts = months.value_counts().sort_index()

        # Convert to dictionary
        monthly_dict = {}
        for month, count in monthly_counts.items():
            monthly_dict[str(month)] = int(count)

        return {
            'date_range': {
                'start': str(dates.min().date()) if dates.notna().any() else None,
                'end': str(dates.max().date()) if dates.notna().any() else None
            },
            'monthly_distribution': monthly_dict,
            'missing_dates': int(dates.isna().sum())
        }

    def _calculate_dosage_statistics(self) -> Dict[str, Any]:
        """Calculate dosage statistics by product type and unit.

        Applies data quality filters to exclude clinically implausible values:
        - PPSB ml: Excluded (reconstituted product, not administered in ml volumes)
        - Fibrinogen IU: Excluded (non-standard unit - should be mg)
        - Fibrinogen mg < 500: Excluded (implausibly low, likely data entry errors)
        """
        dose_col = 'X_433_7_22'
        unit_col = 'X_433_7_734'
        product_col = 'X_433_7_746'

        if dose_col not in self.df.columns:
            return {'error': 'Dosage column not found'}

        results = {}
        data_quality_log = {}

        # Get data with valid dosages
        df_dose = self.df[self.df[dose_col].notna()].copy()

        if len(df_dose) == 0:
            return {'error': 'No dosage data available'}

        # Normalize codes for matching ('1.0' -> '1') so both string forms are
        # aggregated together instead of one form overwriting the other.
        df_dose['product_str'] = df_dose[product_col].map(self._normalize_code)
        df_dose['unit_str'] = df_dose[unit_col].map(self._normalize_code)

        # Calculate for each product (canonical codes only)
        for code, product_name in self._canonical_products().items():
            df_product = df_dose[df_dose['product_str'] == code]

            if len(df_product) == 0:
                continue

            # Group by unit
            product_results = {}
            for unit_code, unit_name in self._canonical_units().items():
                df_unit = df_product[df_product['unit_str'] == unit_code]

                if len(df_unit) == 0:
                    continue

                doses = df_unit[dose_col].dropna()

                # DATA QUALITY FILTERS
                original_n = len(doses)
                excluded_n = 0
                exclusion_reason = None

                # Filter 1: PPSB ml - clinically implausible (reconstituted product)
                if product_name == 'PPSB' and unit_name == 'ml':
                    excluded_n = len(doses)
                    exclusion_reason = "PPSB ml excluded: reconstituted product with implausible ml values (1000-5500 ml)"
                    doses = doses.iloc[0:0]  # Empty series

                # Filter 2: Fibrinogen IU - non-standard unit
                elif product_name == 'Fibrinogen' and unit_name == 'IU':
                    excluded_n = len(doses)
                    exclusion_reason = "Fibrinogen IU excluded: non-standard unit (should be mg)"
                    doses = doses.iloc[0:0]  # Empty series

                # Filter 3: Fibrinogen mg < 500 - implausibly low
                elif product_name == 'Fibrinogen' and unit_name == 'mg':
                    low_doses = doses[doses < 500]
                    if len(low_doses) > 0:
                        excluded_n = len(low_doses)
                        exclusion_reason = f"Fibrinogen mg: excluded {excluded_n} record(s) with dose < 500 mg (implausibly low, likely data entry errors)"
                        doses = doses[doses >= 500]

                # Log exclusions
                if excluded_n > 0:
                    key = f"{product_name}_{unit_name}"
                    data_quality_log[key] = {
                        'original_n': original_n,
                        'excluded_n': excluded_n,
                        'retained_n': len(doses),
                        'reason': exclusion_reason
                    }
                    print(f"  DATA QUALITY: {exclusion_reason}")

                if len(doses) > 0:
                    product_results[unit_name] = {
                        'n': int(len(doses)),
                        'mean': float(doses.mean()),
                        'sd': float(doses.std()) if len(doses) > 1 else 0,
                        'median': float(doses.median()),
                        'q25': float(doses.quantile(0.25)),
                        'q75': float(doses.quantile(0.75)),
                        'min': float(doses.min()),
                        'max': float(doses.max())
                    }

            if product_results:
                results[product_name] = product_results

        # Store data quality log
        self.data_quality_exclusions = data_quality_log

        return results

    def _calculate_indication_statistics(self) -> Dict[str, Any]:
        """Calculate indication distribution by product type."""
        results = {}

        for product_name, indication_col in self.INDICATION_COLUMNS.items():
            if indication_col not in self.df.columns:
                continue

            indications = self.df[indication_col].dropna()

            if len(indications) == 0:
                continue

            # Get value counts
            ind_counts = indications.value_counts()
            total = len(indications)

            ind_dict = {}
            for value, count in ind_counts.items():
                # Try to decode the value
                decoded = self.mapper.decode_value(indication_col, str(value))
                if decoded and decoded != str(value):
                    label = decoded
                else:
                    label = f"Code {value}"

                ind_dict[label] = {
                    'n': int(count),
                    'percent': float(count / total * 100)
                }

            results[product_name] = {
                'indications': ind_dict,
                'total': int(total),
                'missing': int(self.df[indication_col].isna().sum())
            }

        return results

    @staticmethod
    def _csv_row(fields):
        """RFC-conform CSV row (quotes/commas/newlines in free text stay intact)."""
        import csv as _csv
        import io as _io
        buf = _io.StringIO()
        _csv.writer(buf, lineterminator='\n').writerow(
            ['' if f is None else f for f in fields])
        return buf.getvalue()

    def _lab_checker(self):
        """Shared central lab normalization (see lab_value_quality)."""
        if not hasattr(self, '_lab_quality_checker'):
            from lab_value_quality import LabValueQualityChecker
            self._lab_quality_checker = LabValueQualityChecker(self.df)
        return self._lab_quality_checker

    def _calculate_lab_value_statistics(self) -> Dict[str, Any]:
        """Calculate lab value statistics before/after administration."""
        results = {}

        for lab_name, lab_info in self.LAB_COLUMNS.items():
            before_col = lab_info['before']
            after_col = lab_info['after']

            if before_col not in self.df.columns or after_col not in self.df.columns:
                continue

            # Canonical analysis values from the CENTRAL lab normalization
            # (lab_value_quality.get_analysis_series): non-positive values
            # excluded before any scaling, unit correction applied, clinical
            # plausibility gated. Statistics, quality report, and figures
            # all draw from the same series.
            series = self._lab_checker().get_analysis_series(
                lab_name, before_col=before_col, after_col=after_col)
            if series['before'] is None or series['after'] is None:
                continue
            pair_mask = series['before'].notna() & series['after'].notna()
            before_vals = series['before'][pair_mask]
            after_vals = series['after'][pair_mask]
            audit = series['audit']

            if len(before_vals) == 0:
                continue

            change_vals = after_vals - before_vals

            # Before statistics
            before_stats = {
                'n': int(len(before_vals)),
                'mean': float(before_vals.mean()),
                'sd': float(before_vals.std()) if len(before_vals) > 1 else 0,
                'median': float(before_vals.median()),
                'q25': float(before_vals.quantile(0.25)),
                'q75': float(before_vals.quantile(0.75)),
                'min': float(before_vals.min()),
                'max': float(before_vals.max())
            }

            # After statistics
            after_stats = {
                'n': int(len(after_vals)),
                'mean': float(after_vals.mean()),
                'sd': float(after_vals.std()) if len(after_vals) > 1 else 0,
                'median': float(after_vals.median()),
                'q25': float(after_vals.quantile(0.25)),
                'q75': float(after_vals.quantile(0.75)),
                'min': float(after_vals.min()),
                'max': float(after_vals.max())
            }

            # Change statistics
            change_stats = {
                'n': int(len(change_vals)),
                'mean': float(change_vals.mean()),
                'sd': float(change_vals.std()) if len(change_vals) > 1 else 0,
                'median': float(change_vals.median()),
                'q25': float(change_vals.quantile(0.25)),
                'q75': float(change_vals.quantile(0.75)),
                'min': float(change_vals.min()),
                'max': float(change_vals.max())
            }

            results[lab_name] = {
                'unit': lab_info['unit'],
                'normal_range': lab_info['normal_range'],
                'before': before_stats,
                'after': after_stats,
                'change': change_stats,
                'exclusions': audit,
                'n_unit_corrected': int(sum(a['n_unit_corrected'] for a in audit.values())),
                'n_excluded_nonpositive': int(sum(a['n_excluded_nonpositive'] for a in audit.values())),
                'n_excluded_implausible': int(sum(a['n_excluded_implausible'] for a in audit.values())),
                'n_before_only': int(series['before'].notna().sum()) - int(pair_mask.sum()),
                'n_after_only': int(series['after'].notna().sum()) - int(pair_mask.sum())
            }

        return results

    def _calculate_patient_statistics(self) -> Dict[str, int]:
        """Calculate basic patient statistics."""
        n_patients = self.df['PID'].nunique()
        n_administrations = len(self.df)

        return {
            'n_unique_patients': n_patients,
            'n_total_administrations': n_administrations
        }

    def _calculate_products_per_patient(self) -> Dict[str, Any]:
        """Calculate how many patients received each product type."""
        product_col = 'X_433_7_746'

        if product_col not in self.df.columns:
            return {'error': 'Product column not found'}

        # Get unique patients per product (normalized codes: '1' and '1.0' aggregated)
        df_products = self.df[self.df[product_col].notna()].copy()
        df_products['product_str'] = df_products[product_col].map(self._normalize_code)

        total_patients = self.df['PID'].nunique()

        results = {}
        for code, product_name in self._canonical_products().items():
            df_prod = df_products[df_products['product_str'] == code]

            if len(df_prod) == 0:
                continue

            n_patients = df_prod['PID'].nunique()
            n_administrations = len(df_prod)

            results[product_name] = {
                'n_patients': int(n_patients),
                'percent_patients': float(n_patients / total_patients * 100) if total_patients > 0 else 0,
                'n_administrations': int(n_administrations),
                'administrations_per_patient': float(n_administrations / n_patients) if n_patients > 0 else 0
            }

        return results

    def _calculate_administration_frequency(self) -> Dict[str, Any]:
        """Calculate distribution of number of administrations per patient."""
        # Count administrations per patient
        admin_counts = self.df.groupby('PID').size()

        stats = {
            'n_patients': int(len(admin_counts)),
            'mean': float(admin_counts.mean()),
            'sd': float(admin_counts.std()) if len(admin_counts) > 1 else 0,
            'median': float(admin_counts.median()),
            'q25': float(admin_counts.quantile(0.25)),
            'q75': float(admin_counts.quantile(0.75)),
            'min': int(admin_counts.min()),
            'max': int(admin_counts.max())
        }

        # Distribution categories
        distribution = {}
        for count in sorted(admin_counts.unique()):
            n_patients = (admin_counts == count).sum()
            distribution[f"{int(count)} administration{'s' if count > 1 else ''}"] = {
                'n_patients': int(n_patients),
                'percent': float(n_patients / len(admin_counts) * 100)
            }

        return {
            'statistics': stats,
            'distribution': distribution
        }

    def _calculate_data_completeness_by_product(self) -> Dict[str, Any]:
        """
        Calculate data completeness statistics for each blood product.

        Returns a table showing for each product:
        - Total administrations
        - With dosage documented
        - With indication documented
        - With primary lab value before
        - With primary lab value after
        """
        product_col = 'X_433_7_746'
        dosage_col = 'X_433_7_22'

        completeness = {}

        for product_code, product_name in self._canonical_products().items():
            # Skip Machine Autotransfusion - it has its own separate table
            if 'Autotransfusion' in product_name:
                continue

            # Get records for this product (canonical code matches both forms)
            df_product = self.df[self.df[product_col].astype(str).isin([product_code, f"{product_code}.0"])]

            if len(df_product) == 0:
                continue

            total = len(df_product)

            # Dosage completeness
            with_dosage = df_product[dosage_col].notna().sum()

            # Indication completeness
            indication_col = self.INDICATION_COLUMNS.get(product_name)
            if indication_col and indication_col in df_product.columns:
                with_indication = df_product[indication_col].notna().sum()
            else:
                with_indication = None

            # Lab value completeness (product-specific)
            lab_name = self.PRODUCT_LAB_MAPPING.get(product_name)
            with_lab_before = None
            with_lab_after = None

            if lab_name and lab_name in self.LAB_COLUMNS:
                lab_cols = self.LAB_COLUMNS[lab_name]
                before_col = lab_cols['before']
                after_col = lab_cols['after']

                if before_col in df_product.columns:
                    with_lab_before = df_product[before_col].notna().sum()
                if after_col in df_product.columns:
                    with_lab_after = df_product[after_col].notna().sum()

            completeness[product_name] = {
                'total': int(total),
                'with_dosage': int(with_dosage) if with_dosage is not None else None,
                'with_dosage_pct': float(with_dosage / total * 100) if with_dosage is not None and total > 0 else None,
                'with_indication': int(with_indication) if with_indication is not None else None,
                'with_indication_pct': float(with_indication / total * 100) if with_indication is not None and total > 0 else None,
                'primary_lab': lab_name,
                'with_lab_before': int(with_lab_before) if with_lab_before is not None else None,
                'with_lab_before_pct': float(with_lab_before / total * 100) if with_lab_before is not None and total > 0 else None,
                'with_lab_after': int(with_lab_after) if with_lab_after is not None else None,
                'with_lab_after_pct': float(with_lab_after / total * 100) if with_lab_after is not None and total > 0 else None
            }

        return completeness

    def create_data_completeness_table(self) -> str:
        """Create formatted data completeness table."""
        if 'data_completeness' not in self.results:
            self.results['data_completeness'] = self._calculate_data_completeness_by_product()

        completeness = self.results['data_completeness']

        lines = []
        lines.append("=" * 120)
        lines.append("DATA COMPLETENESS BY BLOOD PRODUCT")
        lines.append("=" * 120)
        lines.append("")

        # Header
        header = f"{'Product':<45} {'Total':>8} {'Dosage':>12} {'Indication':>14} {'Lab Before':>14} {'Lab After':>14}"
        lines.append(header)
        lines.append("-" * 120)

        # Sort by total administrations (descending)
        sorted_products = sorted(completeness.items(), key=lambda x: x[1]['total'], reverse=True)

        for product_name, data in sorted_products:
            total = data['total']

            # Dosage
            if data['with_dosage'] is not None:
                dosage_str = f"{data['with_dosage']} ({data['with_dosage_pct']:.1f}%)"
            else:
                dosage_str = "N/A"

            # Indication
            if data['with_indication'] is not None:
                indication_str = f"{data['with_indication']} ({data['with_indication_pct']:.1f}%)"
            else:
                indication_str = "N/A"

            # Lab before
            if data['with_lab_before'] is not None:
                lab_before_str = f"{data['with_lab_before']} ({data['with_lab_before_pct']:.1f}%)"
            else:
                lab_before_str = "N/A"

            # Lab after
            if data['with_lab_after'] is not None:
                lab_after_str = f"{data['with_lab_after']} ({data['with_lab_after_pct']:.1f}%)"
            else:
                lab_after_str = "N/A"

            # Clean product name (remove abbreviation)
            clean_name = product_name.split('(')[0].strip() if '(' in product_name else product_name

            line = f"{clean_name:<45} {total:>8} {dosage_str:>12} {indication_str:>14} {lab_before_str:>14} {lab_after_str:>14}"
            lines.append(line)

        lines.append("")
        lines.append("-" * 120)
        lines.append("Note: Lab values shown are the primary lab parameter for each product type:")
        lines.append("  RBC: Hemoglobin | Platelets: Platelets | PPSB: Quick's test | FFP: N/A")
        lines.append("  Fibrinogen: Fibrinogen | Albumin: Serum albumin | Iron i.v.: Ferritin | ATIII: Antithrombin activity")
        lines.append("  Machine Autotransfusion: See separate autotransfusion statistics table")
        lines.append("=" * 120)

        return "\n".join(lines)

    def _calculate_autotransfusion_statistics(self) -> Dict[str, Any]:
        """
        Calculate statistics for Machine Autotransfusion (Cell Salvage).

        Returns statistics for:
        - Volume of wound blood collected
        - Hematocrit of wound blood
        - Recovered RBC volume
        - Recovered hematocrit
        """
        product_col = 'X_433_7_746'

        # Find Machine Autotransfusion code
        autotransfusion_code = None
        for code, name in self.PRODUCT_MAPPING.items():
            if 'Autotransfusion' in name:
                autotransfusion_code = code
                break

        if autotransfusion_code is None:
            return {'error': 'Autotransfusion product code not found'}

        # Get autotransfusion records
        df_auto = self.df[self.df[product_col].astype(str).isin([autotransfusion_code, f"{autotransfusion_code}.0"])]

        if len(df_auto) == 0:
            return {'total': 0, 'parameters': {}}

        total = len(df_auto)
        n_patients = df_auto['PID'].nunique()

        # Calculate statistics for each parameter
        parameters = {}
        for param_key, param_info in self.AUTOTRANSFUSION_COLUMNS.items():
            col = param_info['column']
            name = param_info['name']
            unit = param_info['unit']

            if col not in df_auto.columns:
                parameters[param_key] = {
                    'name': name,
                    'unit': unit,
                    'n': 0,
                    'n_missing': total,
                    'completeness_pct': 0
                }
                continue

            # Get non-null values
            values = pd.to_numeric(df_auto[col], errors='coerce').dropna()
            n_documented = len(values)
            n_missing = total - n_documented

            param_stats = {
                'name': name,
                'unit': unit,
                'n': int(n_documented),
                'n_missing': int(n_missing),
                'completeness_pct': float(n_documented / total * 100) if total > 0 else 0
            }

            if n_documented > 0:
                param_stats.update({
                    'mean': float(values.mean()),
                    'sd': float(values.std()) if n_documented > 1 else 0,
                    'median': float(values.median()),
                    'q25': float(values.quantile(0.25)),
                    'q75': float(values.quantile(0.75)),
                    'min': float(values.min()),
                    'max': float(values.max())
                })

            parameters[param_key] = param_stats

        return {
            'total': int(total),
            'n_patients': int(n_patients),
            'parameters': parameters
        }

    def create_autotransfusion_table(self) -> str:
        """Create formatted table for Machine Autotransfusion (Cell Salvage) statistics."""
        if 'autotransfusion' not in self.results:
            self.results['autotransfusion'] = self._calculate_autotransfusion_statistics()

        auto = self.results['autotransfusion']

        lines = []
        lines.append("=" * 100)
        lines.append("MACHINE AUTOTRANSFUSION (CELL SALVAGE) STATISTICS")
        lines.append("=" * 100)
        lines.append("")

        if auto.get('total', 0) == 0:
            lines.append("No autotransfusion records found.")
            lines.append("=" * 100)
            return "\n".join(lines)

        lines.append(f"Total autotransfusion procedures: n = {auto['total']}")
        lines.append(f"Unique patients: n = {auto['n_patients']}")
        lines.append("")
        lines.append("-" * 100)
        lines.append("PARAMETER STATISTICS")
        lines.append("-" * 100)
        lines.append("")

        # Header
        header = f"{'Parameter':<35} {'n':>6} {'Complete':>10} {'Mean (SD)':>18} {'Median [IQR]':>22} {'Range':>15}"
        lines.append(header)
        lines.append("-" * 100)

        for param_key, param_data in auto['parameters'].items():
            name = param_data['name']
            unit = param_data['unit']
            n = param_data['n']
            pct = param_data['completeness_pct']

            if n > 0:
                mean_sd = f"{param_data['mean']:.1f} ({param_data['sd']:.1f})"
                median_iqr = f"{param_data['median']:.1f} [{param_data['q25']:.1f}-{param_data['q75']:.1f}]"
                range_str = f"{param_data['min']:.1f}-{param_data['max']:.1f}"
            else:
                mean_sd = "N/A"
                median_iqr = "N/A"
                range_str = "N/A"

            line = f"{name} ({unit})"
            lines.append(f"{line:<35} {n:>6} {pct:>9.1f}% {mean_sd:>18} {median_iqr:>22} {range_str:>15}")

        lines.append("")
        lines.append("=" * 100)

        return "\n".join(lines)

    def _get_record_review_details(self, row, product_name: str) -> Dict[str, Any]:
        """
        Collect administration and follow-up details for a record flagged for review.

        Used for ABO-incompatible and RhD-flagged transfusion records.
        """
        pid = row['PID']

        # Get administration details
        admin_date = row.get('X_433_7_11', None)  # Date of product administration
        dosage = row.get('X_433_7_22', None)  # Dosage value

        # Get follow-up data for this patient (from any record)
        patient_records = self.df_all[self.df_all['PID'] == pid]

        # Follow-up columns
        problems_col = 'X_435_0_737'  # Problems related to blood product
        problems_detail_col = 'X_435_0_616'  # Which problems
        anaemia_col = 'X_435_0_740'  # Has anaemia been diagnosed
        transfusions_col = 'X_435_0_752'  # Blood transfusions in past year

        # Decode follow-up answers with the DICTIONARY codes (737/740 are
        # Y/N/U; 752 is 0-3 with 3 = cannot answer). Values are taken
        # row-wise from the EARLIEST completed follow-up questionnaire (no
        # per-column composites across different follow-ups); disagreement
        # between multiple follow-ups is reported as a conflict flag.
        YNU = {'Y': 'Yes', 'N': 'No', 'U': 'Cannot answer'}
        T752 = {'0': 'None', '1': 'One', '2': 'More than one',
                '3': 'Cannot answer'}

        def _code(v):
            sv = str(v).strip()
            return sv[:-2] if sv.endswith('.0') else sv

        has_problems = None
        problem_details = None
        has_anaemia = None
        more_transfusions = None
        followup_date = None
        followup_conflict = False
        has_followup = False

        date_col = 'X_435_0_751'
        followup_window = None
        if date_col in patient_records.columns:
            fu_rows = patient_records[patient_records[date_col].notna()].sort_values(date_col)
            if len(fu_rows) > 0:
                has_followup = True
                # Assign the follow-up relative to the patient's FIRST
                # product administration - the same anchor the follow-up
                # statistics use. One questionnaire is the patient's
                # follow-up per schedule; it is never re-anchored per
                # flagged administration, and a questionnaire completed
                # BEFORE the first administration is never reported as a
                # follow-up. Without any administration date the earliest
                # questionnaire is used and labeled accordingly.
                prod_col = 'X_433_7_746'
                admin_date_col = 'X_433_7_11'
                anchor_ts = pd.NaT
                if prod_col in patient_records.columns and admin_date_col in patient_records.columns:
                    _admins = patient_records[patient_records[prod_col].notna()]
                    anchor_ts = pd.to_datetime(_admins[admin_date_col], errors='coerce').min()
                if pd.isna(anchor_ts):
                    anchor_ts = pd.to_datetime(admin_date, errors='coerce')
                fu_dates = pd.to_datetime(fu_rows[date_col], errors='coerce')
                first = None
                if pd.notna(anchor_ts):
                    post = fu_dates[fu_dates >= anchor_ts]
                    if len(post) > 0:
                        first = fu_rows.loc[post.index[0]]
                    else:
                        has_followup = False
                        followup_window = 'no post-administration follow-up'
                else:
                    first = fu_rows.iloc[0]
                followup_date = (str(pd.to_datetime(first[date_col]).date())
                                 if first is not None else None)
                if first is not None and pd.notna(anchor_ts):
                    _days = (pd.to_datetime(first[date_col]) - anchor_ts).days
                    if 68 <= _days <= 113:
                        followup_window = '3-month (vs first administration)'
                    elif 273 <= _days <= 455:
                        followup_window = '1-year (vs first administration)'
                    else:
                        followup_window = f'outside windows ({_days} d vs first administration)'
                elif first is not None:
                    followup_window = 'no administration date'
                if first is not None and problems_col in fu_rows.columns and pd.notna(first.get(problems_col)):
                    has_problems = YNU.get(_code(first[problems_col]),
                                           f'Unexpected code {_code(first[problems_col])}')
                if first is not None and problems_detail_col in fu_rows.columns and pd.notna(first.get(problems_detail_col)):
                    problem_details = str(first[problems_detail_col])
                if first is not None and anaemia_col in fu_rows.columns and pd.notna(first.get(anaemia_col)):
                    has_anaemia = YNU.get(_code(first[anaemia_col]),
                                          f'Unexpected code {_code(first[anaemia_col])}')
                if first is not None and transfusions_col in fu_rows.columns and pd.notna(first.get(transfusions_col)):
                    more_transfusions = T752.get(_code(first[transfusions_col]),
                                                 f'Unexpected code {_code(first[transfusions_col])}')
                if len(fu_rows) > 1:
                    for c in (problems_col, problems_detail_col, anaemia_col,
                              transfusions_col):
                        if c in fu_rows.columns and fu_rows[c].dropna().nunique() > 1:
                            followup_conflict = True
                            break

        try:
            pid_out = int(pid)
        except (TypeError, ValueError):
            pid_out = str(pid)

        return {
            'PID': pid_out,
            'product': product_name,
            'administration_date': str(admin_date) if pd.notna(admin_date) else None,
            'dosage': float(dosage) if pd.notna(dosage) else None,
            'has_followup': has_followup,
            'followup_date': followup_date,
            'followup_window': followup_window,
            'followup_conflict': followup_conflict,
            'problems_reported': has_problems,
            'problem_details': problem_details,
            'anaemia_at_followup': has_anaemia,
            'subsequent_transfusions': more_transfusions
        }

    def _calculate_blood_type_statistics(self) -> Dict[str, Any]:
        """
        Calculate blood type documentation and compatibility statistics.

        Analyzes ABO and RhD blood type documentation for products where
        blood type compatibility is clinically important (RBC, FFP, PC).

        ABO compatibility uses real transfusion rules (registry code for O is '0'):
        - RBC: recipient 0<-{0}, A<-{A,0}, B<-{B,0}, AB<-{A,B,AB,0}
        - FFP/plasma (REVERSED): recipient 0<-{0,A,B,AB}, A<-{A,AB}, B<-{B,AB}, AB<-{AB}
        - PC: ABO-identical vs ABO-non-identical reported as neutral categories
          (ABO-identical PC transfusion is preferred but not mandatory)

        RhD (RBC and PC): RhD-positive product to RhD-negative patient is flagged.

        Returns:
            Dictionary with blood type statistics by product
        """
        product_col = 'X_433_7_746'
        patient_abo = self.BLOOD_TYPE_COLUMNS['patient_abo']
        patient_rh = self.BLOOD_TYPE_COLUMNS['patient_rh']
        product_abo = self.BLOOD_TYPE_COLUMNS['product_abo']
        product_rh = self.BLOOD_TYPE_COLUMNS['product_rh']

        results = {}

        product_norm = self.df[product_col].map(self._normalize_code)

        for product_code, product_name in self.BLOOD_TYPE_PRODUCTS.items():
            # Filter to this product (normalized code matching)
            df_product = self.df[product_norm == self._normalize_code(product_code)]

            if len(df_product) == 0:
                continue

            total = len(df_product)
            product_class = self.ABO_PRODUCT_CLASS[product_name]

            # ABO blood type documentation
            has_patient_abo = df_product[patient_abo].notna().sum()
            has_product_abo = df_product[product_abo].notna().sum()
            has_either_abo = df_product[(df_product[patient_abo].notna()) | (df_product[product_abo].notna())].shape[0]
            has_both_abo = df_product[(df_product[patient_abo].notna()) & (df_product[product_abo].notna())].shape[0]

            # ABO compatibility classification (among those with both documented)
            df_both_abo = df_product[(df_product[patient_abo].notna()) & (df_product[product_abo].notna())].copy()

            n_identical = 0
            n_compatible_non_identical = 0  # RBC/plasma only
            n_non_identical = 0             # PC only (neutral category)
            n_incompatible = 0              # RBC/plasma only
            n_not_assessable = 0            # both documented but not interpretable
            incompatible_details = []

            for _, row in df_both_abo.iterrows():
                status = self._classify_abo_compatibility(
                    row[patient_abo], row[product_abo], product_class)
                if status == 'identical':
                    n_identical += 1
                elif status == 'compatible':
                    n_compatible_non_identical += 1
                elif status == 'non_identical':
                    n_non_identical += 1
                elif status == 'incompatible':
                    n_incompatible += 1
                    detail = self._get_record_review_details(row, product_name)
                    detail['issue'] = 'ABO incompatible'
                    detail['patient_abo'] = row[patient_abo]
                    detail['product_abo'] = row[product_abo]
                    incompatible_details.append(detail)
                else:
                    n_not_assessable += 1

            n_assessed = len(df_both_abo) - n_not_assessable
            n_compatible_total = n_identical + (
                n_compatible_non_identical if product_class != 'PC' else n_non_identical)

            # Rh factor documentation
            has_patient_rh = df_product[patient_rh].notna().sum()
            has_product_rh = df_product[product_rh].notna().sum()
            has_either_rh = df_product[(df_product[patient_rh].notna()) | (df_product[product_rh].notna())].shape[0]
            has_both_rh = df_product[(df_product[patient_rh].notna()) & (df_product[product_rh].notna())].shape[0]

            # RhD check (RBC and PC): RhD-positive product to RhD-negative patient flagged
            rhd_checked = product_name in self.RHD_CHECK_PRODUCTS
            n_rhd_flagged = 0
            n_rhd_unflagged = 0
            n_rhd_not_assessable = 0
            rhd_flagged_details = []

            if rhd_checked:
                df_both_rh = df_product[(df_product[patient_rh].notna()) & (df_product[product_rh].notna())]
                for _, row in df_both_rh.iterrows():
                    p_rh = self._normalize_rh(row[patient_rh])
                    d_rh = self._normalize_rh(row[product_rh])
                    if p_rh is None or d_rh is None:
                        n_rhd_not_assessable += 1  # 'Unknown' (code 0) or uninterpretable
                    elif p_rh == '2' and d_rh == '1':
                        n_rhd_flagged += 1
                        detail = self._get_record_review_details(row, product_name)
                        detail['issue'] = 'RhD-positive product to RhD-negative patient'
                        detail['patient_rh'] = row[patient_rh]
                        detail['product_rh'] = row[product_rh]
                        rhd_flagged_details.append(detail)
                    else:
                        n_rhd_unflagged += 1

            # ABO distribution for this product
            patient_abo_dist = df_product[patient_abo].value_counts(dropna=True).to_dict()
            product_abo_dist = df_product[product_abo].value_counts(dropna=True).to_dict()

            abo_result = {
                'patient_documented': int(has_patient_abo),
                'patient_documented_pct': float(has_patient_abo / total * 100) if total > 0 else 0,
                'product_documented': int(has_product_abo),
                'product_documented_pct': float(has_product_abo / total * 100) if total > 0 else 0,
                'either_documented': int(has_either_abo),
                'either_documented_pct': float(has_either_abo / total * 100) if total > 0 else 0,
                'both_documented': int(has_both_abo),
                'both_documented_pct': float(has_both_abo / total * 100) if total > 0 else 0,
                'compatibility_class': product_class,
                'n_assessed': int(n_assessed),
                'identical': int(n_identical),
                'not_assessable': int(n_not_assessable),
                'incompatible_details': incompatible_details,
                'patient_distribution': patient_abo_dist,
                'product_distribution': product_abo_dist
            }

            if product_class == 'PC':
                # Neutral categories only - non-identical PC is NOT a mismatch
                abo_result['non_identical'] = int(n_non_identical)
                abo_result['compatible_total'] = int(n_compatible_total)
                abo_result['incompatible'] = None
            else:
                abo_result['compatible_non_identical'] = int(n_compatible_non_identical)
                abo_result['compatible_total'] = int(n_compatible_total)
                abo_result['incompatible'] = int(n_incompatible)

            results[product_name] = {
                'total': int(total),
                'abo': abo_result,
                'rh': {
                    'patient_documented': int(has_patient_rh),
                    'patient_documented_pct': float(has_patient_rh / total * 100) if total > 0 else 0,
                    'product_documented': int(has_product_rh),
                    'product_documented_pct': float(has_product_rh / total * 100) if total > 0 else 0,
                    'either_documented': int(has_either_rh),
                    'either_documented_pct': float(has_either_rh / total * 100) if total > 0 else 0,
                    'both_documented': int(has_both_rh),
                    'both_documented_pct': float(has_both_rh / total * 100) if total > 0 else 0,
                    'rhd_checked': rhd_checked,
                    'rhd_flagged': int(n_rhd_flagged),
                    'rhd_unflagged': int(n_rhd_unflagged),
                    'rhd_not_assessable': int(n_rhd_not_assessable),
                    'rhd_flagged_details': rhd_flagged_details
                }
            }

        return results

    def create_blood_type_table(self) -> str:
        """Create formatted table for blood type documentation and compatibility."""
        if 'blood_type' not in self.results:
            self.results['blood_type'] = self._calculate_blood_type_statistics()

        bt = self.results['blood_type']

        lines = []
        lines.append("=" * 100)
        lines.append("BLOOD TYPE DOCUMENTATION AND COMPATIBILITY ANALYSIS")
        lines.append("=" * 100)
        lines.append("")
        lines.append("Products analyzed: RBC, FFP, and Platelet concentrate (where ABO/Rh compatibility is important)")
        lines.append("")

        for product_name, data in bt.items():
            lines.append("-" * 100)
            lines.append(f"{product_name} (n={data['total']})")
            lines.append("-" * 100)
            lines.append("")

            # ABO Blood Group
            abo = data['abo']
            lines.append("ABO Blood Group:")
            lines.append(f"  Patient blood type documented:  {abo['patient_documented']:>4} ({abo['patient_documented_pct']:>5.1f}%)")
            lines.append(f"  Product blood type documented:  {abo['product_documented']:>4} ({abo['product_documented_pct']:>5.1f}%)")
            lines.append(f"  At least ONE documented:        {abo['either_documented']:>4} ({abo['either_documented_pct']:>5.1f}%)")
            lines.append(f"  BOTH documented:                {abo['both_documented']:>4} ({abo['both_documented_pct']:>5.1f}%)")
            lines.append("")
            lines.append(f"  ABO compatibility (n={abo['n_assessed']} assessable):")

            if abo['compatibility_class'] == 'PC':
                lines.append(f"    ABO-identical:                {abo['identical']:>4}")
                lines.append(f"    ABO-non-identical:            {abo['non_identical']:>4}")
                lines.append("    (ABO-identical PC transfusion is preferred but not mandatory;")
                lines.append("     non-identical PC is reported as a neutral category, not a mismatch)")
            else:
                lines.append(f"    ABO-identical:                {abo['identical']:>4}")
                lines.append(f"    Compatible (non-identical):   {abo['compatible_non_identical']:>4}")
                lines.append(f"    Compatible total:             {abo['compatible_total']:>4}")
                lines.append(f"    INCOMPATIBLE:                 {abo['incompatible']:>4}")
            if abo['not_assessable'] > 0:
                lines.append(f"    Not assessable (invalid ABO value): {abo['not_assessable']:>4}")

            if abo.get('incompatible') and abo['incompatible'] > 0:
                lines.append("")
                lines.append("  WARNING: ABO-INCOMPATIBLE transfusions detected!")
                lines.append("  " + "-" * 96)
                for m in abo['incompatible_details']:
                    lines.append(f"    PID {m['PID']}: Patient={m['patient_abo']}, Product={m['product_abo']}")
                    if m.get('administration_date'):
                        lines.append(f"      Administration date: {m['administration_date']}")
                    if m.get('dosage') is not None:
                        lines.append(f"      Dosage: {m['dosage']}")
                    if m.get('has_followup'):
                        lines.append(f"      Follow-up available: Yes")
                        lines.append(f"        Problems reported: {m.get('problems_reported', 'N/A')}")
                        if m.get('problem_details'):
                            lines.append(f"        Problem details: {m['problem_details']}")
                        lines.append(f"        Anaemia at follow-up: {m.get('anaemia_at_followup', 'N/A')}")
                        lines.append(f"        Subsequent transfusions: {m.get('subsequent_transfusions', 'N/A')}")
                    else:
                        lines.append(f"      Follow-up available: No")
                    lines.append("")

            lines.append("")

            # Rh Factor
            rh = data['rh']
            lines.append("Rhesus Factor:")
            lines.append(f"  Patient Rh documented:          {rh['patient_documented']:>4} ({rh['patient_documented_pct']:>5.1f}%)")
            lines.append(f"  Product Rh documented:          {rh['product_documented']:>4} ({rh['product_documented_pct']:>5.1f}%)")
            lines.append(f"  At least ONE documented:        {rh['either_documented']:>4} ({rh['either_documented_pct']:>5.1f}%)")
            lines.append(f"  BOTH documented:                {rh['both_documented']:>4} ({rh['both_documented_pct']:>5.1f}%)")

            if rh.get('rhd_checked'):
                lines.append(f"  RhD check (RhD+ product to RhD- patient):")
                lines.append(f"    Flagged:                      {rh['rhd_flagged']:>4}")
                lines.append(f"    Not flagged:                  {rh['rhd_unflagged']:>4}")
                lines.append(f"    Not assessable (Rh unknown):  {rh['rhd_not_assessable']:>4}")
                if rh['rhd_flagged'] > 0:
                    lines.append("")
                    lines.append("  NOTE: RhD-positive product administered to RhD-negative patient - review advised")
                    for m in rh['rhd_flagged_details']:
                        lines.append(f"    PID {m['PID']}: Patient Rh={m['patient_rh']}, Product Rh={m['product_rh']}"
                                     + (f", Date: {m['administration_date']}" if m.get('administration_date') else ""))
            lines.append("")

        lines.append("=" * 100)
        lines.append("Note: ABO compatibility assessed per product class (registry code for blood group O is '0'):")
        lines.append("  RBC: donor-compatible per standard rules (recipient 0<-{0}, A<-{A,0}, B<-{B,0}, AB<-{A,B,AB,0}).")
        lines.append("  FFP/plasma: REVERSED rules (recipient 0<-{0,A,B,AB}, A<-{A,AB}, B<-{B,AB}, AB<-{AB}).")
        lines.append("  PC: ABO-identical preferred but not mandatory; reported as identical vs non-identical (neutral).")
        lines.append("  RhD (RBC/PC): RhD-positive product to RhD-negative patient is flagged for review.")
        lines.append("=" * 100)

        return "\n".join(lines)

    def _patient_index_rows(self) -> pd.DataFrame:
        """
        One real documented row per patient (most complete basic data,
        earliest episode), cached. All patient-level attributes (sex,
        height, weight) are read from these rows so they always belong
        to one and the same documented record.
        """
        if getattr(self, '_index_rows_cache', None) is None:
            self._index_rows_cache = select_patient_index_rows(self.df_all)
        return self._index_rows_cache

    def _calculate_estimated_blood_volume(self) -> pd.Series:
        """
        Calculate estimated blood volume (EBV) in liters using Nadler's formula.

        Nadler's formula:
        - Males:   BV (L) = 0.3669 × H³ + 0.03219 × W + 0.6041
        - Females: BV (L) = 0.3561 × H³ + 0.03308 × W + 0.1833
        Where H = height in meters, W = weight in kg.

        Returns:
            pd.Series indexed by PID with EBV values in liters
        """
        height_col = 'X_433_0_2'  # Height in cm
        weight_col = 'X_433_0_3'  # Weight in kg
        gender_col = 'X_433_0_4'  # Sex (M/F)

        # One REAL documented row per patient - height, weight, and sex all
        # come from the same row (never a per-column composite)
        patient_data = self._patient_index_rows().set_index('PID')

        height_m = pd.to_numeric(patient_data[height_col], errors='coerce').astype('float64') / 100  # cm to m
        weight = pd.to_numeric(patient_data[weight_col], errors='coerce').astype('float64')
        gender = patient_data[gender_col]

        # Nadler's formula
        ebv = pd.Series(np.nan, index=patient_data.index, dtype='float64')
        male_mask = gender == 'M'
        female_mask = gender == 'F'

        ebv.loc[male_mask] = (0.3669 * height_m[male_mask]**3
                              + 0.03219 * weight[male_mask] + 0.6041).values
        ebv.loc[female_mask] = (0.3561 * height_m[female_mask]**3
                                + 0.03308 * weight[female_mask] + 0.1833).values

        # Filter out unreasonable values (< 2L or > 10L)
        ebv[(ebv < 2.0) | (ebv > 10.0)] = np.nan

        n_valid = ebv.notna().sum()
        n_total = len(ebv)
        print(f"  Estimated blood volume (Nadler): {n_valid}/{n_total} patients with valid EBV "
              f"(mean: {ebv.mean():.1f} L, range: {ebv.min():.1f}-{ebv.max():.1f} L)")

        return ebv  # Series indexed by PID, values in liters

    def _calculate_gender_stratified_statistics(self) -> Dict[str, Any]:
        """
        Calculate gender-stratified statistics for administrations and lab values.

        Returns:
            Dictionary with statistics stratified by sex
        """
        gender_col = 'X_433_0_4'  # Sex column
        product_col = 'X_433_7_746'

        results = {
            'administrations_per_patient': {},
            'products_per_patient': {},
            'dosages_by_gender': {},
            'dosages_normalized': {},
            'lab_values_before': {},
            # every stratified cell that holds data but is not summarized is
            # listed here with its n, status, and reason (P: no silent gaps)
            'suppressed_cells': [],
            'suppression_policy': (
                f'statistical minima predefined in code: dosage cells need '
                f'n >= {self.MIN_N_DOSAGE_STATS}, lab-value cells n >= '
                f'{self.MIN_N_LAB_STATS} observations for summary statistics. '
                f'Cells below the minimum are listed in suppressed_cells with '
                f'their n. This is a statistical-validity rule; any '
                f'privacy-motivated small-cell suppression is applied at '
                f'publication level, not in these outputs.'
            )
        }

        # Get patient-level gender from any record
        patient_gender = self._patient_index_rows().set_index('PID')[gender_col]

        gender_map = {'M': 'Male', 'F': 'Female'}

        # Count patients excluded from gender stratification (sex not documented as M/F)
        known_mask = patient_gender.isin(list(gender_map.keys()))
        excluded_pids = patient_gender.index[~known_mask]
        treated_pids = set(self.df['PID'].unique())
        n_excluded_registry = int(len(excluded_pids))
        n_excluded_treated = int(sum(1 for pid in excluded_pids if pid in treated_pids))
        results['excluded_non_mf'] = {
            'n_patients_registry': n_excluded_registry,
            'n_treated_patients': n_excluded_treated
        }
        if n_excluded_registry > 0:
            print(f"  GENDER STRATIFICATION: {n_excluded_registry} patient(s) excluded "
                  f"(sex not documented as M/F), of which {n_excluded_treated} with product administrations")

        for code, label in gender_map.items():
            # Get patients of this gender
            pids_gender = patient_gender[patient_gender == code].index.tolist()

            if len(pids_gender) == 0:
                continue

            # Filter administrations to this gender
            df_gender = self.df[self.df['PID'].isin(pids_gender)]

            if len(df_gender) == 0:
                continue

            # Normalized product codes for this gender's administrations
            # ('1' and '1.0' aggregated together)
            product_norm_gender = df_gender[product_col].map(self._normalize_code)

            # 1. Administrations per patient
            admin_counts = df_gender.groupby('PID').size()
            results['administrations_per_patient'][label] = {
                'n_patients': len(admin_counts),
                'n_administrations': int(admin_counts.sum()),
                'mean': float(admin_counts.mean()),
                'sd': float(admin_counts.std()) if len(admin_counts) > 1 else 0,
                'median': float(admin_counts.median()),
                'q25': float(admin_counts.quantile(0.25)),
                'q75': float(admin_counts.quantile(0.75)),
                'min': int(admin_counts.min()),
                'max': int(admin_counts.max())
            }

            # 2. Products per patient (which products each gender receives)
            # Denominator: TREATED patients of this gender (patients with >= 1 product
            # administration), consistent with the overall 'percent_patients' which
            # divides by treated patients. The registry-wide gender count is kept as
            # an explicit separate field.
            n_treated_gender = df_gender['PID'].nunique()
            products_by_gender = {}
            for prod_code, prod_name in self._canonical_products().items():
                df_prod = df_gender[product_norm_gender == prod_code]
                if len(df_prod) > 0:
                    n_patients_prod = df_prod['PID'].nunique()
                    products_by_gender[prod_name] = {
                        'n_patients': n_patients_prod,
                        'percent_of_gender': float(n_patients_prod / n_treated_gender * 100) if n_treated_gender > 0 else 0,
                        'n_gender_treated': int(n_treated_gender),
                        'n_gender_total_registry': len(pids_gender),
                        'n_administrations': len(df_prod)
                    }
            results['products_per_patient'][label] = products_by_gender

            # 3. Dosages by gender (for each product)
            dosages_by_gender = {}
            dose_col = 'X_433_7_22'
            unit_col = 'X_433_7_734'

            for prod_code, prod_name in self._canonical_products().items():
                df_prod = df_gender[product_norm_gender == prod_code]
                if len(df_prod) == 0:
                    continue

                # Get dosages with valid values
                df_dose = df_prod[df_prod[dose_col].notna()].copy()
                if len(df_dose) == 0:
                    continue

                # Group by unit (normalized codes: '1' and '1.0' aggregated)
                df_dose['unit_str'] = df_dose[unit_col].map(self._normalize_code)
                product_dosages = {}

                for unit_code, unit_name in self._canonical_units().items():
                    df_unit = df_dose[df_dose['unit_str'] == unit_code]
                    if len(df_unit) == 0:
                        continue

                    doses = pd.to_numeric(df_unit[dose_col], errors='coerce').dropna()

                    # Apply same data quality filters as in _calculate_dosage_statistics
                    if prod_name == 'PPSB' and unit_name == 'ml':
                        results['suppressed_cells'].append({
                            'section': 'dosages_by_gender', 'sex': label,
                            'product': prod_name, 'unit': unit_name,
                            'n': int(len(doses)), 'status': 'excluded',
                            'reason': 'dosage exclusion rule: ml implausible for reconstituted PPSB'
                        })
                        continue
                    elif prod_name == 'Fibrinogen' and unit_name == 'IU':
                        results['suppressed_cells'].append({
                            'section': 'dosages_by_gender', 'sex': label,
                            'product': prod_name, 'unit': unit_name,
                            'n': int(len(doses)), 'status': 'excluded',
                            'reason': 'dosage exclusion rule: non-standard unit (standard is mg)'
                        })
                        continue
                    elif prod_name == 'Fibrinogen' and unit_name == 'mg':
                        n_below = int((doses < 500).sum())
                        doses = doses[doses >= 500]  # Exclude implausibly low
                        if n_below > 0 and len(doses) == 0:
                            results['suppressed_cells'].append({
                                'section': 'dosages_by_gender', 'sex': label,
                                'product': prod_name, 'unit': unit_name,
                                'n': 0, 'status': 'excluded',
                                'reason': f'all {n_below} value(s) below the 500 mg plausibility threshold'
                            })
                            continue

                    if len(doses) >= self.MIN_N_DOSAGE_STATS:
                        product_dosages[unit_name] = {
                            'n': len(doses),
                            'mean': float(doses.mean()),
                            'sd': float(doses.std()) if len(doses) > 1 else 0,
                            'median': float(doses.median()),
                            'q25': float(doses.quantile(0.25)),
                            'q75': float(doses.quantile(0.75)),
                            'min': float(doses.min()),
                            'max': float(doses.max()),
                            'total': float(doses.sum())
                        }
                    elif len(doses) > 0:
                        results['suppressed_cells'].append({
                            'section': 'dosages_by_gender', 'sex': label,
                            'product': prod_name, 'unit': unit_name,
                            'n': int(len(doses)), 'status': 'suppressed',
                            'reason': f'below statistical minimum (n < {self.MIN_N_DOSAGE_STATS})'
                        })

                if product_dosages:
                    dosages_by_gender[prod_name] = product_dosages

            results['dosages_by_gender'][label] = dosages_by_gender

            # 3b. Normalized dosages
            # RBC and FFP: dose per liter estimated blood volume (Nadler's formula)
            # Other products: dose per kg body weight
            weight_col = 'X_433_0_3'  # Weight in kg
            dosages_normalized = {}

            # Products normalized by EBV (Nadler's formula)
            EBV_PRODUCTS = {
                'Red blood cell concentrate (RBC)',
                'Fresh Frozen Plasma (FFP)',
            }

            # Get patient-level weight and EBV
            patient_weight = self._patient_index_rows().set_index('PID')[weight_col]
            patient_ebv = self._calculate_estimated_blood_volume()

            # Predefined units for each product
            PRODUCT_UNITS = {
                'Red blood cell concentrate (RBC)': 'ml',
                'Fresh Frozen Plasma (FFP)': 'ml',
                'Platelet concentrate (PC)': 'ml',
                'PPSB': 'IU',
                'Fibrinogen': 'mg',
                'Albumin': 'ml',
                'Antithrombin III (ATIII)': 'IU',
            }

            for prod_code, prod_name in self._canonical_products().items():
                df_prod = df_gender[product_norm_gender == prod_code]
                if len(df_prod) == 0:
                    continue

                unit_name = PRODUCT_UNITS.get(prod_name)
                if unit_name is None:
                    continue

                # Get dosages with valid values
                df_dose = df_prod[df_prod[dose_col].notna()].copy()

                if prod_name in EBV_PRODUCTS:
                    # Normalize by estimated blood volume (Nadler)
                    df_dose['patient_ebv'] = df_dose['PID'].map(patient_ebv)
                    df_dose = df_dose[df_dose['patient_ebv'].notna()]
                else:
                    # Normalize by body weight
                    df_dose['patient_weight'] = df_dose['PID'].map(patient_weight)
                    df_dose = df_dose[df_dose['patient_weight'].notna()]

                if len(df_dose) == 0:
                    continue

                # Get the canonical unit code for filtering
                unit_code = None
                for uc, un in self._canonical_units().items():
                    if un == unit_name:
                        unit_code = uc
                        break

                if unit_code is None or unit_col not in df_dose.columns:
                    print(f"  WARNING: Normalized dosage skipped for {prod_name} ({label}): "
                          f"expected unit '{unit_name}' cannot be resolved")
                    continue

                # STRICT unit filter: only doses documented in the expected unit are
                # normalized. No fallback to all doses - doses in other units must
                # NOT be reported under the expected unit's label.
                df_unit = df_dose[df_dose[unit_col].map(self._normalize_code) == unit_code]
                if len(df_unit) == 0:
                    print(f"  WARNING: Normalized dosage skipped for {prod_name} ({label}): "
                          f"no doses documented in expected unit '{unit_name}' "
                          f"(doses in other units are not normalized under this label)")
                    continue

                doses = pd.to_numeric(df_unit[dose_col], errors='coerce')

                # Apply the same data quality exclusions as _calculate_dosage_statistics
                valid_mask = doses.notna()
                if prod_name == 'PPSB' and unit_name == 'ml':
                    valid_mask &= False  # reconstituted product: ml values implausible
                elif prod_name == 'Fibrinogen' and unit_name == 'IU':
                    valid_mask &= False  # non-standard unit (should be mg)
                elif prod_name == 'Fibrinogen' and unit_name == 'mg':
                    valid_mask &= doses >= 500  # exclude implausibly low values
                doses = doses[valid_mask]
                df_unit = df_unit[valid_mask]
                if len(df_unit) == 0:
                    continue

                if prod_name in EBV_PRODUCTS:
                    # Dose per liter EBV
                    ebv_values = df_unit['patient_ebv']
                    normalized_dose = doses / ebv_values
                    normalized_dose = normalized_dose.dropna()
                    norm_unit = f"{unit_name}/L EBV"
                    norm_method = 'ebv_nadler'
                else:
                    # Dose per kg
                    weights = df_unit['patient_weight']
                    normalized_dose = doses / weights
                    normalized_dose = normalized_dose.dropna()
                    norm_unit = f"{unit_name}/kg"
                    norm_method = 'per_kg'

                if len(normalized_dose) < self.MIN_N_DOSAGE_STATS and len(normalized_dose) > 0:
                    results['suppressed_cells'].append({
                        'section': 'dosages_normalized', 'sex': label,
                        'product': prod_name, 'unit': norm_unit,
                        'n': int(len(normalized_dose)), 'status': 'suppressed',
                        'reason': f'below statistical minimum (n < {self.MIN_N_DOSAGE_STATS})'
                    })
                if len(normalized_dose) >= self.MIN_N_DOSAGE_STATS:
                    entry = {
                        'unit': norm_unit,
                        'normalization': norm_method,
                        'n': len(normalized_dose),
                        'mean': float(normalized_dose.mean()),
                        'sd': float(normalized_dose.std()) if len(normalized_dose) > 1 else 0,
                        'median': float(normalized_dose.median()),
                        'q25': float(normalized_dose.quantile(0.25)),
                        'q75': float(normalized_dose.quantile(0.75)),
                        'min': float(normalized_dose.min()),
                        'max': float(normalized_dose.max())
                    }
                    # Store raw values for EBV products (for violin plots)
                    if norm_method == 'ebv_nadler':
                        entry['values'] = normalized_dose.tolist()
                    dosages_normalized[prod_name] = entry

            results['dosages_normalized'][label] = dosages_normalized

            # 4. Lab values BEFORE administration (for violin plots)
            lab_values_gender = {}
            for lab_name, lab_info in self.LAB_COLUMNS.items():
                before_col = lab_info['before']
                if before_col in df_gender.columns:
                    # identical canonical normalization as the headline table
                    series = self._lab_checker().get_analysis_series(
                        lab_name, before_col=before_col, after_col=None)
                    values = series['before'].loc[df_gender.index].dropna()

                    if 0 < len(values) < self.MIN_N_LAB_STATS:
                        results['suppressed_cells'].append({
                            'section': 'lab_values_before', 'sex': label,
                            'lab': lab_name, 'unit': lab_info['unit'],
                            'n': int(len(values)), 'status': 'suppressed',
                            'reason': f'below statistical minimum (n < {self.MIN_N_LAB_STATS})'
                        })
                    if len(values) >= self.MIN_N_LAB_STATS:
                        lab_values_gender[lab_name] = {
                            'n': len(values),
                            'mean': float(values.mean()),
                            'sd': float(values.std()),
                            'median': float(values.median()),
                            'q25': float(values.quantile(0.25)),
                            'q75': float(values.quantile(0.75)),
                            'min': float(values.min()),
                            'max': float(values.max()),
                            'unit': lab_info['unit'],
                            'normal_range': lab_info['normal_range'],
                            'values': values.tolist()  # For violin plots
                        }

            results['lab_values_before'][label] = lab_values_gender

        return results

    def create_gender_stratified_table(self) -> str:
        """Create formatted table for gender-stratified statistics."""
        if 'by_gender' not in self.results:
            self.results['by_gender'] = self._calculate_gender_stratified_statistics()

        gs = self.results['by_gender']

        lines = []
        lines.append("=" * 100)
        lines.append("GENDER-STRATIFIED STATISTICS")
        lines.append("=" * 100)
        lines.append("")

        excluded = gs.get('excluded_non_mf', {})
        if excluded.get('n_patients_registry', 0) > 0:
            lines.append(f"NOTE: {excluded['n_patients_registry']} patient(s) excluded from gender "
                         f"stratification (sex not documented as M/F), "
                         f"of which {excluded['n_treated_patients']} with product administrations.")
            lines.append("")

        suppressed = gs.get('suppressed_cells', [])
        if suppressed:
            lines.append("CELLS NOT SUMMARIZED (listed with n, status, and reason — no silent gaps):")
            lines.append(f"  Policy: {gs.get('suppression_policy', '')}")
            for cell in suppressed:
                what = cell.get('product') or cell.get('lab')
                lines.append(f"  {cell['sex']:<7} {cell['section']:<20} {what} [{cell['unit']}]: "
                             f"n={cell['n']}, {cell['status']} — {cell['reason']}")
            lines.append("")

        # Administrations per patient by gender
        lines.append("-" * 100)
        lines.append("ADMINISTRATIONS PER PATIENT BY SEX")
        lines.append("-" * 100)
        lines.append("")

        header = f"{'Sex':<10} {'Patients':>10} {'Admins':>10} {'Mean (SD)':>15} {'Median [IQR]':>20} {'Range':>12}"
        lines.append(header)
        lines.append("-" * 80)

        for gender, data in gs.get('administrations_per_patient', {}).items():
            mean_sd = f"{data['mean']:.1f} ({data['sd']:.1f})"
            median_iqr = f"{data['median']:.0f} [{data['q25']:.0f}-{data['q75']:.0f}]"
            range_str = f"{data['min']}-{data['max']}"
            lines.append(f"{gender:<10} {data['n_patients']:>10} {data['n_administrations']:>10} {mean_sd:>15} {median_iqr:>20} {range_str:>12}")

        lines.append("")

        # Dosages by gender
        lines.append("-" * 100)
        lines.append("DOSAGES BY SEX")
        lines.append("-" * 100)
        lines.append("")

        # Collect all products that have dosage data
        all_products_with_dosage = set()
        for gender in ['Male', 'Female']:
            if gender in gs.get('dosages_by_gender', {}):
                all_products_with_dosage.update(gs['dosages_by_gender'][gender].keys())

        for prod_name in sorted(all_products_with_dosage):
            lines.append(f"{prod_name}")

            for gender in ['Male', 'Female']:
                if gender in gs.get('dosages_by_gender', {}) and prod_name in gs['dosages_by_gender'][gender]:
                    for unit, data in gs['dosages_by_gender'][gender][prod_name].items():
                        total_vol = data['total']
                        if unit == 'ml':
                            total_str = f"{total_vol/1000:.1f} L"
                        elif unit == 'mg':
                            total_str = f"{total_vol/1000:.1f} g"
                        elif unit == 'IU':
                            total_str = f"{total_vol/1000:.1f} kIU"
                        else:
                            total_str = f"{total_vol:.0f} {unit}"
                        lines.append(f"  {gender} ({unit}): n={data['n']}, Mean (SD): {data['mean']:.1f} ({data['sd']:.1f}), "
                                   f"Median [{data['q25']:.0f}-{data['q75']:.0f}], Total: {total_str}")
                else:
                    lines.append(f"  {gender}: No data")

            lines.append("")

        # Normalized dosages by gender
        lines.append("-" * 100)
        lines.append("NORMALIZED DOSAGES BY SEX")
        lines.append("-" * 100)
        lines.append("")

        # Collect all products that have normalized dosage data
        all_products_normalized = set()
        for gender in ['Male', 'Female']:
            if gender in gs.get('dosages_normalized', {}):
                all_products_normalized.update(gs['dosages_normalized'][gender].keys())

        if all_products_normalized:
            # Print header
            lines.append(f"{'Product':<40} {'Sex':<8} {'n':>6}   {'Mean (SD)':<18}   {'Median [IQR]':<22}")
            lines.append("-" * 100)

            for prod_name in sorted(all_products_normalized):
                first_line = True
                for gender in ['Male', 'Female']:
                    if gender in gs.get('dosages_normalized', {}) and prod_name in gs['dosages_normalized'][gender]:
                        data = gs['dosages_normalized'][gender][prod_name]
                        unit = data['unit']
                        mean_sd = f"{data['mean']:.1f} ({data['sd']:.1f}) {unit}"
                        median_iqr = f"{data['median']:.1f} [{data['q25']:.1f}-{data['q75']:.1f}]"
                        prod_display = prod_name if first_line else ""
                        lines.append(f"{prod_display:<40} {gender:<8} {data['n']:>6}   {mean_sd:<18}   {median_iqr:<22}")
                        first_line = False
                    else:
                        prod_display = prod_name if first_line else ""
                        lines.append(f"{prod_display:<40} {gender:<8} {'n/a':>6}   {'n/a':<18}   {'n/a':<22}")
                        first_line = False

            lines.append("")
            lines.append("Note: RBC and FFP normalized by estimated blood volume (Nadler's formula).")
            lines.append("      Other products normalized by body weight (dose per kg).")
        else:
            lines.append("No normalized dosage data available (patient height/weight not documented).")

        lines.append("")

        # Lab values before administration by gender
        lines.append("-" * 100)
        lines.append("LABORATORY VALUES BEFORE ADMINISTRATION BY SEX")
        lines.append("-" * 100)
        lines.append("")

        for lab_name in self.LAB_COLUMNS.keys():
            has_data = False
            for gender in ['Male', 'Female']:
                if gender in gs.get('lab_values_before', {}):
                    if lab_name in gs['lab_values_before'][gender]:
                        has_data = True
                        break

            if not has_data:
                continue

            lab_info = self.LAB_COLUMNS[lab_name]
            lines.append(f"{lab_name} ({lab_info['unit']})")
            lines.append(f"  Normal range: {lab_info['normal_range']}")

            for gender in ['Male', 'Female']:
                if gender in gs.get('lab_values_before', {}) and lab_name in gs['lab_values_before'][gender]:
                    data = gs['lab_values_before'][gender][lab_name]
                    lines.append(f"  {gender}: n={data['n']}, Mean (SD): {data['mean']:.2f} ({data['sd']:.2f}), Median: {data['median']:.2f}, Range: {data['min']:.2f}-{data['max']:.2f}")
                else:
                    lines.append(f"  {gender}: Insufficient data")

            lines.append("")

        lines.append("=" * 100)

        return "\n".join(lines)

    def create_summary_tables(self) -> Tuple[str, str]:
        """
        Create formatted summary tables for administration and patient level.

        Returns:
            Tuple of (administration_table, patient_table)
        """
        if not self.results:
            self.calculate_all()

        # Administration-level table
        admin_lines = []
        admin_lines.append("=" * 80)
        admin_lines.append("TREATMENT STATISTICS: ADMINISTRATION LEVEL")
        admin_lines.append("=" * 80)
        admin_lines.append("")

        # Total administrations
        total_info = self.results['administration_level']['total_count']
        admin_lines.append(f"Total administrations: n = {total_info['total_administrations']}")
        admin_lines.append(f"Unique patients: n = {total_info['unique_patients']}")
        admin_lines.append("")
        admin_lines.append("Administrations per patient:")
        app_stats = total_info['administrations_per_patient']
        admin_lines.append(f"  Mean (SD): {app_stats['mean']:.1f} ({app_stats['sd']:.1f})")
        admin_lines.append(f"  Median [IQR]: {app_stats['median']:.0f} [{app_stats['q25']:.0f}-{app_stats['q75']:.0f}]")
        admin_lines.append(f"  Range: {app_stats['min']}-{app_stats['max']}")
        admin_lines.append("")

        # Product distribution
        admin_lines.append("-" * 80)
        admin_lines.append("PRODUCT DISTRIBUTION")
        admin_lines.append("-" * 80)
        products = self.results['administration_level']['products']['products']
        for product_name in sorted(products.keys()):
            data = products[product_name]
            admin_lines.append(f"{product_name:45s} {data['n']:>5d} ({data['percent']:>5.1f}%)")
        admin_lines.append("")

        # Temporal distribution
        admin_lines.append("-" * 80)
        admin_lines.append("TEMPORAL DISTRIBUTION (by month)")
        admin_lines.append("-" * 80)
        temporal = self.results['administration_level']['temporal']
        if 'monthly_distribution' in temporal:
            for month in sorted(temporal['monthly_distribution'].keys()):
                count = temporal['monthly_distribution'][month]
                admin_lines.append(f"{month:20s} {count:>5d}")
        admin_lines.append("")

        # Dosages
        admin_lines.append("-" * 80)
        admin_lines.append("DOSAGE STATISTICS BY PRODUCT")
        admin_lines.append("-" * 80)
        dosages = self.results['administration_level']['dosages']
        for product_name in sorted(dosages.keys()):
            admin_lines.append(f"\n{product_name}:")
            for unit, stats in dosages[product_name].items():
                admin_lines.append(f"  Unit: {unit}")
                admin_lines.append(f"    n = {stats['n']}")
                admin_lines.append(f"    Mean (SD): {stats['mean']:.1f} ({stats['sd']:.1f})")
                admin_lines.append(f"    Median [IQR]: {stats['median']:.1f} [{stats['q25']:.1f}-{stats['q75']:.1f}]")
                admin_lines.append(f"    Range: {stats['min']:.1f}-{stats['max']:.1f}")
        admin_lines.append("")

        # Lab values
        admin_lines.append("-" * 80)
        admin_lines.append("LABORATORY VALUES (Before → After)")
        admin_lines.append("-" * 80)
        labs = self.results['administration_level']['lab_values']
        for lab_name in labs.keys():
            lab_data = labs[lab_name]
            admin_lines.append(f"\n{lab_name} ({lab_data['unit']})")
            admin_lines.append(f"  Normal range: {lab_data['normal_range']}")
            admin_lines.append(f"  n = {lab_data['before']['n']} (paired measurements)")
            admin_lines.append(f"  Before:  Mean (SD) = {lab_data['before']['mean']:.2f} ({lab_data['before']['sd']:.2f}), "
                             f"Median = {lab_data['before']['median']:.2f}")
            admin_lines.append(f"  After:   Mean (SD) = {lab_data['after']['mean']:.2f} ({lab_data['after']['sd']:.2f}), "
                             f"Median = {lab_data['after']['median']:.2f}")
            admin_lines.append(f"  Change:  Mean (SD) = {lab_data['change']['mean']:.2f} ({lab_data['change']['sd']:.2f}), "
                             f"Median = {lab_data['change']['median']:.2f}")

        # Patient summary section
        patient_summary = self.results.get('patient_summary', {})
        if patient_summary:
            admin_lines.append("")
            admin_lines.append("-" * 80)
            admin_lines.append("PATIENT SUMMARY")
            admin_lines.append("-" * 80)
            admin_lines.append(f"Total patients in registry: {patient_summary['total_patients']}")
            admin_lines.append("")

            wp = patient_summary['patients_with_product']
            admin_lines.append(f"Patients WITH product administrations: {wp['total']}")
            admin_lines.append(f"  - With follow-up data: {wp['with_followup']}")
            admin_lines.append(f"  - Without follow-up data: {wp['without_followup']}")
            admin_lines.append("")

            wop = patient_summary['patients_without_product']
            admin_lines.append(f"Patients WITHOUT product administrations: {wop['total']}")
            admin_lines.append(f"  - With follow-up only (ERROR - needs review): {wop['followup_only_ERROR']}")
            admin_lines.append(f"  - With baseline only: {wop['baseline_only']}")
            admin_lines.append(f"  - With only basic demographics: {wop['demographics_only']}")

            if wop['total'] > 0:
                admin_lines.append("")
                admin_lines.append("Patient IDs WITHOUT products (for manual review):")
                patient_ids = wop.get('patient_ids', [])
                for i in range(0, len(patient_ids), 10):
                    batch = patient_ids[i:i+10]
                    admin_lines.append("  " + ", ".join(str(pid) for pid in batch))

        admin_lines.append("\n" + "=" * 80)

        # Patient-level table
        patient_lines = []
        patient_lines.append("=" * 80)
        patient_lines.append("TREATMENT STATISTICS: PATIENT LEVEL")
        patient_lines.append("=" * 80)
        patient_lines.append("")

        # Patient counts
        patient_info = self.results['patient_level']['patient_count']
        patient_lines.append(f"Unique patients: n = {patient_info['n_unique_patients']}")
        patient_lines.append(f"Total administrations: n = {patient_info['n_total_administrations']}")
        patient_lines.append("")

        # Administrations per patient
        patient_lines.append("-" * 80)
        patient_lines.append("ADMINISTRATIONS PER PATIENT")
        patient_lines.append("-" * 80)
        freq_stats = self.results['patient_level']['administration_frequency']['statistics']
        patient_lines.append(f"Mean (SD): {freq_stats['mean']:.1f} ({freq_stats['sd']:.1f})")
        patient_lines.append(f"Median [IQR]: {freq_stats['median']:.0f} [{freq_stats['q25']:.0f}-{freq_stats['q75']:.0f}]")
        patient_lines.append(f"Range: {freq_stats['min']}-{freq_stats['max']}")
        patient_lines.append("")

        # Distribution
        patient_lines.append("Distribution:")
        freq_dist = self.results['patient_level']['administration_frequency']['distribution']
        for category in sorted(freq_dist.keys(), key=lambda x: int(x.split()[0])):
            data = freq_dist[category]
            patient_lines.append(f"  {category:30s} {data['n_patients']:>5d} patients ({data['percent']:>5.1f}%)")
        patient_lines.append("")

        # Products per patient
        patient_lines.append("-" * 80)
        patient_lines.append("PRODUCTS RECEIVED PER PATIENT")
        patient_lines.append("-" * 80)
        products_pp = self.results['patient_level']['products_per_patient']
        for product_name in sorted(products_pp.keys()):
            data = products_pp[product_name]
            patient_lines.append(f"{product_name:45s}")
            patient_lines.append(f"  Patients receiving: {data['n_patients']:>5d} ({data['percent_patients']:>5.1f}%)")
            patient_lines.append(f"  Total administrations: {data['n_administrations']:>5d}")
            patient_lines.append(f"  Mean per patient: {data['administrations_per_patient']:>5.1f}")

        patient_lines.append("\n" + "=" * 80)

        return "\n".join(admin_lines), "\n".join(patient_lines)

    def _export_dosage_exclusions(self, output_path: Path) -> None:
        """
        Export the dosage data-quality exclusion log to CSV.

        Writes '<output_dir>/dosage_exclusions.csv' with one row per applied
        exclusion rule (product/unit combination).
        """
        exclusions = getattr(self, 'data_quality_exclusions', None)
        if exclusions is None:
            return

        exclusions_csv = output_path / "dosage_exclusions.csv"
        with open(exclusions_csv, 'w', newline='') as f:
            f.write(self._csv_row(["Product_Unit", "Original_N", "Excluded_N",
                                   "Retained_N", "Reason"]))
            for key, entry in exclusions.items():
                f.write(self._csv_row([key, entry['original_n'],
                                       entry['excluded_n'], entry['retained_n'],
                                       str(entry.get('reason', ''))]))
        print(f"Dosage exclusion log exported to: {exclusions_csv} "
              f"({len(exclusions)} exclusion rule(s) applied)")

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
        json_file = output_path / "treatment_statistics_detailed.json"
        with open(json_file, 'w') as f:
            json.dump(_json_sanitize(self.results), f, indent=2, allow_nan=False)
        print(f"Detailed results exported to: {json_file}")

        # Export formatted tables
        admin_table, patient_table = self.create_summary_tables()

        # Administration-level table
        admin_file = output_path / "treatment_statistics_administration_level.txt"
        with open(admin_file, 'w') as f:
            f.write(admin_table)
        print(f"Administration-level table exported to: {admin_file}")

        # Patient-level table
        patient_file = output_path / "treatment_statistics_patient_level.txt"
        with open(patient_file, 'w') as f:
            f.write(patient_table)
        print(f"Patient-level table exported to: {patient_file}")

        # Combined table
        combined_file = output_path / "treatment_statistics_combined.txt"
        with open(combined_file, 'w') as f:
            f.write(admin_table)
            f.write("\n\n\n")
            f.write(patient_table)
        print(f"Combined table exported to: {combined_file}")

        # Data completeness table
        completeness_table = self.create_data_completeness_table()
        completeness_file = output_path / "data_completeness_by_product.txt"
        with open(completeness_file, 'w') as f:
            f.write(completeness_table)
        print(f"Data completeness table exported to: {completeness_file}")

        # Export dosage data-quality exclusion log as CSV (previously stdout-only)
        self._export_dosage_exclusions(output_path)

        # Export data completeness as CSV for easy import
        completeness_csv = output_path / "data_completeness_by_product.csv"
        with open(completeness_csv, 'w') as f:
            f.write("Product,Total,With Dosage,Dosage %,With Indication,Indication %,Primary Lab,With Lab Before,Lab Before %,With Lab After,Lab After %\n")
            for product_name, data in sorted(self.results['data_completeness'].items(), key=lambda x: x[1]['total'], reverse=True):
                clean_name = product_name.split('(')[0].strip() if '(' in product_name else product_name
                row = [
                    clean_name,
                    str(data['total']),
                    str(data['with_dosage']) if data['with_dosage'] is not None else '',
                    f"{data['with_dosage_pct']:.1f}" if data['with_dosage_pct'] is not None else '',
                    str(data['with_indication']) if data['with_indication'] is not None else '',
                    f"{data['with_indication_pct']:.1f}" if data['with_indication_pct'] is not None else '',
                    data['primary_lab'] if data['primary_lab'] else '',
                    str(data['with_lab_before']) if data['with_lab_before'] is not None else '',
                    f"{data['with_lab_before_pct']:.1f}" if data['with_lab_before_pct'] is not None else '',
                    str(data['with_lab_after']) if data['with_lab_after'] is not None else '',
                    f"{data['with_lab_after_pct']:.1f}" if data['with_lab_after_pct'] is not None else ''
                ]
                f.write(self._csv_row(row))
        print(f"Data completeness CSV exported to: {completeness_csv}")

        # Autotransfusion (Cell Salvage) statistics table
        autotransfusion_table = self.create_autotransfusion_table()
        autotransfusion_file = output_path / "autotransfusion_statistics.txt"
        with open(autotransfusion_file, 'w') as f:
            f.write(autotransfusion_table)
        print(f"Autotransfusion statistics exported to: {autotransfusion_file}")

        # Export autotransfusion as CSV
        auto_data = self.results.get('autotransfusion', {})
        if auto_data.get('total', 0) > 0:
            auto_csv = output_path / "autotransfusion_statistics.csv"
            with open(auto_csv, 'w') as f:
                f.write("Parameter,Unit,n,Completeness %,Mean,SD,Median,Q25,Q75,Min,Max\n")
                for param_key, param_data in auto_data.get('parameters', {}).items():
                    row = [
                        param_data['name'],
                        param_data['unit'],
                        str(param_data['n']),
                        f"{param_data['completeness_pct']:.1f}",
                        f"{param_data.get('mean', ''):.1f}" if param_data.get('mean') is not None else '',
                        f"{param_data.get('sd', ''):.1f}" if param_data.get('sd') is not None else '',
                        f"{param_data.get('median', ''):.1f}" if param_data.get('median') is not None else '',
                        f"{param_data.get('q25', ''):.1f}" if param_data.get('q25') is not None else '',
                        f"{param_data.get('q75', ''):.1f}" if param_data.get('q75') is not None else '',
                        f"{param_data.get('min', ''):.1f}" if param_data.get('min') is not None else '',
                        f"{param_data.get('max', ''):.1f}" if param_data.get('max') is not None else ''
                    ]
                    f.write(self._csv_row(row))
            print(f"Autotransfusion CSV exported to: {auto_csv}")

        # Blood type documentation and compatibility table
        blood_type_table = self.create_blood_type_table()
        blood_type_file = output_path / "blood_type_compatibility.txt"
        with open(blood_type_file, 'w') as f:
            f.write(blood_type_table)
        print(f"Blood type compatibility table exported to: {blood_type_file}")

        # Export blood type as CSV
        bt_data = self.results.get('blood_type', {})
        if bt_data:
            bt_csv = output_path / "blood_type_compatibility.csv"
            with open(bt_csv, 'w') as f:
                f.write("Product,Total,Patient ABO,Patient ABO %,Product ABO,Product ABO %,"
                        "Either ABO,Either ABO %,Both ABO,Both ABO %,"
                        "ABO Assessed,ABO Identical,ABO Compatible Non-Identical,ABO Non-Identical (PC neutral),"
                        "ABO Incompatible,ABO Not Assessable,"
                        "Patient Rh,Patient Rh %,Product Rh,Product Rh %,"
                        "RhD Checked,RhD Flagged,RhD Not Flagged,RhD Not Assessable\n")
                for product_name, data in bt_data.items():
                    abo = data['abo']
                    rh = data['rh']
                    is_pc = abo['compatibility_class'] == 'PC'
                    row = [
                        product_name,
                        str(data['total']),
                        str(abo['patient_documented']),
                        f"{abo['patient_documented_pct']:.1f}",
                        str(abo['product_documented']),
                        f"{abo['product_documented_pct']:.1f}",
                        str(abo['either_documented']),
                        f"{abo['either_documented_pct']:.1f}",
                        str(abo['both_documented']),
                        f"{abo['both_documented_pct']:.1f}",
                        str(abo['n_assessed']),
                        str(abo['identical']),
                        '' if is_pc else str(abo['compatible_non_identical']),
                        str(abo['non_identical']) if is_pc else '',
                        '' if is_pc else str(abo['incompatible']),
                        str(abo['not_assessable']),
                        str(rh['patient_documented']),
                        f"{rh['patient_documented_pct']:.1f}",
                        str(rh['product_documented']),
                        f"{rh['product_documented_pct']:.1f}",
                        'Yes' if rh['rhd_checked'] else 'No',
                        str(rh['rhd_flagged']) if rh['rhd_checked'] else '',
                        str(rh['rhd_unflagged']) if rh['rhd_checked'] else '',
                        str(rh['rhd_not_assessable']) if rh['rhd_checked'] else ''
                    ]
                    f.write(self._csv_row(row))
            print(f"Blood type CSV exported to: {bt_csv}")

            # Export ABO-incompatible and RhD-flagged records for review
            all_flagged = []
            for product_name, data in bt_data.items():
                all_flagged.extend(data['abo'].get('incompatible_details', []))
                all_flagged.extend(data['rh'].get('rhd_flagged_details', []))

            if all_flagged:
                flagged_csv = output_path / "blood_type_incompatible_for_review.csv"
                with open(flagged_csv, 'w') as f:
                    f.write("PID,Product,Issue,Patient_ABO,Product_ABO,Patient_Rh,Product_Rh,"
                            "Administration_Date,Dosage,Has_Followup,Followup_Date,Followup_Window,"
                            "Followup_Conflict,"
                            "Problems_Reported,Problem_Details,Anaemia_at_Followup,Subsequent_Transfusions\n")
                    for m in all_flagged:
                        row = [
                            str(m['PID']),
                            m.get('product', ''),
                            m.get('issue', ''),
                            str(m.get('patient_abo', '')) if m.get('patient_abo') is not None else '',
                            str(m.get('product_abo', '')) if m.get('product_abo') is not None else '',
                            str(m.get('patient_rh', '')) if m.get('patient_rh') is not None else '',
                            str(m.get('product_rh', '')) if m.get('product_rh') is not None else '',
                            m.get('administration_date', '') or '',
                            '' if m.get('dosage') is None else str(m.get('dosage')),
                            'Yes' if m.get('has_followup') else 'No',
                            m.get('followup_date', '') or '',
                            m.get('followup_window', '') or '',
                            'Yes' if m.get('followup_conflict') else 'No',
                            m.get('problems_reported', '') or '',
                            m.get('problem_details', '') or '',
                            m.get('anaemia_at_followup', '') or '',
                            m.get('subsequent_transfusions', '') or ''
                        ]
                        f.write(self._csv_row(row))
                print(f"Blood type records for review exported to: {flagged_csv}")
                print(f"  WARNING: {len(all_flagged)} ABO-incompatible/RhD-flagged record(s) detected - see file for details")

        # Gender-stratified statistics table
        gender_table = self.create_gender_stratified_table()
        gender_file = output_path / "gender_stratified_statistics.txt"
        with open(gender_file, 'w') as f:
            f.write(gender_table)
        print(f"Gender-stratified statistics exported to: {gender_file}")

        # Export gender-stratified lab values as CSV (for violin plots)
        gs_data = self.results.get('by_gender', {})
        if gs_data.get('lab_values_before'):
            lab_csv = output_path / "lab_values_by_gender.csv"
            with open(lab_csv, 'w') as f:
                f.write("Lab_Value,Sex,n,Mean,SD,Median,Q25,Q75,Min,Max,Unit,Normal_Range\n")
                for gender in ['Male', 'Female']:
                    if gender in gs_data.get('lab_values_before', {}):
                        for lab_name, data in gs_data['lab_values_before'][gender].items():
                            row = [
                                lab_name,
                                gender,
                                str(data['n']),
                                f"{data['mean']:.2f}",
                                f"{data['sd']:.2f}",
                                f"{data['median']:.2f}",
                                f"{data['q25']:.2f}",
                                f"{data['q75']:.2f}",
                                f"{data['min']:.2f}",
                                f"{data['max']:.2f}",
                                data['unit'],
                                data['normal_range']
                            ]
                            f.write(self._csv_row(row))
            print(f"Lab values by gender CSV exported to: {lab_csv}")

        # Export dosages by gender as CSV
        if gs_data.get('dosages_by_gender'):
            dosage_csv = output_path / "dosages_by_gender.csv"
            with open(dosage_csv, 'w') as f:
                f.write("Product,Unit,Sex,n,Mean,SD,Median,Q25,Q75,Min,Max,Total\n")
                for gender in ['Male', 'Female']:
                    if gender in gs_data.get('dosages_by_gender', {}):
                        for prod_name, units in gs_data['dosages_by_gender'][gender].items():
                            for unit, data in units.items():
                                row = [
                                    prod_name,
                                    unit,
                                    gender,
                                    str(data['n']),
                                    f"{data['mean']:.1f}",
                                    f"{data['sd']:.1f}",
                                    f"{data['median']:.1f}",
                                    f"{data['q25']:.1f}",
                                    f"{data['q75']:.1f}",
                                    f"{data['min']:.1f}",
                                    f"{data['max']:.1f}",
                                    f"{data['total']:.1f}"
                                ]
                                f.write(self._csv_row(row))
            print(f"Dosages by gender CSV exported to: {dosage_csv}")

            # Also export formatted text table
            dosage_txt = output_path / "dosages_by_gender.txt"
            with open(dosage_txt, 'w') as f:
                f.write("=" * 100 + "\n")
                f.write("BLOOD PRODUCT DOSAGES BY GENDER\n")
                f.write("=" * 100 + "\n\n")

                # Collect all products
                all_products = set()
                for gender in ['Male', 'Female']:
                    if gender in gs_data.get('dosages_by_gender', {}):
                        all_products.update(gs_data['dosages_by_gender'][gender].keys())

                # Sort products by total administrations (male + female)
                product_totals = {}
                for prod in all_products:
                    total_n = 0
                    for gender in ['Male', 'Female']:
                        if gender in gs_data.get('dosages_by_gender', {}) and prod in gs_data['dosages_by_gender'][gender]:
                            for unit, data in gs_data['dosages_by_gender'][gender][prod].items():
                                total_n += data['n']
                    product_totals[prod] = total_n

                sorted_products = sorted(all_products, key=lambda x: product_totals.get(x, 0), reverse=True)

                for prod_name in sorted_products:
                    f.write("-" * 100 + "\n")
                    f.write(f"{prod_name}\n")
                    f.write("-" * 100 + "\n")

                    # Get unit for this product
                    unit = None
                    for gender in ['Male', 'Female']:
                        if gender in gs_data.get('dosages_by_gender', {}) and prod_name in gs_data['dosages_by_gender'][gender]:
                            unit = list(gs_data['dosages_by_gender'][gender][prod_name].keys())[0]
                            break

                    if unit:
                        f.write(f"\n{'Sex':<10} {'n':>6}   {'Mean (SD)':<20}   {'Median [IQR]':<25}   {'Min':>8}   {'Max':>8}   {'Total':>12}\n")
                        f.write("-" * 100 + "\n")

                        for gender in ['Male', 'Female']:
                            if gender in gs_data.get('dosages_by_gender', {}) and prod_name in gs_data['dosages_by_gender'][gender]:
                                if unit in gs_data['dosages_by_gender'][gender][prod_name]:
                                    data = gs_data['dosages_by_gender'][gender][prod_name][unit]
                                    mean_sd = f"{data['mean']:.0f} ({data['sd']:.0f})"
                                    median_iqr = f"{data['median']:.0f} [{data['q25']:.0f}-{data['q75']:.0f}]"

                                    # Format total with appropriate unit
                                    total = data['total']
                                    if unit == 'ml' and total >= 1000:
                                        total_str = f"{total/1000:.1f} L"
                                    elif unit == 'mg' and total >= 1000:
                                        total_str = f"{total/1000:.1f} g"
                                    elif unit == 'IU' and total >= 1000:
                                        total_str = f"{total/1000:.0f} kIU"
                                    else:
                                        total_str = f"{total:.0f} {unit}"

                                    f.write(f"{gender:<10} {data['n']:>6}   {mean_sd:<20}   {median_iqr:<25}   {data['min']:>8.0f}   {data['max']:>8.0f}   {total_str:>12}\n")
                            else:
                                f.write(f"{gender:<10}      -   {'n/a':<20}   {'n/a':<25}   {'n/a':>8}   {'n/a':>8}   {'n/a':>12}\n")

                        f.write(f"\nUnit: {unit}\n")
                    f.write("\n")

                f.write("=" * 100 + "\n")
                f.write("Note: Products sorted by total number of administrations (descending)\n")
                f.write("=" * 100 + "\n")
            print(f"Dosages by gender table exported to: {dosage_txt}")

        # Export normalized dosages as CSV and TXT
        if gs_data.get('dosages_normalized'):
            # CSV export
            dose_norm_csv = output_path / "dosages_normalized_by_gender.csv"
            with open(dose_norm_csv, 'w') as f:
                f.write("Product,Unit,Normalization,Sex,n,Mean,SD,Median,Q25,Q75,Min,Max\n")
                for gender in ['Male', 'Female']:
                    if gender in gs_data.get('dosages_normalized', {}):
                        for prod_name, data in gs_data['dosages_normalized'][gender].items():
                            row = [
                                prod_name,
                                data['unit'],
                                data.get('normalization', 'per_kg'),
                                gender,
                                str(data['n']),
                                f"{data['mean']:.1f}",
                                f"{data['sd']:.1f}",
                                f"{data['median']:.1f}",
                                f"{data['q25']:.1f}",
                                f"{data['q75']:.1f}",
                                f"{data['min']:.1f}",
                                f"{data['max']:.1f}"
                            ]
                            f.write(self._csv_row(row))
            print(f"Normalized dosages CSV exported to: {dose_norm_csv}")

            # TXT export
            dose_norm_txt = output_path / "dosages_normalized_by_gender.txt"
            with open(dose_norm_txt, 'w') as f:
                f.write("=" * 100 + "\n")
                f.write("NORMALIZED BLOOD PRODUCT DOSAGES BY GENDER\n")
                f.write("=" * 100 + "\n\n")
                f.write("RBC and FFP: dose per liter estimated blood volume (Nadler's formula)\n")
                f.write("Other products: dose per kg body weight\n\n")

                # Collect all products
                all_products = set()
                for gender in ['Male', 'Female']:
                    if gender in gs_data.get('dosages_normalized', {}):
                        all_products.update(gs_data['dosages_normalized'][gender].keys())

                # Sort products by total n
                product_totals = {}
                for prod in all_products:
                    total_n = 0
                    for gender in ['Male', 'Female']:
                        if gender in gs_data.get('dosages_normalized', {}) and prod in gs_data['dosages_normalized'][gender]:
                            total_n += gs_data['dosages_normalized'][gender][prod]['n']
                    product_totals[prod] = total_n

                sorted_products = sorted(all_products, key=lambda x: product_totals.get(x, 0), reverse=True)

                # Table header
                f.write(f"{'Product':<40} {'Sex':<8} {'n':>6}   {'Mean (SD)':<20}   {'Median [IQR]':<25}\n")
                f.write("-" * 100 + "\n")

                for prod_name in sorted_products:
                    first_line = True
                    for gender in ['Male', 'Female']:
                        if gender in gs_data.get('dosages_normalized', {}) and prod_name in gs_data['dosages_normalized'][gender]:
                            data = gs_data['dosages_normalized'][gender][prod_name]
                            unit = data['unit']
                            mean_sd = f"{data['mean']:.1f} ({data['sd']:.1f}) {unit}"
                            median_iqr = f"{data['median']:.1f} [{data['q25']:.1f}-{data['q75']:.1f}]"
                            prod_display = prod_name if first_line else ""
                            f.write(f"{prod_display:<40} {gender:<8} {data['n']:>6}   {mean_sd:<20}   {median_iqr:<25}\n")
                            first_line = False
                        else:
                            prod_display = prod_name if first_line else ""
                            f.write(f"{prod_display:<40} {gender:<8} {'n/a':>6}   {'n/a':<20}   {'n/a':<25}\n")
                            first_line = False
                    f.write("\n")

                f.write("=" * 100 + "\n")
                f.write("Note: RBC and FFP normalized by estimated blood volume (Nadler's formula).\n")
                f.write("      Nadler (Males):   BV = 0.3669*H^3 + 0.03219*W + 0.6041\n")
                f.write("      Nadler (Females): BV = 0.3561*H^3 + 0.03308*W + 0.1833\n")
                f.write("      (H in meters, W in kg, BV in liters)\n")
                f.write("      Other products normalized by body weight (dose per kg).\n")
                f.write("=" * 100 + "\n")
            print(f"Normalized dosages table exported to: {dose_norm_txt}")

        # Export patient IDs without products for manual review
        patient_summary = self.results.get('patient_summary', {})
        wop = patient_summary.get('patients_without_product', {})
        if wop.get('total', 0) > 0:
            patient_ids_file = output_path / "patients_without_product_for_review.csv"
            with open(patient_ids_file, 'w') as f:
                f.write("PID,Note\n")
                for pid in wop.get('patient_ids', []):
                    f.write(f"{pid},Patient registered but no product administration recorded\n")
            print(f"Patient IDs for review exported to: {patient_ids_file}")


def run_treatment_analysis(data_file: str, output_dir: str = ".") -> TreatmentDescriptives:
    """
    Run complete treatment analysis workflow.

    Args:
        data_file: Path to CSV data file
        output_dir: Directory for output files

    Returns:
        TreatmentDescriptives object with calculated results
    """
    print("=" * 80)
    print("TREATMENT STATISTICS ANALYSIS")
    print("=" * 80)

    # Load data
    print("\nLoading data...")
    loader = TransfusionDataLoader()
    loader.load_data(data_file, validate=False)

    # Calculate statistics
    treatment = TreatmentDescriptives(loader)
    treatment.calculate_all()

    # Display tables
    admin_table, patient_table = treatment.create_summary_tables()
    print("\n" + admin_table)
    print("\n" + patient_table)

    # Export results
    print("\nExporting results...")
    treatment.export_results(output_dir)

    print("\nAnalysis complete!")
    return treatment


if __name__ == "__main__":
    # Example usage
    treatment = run_treatment_analysis("../test_data_150patients.csv", output_dir=".")
