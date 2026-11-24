"""
Descriptive Indication and Intervention Statistics Module

Calculates comprehensive descriptive statistics for indications and interventions
related to blood product administrations.

Author: Elina Nuerenberg-Goloub with Claude Sonnet 4.5 by Anthropic
Date: 2025-10-15
Revised on 2026-01-20 by Elina Nuerenberg-Goloub and Claude Opus 4.5
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List, Tuple
from transfusion_data_loader import TransfusionDataLoader
from transfusion_registry_mapping import PRODUCT_MAPPING, json_sanitize
import json
from pathlib import Path


class IndicationInterventionDescriptives:
    """
    Calculate descriptive statistics for indications and interventions.

    Calculates statistics at two levels:
    - Administration level: All product administrations
    - Patient level: Aggregated by patient
    """

    # Use central mapping from transfusion_registry_mapping
    PRODUCT_MAPPING = PRODUCT_MAPPING

    # Indication columns by product
    INDICATION_COLUMNS = {
        'Red blood cell concentrate (RBC)': {
            'column': 'X_433_7_593',
            'values': {
                '1': 'Hb <7 g/dl (independent of compensation)',
                '1.0': 'Hb <7 g/dl (independent of compensation)',
                '2': 'Hb 7-8 g/dl (anemic hypoxia signs or risk factors)',
                '2.0': 'Hb 7-8 g/dl (anemic hypoxia signs or risk factors)',
                '3': 'Hb 8-10 g/dl (individual assessment)',
                '3.0': 'Hb 8-10 g/dl (individual assessment)',
                '4': 'Massive transfusion',
                '4.0': 'Massive transfusion',
                '5': 'Other',
                '5.0': 'Other'
            }
        },
        'Fresh Frozen Plasma (FFP)': {
            'column': 'X_433_7_604',
            'values': {
                '1': 'Dilutional coagulopathy',
                '1.0': 'Dilutional coagulopathy',
                '2': 'INR >1.5 with bleeding',
                '2.0': 'INR >1.5 with bleeding',
                '3': 'INR >2.0 pre-intervention',
                '3.0': 'INR >2.0 pre-intervention',
                '4': 'Massive transfusion',
                '4.0': 'Massive transfusion',
                '5': 'Coagulation factor deficiency',
                '5.0': 'Coagulation factor deficiency',
                '6': 'Plasmapheresis',
                '6.0': 'Plasmapheresis',
                '7': 'TTP/HUS',
                '7.0': 'TTP/HUS',
                '8': 'Liver failure',
                '8.0': 'Liver failure',
                '9': 'Other',
                '9.0': 'Other'
            }
        },
        'Platelet concentrate (PC)': {
            'column': 'X_433_7_605',
            'values': {
                '1': 'Plt <10,000/µl (prophylactic)',
                '1.0': 'Plt <10,000/µl (prophylactic)',
                '2': 'Plt <50,000/µl with bleeding/intervention',
                '2.0': 'Plt <50,000/µl with bleeding/intervention',
                '3': 'Plt <100,000/µl (CNS/ophth surgery)',
                '3.0': 'Plt <100,000/µl (CNS/ophth surgery)',
                '4': 'Thrombocytopenia',
                '4.0': 'Thrombocytopenia',
                '5': 'Thrombocytopathy',
                '5.0': 'Thrombocytopathy',
                '6': 'Platelet inhibition',
                '6.0': 'Platelet inhibition',
                '7': 'Massive transfusion',
                '7.0': 'Massive transfusion',
                '8': 'Platelet function disorder',
                '8.0': 'Platelet function disorder',
                '9': 'Other',
                '9.0': 'Other'
            }
        },
        'PPSB': {
            'column': 'X_433_7_606',
            'values': {
                '1': 'Anticoagulant reversal',
                '1.0': 'Anticoagulant reversal',
                '2': 'INR >1.5 with bleeding',
                '2.0': 'INR >1.5 with bleeding',
                '3': 'INR >2.0 pre-intervention',
                '3.0': 'INR >2.0 pre-intervention',
                '4': 'Acquired coag. factor deficiency',
                '4.0': 'Acquired coag. factor deficiency',
                '5': 'Congenital coag. factor deficiency',
                '5.0': 'Congenital coag. factor deficiency',
                '6': 'Dilutional coagulopathy',
                '6.0': 'Dilutional coagulopathy',
                '7': 'Massive transfusion',
                '7.0': 'Massive transfusion',
                '8': 'Liver failure',
                '8.0': 'Liver failure',
                '9': 'Other',
                '9.0': 'Other'
            }
        },
        'Fibrinogen': {
            'column': 'X_433_7_607',
            'values': {
                '1': 'Fibrinogen <1.5 g/l with bleeding',
                '1.0': 'Fibrinogen <1.5 g/l with bleeding',
                '2': 'Fibrinogen <2.0 g/l pre-intervention',
                '2.0': 'Fibrinogen <2.0 g/l pre-intervention',
                '3': 'Massive transfusion',
                '3.0': 'Massive transfusion',
                '4': 'Acquired hypofibrinogenemia',
                '4.0': 'Acquired hypofibrinogenemia',
                '5': 'Congenital hypofibrinogenemia',
                '5.0': 'Congenital hypofibrinogenemia',
                '6': 'Dilutional coagulopathy',
                '6.0': 'Dilutional coagulopathy',
                '7': 'Liver failure',
                '7.0': 'Liver failure',
                '8': 'DIC',
                '8.0': 'DIC',
                '9': 'Other',
                '9.0': 'Other'
            }
        },
        'Albumin': {
            'column': 'X_433_7_610',
            'values': {
                '1': 'Hypoalbuminemia with edema/ascites',
                '1.0': 'Hypoalbuminemia with edema/ascites',
                '2': 'Volume replacement',
                '2.0': 'Volume replacement',
                '3': 'Other',
                '3.0': 'Other'
            }
        },
        'Iron i.v.': {
            'column': 'X_433_7_608',
            'values': {
                '1': 'Failure of oral iron treatment',
                '1.0': 'Failure of oral iron treatment',
                '2': 'Continuous excessive blood loss',
                '2.0': 'Continuous excessive blood loss',
                '3': 'Malabsorption',
                '3.0': 'Malabsorption',
                '4': 'Functional iron deficiency',
                '4.0': 'Functional iron deficiency',
                '5': 'Pregnancy with severe iron deficiency anemia',
                '5.0': 'Pregnancy with severe iron deficiency anemia',
                '6': 'Other',
                '6.0': 'Other'
            }
        },
        'Antithrombin III (ATIII)': {
            'column': 'X_433_7_612',
            'values': {
                '1': 'AT <70% with heparin resistance',
                '1.0': 'AT <70% with heparin resistance',
                '2': 'AT <50% prophylactic',
                '2.0': 'AT <50% prophylactic',
                '3': 'Congenital AT deficiency',
                '3.0': 'Congenital AT deficiency',
                '4': 'Acquired AT deficiency',
                '4.0': 'Acquired AT deficiency',
                '5': 'Other',
                '5.0': 'Other'
            }
        }
    }

    def __init__(self, loader: TransfusionDataLoader):
        """
        Initialize indication/intervention descriptives calculator.

        Args:
            loader: TransfusionDataLoader with loaded data
        """
        self.loader = loader
        self.df_all = loader.df_clean.copy()  # All records
        self.mapper = loader.mapper
        self.results = {}

        # Filter to only records WITH blood product administrations
        # This ensures we analyze only actual transfusion events, not follow-ups or empty records
        product_col = 'X_433_7_746'
        self.df = self.df_all[self.df_all[product_col].notna()].copy()

        print(f"  Total records in dataset: {len(self.df_all)}")
        print(f"  Records with blood product (administrations): {len(self.df)}")

    def calculate_all(self) -> Dict[str, Any]:
        """
        Calculate all indication and intervention statistics.

        Returns:
            Dictionary with all calculated statistics
        """
        print("\nCalculating indication and intervention statistics...")

        # Administration-level statistics
        self.results['administration_level'] = {
            'intervention_connection': self._calculate_intervention_connection(),
            'hemorrhage_risk': self._calculate_hemorrhage_risk(),
            'indications_by_product': self._calculate_indications_by_product()
        }

        # Patient-level statistics
        self.results['patient_level'] = {
            'patients_with_interventions': self._calculate_patients_with_interventions(),
            'patients_by_hemorrhage_risk': self._calculate_patients_by_hemorrhage_risk()
        }

        print("Indication and intervention statistics calculated successfully")
        return self.results

    def _calculate_intervention_connection(self) -> Dict[str, Any]:
        """Calculate statistics for intervention connection."""
        intervention_col = 'X_433_0_7'  # Connected to interventional care

        if intervention_col not in self.df.columns:
            return {'error': 'Intervention column not found'}

        total = len(self.df)
        values = self.df[intervention_col].copy()

        # Count Yes/No
        yes_count = (values == 'Y').sum()
        no_count = (values == 'N').sum()
        missing = values.isna().sum()
        total_with_data = yes_count + no_count

        return {
            'connected_yes': {
                'n': int(yes_count),
                'percent': float(yes_count / total_with_data * 100) if total_with_data > 0 else 0
            },
            'connected_no': {
                'n': int(no_count),
                'percent': float(no_count / total_with_data * 100) if total_with_data > 0 else 0
            },
            'missing': int(missing),
            'total': total,
            'total_with_data': int(total_with_data)
        }

    def _calculate_hemorrhage_risk(self) -> Dict[str, Any]:
        """Calculate hemorrhage risk distribution."""
        risk_col = 'X_433_0_10'  # Risk of haemorrhage

        if risk_col not in self.df.columns:
            return {'error': 'Hemorrhage risk column not found'}

        total = len(self.df)
        values = self.df[risk_col].astype(str)

        # Count low/high risk
        low_risk = (values.isin(['1', '1.0'])).sum()
        high_risk = (values.isin(['2', '2.0'])).sum()
        missing = self.df[risk_col].isna().sum()
        total_with_data = low_risk + high_risk

        return {
            'low_risk': {
                'n': int(low_risk),
                'percent': float(low_risk / total_with_data * 100) if total_with_data > 0 else 0,
                'description': 'Low (<500 ml expected blood loss)'
            },
            'high_risk': {
                'n': int(high_risk),
                'percent': float(high_risk / total_with_data * 100) if total_with_data > 0 else 0,
                'description': 'High (≥500 ml expected blood loss)'
            },
            'missing': int(missing),
            'total': total,
            'total_with_data': int(total_with_data)
        }

    def _calculate_indications_by_product(self) -> Dict[str, Any]:
        """Calculate detailed indication distribution by product."""
        product_col = 'X_433_7_746'
        results = {}

        for product_name, indication_info in self.INDICATION_COLUMNS.items():
            indication_col = indication_info['column']
            indication_values = indication_info['values']

            if indication_col not in self.df.columns:
                continue

            # Get data for this product
            df_product = self.df[self.df[product_col].astype(str).isin(
                [k for k, v in self.PRODUCT_MAPPING.items() if v == product_name]
            )].copy()

            if len(df_product) == 0:
                continue

            # Count indications. Missingness must be assessed BEFORE astype(str),
            # which would turn NaN into the literal string 'nan' and make
            # notna() count everything as documented.
            raw_indications = df_product[indication_col]
            total_administrations = len(df_product)
            total_with_indication = raw_indications.notna().sum()
            # Normalize documented values to plain code strings ('2.0' -> '2')
            indications = raw_indications.dropna().astype(str).str.replace(r'\.0$', '', regex=True)

            indication_counts = {}
            for code, description in indication_values.items():
                count = (indications == code).sum()
                if count > 0:
                    indication_counts[description] = {
                        'n': int(count),
                        'percent_of_product': float(count / total_administrations * 100),
                        'percent_of_documented': float(count / total_with_indication * 100) if total_with_indication > 0 else 0
                    }

            results[product_name] = {
                'total_administrations': int(total_administrations),
                'documented_indications': int(total_with_indication),
                'missing_indications': int(total_administrations - total_with_indication),
                'indications': indication_counts
            }

        return results

    def _calculate_patients_with_interventions(self) -> Dict[str, Any]:
        """Calculate patient-level intervention statistics."""
        intervention_col = 'X_433_0_7'

        if intervention_col not in self.df.columns:
            return {'error': 'Intervention column not found'}

        # EXCLUSIVE patient-level partition: a patient belongs to exactly one
        # of yes / no / conflicting / unexpected-code, so the categories sum
        # to patients_with_data.
        df_with_data = self.df[self.df[intervention_col].notna()].copy()
        codes_per_patient = (df_with_data.groupby('PID')[intervention_col]
                             .agg(lambda v: frozenset(v.astype(str).str.strip())))
        n_yes = int((codes_per_patient == frozenset({'Y'})).sum())
        n_no = int((codes_per_patient == frozenset({'N'})).sum())
        n_conflicting = int(codes_per_patient.apply(
            lambda c: {'Y', 'N'} <= c).sum())
        patients_with_data = int(len(codes_per_patient))
        n_unexpected = patients_with_data - n_yes - n_no - n_conflicting
        total_patients = self.df['PID'].nunique()

        def _cat(n):
            return {'n': int(n),
                    'percent': float(n / patients_with_data * 100) if patients_with_data > 0 else 0}

        return {
            'total_patients': int(total_patients),
            'patients_with_data': patients_with_data,
            'connected_to_intervention': _cat(n_yes),
            'not_connected': _cat(n_no),
            'conflicting_entries': _cat(n_conflicting),
            'unexpected_codes': _cat(n_unexpected),
            'note': 'categories are exclusive per patient and sum to patients_with_data'
        }

    def _calculate_patients_by_hemorrhage_risk(self) -> Dict[str, Any]:
        """Calculate patient-level hemorrhage risk statistics."""
        risk_col = 'X_433_0_10'

        if risk_col not in self.df.columns:
            return {'error': 'Hemorrhage risk column not found'}

        # EXCLUSIVE patient-level partition (see interventions): low / high /
        # conflicting / unexpected-code sum to patients_with_data.
        df_with_data = self.df[self.df[risk_col].notna()].copy()
        risk_norm = (df_with_data[risk_col].astype(str).str.strip()
                     .str.replace(r'\.0$', '', regex=True))
        codes_per_patient = (risk_norm.groupby(df_with_data['PID'])
                             .agg(lambda v: frozenset(v)))
        n_low = int((codes_per_patient == frozenset({'1'})).sum())
        n_high = int((codes_per_patient == frozenset({'2'})).sum())
        n_conflicting = int(codes_per_patient.apply(
            lambda c: {'1', '2'} <= c).sum())
        patients_with_data = int(len(codes_per_patient))
        n_unexpected = patients_with_data - n_low - n_high - n_conflicting
        total_patients = self.df['PID'].nunique()

        def _cat(n):
            return {'n': int(n),
                    'percent': float(n / patients_with_data * 100) if patients_with_data > 0 else 0}

        return {
            'total_patients': int(total_patients),
            'patients_with_data': patients_with_data,
            'low_risk': _cat(n_low),
            'high_risk': _cat(n_high),
            'conflicting_entries': _cat(n_conflicting),
            'unexpected_codes': _cat(n_unexpected),
            'note': 'categories are exclusive per patient and sum to patients_with_data'
        }

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
        admin_lines.append("=" * 90)
        admin_lines.append("INDICATION AND INTERVENTION STATISTICS: ADMINISTRATION LEVEL")
        admin_lines.append("=" * 90)
        admin_lines.append("")

        # Intervention connection
        admin_lines.append("-" * 90)
        admin_lines.append("CONNECTION TO PLANNED INTERVENTION")
        admin_lines.append("-" * 90)
        interv = self.results['administration_level']['intervention_connection']
        admin_lines.append(f"Total administrations: n = {interv['total']}")
        admin_lines.append(f"Documented: n = {interv['total_with_data']}")
        admin_lines.append("")
        admin_lines.append(f"Connected to intervention (Yes): {interv['connected_yes']['n']:>5d} ({interv['connected_yes']['percent']:>5.1f}%)")
        admin_lines.append(f"Not connected (No):             {interv['connected_no']['n']:>5d} ({interv['connected_no']['percent']:>5.1f}%)")
        admin_lines.append(f"Not documented:                 {interv['missing']:>5d}")
        admin_lines.append("")

        # Hemorrhage risk
        admin_lines.append("-" * 90)
        admin_lines.append("HEMORRHAGE RISK (BLUTUNGSRISIKO)")
        admin_lines.append("-" * 90)
        risk = self.results['administration_level']['hemorrhage_risk']
        admin_lines.append(f"Total administrations: n = {risk['total']}")
        admin_lines.append(f"Documented: n = {risk['total_with_data']}")
        admin_lines.append("")
        admin_lines.append(f"Low risk (<500 ml):             {risk['low_risk']['n']:>5d} ({risk['low_risk']['percent']:>5.1f}%)")
        admin_lines.append(f"High risk (≥500 ml):            {risk['high_risk']['n']:>5d} ({risk['high_risk']['percent']:>5.1f}%)")
        admin_lines.append(f"Not documented:                 {risk['missing']:>5d}")
        admin_lines.append("")

        # Indications by product
        admin_lines.append("-" * 90)
        admin_lines.append("INDICATIONS BY BLOOD PRODUCT")
        admin_lines.append("-" * 90)
        indications = self.results['administration_level']['indications_by_product']

        for product_name in sorted(indications.keys()):
            product_data = indications[product_name]
            admin_lines.append(f"\n{product_name}")
            admin_lines.append(f"  Total administrations: {product_data['total_administrations']}")
            admin_lines.append(f"  Documented indications: {product_data['documented_indications']}")
            admin_lines.append(f"  Missing: {product_data['missing_indications']}")
            admin_lines.append("")

            if product_data['indications']:
                admin_lines.append("  Indication                                                    n      % of all    % of doc.")
                admin_lines.append("  " + "-" * 84)
                for indication, data in sorted(product_data['indications'].items(),
                                               key=lambda x: x[1]['n'], reverse=True):
                    admin_lines.append(f"  {indication[:58]:58s} {data['n']:>5d}    {data['percent_of_product']:>5.1f}%     {data['percent_of_documented']:>5.1f}%")
            else:
                admin_lines.append("  No indications documented")

        admin_lines.append("\n" + "=" * 90)

        # Patient-level table
        patient_lines = []
        patient_lines.append("=" * 90)
        patient_lines.append("INDICATION AND INTERVENTION STATISTICS: PATIENT LEVEL")
        patient_lines.append("=" * 90)
        patient_lines.append("")

        # Patients with interventions
        patient_lines.append("-" * 90)
        patient_lines.append("PATIENTS WITH PLANNED INTERVENTIONS")
        patient_lines.append("-" * 90)
        pat_interv = self.results['patient_level']['patients_with_interventions']
        patient_lines.append(f"Total patients: n = {pat_interv['total_patients']}")
        patient_lines.append(f"Patients with documented data: n = {pat_interv['patients_with_data']}")
        patient_lines.append("")
        patient_lines.append(f"Connected to intervention: {pat_interv['connected_to_intervention']['n']:>5d} ({pat_interv['connected_to_intervention']['percent']:>5.1f}%)")
        patient_lines.append(f"Not connected:             {pat_interv['not_connected']['n']:>5d} ({pat_interv['not_connected']['percent']:>5.1f}%)")
        patient_lines.append("")

        # Patients by hemorrhage risk
        patient_lines.append("-" * 90)
        patient_lines.append("PATIENTS BY HEMORRHAGE RISK")
        patient_lines.append("-" * 90)
        pat_risk = self.results['patient_level']['patients_by_hemorrhage_risk']
        patient_lines.append(f"Total patients: n = {pat_risk['total_patients']}")
        patient_lines.append(f"Patients with documented data: n = {pat_risk['patients_with_data']}")
        patient_lines.append("")
        patient_lines.append(f"Low risk (<500 ml):  {pat_risk['low_risk']['n']:>5d} ({pat_risk['low_risk']['percent']:>5.1f}%)")
        patient_lines.append(f"High risk (≥500 ml): {pat_risk['high_risk']['n']:>5d} ({pat_risk['high_risk']['percent']:>5.1f}%)")
        patient_lines.append("")

        patient_lines.append("=" * 90)

        return "\n".join(admin_lines), "\n".join(patient_lines)

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
        json_file = output_path / "indication_intervention_statistics_detailed.json"
        with open(json_file, 'w') as f:
            json.dump(json_sanitize(self.results), f, indent=2, allow_nan=False)
        print(f"Detailed results exported to: {json_file}")

        # Export formatted tables
        admin_table, patient_table = self.create_summary_tables()

        # Administration-level table
        admin_file = output_path / "indication_intervention_statistics_administration_level.txt"
        with open(admin_file, 'w') as f:
            f.write(admin_table)
        print(f"Administration-level table exported to: {admin_file}")

        # Patient-level table
        patient_file = output_path / "indication_intervention_statistics_patient_level.txt"
        with open(patient_file, 'w') as f:
            f.write(patient_table)
        print(f"Patient-level table exported to: {patient_file}")

        # Combined table
        combined_file = output_path / "indication_intervention_statistics_combined.txt"
        with open(combined_file, 'w') as f:
            f.write(admin_table)
            f.write("\n\n\n")
            f.write(patient_table)
        print(f"Combined table exported to: {combined_file}")


def run_indication_intervention_analysis(data_file: str, output_dir: str = ".") -> IndicationInterventionDescriptives:
    """
    Run complete indication and intervention analysis workflow.

    Args:
        data_file: Path to CSV data file
        output_dir: Directory for output files

    Returns:
        IndicationInterventionDescriptives object with calculated results
    """
    print("=" * 90)
    print("INDICATION AND INTERVENTION STATISTICS ANALYSIS")
    print("=" * 90)

    # Load data
    print("\nLoading data...")
    loader = TransfusionDataLoader()
    loader.load_data(data_file, validate=False)

    # Calculate statistics
    ind_interv = IndicationInterventionDescriptives(loader)
    ind_interv.calculate_all()

    # Display tables
    admin_table, patient_table = ind_interv.create_summary_tables()
    print("\n" + admin_table)
    print("\n" + patient_table)

    # Export results
    print("\nExporting results...")
    ind_interv.export_results(output_dir)

    print("\nAnalysis complete!")
    return ind_interv


if __name__ == "__main__":
    # Example usage
    ind_interv = run_indication_intervention_analysis("../test_data_150patients.csv", output_dir=".")
