"""
Lab Value Data Quality Module

This module handles unit detection and standardization for laboratory values
in transfusion registry data. Blood product registries often have unit confusion
issues where values are entered in different units (e.g., g/dl vs mg/dl).

Key features:
- Detects dominant unit based on value distribution
- Flags values entered in minority/wrong units
- Exports problematic records for manual review
- Returns standardized data for visualization

Author: Elina Nuerenberg-Goloub with Claude Opus 4.5 by Anthropic
Date: 2026-01-22
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import os
import csv

from transfusion_registry_mapping import CLINICAL_RANGE_REGISTRY


def _registry_range(parameter):
    """(min, max) from the central physician range registry."""
    p = CLINICAL_RANGE_REGISTRY['parameters'][parameter]
    return (p['min'], p['max'])

# Lab value expected ranges and unit detection thresholds
# Format: {
#     'parameter': {
#         'expected_unit': 'unit string',
#         'normal_range': (min, max),  # in expected unit
#         'unit_detection': {
#             'threshold': value,  # values below this are likely in wrong unit
#             'multiply_by': factor,  # to convert to expected unit
#             'wrong_unit': 'unit string'  # what the wrong unit likely is
#         }
#     }
# }

LAB_VALUE_CONFIG = {
    'Platelets': {
        'expected_unit': '/µl',
        'normal_range': (150000, 400000),
        'clinical_range': _registry_range('platelets'),  # physicians' table, canonical /µl
        'unit_detection': {
            # If >90% of values are <1000, they're likely in thousands
            'threshold': 1000,
            'multiply_by': 1000,
            'wrong_unit': 'thousands/µl',
            'corrected_unit': '/µl (×1000)'
        }
    },
    'Serum albumin': {
        'expected_unit': 'g/dl',  # Standard clinical unit
        'normal_range': (3.5, 5.0),
        'clinical_range': _registry_range('serum_albumin'),  # physicians' table 0-7000 mg/dl, canonical g/dl
        'unit_detection': {
            # If values are >100, they're likely in mg/dl
            'threshold': 100,
            'divide_by': 1000,
            'wrong_unit': 'mg/dl',
            'corrected_unit': 'g/dl'
        }
    },
    'Hemoglobin': {
        'expected_unit': 'g/dl',
        'normal_range': (12.0, 17.5),  # Varies by sex
        'clinical_range': _registry_range('hemoglobin'),
        'unit_detection': None  # Usually entered correctly
    },
    "Quick's test": {
        'expected_unit': '%',
        'normal_range': (70, 120),
        'clinical_range': _registry_range('quicks_test'),
        'unit_detection': None
    },
    'Fibrinogen': {
        'expected_unit': 'mg/dl',
        'normal_range': (200, 400),
        'clinical_range': _registry_range('fibrinogen'),
        'unit_detection': None
    },
    'Ferritin': {
        'expected_unit': 'µg/l',
        'normal_range': (20, 250),  # Varies by sex
        'clinical_range': _registry_range('ferritin'),
        'unit_detection': None
    },
    'Transferrin saturation': {
        'expected_unit': '%',
        'normal_range': (20, 50),
        'clinical_range': _registry_range('transferrin'),
        'unit_detection': None
    },
    'Antithrombin activity': {
        'expected_unit': '%',
        'normal_range': (80, 120),
        'clinical_range': _registry_range('atiii_activity'),
        'unit_detection': None
    },
}

# Column mappings (same as in visualize_treatments.py)
LAB_COLUMNS = {
    'Hemoglobin': {'before': 'X_433_7_614', 'after': 'X_433_7_615'},
    'Platelets': {'before': 'X_433_7_37', 'after': 'X_433_7_587'},
    "Quick's test": {'before': 'X_433_7_374', 'after': 'X_433_7_596'},
    'Fibrinogen': {'before': 'X_433_7_585', 'after': 'X_433_7_586'},
    'Serum albumin': {'before': 'X_433_7_603', 'after': 'X_433_7_591'},
    'Ferritin': {'before': 'X_433_7_736', 'after': 'X_433_7_735'},
    'Transferrin saturation': {'before': 'X_433_7_589', 'after': 'X_433_7_590'},
    'Antithrombin activity': {'before': 'X_433_7_601', 'after': 'X_433_7_602'},
}


class LabValueQualityChecker:
    """Checks and standardizes lab value units in transfusion registry data."""

    def __init__(self, df: pd.DataFrame, patient_id_col: str = 'PID'):
        """
        Initialize the quality checker.

        Args:
            df: DataFrame with raw lab value data
            patient_id_col: Name of the patient ID column (registry export uses 'PID')
        """
        self.df = df.copy()
        # Resolve the patient ID column: use the requested column if present,
        # otherwise fall back to known alternatives so exported problematic-record
        # CSVs always carry patient identifiers when available.
        candidates = [patient_id_col, 'PID', 'patient_id', 'Patient_ID', 'pid']
        self.patient_id_col = next(
            (c for c in candidates if c in self.df.columns), patient_id_col)
        if self.patient_id_col not in self.df.columns:
            print(f"  WARNING: No patient ID column found (tried: {candidates}); "
                  f"problematic-record exports will lack patient identifiers")
        self.issues = {}  # Will store detected issues per lab parameter
        self.corrections = {}  # Will store applied corrections

    def detect_unit_issues(self, lab_name: str) -> Dict:
        """
        Detect unit inconsistencies for a specific lab parameter.

        Args:
            lab_name: Name of the lab parameter

        Returns:
            Dictionary with detection results
        """
        if lab_name not in LAB_COLUMNS or lab_name not in LAB_VALUE_CONFIG:
            return {'status': 'skipped', 'reason': 'No configuration'}

        config = LAB_VALUE_CONFIG[lab_name]
        cols = LAB_COLUMNS[lab_name]
        before_col, after_col = cols['before'], cols['after']

        # Check if columns exist
        if before_col not in self.df.columns or after_col not in self.df.columns:
            return {'status': 'skipped', 'reason': 'Columns not found'}

        # Get all values (before and after combined)
        before_vals = self.df[before_col].dropna().values
        after_vals = self.df[after_col].dropna().values
        all_vals = np.concatenate([before_vals, after_vals])

        if len(all_vals) == 0:
            return {'status': 'skipped', 'reason': 'No data'}

        result = {
            'lab_name': lab_name,
            'expected_unit': config['expected_unit'],
            'n_total': len(all_vals),
            'n_before': len(before_vals),
            'n_after': len(after_vals),
            'value_range': (float(np.min(all_vals)), float(np.max(all_vals))),
            'median': float(np.median(all_vals)),
        }

        # Check for unit detection rules
        if config['unit_detection'] is None:
            result['status'] = 'ok'
            result['unit_issue'] = False
            return result

        detection = config['unit_detection']
        threshold = detection['threshold']

        if 'multiply_by' in detection:
            # Deterministic per-value rule: POSITIVE values below the threshold
            # are on the smaller-unit scale and are converted; values at/above
            # the threshold are already in the expected unit and stay unchanged;
            # non-positive values are impossible and excluded, never scaled.
            n_below = int(np.sum(all_vals[all_vals > 0] < threshold))
            n_nonpositive = int(np.sum(all_vals <= 0))
            pct_below = n_below / len(all_vals) * 100

            result['n_below_threshold'] = n_below
            result['pct_below_threshold'] = pct_below
            result['n_nonpositive'] = n_nonpositive
            result['threshold'] = threshold

            if n_below > 0 or n_nonpositive > 0:
                result['status'] = 'unit_issue_detected'
                result['unit_issue'] = True
                result['dominant_unit'] = detection['wrong_unit']
                result['minority_unit'] = config['expected_unit']
                result['recommendation'] = (
                    f"{n_below} value(s) entered on the {detection['wrong_unit']} scale "
                    f"are converted (x{detection['multiply_by']}) to {config['expected_unit']}; "
                    f"values >= {threshold} are already in {config['expected_unit']} and are left unchanged. "
                    f"{n_nonpositive} non-positive value(s) are impossible and excluded, never scaled.")
                result['corrected_unit'] = detection['corrected_unit']
            else:
                result['status'] = 'ok'
                result['unit_issue'] = False

        elif 'divide_by' in detection:
            # Values above threshold are likely in wrong unit (need division)
            n_above = np.sum(all_vals >= threshold)
            pct_above = n_above / len(all_vals) * 100
            n_below = np.sum(all_vals < threshold)
            pct_below = n_below / len(all_vals) * 100

            result['n_above_threshold'] = int(n_above)
            result['pct_above_threshold'] = pct_above
            result['threshold'] = threshold

            # A unit issue requires BOTH: at least one value in the wrong unit
            # (n_above > 0) AND a majority of values in the correct unit.
            # Previously this flagged an issue whenever pct_below > 90, i.e. even
            # with zero wrong-unit values present.
            if n_above > 0 and pct_below > 90:
                result['status'] = 'unit_issue_detected'
                result['unit_issue'] = True
                result['dominant_unit'] = detection['corrected_unit']
                result['minority_unit'] = detection['wrong_unit']
                result['recommendation'] = f"Most values ({pct_below:.1f}%) appear to be in {detection['corrected_unit']}. " \
                                          f"Values >= {threshold} are likely in {detection['wrong_unit']} and should be reviewed."
                result['corrected_unit'] = detection['corrected_unit']
            else:
                result['status'] = 'ok'
                result['unit_issue'] = False

        return result

    def get_problematic_records(self, lab_name: str) -> pd.DataFrame:
        """
        Get records with values in the minority/wrong unit.

        Args:
            lab_name: Name of the lab parameter

        Returns:
            DataFrame with problematic records
        """
        if lab_name not in LAB_COLUMNS or lab_name not in LAB_VALUE_CONFIG:
            return pd.DataFrame()

        config = LAB_VALUE_CONFIG[lab_name]
        if config['unit_detection'] is None:
            return pd.DataFrame()

        cols = LAB_COLUMNS[lab_name]
        before_col, after_col = cols['before'], cols['after']
        detection = config['unit_detection']
        threshold = detection['threshold']

        # Flag the values that actually deviate from the expected unit scale:
        # entries that REQUIRED a conversion (wrong scale) and non-positive
        # entries (impossible on any scale). Values already in the expected
        # unit are NOT flagged.
        def _issue_masks(col):
            vals = pd.to_numeric(self.df[col], errors='coerce')
            nonpos = vals.notna() & (vals <= 0)
            if 'multiply_by' in detection:
                wrong = vals.notna() & (vals > 0) & (vals < threshold)
            else:
                wrong = vals.notna() & (vals >= threshold)
            return nonpos, wrong

        nonpos_before, wrong_before = _issue_masks(before_col)
        nonpos_after, wrong_after = _issue_masks(after_col)
        mask_before = nonpos_before | wrong_before
        mask_after = nonpos_after | wrong_after

        mask = mask_before | mask_after
        problematic = self.df[mask].copy()

        if len(problematic) == 0:
            return pd.DataFrame()

        # Select relevant columns
        cols_to_keep = [self.patient_id_col] if self.patient_id_col in self.df.columns else []
        cols_to_keep.extend([before_col, after_col])

        # Add any ID columns that exist
        for id_col in ['X_433_0_24', 'record_id', 'case_id']:
            if id_col in self.df.columns and id_col not in cols_to_keep:
                cols_to_keep.insert(0, id_col)

        available_cols = [c for c in cols_to_keep if c in problematic.columns]
        result = problematic[available_cols].copy()

        issue_desc = []
        for idx in problematic.index:
            parts = []
            for side, col, nonpos, wrong in (('before', before_col, nonpos_before, wrong_before),
                                             ('after', after_col, nonpos_after, wrong_after)):
                raw = self.df.at[idx, col]
                if nonpos.loc[idx]:
                    parts.append(f"{side}={raw} non-positive (impossible, excluded - never scaled)")
                elif wrong.loc[idx]:
                    parts.append(f"{side}={raw} entered in {detection.get('wrong_unit', 'wrong unit')} (converted)")
            issue_desc.append("; ".join(parts))

        result['lab_parameter'] = lab_name
        result['issue'] = ('Wrong-scale entry (converted to expected unit) '
                           'or impossible non-positive value')
        result['expected_unit'] = config['expected_unit']
        result['likely_entered_as'] = detection.get('wrong_unit', 'unknown')
        result['flagged_values'] = issue_desc

        return result

    def _unit_corrected_series(self, lab_name: str, column: str) -> pd.Series:
        """
        Return the column as a numeric series with the configured unit correction
        (multiply_by/divide_by) applied, so values can be judged on the expected
        unit's scale.
        """
        vals = pd.to_numeric(self.df[column], errors='coerce')
        detection = LAB_VALUE_CONFIG.get(lab_name, {}).get('unit_detection')
        if detection:
            threshold = detection['threshold']
            if 'multiply_by' in detection:
                # Only POSITIVE values below threshold are on the smaller unit
                # scale (e.g. thousands/µl). Non-positive values are impossible
                # on any scale and are NEVER scaled - they stay unchanged and
                # fail the clinical range check as they are.
                m = vals.notna() & (vals > 0) & (vals < threshold)
                vals = vals.mask(m, vals * detection['multiply_by'])
            elif 'divide_by' in detection:
                # Values at/above threshold are in the larger unit (e.g. mg/dl)
                vals = vals.mask(vals >= threshold, vals / detection['divide_by'])
        return vals

    def get_analysis_series(self, lab_name: str, before_col: str = None,
                            after_col: str = None) -> dict:
        """
        Canonical analysis values for one lab parameter - the single source
        used by descriptive statistics, quality reporting, and figures.

        Fixed order of operations:
          1. numeric parse
          2. non-positive values (<= 0) are physiologically impossible for
             every configured parameter: excluded, and NEVER unit-scaled
          3. unit correction on the remaining values (per configuration)
          4. clinical plausibility gate on the corrected scale

        Returns {'before': Series, 'after': Series or None, 'unit': str,
                 'audit': {column: {n_raw, n_excluded_nonpositive,
                                    n_unit_corrected,
                                    n_excluded_implausible, n_analysis}}}.
        Series are aligned to self.df.index with NaN at excluded positions.
        """
        config = LAB_VALUE_CONFIG.get(lab_name, {})
        cols = LAB_COLUMNS.get(lab_name, {})
        if before_col is None:
            before_col = cols.get('before')
        if after_col is None and before_col == cols.get('before'):
            after_col = cols.get('after')

        out = {'unit': config.get('expected_unit', ''), 'audit': {}}
        for side, col in (('before', before_col), ('after', after_col)):
            if col is None or col not in self.df.columns:
                out[side] = None
                continue
            raw = pd.to_numeric(self.df[col], errors='coerce')
            nonpos = raw.notna() & (raw <= 0)
            vals = raw.mask(nonpos)
            n_corrected = 0
            detection = config.get('unit_detection')
            if detection:
                threshold = detection['threshold']
                if 'multiply_by' in detection:
                    m = vals.notna() & (vals < threshold)
                    n_corrected = int(m.sum())
                    vals = vals.mask(m, vals * detection['multiply_by'])
                elif 'divide_by' in detection:
                    m = vals.notna() & (vals >= threshold)
                    n_corrected = int(m.sum())
                    vals = vals.mask(m, vals / detection['divide_by'])
            implausible = pd.Series(False, index=vals.index)
            if 'clinical_range' in config:
                lo, hi = config['clinical_range']
                implausible = vals.notna() & ((vals < lo) | (vals > hi))
                vals = vals.mask(implausible)
            out[side] = vals
            out['audit'][col] = {
                'n_raw': int(raw.notna().sum()),
                'n_excluded_nonpositive': int(nonpos.sum()),
                'n_unit_corrected': n_corrected,
                'n_excluded_implausible': int(implausible.sum()),
                'n_analysis': int(vals.notna().sum()),
            }
        return out

    def get_range_violations(self, lab_name: str) -> pd.DataFrame:
        """
        Flag values outside the configured plausible clinical range.

        The configured unit correction (multiply_by/divide_by) is applied BEFORE
        screening, so values in a wrong-but-convertible unit are judged on the
        corrected scale. Impossible values (e.g. negative platelet counts) remain
        impossible after correction and are flagged.

        Args:
            lab_name: Name of the lab parameter

        Returns:
            DataFrame with records containing values outside the clinical range
        """
        config = LAB_VALUE_CONFIG.get(lab_name)
        if config is None or 'clinical_range' not in config or lab_name not in LAB_COLUMNS:
            return pd.DataFrame()

        cols = LAB_COLUMNS[lab_name]
        before_col, after_col = cols['before'], cols['after']
        if before_col not in self.df.columns or after_col not in self.df.columns:
            return pd.DataFrame()

        low, high = config['clinical_range']

        corr_before = self._unit_corrected_series(lab_name, before_col)
        corr_after = self._unit_corrected_series(lab_name, after_col)

        # Documented non-positive laboratory values are impossible on every
        # path (zero floors in the physician table are entry floors, not
        # plausible measured values) - they are flagged here as findings,
        # itemized separately from missing values
        viol_before = corr_before.notna() & ((corr_before <= 0) |
                                             (corr_before < low) | (corr_before > high))
        viol_after = corr_after.notna() & ((corr_after <= 0) |
                                           (corr_after < low) | (corr_after > high))
        mask = viol_before | viol_after

        if not mask.any():
            return pd.DataFrame()

        problematic = self.df[mask].copy()

        # Select relevant columns (patient ID first)
        cols_to_keep = [self.patient_id_col] if self.patient_id_col in self.df.columns else []
        cols_to_keep.extend([before_col, after_col])
        for id_col in ['X_433_0_24', 'record_id', 'case_id']:
            if id_col in self.df.columns and id_col not in cols_to_keep:
                cols_to_keep.insert(0, id_col)
        available_cols = [c for c in cols_to_keep if c in problematic.columns]
        result = problematic[available_cols].copy()

        # Human-readable description of which value(s) were flagged
        flagged_desc = []
        for idx in problematic.index:
            parts = []
            for side, col, corr, viol in (('before', before_col, corr_before, viol_before),
                                          ('after', after_col, corr_after, viol_after)):
                if not viol.loc[idx]:
                    continue
                raw = self.df.at[idx, col]
                cv = corr.loc[idx]
                if pd.notna(cv) and cv <= 0:
                    parts.append(f"{side}={raw} (non-positive, impossible - never scaled)")
                elif pd.notna(cv) and float(cv) != float(raw):
                    parts.append(f"{side}={raw} (corrected={cv:g})")
                else:
                    parts.append(f"{side}={raw}")
            flagged_desc.append("; ".join(parts))

        result['lab_parameter'] = lab_name
        result['issue'] = (f'Outside plausible clinical range '
                           f'({low}-{high} {config["expected_unit"]}, after unit correction)')
        result['expected_unit'] = config['expected_unit']
        result['flagged_values'] = flagged_desc

        return result

    def get_cleaned_data(self, lab_name: str, exclude_outliers: bool = True) -> Tuple[np.ndarray, np.ndarray, str]:
        """
        Paired analysis values for plotting, drawn from the SAME canonical
        normalization as the statistics (get_analysis_series): non-positive
        values excluded before scaling, unit correction applied, clinical
        plausibility gated. The returned unit label describes the actual
        scale of the returned values.
        """
        if lab_name not in LAB_COLUMNS or lab_name not in LAB_VALUE_CONFIG:
            return np.array([]), np.array([]), ''
        series = self.get_analysis_series(lab_name)
        if series['before'] is None or series['after'] is None:
            return np.array([]), np.array([]), series['unit']
        mask = series['before'].notna() & series['after'].notna()
        return (series['before'][mask].to_numpy(),
                series['after'][mask].to_numpy(),
                series['unit'])

    def run_all_checks(self) -> Dict[str, Dict]:
        """
        Run unit detection for all configured lab parameters.

        Returns:
            Dictionary with results for each parameter
        """
        results = {}
        for lab_name in LAB_VALUE_CONFIG.keys():
            results[lab_name] = self.detect_unit_issues(lab_name)
        return results

    def export_problematic_records(self, output_dir: str) -> str:
        """
        Export all problematic records to a CSV file for manual review.

        Args:
            output_dir: Directory to save the output file

        Returns:
            Path to the output file
        """
        all_problematic = []

        for lab_name in LAB_VALUE_CONFIG.keys():
            detection = self.detect_unit_issues(lab_name)
            if detection.get('unit_issue', False):
                records = self.get_problematic_records(lab_name)
                if len(records) > 0:
                    all_problematic.append(records)

            # Clinical range screening: flag impossible values (e.g. negative
            # platelet counts) into the problematic-records export
            range_records = self.get_range_violations(lab_name)
            if len(range_records) > 0:
                all_problematic.append(range_records)

        if not all_problematic:
            print("  No problematic records found")
            return ''

        combined = pd.concat(all_problematic, ignore_index=True)

        # Save to CSV
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, 'lab_value_unit_issues.csv')
        combined.to_csv(output_path, index=False)

        print(f"  Exported {len(combined)} problematic records to: {output_path}")
        return output_path

    def generate_report(self, output_dir: str) -> str:
        """
        Generate a data quality report for lab values.

        Args:
            output_dir: Directory to save the report

        Returns:
            Path to the report file
        """
        results = self.run_all_checks()

        os.makedirs(output_dir, exist_ok=True)
        report_path = os.path.join(output_dir, 'lab_value_quality_report.txt')

        with open(report_path, 'w') as f:
            f.write("LAB VALUE DATA QUALITY REPORT\n")
            f.write("=" * 60 + "\n\n")
            f.write("This report identifies unit inconsistencies in laboratory values.\n")
            f.write("Wrong-scale entries are converted deterministically per value;\n")
            f.write("converted and impossible (non-positive) entries are listed for review.\n\n")

            issues_found = False

            for lab_name, result in results.items():
                f.write(f"\n{lab_name}\n")
                f.write("-" * 40 + "\n")

                if result['status'] == 'skipped':
                    f.write(f"  Skipped: {result['reason']}\n")
                    continue

                f.write(f"  Expected unit: {result['expected_unit']}\n")
                f.write(f"  Total values: {result['n_total']} (Before: {result['n_before']}, After: {result['n_after']})\n")
                f.write(f"  Value range: {result['value_range'][0]:.2f} - {result['value_range'][1]:.2f}\n")
                f.write(f"  Median: {result['median']:.2f}\n")

                if result.get('unit_issue', False):
                    issues_found = True
                    f.write(f"\n  *** UNIT ISSUE DETECTED ***\n")
                    f.write(f"  {result['recommendation']}\n")
                    f.write(f"  Corrected unit for visualization: {result['corrected_unit']}\n")

                    if 'n_below_threshold' in result:
                        f.write(f"  Values below threshold ({result['threshold']}): {result['n_below_threshold']} ({result['pct_below_threshold']:.1f}%)\n")
                    if 'n_above_threshold' in result:
                        f.write(f"  Values above threshold ({result['threshold']}): {result['n_above_threshold']} ({result['pct_above_threshold']:.1f}%)\n")
                else:
                    f.write(f"  Status: OK - No unit issues detected\n")

                # Clinical range screening (values judged after unit correction)
                config = LAB_VALUE_CONFIG.get(lab_name, {})
                if 'clinical_range' in config:
                    low, high = config['clinical_range']
                    violations = self.get_range_violations(lab_name)
                    f.write(f"\n  Clinical range screening: {low} - {high} {config['expected_unit']} "
                            f"(after unit correction; documented values <= 0 are impossible\n"
                            f"   and excluded - counted separately from missing values)\n")
                    if len(violations) == 0:
                        f.write("    No implausible values detected\n")
                    else:
                        issues_found = True
                        f.write(f"    *** {len(violations)} record(s) with implausible values flagged ***\n")
                        for _, row in violations.iterrows():
                            pid = row.get(self.patient_id_col, 'n/a')
                            f.write(f"      {self.patient_id_col}={pid}: {row['flagged_values']}\n")

            f.write("\n\n" + "=" * 60 + "\n")
            if issues_found:
                f.write("ACTION REQUIRED: Review problematic records in lab_value_unit_issues.csv\n")
            else:
                f.write("No unit issues detected.\n")

        print(f"  Generated report: {report_path}")
        return report_path


def run_lab_value_quality_check(raw_data_path: str, output_dir: str) -> LabValueQualityChecker:
    """
    Run lab value quality check on raw data.

    Args:
        raw_data_path: Path to raw CSV data file
        output_dir: Directory for output files

    Returns:
        LabValueQualityChecker instance
    """
    print("\nRunning lab value quality check...")

    # Load through the standard loader so the QC report uses the SAME cohort
    # as the statistics (test-site rows excluded, columns typed)
    from transfusion_data_loader import TransfusionDataLoader
    _loader = TransfusionDataLoader()
    _loader.load_data(raw_data_path)
    df = _loader.df_clean

    print(f"  Loaded {len(df)} records (via standard loader)")

    # Create checker
    checker = LabValueQualityChecker(df)

    # Run checks and generate outputs
    checker.generate_report(output_dir)
    checker.export_problematic_records(output_dir)

    return checker


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 3:
        print("Usage: python lab_value_quality.py <raw_data_path> <output_dir>")
        print("Example: python lab_value_quality.py ../test_data_150patients.csv test_data_150patients")
        sys.exit(1)

    raw_data = sys.argv[1]
    output = sys.argv[2]

    run_lab_value_quality_check(raw_data, output)
