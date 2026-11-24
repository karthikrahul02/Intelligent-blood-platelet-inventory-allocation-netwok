"""
Temporal Volume Analysis Module

Calculates total volumes/amounts of blood products administered by time period:
- Monthly totals (mg, IU, ml per product)
- Quarterly totals (Q1-Q4)

Includes administration counts and patient counts per time period.

Author: Elina Nuerenberg-Goloub with Claude Sonnet 4.5 by Anthropic
Date: 2025-10-21
Revised on 2026-01-20 by Elina Nuerenberg-Goloub and Claude Opus 4.5
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List, Tuple
from transfusion_data_loader import TransfusionDataLoader
from transfusion_registry_mapping import PRODUCT_MAPPING, UNIT_MAPPING, json_sanitize
import json
import csv
from pathlib import Path
from collections import defaultdict


class TemporalVolumeAnalysis:
    """
    Calculate temporal analysis of blood product volumes.

    Analyzes total amounts (ml, IU, mg) of products administered:
    - By month (YYYY-MM)
    - By quarter (YYYY-Q1, YYYY-Q2, YYYY-Q3, YYYY-Q4)
    """

    # Use central mappings from transfusion_registry_mapping
    PRODUCT_MAPPING = PRODUCT_MAPPING
    UNIT_MAPPING = UNIT_MAPPING

    def __init__(self, loader: TransfusionDataLoader):
        """
        Initialize temporal volume analyzer.

        Args:
            loader: TransfusionDataLoader with loaded data
        """
        self.loader = loader
        self.df = loader.df_clean.copy()
        self.results = {}

    def _apply_data_quality_filters(self, df_dose: pd.DataFrame,
                                   dose_col: str, product_col: str,
                                   unit_col: str) -> pd.DataFrame:
        """
        Apply same data quality filters as treatment analysis.

        Args:
            df_dose: DataFrame with dosage data
            dose_col: Dosage column name
            product_col: Product column name
            unit_col: Unit column name

        Returns:
            Filtered DataFrame
        """
        df_filtered = df_dose.copy()

        # Convert to strings for matching
        # canonical code strings: '1' and '1.0' are the same code
        df_filtered['product_str'] = (df_filtered[product_col].astype(str)
                                      .str.replace(r'\.0$', '', regex=True))
        df_filtered['unit_str'] = (df_filtered[unit_col].astype(str)
                                   .str.replace(r'\.0$', '', regex=True))

        # Filter 1: PPSB ml - clinically implausible
        mask_ppsb_ml = (
            (df_filtered['product_str'].isin(['4', '4.0'])) &
            (df_filtered['unit_str'].isin(['1', '1.0']))
        )
        excluded_ppsb_ml = mask_ppsb_ml.sum()
        if excluded_ppsb_ml > 0:
            print(f"  DATA QUALITY: Excluded {excluded_ppsb_ml} PPSB ml records (implausible volumes)")
            df_filtered = df_filtered[~mask_ppsb_ml]

        # Filter 2: Fibrinogen IU - non-standard unit
        mask_fib_iu = (
            (df_filtered['product_str'].isin(['5', '5.0'])) &
            (df_filtered['unit_str'].isin(['2', '2.0']))
        )
        excluded_fib_iu = mask_fib_iu.sum()
        if excluded_fib_iu > 0:
            print(f"  DATA QUALITY: Excluded {excluded_fib_iu} Fibrinogen IU records (non-standard unit)")
            df_filtered = df_filtered[~mask_fib_iu]

        # Filter 3: Fibrinogen mg < 500 - implausibly low
        mask_fib_mg = (
            (df_filtered['product_str'].isin(['5', '5.0'])) &
            (df_filtered['unit_str'].isin(['3', '3.0']))
        )
        df_fib_mg = df_filtered[mask_fib_mg]
        if len(df_fib_mg) > 0:
            mask_fib_low = mask_fib_mg & (df_filtered[dose_col] < 500)
            excluded_fib_low = mask_fib_low.sum()
            if excluded_fib_low > 0:
                print(f"  DATA QUALITY: Excluded {excluded_fib_low} Fibrinogen mg records <500 mg (implausibly low)")
                df_filtered = df_filtered[~mask_fib_low]

        return df_filtered

    def calculate_all(self) -> Dict[str, Any]:
        """
        Calculate all temporal volume statistics.

        Returns:
            Dictionary with monthly and quarterly results
        """
        print("\nCalculating temporal volume analysis...")

        # Get dosage data with dates
        dose_col = 'X_433_7_22'
        unit_col = 'X_433_7_734'
        product_col = 'X_433_7_746'
        date_col = 'X_433_7_11'

        # First, get ALL records with product and date (for administration counts)
        df_all = self.df[
            (self.df[product_col].notna()) &
            (self.df[date_col].notna())
        ].copy()

        if len(df_all) == 0:
            print("  No product data with dates available")
            return {'error': 'No product data with dates'}

        print(f"  Found {len(df_all)} records with product and date information")

        # Parse dates for all records
        df_all['date'] = pd.to_datetime(df_all[date_col], errors='coerce')
        df_all = df_all[df_all['date'].notna()]
        df_all['year_month'] = df_all['date'].dt.to_period('M').astype(str)
        df_all['year'] = df_all['date'].dt.year
        df_all['quarter'] = df_all['date'].dt.quarter
        df_all['year_quarter'] = df_all['year'].astype(str) + '-Q' + df_all['quarter'].astype(str)

        # Calculate administration counts for ALL products (including those without dosage)
        print("  Calculating administration counts for all products...")
        monthly_admin_counts = self._calculate_administration_counts(df_all, 'year_month', product_col)
        quarterly_admin_counts = self._calculate_administration_counts(df_all, 'year_quarter', product_col)

        # Now filter for records with dosage (for volume calculations)
        df_dose = df_all[df_all[dose_col].notna()].copy()

        print(f"  Found {len(df_dose)} records with dosage information")

        # Apply data quality filters
        df_dose = self._apply_data_quality_filters(df_dose, dose_col, product_col, unit_col)
        print(f"  After quality filters: {len(df_dose)} records")

        # Calculate monthly volumes
        print("  Calculating monthly volumes...")
        monthly_results = self._calculate_period_volumes(
            df_dose, 'year_month', dose_col, product_col, unit_col
        )

        # Calculate quarterly volumes
        print("  Calculating quarterly volumes...")
        quarterly_results = self._calculate_period_volumes(
            df_dose, 'year_quarter', dose_col, product_col, unit_col
        )

        # Merge administration counts into monthly/quarterly results
        self._merge_administration_counts(monthly_results, monthly_admin_counts)
        self._merge_administration_counts(quarterly_results, quarterly_admin_counts)

        # Overall summary
        print("  Calculating overall summary...")
        overall_summary = self._calculate_overall_summary(df_dose, dose_col, product_col, unit_col)

        self.results = {
            'date_range': {
                'start': str(df_all['date'].min().date()),
                'end': str(df_all['date'].max().date())
            },
            'total_records_analyzed': len(df_all),
            'total_records_with_dosage': len(df_dose),
            'monthly': monthly_results,
            'quarterly': quarterly_results,
            'overall_summary': overall_summary
        }

        print("Temporal volume analysis completed successfully")
        return self.results

    def _calculate_administration_counts(self, df: pd.DataFrame, period_col: str,
                                         product_col: str) -> Dict[str, Dict[str, int]]:
        """
        Calculate administration counts per product per period (regardless of dosage).

        Args:
            df: DataFrame with product and date data
            period_col: Column name for the period
            product_col: Product column name

        Returns:
            Dictionary with counts per period per product
        """
        df = df.copy()
        df['product_str'] = df[product_col].astype(str)

        results = {}
        periods = sorted(df[period_col].unique())

        for period in periods:
            df_period = df[df[period_col] == period]
            period_counts = {
                'total_administrations': len(df_period),
                # Unique patients must come from ALL administrations in the
                # period, not only those carrying dosage data
                'unique_patients_all': int(df_period['PID'].nunique()) if 'PID' in df_period.columns else 0,
                'products': {}
            }

            # Aggregate across code spellings ('1' and '1.0' map to the same
            # product) — sum instead of overwrite
            for product_code, product_name in self.PRODUCT_MAPPING.items():
                count = len(df_period[df_period['product_str'] == product_code])
                if count > 0:
                    period_counts['products'][product_name] = \
                        period_counts['products'].get(product_name, 0) + count

            results[period] = period_counts

        return results

    def _merge_administration_counts(self, period_results: Dict[str, Any],
                                     admin_counts: Dict[str, Dict[str, int]]) -> None:
        """
        Merge administration counts into period results.
        Updates period_results in place.

        The admin_counts has the TRUE count of all administrations per product.
        The period_results only has counts for administrations WITH dosage data.
        We need to use admin_counts as the source of truth for n_administrations.

        Args:
            period_results: Results from _calculate_period_volumes
            admin_counts: Results from _calculate_administration_counts
        """
        # Get all periods from admin_counts (includes periods without dosage data)
        for period, counts in admin_counts.items():
            if period not in period_results:
                # Period exists in admin counts but not in volume results
                period_results[period] = {
                    'total_administrations': counts['total_administrations'],
                    'unique_patients': 0,
                    'products': {}
                }

            # Update total administrations to include all products
            period_results[period]['total_administrations'] = counts['total_administrations']
            # Unique patients likewise from ALL administrations, so both headline
            # numbers per period describe the same population
            if counts.get('unique_patients_all', 0):
                period_results[period]['unique_patients'] = counts['unique_patients_all']

            # Update or add product counts
            for product_name, count in counts['products'].items():
                if product_name not in period_results[period]['products']:
                    # Product has no dosage data at all, add with just the count
                    period_results[period]['products'][product_name] = {
                        'n_administrations': count
                    }
                else:
                    # Product exists but may have more administrations than dosage records
                    # Add the total administration count from admin_counts
                    period_results[period]['products'][product_name]['total_n_administrations'] = count

    def _calculate_period_volumes(self, df: pd.DataFrame, period_col: str,
                                  dose_col: str, product_col: str,
                                  unit_col: str) -> Dict[str, Any]:
        """
        Calculate volumes for a specific time period (month or quarter).

        Args:
            df: DataFrame with dosage data
            period_col: Column name for the period (year_month or year_quarter)
            dose_col: Dosage column name
            product_col: Product column name
            unit_col: Unit column name

        Returns:
            Dictionary with results per period
        """
        results = {}

        # Convert columns to strings for matching
        df = df.copy()
        df['product_str'] = df[product_col].astype(str)
        df['unit_str'] = df[unit_col].astype(str)

        # Get all periods
        periods = sorted(df[period_col].unique())

        for period in periods:
            df_period = df[df[period_col] == period]

            period_data = {
                'total_administrations': len(df_period),
                'unique_patients': df_period['PID'].nunique(),
                'products': {}
            }

            # Calculate for each product-unit combination
            for product_code, product_name in self.PRODUCT_MAPPING.items():
                df_product = df_period[df_period['product_str'] == product_code]

                if len(df_product) == 0:
                    continue

                product_data = {}

                for unit_code, unit_name in self.UNIT_MAPPING.items():
                    df_unit = df_product[df_product['unit_str'] == unit_code]

                    if len(df_unit) == 0:
                        continue

                    doses = df_unit[dose_col].dropna()

                    if len(doses) > 0:
                        product_data[unit_name] = {
                            'total_amount': float(doses.sum()),
                            'n_administrations': int(len(doses)),
                            'n_patients': int(df_unit['PID'].nunique()),
                            'mean_per_administration': float(doses.mean()),
                            'median_per_administration': float(doses.median()),
                            'min': float(doses.min()),
                            'max': float(doses.max())
                        }

                if product_data:
                    period_data['products'][product_name] = product_data

            results[period] = period_data

        return results

    def _calculate_overall_summary(self, df: pd.DataFrame, dose_col: str,
                                   product_col: str, unit_col: str) -> Dict[str, Any]:
        """
        Calculate overall summary across all time periods.

        Args:
            df: DataFrame with dosage data
            dose_col: Dosage column name
            product_col: Product column name
            unit_col: Unit column name

        Returns:
            Dictionary with overall totals per product-unit
        """
        df = df.copy()
        df['product_str'] = df[product_col].astype(str)
        df['unit_str'] = df[unit_col].astype(str)

        summary = {}

        for product_code, product_name in self.PRODUCT_MAPPING.items():
            df_product = df[df['product_str'] == product_code]

            if len(df_product) == 0:
                continue

            product_data = {}

            for unit_code, unit_name in self.UNIT_MAPPING.items():
                df_unit = df_product[df_product['unit_str'] == unit_code]

                if len(df_unit) == 0:
                    continue

                doses = df_unit[dose_col].dropna()

                if len(doses) > 0:
                    product_data[unit_name] = {
                        'total_amount': float(doses.sum()),
                        'n_administrations': int(len(doses)),
                        'n_patients': int(df_unit['PID'].nunique())
                    }

            if product_data:
                summary[product_name] = product_data

        return summary

    def create_summary_tables(self) -> Tuple[str, str, str]:
        """
        Create formatted summary tables for monthly, quarterly, and overall.

        Returns:
            Tuple of (monthly_table, quarterly_table, overall_table)
        """
        if not self.results:
            self.calculate_all()

        # Monthly table
        monthly_lines = self._create_period_table(
            self.results['monthly'],
            "MONTHLY BLOOD PRODUCT VOLUMES"
        )

        # Quarterly table
        quarterly_lines = self._create_period_table(
            self.results['quarterly'],
            "QUARTERLY BLOOD PRODUCT VOLUMES"
        )

        # Overall table
        overall_lines = self._create_overall_table()

        return (
            "\n".join(monthly_lines),
            "\n".join(quarterly_lines),
            "\n".join(overall_lines)
        )

    def _create_period_table(self, period_data: Dict[str, Any],
                            title: str) -> List[str]:
        """Create formatted table for a time period (month or quarter)."""
        lines = []
        lines.append("=" * 100)
        lines.append(title)
        lines.append("=" * 100)
        lines.append(f"Date range: {self.results['date_range']['start']} to {self.results['date_range']['end']}")
        lines.append(f"Total records analyzed: {self.results['total_records_analyzed']}")
        lines.append("")

        for period in sorted(period_data.keys()):
            data = period_data[period]
            lines.append("-" * 100)
            lines.append(f"Period: {period}")
            lines.append(f"  Total administrations: {data['total_administrations']}")
            lines.append(f"  Unique patients: {data['unique_patients']}")
            lines.append("")

            if not data['products']:
                lines.append("  No product data for this period")
                lines.append("")
                continue

            # Create table
            for product_name in sorted(data['products'].keys()):
                product_data = data['products'][product_name]
                lines.append(f"  {product_name}:")

                # Check if product has only n_administrations (no dosage data)
                if 'n_administrations' in product_data and len(product_data) == 1:
                    lines.append(f"    Administrations: {product_data['n_administrations']} (no dosage data)")
                else:
                    for unit in sorted(product_data.keys()):
                        unit_data = product_data[unit]
                        if isinstance(unit_data, dict) and 'total_amount' in unit_data:
                            lines.append(f"    {unit}:")
                            lines.append(f"      Total amount: {unit_data['total_amount']:,.1f} {unit}")
                            lines.append(f"      Administrations: {unit_data['n_administrations']}")
                            lines.append(f"      Patients: {unit_data['n_patients']}")
                            lines.append(f"      Mean per admin: {unit_data['mean_per_administration']:.1f} {unit}")
                            lines.append(f"      Median per admin: {unit_data['median_per_administration']:.1f} {unit}")
                lines.append("")

        lines.append("=" * 100)
        return lines

    def _create_overall_table(self) -> List[str]:
        """Create formatted overall summary table."""
        lines = []
        lines.append("=" * 100)
        lines.append("OVERALL SUMMARY - TOTAL VOLUMES ACROSS ALL TIME PERIODS")
        lines.append("=" * 100)
        lines.append(f"Date range: {self.results['date_range']['start']} to {self.results['date_range']['end']}")
        lines.append(f"Total records analyzed: {self.results['total_records_analyzed']}")
        lines.append("")

        summary = self.results['overall_summary']

        for product_name in sorted(summary.keys()):
            product_data = summary[product_name]
            lines.append(f"{product_name}:")

            for unit in sorted(product_data.keys()):
                unit_data = product_data[unit]
                lines.append(f"  {unit}:")
                lines.append(f"    Total amount: {unit_data['total_amount']:,.1f} {unit}")
                lines.append(f"    Total administrations: {unit_data['n_administrations']}")
                lines.append(f"    Unique patients: {unit_data['n_patients']}")
            lines.append("")

        lines.append("=" * 100)
        return lines

    def export_results(self, output_dir: str = ".") -> None:
        """
        Export results to files (JSON, TXT, CSV).

        Args:
            output_dir: Directory to save output files
        """
        if not self.results:
            self.calculate_all()

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Export detailed JSON
        json_file = output_path / "temporal_volumes_detailed.json"
        with open(json_file, 'w') as f:
            json.dump(json_sanitize(self.results), f, indent=2, allow_nan=False)
        print(f"Detailed results exported to: {json_file}")

        # Export formatted tables
        monthly_table, quarterly_table, overall_table = self.create_summary_tables()

        # Monthly table
        monthly_file = output_path / "temporal_volumes_monthly.txt"
        with open(monthly_file, 'w') as f:
            f.write(monthly_table)
        print(f"Monthly table exported to: {monthly_file}")

        # Quarterly table
        quarterly_file = output_path / "temporal_volumes_quarterly.txt"
        with open(quarterly_file, 'w') as f:
            f.write(quarterly_table)
        print(f"Quarterly table exported to: {quarterly_file}")

        # Overall table
        overall_file = output_path / "temporal_volumes_overall.txt"
        with open(overall_file, 'w') as f:
            f.write(overall_table)
        print(f"Overall summary exported to: {overall_file}")

        # Combined table
        combined_file = output_path / "temporal_volumes_combined.txt"
        with open(combined_file, 'w') as f:
            f.write(overall_table)
            f.write("\n\n\n")
            f.write(quarterly_table)
            f.write("\n\n\n")
            f.write(monthly_table)
        print(f"Combined table exported to: {combined_file}")

        # Export CSV tables
        self._export_csv_tables(output_path)

    def _export_csv_tables(self, output_path: Path) -> None:
        """Export CSV tables for monthly and quarterly data."""

        # Monthly CSV
        monthly_csv = output_path / "temporal_volumes_monthly.csv"
        self._write_period_csv(self.results['monthly'], monthly_csv, 'Month')
        print(f"Monthly CSV exported to: {monthly_csv}")

        # Quarterly CSV
        quarterly_csv = output_path / "temporal_volumes_quarterly.csv"
        self._write_period_csv(self.results['quarterly'], quarterly_csv, 'Quarter')
        print(f"Quarterly CSV exported to: {quarterly_csv}")

        # Overall summary CSV
        overall_csv = output_path / "temporal_volumes_overall.csv"
        self._write_overall_csv(self.results['overall_summary'], overall_csv)
        print(f"Overall summary CSV exported to: {overall_csv}")

    def _write_period_csv(self, period_data: Dict[str, Any],
                         filepath: Path, period_label: str) -> None:
        """Write period data (monthly or quarterly) to CSV."""
        rows = []

        # Header
        rows.append([
            period_label, 'Product', 'Unit',
            'Total Amount', 'N Administrations', 'N Patients',
            'Mean per Admin', 'Median per Admin', 'Min', 'Max'
        ])

        # Data rows
        for period in sorted(period_data.keys()):
            data = period_data[period]

            if not data['products']:
                continue

            for product_name in sorted(data['products'].keys()):
                # Clean product name
                clean_name = product_name.split('(')[0].strip()
                product_data = data['products'][product_name]

                # Check if product has only n_administrations (no dosage data)
                if 'n_administrations' in product_data and len(product_data) == 1:
                    rows.append([
                        period,
                        clean_name,
                        'N/A',
                        'N/A',
                        product_data['n_administrations'],
                        'N/A',
                        'N/A',
                        'N/A',
                        'N/A',
                        'N/A'
                    ])
                else:
                    for unit in sorted(product_data.keys()):
                        unit_data = product_data[unit]
                        if isinstance(unit_data, dict) and 'total_amount' in unit_data:
                            rows.append([
                                period,
                                clean_name,
                                unit,
                                f"{unit_data['total_amount']:.1f}",
                                unit_data['n_administrations'],
                                unit_data['n_patients'],
                                f"{unit_data['mean_per_administration']:.1f}",
                                f"{unit_data['median_per_administration']:.1f}",
                                f"{unit_data['min']:.1f}",
                                f"{unit_data['max']:.1f}"
                            ])

        # Write CSV
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(rows)

    def _write_overall_csv(self, summary_data: Dict[str, Any],
                          filepath: Path) -> None:
        """Write overall summary to CSV."""
        rows = []

        # Header
        rows.append([
            'Product', 'Unit',
            'Total Amount', 'N Administrations', 'N Patients'
        ])

        # Data rows
        for product_name in sorted(summary_data.keys()):
            # Clean product name
            clean_name = product_name.split('(')[0].strip()
            product_data = summary_data[product_name]

            for unit in sorted(product_data.keys()):
                unit_data = product_data[unit]
                rows.append([
                    clean_name,
                    unit,
                    f"{unit_data['total_amount']:.1f}",
                    unit_data['n_administrations'],
                    unit_data['n_patients']
                ])

        # Write CSV
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(rows)


def run_temporal_volume_analysis(data_file: str, output_dir: str = ".") -> TemporalVolumeAnalysis:
    """
    Run complete temporal volume analysis workflow.

    Args:
        data_file: Path to CSV data file
        output_dir: Directory for output files

    Returns:
        TemporalVolumeAnalysis object with calculated results
    """
    print("=" * 100)
    print("TEMPORAL VOLUME ANALYSIS - BLOOD PRODUCTS BY MONTH AND QUARTER")
    print("=" * 100)

    # Load data
    print("\nLoading data...")
    loader = TransfusionDataLoader()
    loader.load_data(data_file, validate=False)

    # Calculate statistics
    temporal = TemporalVolumeAnalysis(loader)
    temporal.calculate_all()

    # Display tables
    monthly_table, quarterly_table, overall_table = temporal.create_summary_tables()
    print("\n" + overall_table)
    print("\n" + quarterly_table)
    print("\n" + monthly_table)

    # Export results
    print("\nExporting results...")
    temporal.export_results(output_dir)

    print("\nAnalysis complete!")
    return temporal


if __name__ == "__main__":
    # Example usage
    temporal = run_temporal_volume_analysis("../test_data_150patients.csv", output_dir=".")
