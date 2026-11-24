"""
Data Quality Analysis: Module 2 - Dosage Consistency
=====================================================

Checks dosage data for unit consistency and identifies anomalies.

Note: Expected dosage ranges are not available. This module focuses on:
- Unit consistency (correct units for each product)
- Extreme values identification
- Missing dosages

Author: Elina Nuerenberg-Goloub with Claude Sonnet 4.5 by Anthropic
Date: 2025-10-23
Revised on 2026-01-21 by Elina Nuerenberg-Goloub and Claude Opus 4.5
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple
from transfusion_data_loader import TransfusionDataLoader
import json
import math
from pathlib import Path
from datetime import datetime


def _json_sanitize(obj):
    """RFC 8259 conformance - delegates to the central sanitizer."""
    from transfusion_registry_mapping import json_sanitize
    return json_sanitize(obj)


class DosageConsistency:
    """
    Analyze dosage consistency by checking units and identifying anomalies.

    Checks:
    - Unit consistency (correct unit for each product)
    - Missing dosage values
    - Extreme dosage values (statistical outliers)
    - Summary statistics by product
    """

    # Expected units for each product (plain registry codes; all comparisons
    # go through _norm_code so '4' and '4.0' both match)
    EXPECTED_UNITS = {
        '1': ('ml', '1', 'Red blood cell concentrate (RBC)'),
        '2': ('ml', '1', 'Fresh Frozen Plasma (FFP)'),
        '3': ('ml', '1', 'Platelet concentrate (PC)'),
        '4': ('IU', '2', 'PPSB'),
        '5': ('mg', '3', 'Fibrinogen'),
        '6': ('mg', '3', 'Iron i.v.'),      # clinical convention confirmed 2026-08-21
        '7': ('ml', '1', 'Albumin'),
        '8': ('IU', '2', 'EPO'),            # clinical convention confirmed 2026-08-21
        '9': ('IU', '2', 'Antithrombin III (ATIII)'),
        '10': ('mg', '3', 'Oral iron'),     # clinical convention confirmed 2026-08-21
    }

    # Unit codes
    UNIT_CODES = {
        '1': 'ml',
        '2': 'IU',
        '3': 'mg',
    }

    @staticmethod
    def _norm_code(series: pd.Series) -> pd.Series:
        """Normalize code strings: '4.0' -> '4'. The float form only arises
        from NaN-induced float parsing; exact matching against it silently
        breaks when a column loads as int or plain string."""
        return series.astype(str).str.replace(r'\.0$', '', regex=True)

    # Field mappings
    FIELD_MAP = {
        'product_type': 'X_433_7_746',
        'dosage_amount': 'X_433_7_22',
        'dosage_unit': 'X_433_7_734',
        'admin_date': 'X_433_7_11',
    }

    def __init__(self, loader: TransfusionDataLoader):
        """
        Initialize dosage consistency analyzer.

        Args:
            loader: TransfusionDataLoader with loaded data
        """
        self.loader = loader
        self.df = loader.df_clean.copy()
        self.mapper = loader.mapper
        self.results = {}

    def calculate_all(self) -> Dict[str, Any]:
        """
        Calculate all dosage consistency statistics.

        Returns:
            Dictionary with all analysis results
        """
        print("\nCalculating data quality: Dosage consistency analysis...")
        print("=" * 90)

        # Filter to treatment records only (exclude MAT and other non-treatment records)
        product_norm = self._norm_code(self.df[self.FIELD_MAP['product_type']])
        self.treatment_df = self.df[
            (self.df[self.FIELD_MAP['product_type']].notna()) &
            (product_norm != '11')  # Exclude MAT (code 11)
        ].copy()
        # Pre-normalized code columns used by all downstream checks
        self.treatment_df['_product_code'] = self._norm_code(self.treatment_df[self.FIELD_MAP['product_type']])
        self.treatment_df['_unit_code'] = self._norm_code(self.treatment_df[self.FIELD_MAP['dosage_unit']])

        # Convert dosage to numeric
        self.treatment_df['dosage_numeric'] = pd.to_numeric(
            self.treatment_df[self.FIELD_MAP['dosage_amount']],
            errors='coerce'
        )

        # Step 1: Check unit consistency
        print("\n1. Checking unit consistency...")
        self._check_unit_consistency()

        # Step 2: Check for missing dosages
        print("2. Checking for missing dosages...")
        self._check_missing_dosages()

        # Step 3: an extreme-values screen for dosages is intentionally
        # not part of this release; it would require clinically defined
        # per-product dosage ranges
        # print("3. Identifying extreme dosage values...")
        # self._identify_extreme_values()
        self.results['extreme_values'] = {
            'status': 'NOT ASSESSED',
            'reason': 'clinically defined per-product dosage ranges are not yet available; no extreme-value screening was performed',
            'n_products_with_extremes': None,
            'n_total_extremes': None,
            'records': []
        }
        # unit-check coverage matrix: make explicit which product codes the
        # expected-unit convention covers
        _all_products = {'1': 'RBC', '2': 'FFP', '3': 'PC', '4': 'PPSB',
                         '5': 'Fibrinogen', '6': 'Iron i.v.', '7': 'Albumin',
                         '8': 'Erythropoetin', '9': 'ATIII', '10': 'Oral iron',
                         '11': 'Machine autotransfusion'}
        _configured = set(self.EXPECTED_UNITS.keys())
        self.results['unit_check_coverage'] = {
            code: {'product': name,
                   'status': ('not applicable' if code == '11' else
                              'checked' if code in _configured else
                              'not configured'),
                   'note': ('MAT is documented via dedicated fields and excluded by design' if code == '11' else
                            '' if code in _configured else
                            'no expected-unit convention defined for this product')}
            for code, name in _all_products.items()
        }

        # Step 3: Create summary
        print("3. Creating summary statistics...")
        self._create_summary()

        print("\nDosage consistency analysis complete")
        print("=" * 90)

        return self.results

    def _check_unit_consistency(self) -> None:
        """Check if units match expected units for each product."""
        unit_issues = []

        for product_code, (expected_unit_name, expected_unit_code, product_name) in self.EXPECTED_UNITS.items():
            # Get all records for this product
            product_df = self.treatment_df[
                self.treatment_df['_product_code'] == product_code
            ].copy()

            if len(product_df) == 0:
                continue

            # Check unit consistency
            non_standard_unit_df = product_df[
                (product_df[self.FIELD_MAP['dosage_unit']].notna()) &
                (product_df['_unit_code'] != expected_unit_code)
            ].copy()

            if len(non_standard_unit_df) > 0:
                for idx, row in non_standard_unit_df.iterrows():
                    actual_unit_code = row['_unit_code']
                    actual_unit_name = self.UNIT_CODES.get(actual_unit_code, f'Unknown ({actual_unit_code})')

                    admin_date = row.get(self.FIELD_MAP['admin_date'], '')
                    if pd.notna(admin_date):
                        admin_date = str(admin_date)[:10] if hasattr(admin_date, '__str__') else ''
                    else:
                        admin_date = ''

                    unit_issues.append({
                        'PID': row['PID'],
                        'Admin_Date': admin_date,
                        'product_code': product_code,
                        'product_name': product_name,
                        'expected_unit_code': expected_unit_code,
                        'expected_unit': expected_unit_name,
                        'actual_unit_code': actual_unit_code,
                        'actual_unit': actual_unit_name,
                        'dosage': row['dosage_numeric'],
                    })

            print(f"   {product_name}: {len(non_standard_unit_df)} records with non-standard unit")

        self.results['unit_consistency'] = {
            'n_total_products': len(self.EXPECTED_UNITS),
            'n_products_with_issues': len(set(issue['product_code'] for issue in unit_issues)),
            'n_total_issues': len(unit_issues),
            'issues': unit_issues
        }

    def _check_missing_dosages(self) -> None:
        """Check for missing dosage values."""
        summary_records = []
        detailed_records = []

        for product_code, (expected_unit_name, expected_unit_code, product_name) in self.EXPECTED_UNITS.items():
            # Get all records for this product
            product_df = self.treatment_df[
                self.treatment_df['_product_code'] == product_code
            ].copy()

            if len(product_df) == 0:
                continue

            # Check for missing dosages (amount or unit)
            missing_amount = product_df[self.FIELD_MAP['dosage_amount']].isna()
            missing_unit = product_df[self.FIELD_MAP['dosage_unit']].isna()
            missing_any = missing_amount | missing_unit

            missing_df = product_df[missing_any].copy()

            if len(missing_df) > 0:
                # Summary record
                pids = ', '.join(sorted(set(str(pid) for pid in missing_df['PID'].unique())))
                summary_records.append({
                    'product_code': product_code,
                    'product_name': product_name,
                    'n_total': len(product_df),
                    'n_missing': len(missing_df),
                    'percent_missing': (len(missing_df) / len(product_df)) * 100,
                    'pids': pids
                })

                # Detailed records for extraction
                for idx, row in missing_df.iterrows():
                    has_amount = pd.notna(row[self.FIELD_MAP['dosage_amount']])
                    has_unit = pd.notna(row[self.FIELD_MAP['dosage_unit']])

                    if not has_amount and not has_unit:
                        missing_field = 'both'
                    elif not has_amount:
                        missing_field = 'amount'
                    else:
                        missing_field = 'unit'

                    admin_date = row.get(self.FIELD_MAP['admin_date'], '')
                    if pd.notna(admin_date):
                        admin_date = str(admin_date)[:10] if hasattr(admin_date, '__str__') else ''
                    else:
                        admin_date = ''

                    detailed_records.append({
                        'PID': row['PID'],
                        'Admin_Date': admin_date,
                        'Product': product_name,
                        'Missing_Field': missing_field
                    })

            print(f"   {product_name}: {len(missing_df)} missing dosages (out of {len(product_df)})")

        self.results['missing_dosages'] = {
            'n_products_with_missing': len(summary_records),
            'total_missing': sum(rec['n_missing'] for rec in summary_records),
            'records': summary_records,
            'detailed_records': detailed_records
        }

    def _identify_extreme_values(self) -> None:
        """Identify statistically extreme dosage values."""
        extreme_records = []

        for product_code, (expected_unit_name, expected_unit_code, product_name) in self.EXPECTED_UNITS.items():
            # Get all records for this product with correct unit and valid dosage
            product_df = self.treatment_df[
                (self.treatment_df['_product_code'] == product_code) &
                (self.treatment_df['_unit_code'] == expected_unit_code) &
                (self.treatment_df['dosage_numeric'].notna())
            ].copy()

            if len(product_df) < 10:  # Skip if too few records for statistical analysis
                continue

            # Calculate statistics
            dosages = product_df['dosage_numeric']
            q1 = dosages.quantile(0.25)
            q3 = dosages.quantile(0.75)
            iqr = q3 - q1
            lower_bound = q1 - 3 * iqr  # 3*IQR for extreme outliers
            upper_bound = q3 + 3 * iqr

            # Find extreme values
            extreme_df = product_df[
                (product_df['dosage_numeric'] < lower_bound) |
                (product_df['dosage_numeric'] > upper_bound)
            ].copy()

            if len(extreme_df) > 0:
                for idx, row in extreme_df.iterrows():
                    if row['dosage_numeric'] < lower_bound:
                        extreme_type = 'Unusually low'
                    else:
                        extreme_type = 'Unusually high'

                    admin_date = row.get(self.FIELD_MAP['admin_date'], '')
                    if pd.notna(admin_date):
                        admin_date = str(admin_date)[:10] if hasattr(admin_date, '__str__') else ''
                    else:
                        admin_date = ''

                    extreme_records.append({
                        'PID': row['PID'],
                        'Admin_Date': admin_date,
                        'product_code': product_code,
                        'product_name': product_name,
                        'unit': expected_unit_name,
                        'dosage': float(row['dosage_numeric']) if pd.notna(row['dosage_numeric']) else None,
                        'extreme_type': extreme_type,
                        'median': float(dosages.median()),
                        'q1': float(q1),
                        'q3': float(q3),
                        'lower_bound': float(lower_bound),
                        'upper_bound': float(upper_bound),
                    })

            print(f"   {product_name}: {len(extreme_df)} extreme values (out of {len(product_df)})")

        self.results['extreme_values'] = {
            'n_products_with_extremes': len(set(rec['product_code'] for rec in extreme_records)),
            'n_total_extremes': len(extreme_records),
            'records': extreme_records
        }

    def _create_summary(self) -> None:
        """Create summary statistics by product."""
        summary_by_product = []

        for product_code, (expected_unit_name, expected_unit_code, product_name) in self.EXPECTED_UNITS.items():
            # Get all records for this product
            product_df = self.treatment_df[
                self.treatment_df['_product_code'] == product_code
            ].copy()

            if len(product_df) == 0:
                continue

            # Overall statistics
            n_total = len(product_df)
            n_with_dosage = product_df['dosage_numeric'].notna().sum()
            n_missing = n_total - n_with_dosage

            # Unit consistency
            n_non_standard_unit = len(product_df[
                (product_df[self.FIELD_MAP['dosage_unit']].notna()) &
                (product_df['_unit_code'] != expected_unit_code)
            ])

            # Dosage statistics (for records with correct unit)
            correct_unit_df = product_df[
                (product_df['_unit_code'] == expected_unit_code) &
                (product_df['dosage_numeric'].notna())
            ]

            if len(correct_unit_df) > 0:
                dosages = correct_unit_df['dosage_numeric']
                min_val = float(dosages.min())
                max_val = float(dosages.max())
                mean_val = float(dosages.mean())
                median_val = float(dosages.median())
                std_val = float(dosages.std())
            else:
                min_val = max_val = mean_val = median_val = std_val = None

            summary_by_product.append({
                'product_code': product_code,
                'product_name': product_name,
                'expected_unit': expected_unit_name,
                'n_total': int(n_total),
                'n_with_dosage': int(n_with_dosage),
                'n_missing_dosage': int(n_missing),
                'percent_missing': float((n_missing / n_total) * 100) if n_total > 0 else 0.0,
                'n_non_standard_unit': int(n_non_standard_unit),
                'n_correct_unit': int(len(correct_unit_df)),
                'min': min_val,
                'max': max_val,
                'mean': mean_val,
                'median': median_val,
                'std': std_val,
            })

        self.results['summary'] = {
            'n_products': len(summary_by_product),
            'n_total_administrations': int(len(self.treatment_df)),
            'by_product': summary_by_product
        }

    def create_summary_tables(self) -> Tuple[str, str, str, str]:
        """
        Create formatted summary tables.

        Returns:
            Tuple of (summary_table, unit_issues_table, missing_table, extremes_table)
        """
        if not self.results:
            self.calculate_all()

        # Summary table
        summary_lines = []
        summary_lines.append("=" * 120)
        summary_lines.append("DATA QUALITY - DOSAGE CONSISTENCY: SUMMARY")
        summary_lines.append("=" * 120)
        summary_lines.append("")
        summary_lines.append(f"Total treatment administrations: {self.results['summary']['n_total_administrations']}")
        summary_lines.append(f"Products analyzed: {self.results['summary']['n_products']}")
        summary_lines.append("")
        summary_lines.append(f"Unit consistency issues: {self.results['unit_consistency']['n_total_issues']} records")
        summary_lines.append(f"  Products affected: {self.results['unit_consistency']['n_products_with_issues']}")
        summary_lines.append("")
        summary_lines.append(f"Missing dosages: {self.results['missing_dosages']['total_missing']} records")
        summary_lines.append(f"  Products affected: {self.results['missing_dosages']['n_products_with_missing']}")
        summary_lines.append("")
        summary_lines.append(f"Extreme values check: DISABLED (awaiting fixed clinical ranges)")
        summary_lines.append("=" * 120)

        # Dosage statistics table
        stats_lines = []
        stats_lines.append("=" * 120)
        stats_lines.append("DOSAGE STATISTICS BY PRODUCT")
        stats_lines.append("=" * 120)
        stats_lines.append("")
        stats_lines.append(f"{'Product':<26} {'Unit':>6} {'Total':>7} {'Missing':>7} {'Non-Std':>10} {'Min':>8} {'Max':>8} {'Median':>8} {'Mean':>8}")
        stats_lines.append("-" * 120)

        for prod in self.results['summary']['by_product']:
            min_str = f"{prod['min']:.0f}" if prod['min'] is not None else "N/A"
            max_str = f"{prod['max']:.0f}" if prod['max'] is not None else "N/A"
            median_str = f"{prod['median']:.0f}" if prod['median'] is not None else "N/A"
            mean_str = f"{prod['mean']:.0f}" if prod['mean'] is not None else "N/A"

            stats_lines.append(
                f"{prod['product_name']:<26} "
                f"{prod['expected_unit']:>6} "
                f"{prod['n_total']:>7} "
                f"{prod['n_missing_dosage']:>7} "
                f"{prod['n_non_standard_unit']:>10} "
                f"{min_str:>8} "
                f"{max_str:>8} "
                f"{median_str:>8} "
                f"{mean_str:>8}"
            )

        stats_lines.append("=" * 120)

        # Unit issues table
        unit_lines = []
        unit_lines.append("=" * 120)
        unit_lines.append("UNIT CONSISTENCY ISSUES")
        unit_lines.append("=" * 120)
        unit_lines.append("")

        if self.results['unit_consistency']['n_total_issues'] == 0:
            unit_lines.append("No unit consistency issues found")
        else:
            unit_lines.append(f"{'Product':<26} {'Standard Unit':>13} {'Actual Unit':>12} {'N Records':>10}")
            unit_lines.append("-" * 120)

            # Group by product and actual unit
            issues_df = pd.DataFrame(self.results['unit_consistency']['issues'])
            grouped = issues_df.groupby(['product_name', 'expected_unit', 'actual_unit']).size().reset_index(name='count')

            for idx, row in grouped.iterrows():
                unit_lines.append(
                    f"{row['product_name']:<26} "
                    f"{row['expected_unit']:>13} "  # standard unit
                    f"{row['actual_unit']:>12} "    # actual unit used
                    f"{row['count']:>10}"
                )

        unit_lines.append("=" * 120)

        # Extreme values table
        extreme_lines = []
        extreme_lines.append("=" * 120)
        extreme_lines.append("EXTREME DOSAGE VALUES")
        extreme_lines.append("=" * 120)
        extreme_lines.append("")

        if self.results['extreme_values'].get('status') == 'NOT ASSESSED':
            extreme_lines.append("NOT ASSESSED - clinically defined per-product dosage ranges are")
            extreme_lines.append("pending; no extreme-value screening was performed.")
            extreme_lines.append("")
            extreme_lines.append("Unit-check coverage by product:")
            for code, cov in self.results.get('unit_check_coverage', {}).items():
                note = f" ({cov['note']})" if cov['note'] else ""
                extreme_lines.append(f"  {cov['product']:<26} {cov['status']}{note}")
        elif self.results['extreme_values']['n_total_extremes'] == 0:
            extreme_lines.append("No extreme values identified")
        else:
            extreme_lines.append(f"{'Product':<26} {'Type':>15} {'N Records':>10}")
            extreme_lines.append("-" * 120)

            # Group by product and extreme type
            extremes_df = pd.DataFrame(self.results['extreme_values']['records'])
            grouped = extremes_df.groupby(['product_name', 'extreme_type']).size().reset_index(name='count')

            for idx, row in grouped.iterrows():
                extreme_lines.append(
                    f"{row['product_name']:<26} "
                    f"{row['extreme_type']:>15} "
                    f"{row['count']:>10}"
                )

        extreme_lines.append("=" * 120)

        return (
            "\n".join(summary_lines),
            "\n".join(stats_lines),
            "\n".join(unit_lines),
            "\n".join(extreme_lines)
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
        json_file = output_path / "data_quality_module2_dosage_consistency.json"
        with open(json_file, 'w') as f:
            json.dump(_json_sanitize(self.results), f, indent=2, allow_nan=False)
        print(f"  JSON: {json_file.name}")

        # Export formatted tables
        (summary_table, stats_table, unit_table, extreme_table) = self.create_summary_tables()

        # Combined TXT report
        combined_file = output_path / "data_quality_module2_dosage_consistency.txt"
        with open(combined_file, 'w') as f:
            f.write(summary_table)
            f.write("\n\n\n")
            f.write(stats_table)
            f.write("\n\n\n")
            f.write(unit_table)
            f.write("\n\n\n")
            f.write(extreme_table)  # explicit NOT-ASSESSED status + coverage matrix
        print(f"  TXT: {combined_file.name}")

        # Export CSV tables
        self._export_csv_tables(output_path)

    def _export_csv_tables(self, output_path: Path) -> None:
        """Export detailed records in CSV format."""

        # Non-standard units (for clinic follow-up)
        if self.results['unit_consistency']['n_total_issues'] > 0:
            non_standard_units_data = []
            for issue in self.results['unit_consistency']['issues']:
                non_standard_units_data.append({
                    'PID': issue['PID'],
                    'Admin_Date': issue.get('Admin_Date', ''),
                    'Product': issue['product_name'],
                    'Issue': 'non_standard_unit',
                    'Value': issue['dosage'],
                    'Current_Unit': issue['actual_unit'],
                    'Standard_Unit': issue['expected_unit']
                })
            non_standard_units_df = pd.DataFrame(non_standard_units_data)
            csv_file = output_path / "data_quality_module2_non_standard_units.csv"
            non_standard_units_df.to_csv(csv_file, index=False)
            print(f"  CSV: {csv_file.name} ({len(non_standard_units_df)} records for clinic follow-up)")

        # Missing dosages summary
        if len(self.results['missing_dosages']['records']) > 0:
            missing_df = pd.DataFrame(self.results['missing_dosages']['records'])
            csv_file = output_path / "data_quality_module2_missing_dosages_summary.csv"
            missing_df.to_csv(csv_file, index=False)
            print(f"  CSV: {csv_file.name}")

        # Missing dosages detailed (for clinic follow-up)
        if len(self.results['missing_dosages']['detailed_records']) > 0:
            detailed_missing_df = pd.DataFrame(self.results['missing_dosages']['detailed_records'])
            csv_file = output_path / "data_quality_module2_missing_dosages.csv"
            detailed_missing_df.to_csv(csv_file, index=False)
            print(f"  CSV: {csv_file.name} ({len(detailed_missing_df)} records for clinic follow-up)")

        # Extreme values - DISABLED (awaiting fixed clinical ranges)
        # if self.results['extreme_values']['n_total_extremes'] > 0:
        #     extreme_df = pd.DataFrame(self.results['extreme_values']['records'])
        #     csv_file = output_path / "data_quality_module2_extreme_values.csv"
        #     extreme_df.to_csv(csv_file, index=False)
        #     print(f"  CSV: {csv_file.name}")

        # Dosage statistics summary
        stats_df = pd.DataFrame(self.results['summary']['by_product'])
        csv_file = output_path / "data_quality_module2_dosage_statistics.csv"
        stats_df.to_csv(csv_file, index=False)
        print(f"  CSV: {csv_file.name}")


def run_dosage_analysis(data_file: str, output_dir: str = ".") -> DosageConsistency:
    """
    Run complete dosage consistency analysis workflow.

    Args:
        data_file: Path to CSV data file
        output_dir: Directory for output files

    Returns:
        DosageConsistency object with calculated results
    """
    print("=" * 90)
    print("DATA QUALITY ANALYSIS - MODULE 2: DOSAGE CONSISTENCY")
    print("=" * 90)

    # Load data
    print("\nLoading data...")
    loader = TransfusionDataLoader()
    loader.load_data(data_file, validate=False)

    # Calculate statistics
    analyzer = DosageConsistency(loader)
    analyzer.calculate_all()

    # Display tables
    (summary_table, stats_table, unit_table, extreme_table) = analyzer.create_summary_tables()
    print("\n" + summary_table)
    print("\n" + stats_table)
    print("\n" + unit_table)
    # Extreme values table disabled - awaiting fixed clinical ranges

    # Export results
    print("\nExporting results...")
    analyzer.export_results(output_dir)

    print("\nAnalysis complete!")
    return analyzer


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python3 data_quality_module2_dosage.py <data_file.csv> <output_directory>")
        print("Example: python3 data_quality_module2_dosage.py ../test_data_150patients.csv test_data_150patients")
        sys.exit(1)

    data_file = sys.argv[1]
    output_dir = sys.argv[2]

    analyzer = run_dosage_analysis(data_file, output_dir=output_dir)
