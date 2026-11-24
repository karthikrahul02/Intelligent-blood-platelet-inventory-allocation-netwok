"""
SNOMED Code Descriptive Statistics Module

Provides coverage statistics and frequency analysis for SNOMED-coded fields:
- Primary diagnosis (X_433_0_5)
- Secondary diagnosis (X_433_0_6)
- Intervention/Procedure (X_433_0_9)

Author: Elina Nuerenberg-Goloub with Claude Opus 4.5 by Anthropic
Date: 2026-02-08
"""

import pandas as pd
import numpy as np
import json

from transfusion_registry_mapping import json_sanitize
import os
from typing import Dict, Any, Optional, Tuple
from datetime import datetime


class SNOMEDDescriptives:
    """
    Calculates descriptive statistics for SNOMED-coded fields in the transfusion registry.

    SNOMED CT codes are standardized medical terminology codes. This module provides:
    - Coverage statistics (documentation rates)
    - Frequency distributions (top codes)
    - Patient-level and administration-level analysis

    Output is designed for manual lookup: codes are provided without descriptions
    so they can be verified against the official SNOMED CT Browser.
    """

    # Column mappings
    SNOMED_COLUMNS = {
        'primary_diagnosis': 'X_433_0_5',
        'secondary_diagnosis': 'X_433_0_6',
        'intervention': 'X_433_0_9'
    }

    # Human-readable names
    FIELD_NAMES = {
        'primary_diagnosis': 'Primary Diagnosis',
        'secondary_diagnosis': 'Secondary Diagnosis',
        'intervention': 'Intervention/Procedure'
    }

    def __init__(self, loader):
        """
        Initialize with a TransfusionDataLoader instance.

        Args:
            loader: TransfusionDataLoader with loaded data
        """
        self.loader = loader
        self.df = loader.df_clean
        self.results = {}

    def calculate_coverage(self) -> Dict[str, Dict[str, Any]]:
        """
        Calculate documentation coverage for each SNOMED field.

        Returns:
            Dict with coverage statistics at administration and patient level
        """
        coverage = {}

        # "Administration level" must be computed over actual administration
        # rows (those with a product type), not all rows — follow-up and
        # baseline-only rows would otherwise dilute the percentage.
        product_col = 'X_433_7_746'
        if product_col in self.df.columns:
            df_admin = self.df[self.df[product_col].notna()]
        else:
            df_admin = self.df
        total_records = len(df_admin)
        total_patients = self.df['PID'].nunique()

        for field_key, col_name in self.SNOMED_COLUMNS.items():
            field_name = self.FIELD_NAMES[field_key]

            if col_name not in self.df.columns:
                coverage[field_key] = {
                    'field_name': field_name,
                    'column': col_name,
                    'error': 'Column not found in data'
                }
                continue

            # Administration-level coverage (administration rows only)
            non_null = df_admin[col_name].notna().sum()

            # Patient-level coverage (at least one value per patient)
            patient_coverage = self.df.groupby('PID')[col_name].apply(
                lambda x: x.notna().any()
            ).sum()

            coverage[field_key] = {
                'field_name': field_name,
                'column': col_name,
                'administration_level': {
                    'total': int(total_records),
                    'documented': int(non_null),
                    'missing': int(total_records - non_null),
                    'percent_documented': round(100 * non_null / total_records, 1) if total_records > 0 else 0
                },
                'patient_level': {
                    'total': int(total_patients),
                    'with_documentation': int(patient_coverage),
                    'without_documentation': int(total_patients - patient_coverage),
                    'percent_documented': round(100 * patient_coverage / total_patients, 1) if total_patients > 0 else 0
                }
            }

        self.results['coverage'] = coverage
        return coverage

    def calculate_top_codes(self, n: int = 5) -> Dict[str, Dict[str, Any]]:
        """
        Calculate top N most frequent SNOMED codes for each field.

        Provides codes without descriptions - designed for manual lookup
        at https://browser.ihtsdotools.org/

        Reports BOTH:
        - n_records: Number of administration records (a patient with 4 transfusions = 4 records)
        - n_patients: Number of unique patients

        Args:
            n: Number of top codes to return (default 5)

        Returns:
            Dict with top codes for each field
        """
        top_codes = {}
        total_patients = self.df['PID'].nunique()

        for field_key, col_name in self.SNOMED_COLUMNS.items():
            field_name = self.FIELD_NAMES[field_key]

            if col_name not in self.df.columns:
                top_codes[field_key] = {
                    'field_name': field_name,
                    'error': 'Column not found'
                }
                continue

            # Get value counts (record level)
            values = self.df[col_name].dropna()

            if len(values) == 0:
                # same schema as the populated case, so summaries and
                # exports handle fields without any documented code
                top_codes[field_key] = {
                    'field_name': field_name,
                    'column': col_name,
                    'total_documented_records': 0,
                    'total_unique_codes': 0,
                    'total_patients': int(total_patients),
                    'top_codes': []
                }
                continue

            value_counts = values.value_counts()
            total_documented = len(values)
            unique_codes = len(value_counts)

            # Get top N codes
            top_n = value_counts.head(n)

            codes_list = []
            for code, count in top_n.items():
                # Count unique patients with this code
                patients_with_code = self.df[self.df[col_name] == code]['PID'].nunique()

                codes_list.append({
                    'snomed_code': str(code),
                    'n_records': int(count),
                    'n_patients': int(patients_with_code),
                    'percent_of_patients': round(100 * patients_with_code / total_patients, 1),
                    'description': ''  # To be filled manually
                })

            top_codes[field_key] = {
                'field_name': field_name,
                'column': col_name,
                'total_documented_records': int(total_documented),
                'total_unique_codes': int(unique_codes),
                'total_patients': int(total_patients),
                'top_codes': codes_list
            }

        self.results['top_codes'] = top_codes
        return top_codes

    def calculate_all(self, top_n: int = 5) -> Dict[str, Any]:
        """
        Calculate all SNOMED statistics.

        Args:
            top_n: Number of top codes to return per field

        Returns:
            Complete results dictionary
        """
        self.calculate_coverage()
        self.calculate_top_codes(n=top_n)

        # Add metadata
        self.results['metadata'] = {
            'generated': datetime.now().isoformat(),
            'total_records': int(len(self.df)),
            'total_patients': int(self.df['PID'].nunique()),
            'snomed_browser_url': 'https://browser.ihtsdotools.org/'
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
        lines.append("SNOMED CODE ANALYSIS")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"Total records: {self.results['metadata']['total_records']}")
        lines.append(f"Total patients: {self.results['metadata']['total_patients']}")
        lines.append(f"Generated: {self.results['metadata']['generated']}")
        lines.append("")

        # Coverage section
        lines.append("-" * 70)
        lines.append("DOCUMENTATION COVERAGE")
        lines.append("-" * 70)
        lines.append("")

        for field_key, data in self.results['coverage'].items():
            if 'error' in data:
                lines.append(f"{data['field_name']}: {data['error']}")
                continue

            lines.append(f"{data['field_name']} ({data['column']})")
            admin = data['administration_level']
            patient = data['patient_level']
            lines.append(f"  Administration level: {admin['documented']}/{admin['total']} ({admin['percent_documented']}%)")
            lines.append(f"  Patient level: {patient['with_documentation']}/{patient['total']} ({patient['percent_documented']}%)")
            lines.append("")

        # Top codes section
        lines.append("-" * 70)
        lines.append("TOP SNOMED CODES")
        lines.append("-" * 70)
        lines.append("")
        lines.append("Look up codes at: https://browser.ihtsdotools.org/")
        lines.append("")
        lines.append("NOTE: n_records = administration records, n_patients = unique patients")
        lines.append("")

        for field_key, data in self.results['top_codes'].items():
            if 'error' in data:
                lines.append(f"{data['field_name']}: {data['error']}")
                continue

            lines.append(f"{data['field_name']} ({data['total_unique_codes']} unique codes)")
            lines.append("")
            lines.append(f"  {'SNOMED Code':<15} {'n_records':>10} {'n_patients':>12} {'% patients':>12}")
            lines.append(f"  {'-'*15} {'-'*10} {'-'*12} {'-'*12}")

            for code_data in data['top_codes']:
                lines.append(f"  {code_data['snomed_code']:<15} {code_data['n_records']:>10} {code_data['n_patients']:>12} {code_data['percent_of_patients']:>11.1f}%")

            lines.append("")

        return "\n".join(lines)

    def export_results(self, output_dir: str) -> None:
        """
        Export results to files.

        Creates:
        - snomed_analysis.json (machine-readable)
        - snomed_analysis.txt (human-readable summary)
        - snomed_codes_for_lookup.csv (CSV for manual annotation)

        Args:
            output_dir: Directory to write output files
        """
        # Create SNOMED subdirectory
        snomed_dir = os.path.join(output_dir, 'SNOMED')
        os.makedirs(snomed_dir, exist_ok=True)

        # Export JSON
        json_path = os.path.join(snomed_dir, 'snomed_analysis.json')
        with open(json_path, 'w') as f:
            json.dump(json_sanitize(self.results), f, indent=2, allow_nan=False)
        print(f"  Exported: {json_path}")

        # Export text summary
        txt_path = os.path.join(snomed_dir, 'snomed_analysis.txt')
        with open(txt_path, 'w') as f:
            f.write(self.create_summary_table())
        print(f"  Exported: {txt_path}")

        # Export CSV for manual lookup
        csv_path = os.path.join(snomed_dir, 'snomed_codes_for_lookup.csv')
        self._export_lookup_csv(csv_path)
        print(f"  Exported: {csv_path}")

        # Export all codes CSV (complete list)
        all_codes_path = os.path.join(snomed_dir, 'snomed_all_codes.csv')
        self._export_all_codes_csv(all_codes_path)
        print(f"  Exported: {all_codes_path}")

    def _export_lookup_csv(self, filepath: str) -> None:
        """
        Export top codes as CSV for manual annotation.

        Format designed for easy lookup and manual description entry.
        Includes both record counts and patient counts.
        """
        rows = []

        for field_key, data in self.results['top_codes'].items():
            if 'error' in data or not data.get('top_codes'):
                continue

            for code_data in data['top_codes']:
                rows.append({
                    'field': data['field_name'],
                    'snomed_code': code_data['snomed_code'],
                    'n_records': code_data['n_records'],
                    'n_patients': code_data['n_patients'],
                    'percent_of_patients': code_data['percent_of_patients'],
                    'description': '',  # To be filled manually
                    'lookup_url': f"https://browser.ihtsdotools.org/?perspective=full&conceptId1={code_data['snomed_code']}"
                })

        df = pd.DataFrame(rows)
        df.to_csv(filepath, index=False)

    def _export_all_codes_csv(self, filepath: str) -> None:
        """
        Export all unique SNOMED codes with frequencies.

        Complete list for comprehensive documentation.
        Includes both record counts and patient counts.
        """
        rows = []
        total_patients = self.df['PID'].nunique()

        for field_key, col_name in self.SNOMED_COLUMNS.items():
            field_name = self.FIELD_NAMES[field_key]

            if col_name not in self.df.columns:
                continue

            values = self.df[col_name].dropna()
            if len(values) == 0:
                continue

            value_counts = values.value_counts()

            for code, count in value_counts.items():
                # Count unique patients with this code
                patients_with_code = self.df[self.df[col_name] == code]['PID'].nunique()

                rows.append({
                    'field': field_name,
                    'snomed_code': str(code),
                    'n_records': int(count),
                    'n_patients': int(patients_with_code),
                    'percent_of_patients': round(100 * patients_with_code / total_patients, 1),
                    'description': ''
                })

        # explicit columns so a dataset without any documented code still
        # yields a well-formed (header-only) CSV
        df = pd.DataFrame(rows, columns=['field', 'snomed_code', 'n_records',
                                         'n_patients', 'percent_of_patients',
                                         'description'])
        if len(df):
            df = df.sort_values(['field', 'n_patients'],
                                ascending=[True, False])
        df.to_csv(filepath, index=False)


def run_snomed_analysis(data_path: str, output_dir: str, top_n: int = 5) -> SNOMEDDescriptives:
    """
    Convenience function to run complete SNOMED analysis.

    Args:
        data_path: Path to CSV data file
        output_dir: Directory for output files
        top_n: Number of top codes to include (default 5)

    Returns:
        SNOMEDDescriptives instance with results
    """
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from transfusion_data_loader import TransfusionDataLoader

    print(f"\nRunning SNOMED analysis...")
    print(f"  Data: {data_path}")
    print(f"  Output: {output_dir}")

    # Load data
    loader = TransfusionDataLoader()
    loader.load_data(data_path)

    # Create analysis
    snomed = SNOMEDDescriptives(loader)
    results = snomed.calculate_all(top_n=top_n)

    # Display summary
    print("\n" + snomed.create_summary_table())

    # Export
    print("\nExporting results...")
    snomed.export_results(output_dir)

    print("\nSNOMED analysis complete.")
    print(f"Results saved to: {os.path.join(output_dir, 'SNOMED')}/")

    return snomed
