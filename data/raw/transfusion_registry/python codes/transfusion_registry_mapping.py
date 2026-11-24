"""
Transfusion Registry Data Mapping Module (Version 2)
==============================================================

This module provides comprehensive mapping functionality for the transfusion registry data.
It maps technical column names to human-readable names, codes to values, and provides
data type information.

Author: Elina Nuerenberg-Goloub with Claude Sonnet 4.5 by Anthropic
Date: 2025-10-15
Revised on 2026-01-20 by Elina Nuerenberg-Goloub and Claude Opus 4.5
"""

import pandas as pd
from typing import Dict, Optional, List, Any
from pathlib import Path
import re


# =============================================================================
# CENTRAL PRODUCT AND UNIT MAPPINGS
# =============================================================================
# These mappings are used across all analysis modules. Import them from here
# to avoid redundancy and ensure consistency.

PRODUCT_MAPPING = {
    '1': 'Red blood cell concentrate (RBC)',
    '1.0': 'Red blood cell concentrate (RBC)',
    '2': 'Fresh Frozen Plasma (FFP)',
    '2.0': 'Fresh Frozen Plasma (FFP)',
    '3': 'Platelet concentrate (PC)',
    '3.0': 'Platelet concentrate (PC)',
    '4': 'PPSB',
    '4.0': 'PPSB',
    '5': 'Fibrinogen',
    '5.0': 'Fibrinogen',
    '6': 'Iron i.v.',
    '6.0': 'Iron i.v.',
    '7': 'Albumin',
    '7.0': 'Albumin',
    '8': 'EPO',
    '8.0': 'EPO',
    '9': 'Antithrombin III (ATIII)',
    '9.0': 'Antithrombin III (ATIII)',
    '10': 'Oral iron',
    '10.0': 'Oral iron',
    '11': 'Machine Autotransfusion (Cell Salvage)',
    '11.0': 'Machine Autotransfusion (Cell Salvage)'
}

UNIT_MAPPING = {
    '1': 'ml',
    '1.0': 'ml',
    '2': 'IU',
    '2.0': 'IU',
    '3': 'mg',
    '3.0': 'mg'
}


class TransfusionRegistryMapper:
    """
    Main mapper class for transfusion registry data.

    This class loads the data dictionaries and provides methods to:
    - Map technical column names to human-readable field names
    - Map coded values to their descriptions
    - Provide data type and validation information
    - Access metadata about data elements
    """

    def __init__(self, data_dict_path: str, permitted_values_path: str):
        """
        Initialize the mapper with data dictionary files.

        Parameters:
        -----------
        data_dict_path : str
            Path to the data elements dictionary CSV file
        permitted_values_path : str
            Path to the permitted values dictionary CSV file
        """
        self.data_dict_path = Path(data_dict_path)
        self.permitted_values_path = Path(permitted_values_path)

        # Initialize data structures
        self.column_to_name = {}
        self.column_to_metadata = {}
        self.value_code_map = {}

        # Load dictionaries
        self._load_data_dictionaries()

        # Create mapping structures
        self._create_mappings()

    def _load_data_dictionaries(self):
        """Load the data dictionary files into pandas DataFrames with robust parsing."""
        print("Loading data dictionaries...")

        # Read data elements file line by line to handle variable field counts
        data_elements_rows = []
        with open(self.data_dict_path, 'r', encoding='utf-8-sig') as f:
            header_line = f.readline().strip()
            # Only keep the first 16 columns (up to "Permissible Values")
            header_parts = header_line.split(';')[:16]

            for line_num, line in enumerate(f, start=2):
                parts = line.strip().split(';')
                if len(parts) >= 13:  # Minimum required fields
                    # Take only the first 16 fields, ignoring extra permissible values
                    row_data = parts[:16]
                    data_elements_rows.append(row_data)

        # Create DataFrame
        column_names = [
            'Form', 'Form ID:Version', 'Form Type', 'Record URN', 'Record Designation',
            'Record Mandatory', 'Record Repeatable', 'Data Element - URN',
            'Data Element - Designation', 'Data Element - Definition',
            'Data Element Mandatory', 'Data Element Repeatable', 'Data Type',
            'Data Format', 'Unit of Measure', 'Permissible Values'
        ]
        self.data_elements_df = pd.DataFrame(data_elements_rows, columns=column_names)

        # Load permitted values dictionary
        self.permitted_values_df = pd.read_csv(
            self.permitted_values_path,
            sep=';',
            encoding='utf-8-sig'
        )

        print(f"Loaded {len(self.data_elements_df)} data elements")
        print(f"Loaded {len(self.permitted_values_df)} permitted values")

    def _extract_urn_info(self, urn: str) -> Dict[str, int]:
        """
        Extract element ID and version from URN.

        Example: 'urn:osse-19:dataelement:1:1' -> {'element_id': 1, 'version': 1}
        """
        if pd.isna(urn) or not urn:
            return {'element_id': None, 'version': None}

        try:
            parts = urn.split(':')
            if len(parts) >= 5:
                element_id = int(parts[-2])
                version = int(parts[-1])
                return {'element_id': element_id, 'version': version}
        except:
            pass

        return {'element_id': None, 'version': None}

    def _create_mappings(self):
        """Create various mapping dictionaries for quick lookup."""
        print("Creating mapping structures...")

        # Map form IDs
        self.form_id_map = {
            '541': 'Basic data',
            '433': 'Entry transfusion / blood products',
            '435': 'Follow-up'
        }

        # Process data elements
        for _, row in self.data_elements_df.iterrows():
            urn = row.get('Data Element - URN', '')
            designation = row.get('Data Element - Designation', '')
            definition = row.get('Data Element - Definition', '')
            data_type = row.get('Data Type', '')
            data_format = row.get('Data Format', '')
            unit = row.get('Unit of Measure', '')
            form_id = row.get('Form ID:Version', '')
            record_urn = row.get('Record URN', '')

            if pd.isna(urn) or not urn:
                continue

            # Extract element ID
            urn_info = self._extract_urn_info(urn)
            element_id = urn_info['element_id']

            if element_id is None:
                continue

            # Extract form ID (e.g., "433:18" -> "433")
            if not pd.isna(form_id):
                form_id_clean = str(form_id).split(':')[0]
            else:
                form_id_clean = ''

            # Determine record ID
            # If record_urn exists, extract record ID, otherwise use 0
            record_id = '0'
            if not pd.isna(record_urn) and record_urn:
                try:
                    record_parts = str(record_urn).split(':')
                    if len(record_parts) >= 4:
                        record_id = record_parts[-2]
                except:
                    pass

            # Create column name patterns
            if form_id_clean:
                col_name = f"X_{form_id_clean}_{record_id}_{element_id}"

                # Store mapping
                self.column_to_name[col_name] = designation
                self.column_to_metadata[col_name] = {
                    'designation': designation,
                    'definition': definition,
                    'data_type': data_type,
                    'data_format': data_format,
                    'unit': unit,
                    'urn': urn,
                    'form_id': form_id_clean,
                    'record_id': record_id,
                    'element_id': element_id,
                    'form_name': self.form_id_map.get(form_id_clean, 'Unknown')
                }

        # Add form status columns
        for form_id, form_name in self.form_id_map.items():
            col_name = f"FormStatus_{form_id}"
            self.column_to_name[col_name] = f"{form_name} - Status"
            self.column_to_metadata[col_name] = {
                'designation': f"{form_name} - Status",
                'definition': f"Status of the {form_name} form",
                'data_type': 'enumerated',
                'data_format': 'enumerated',
                'unit': '',
                'urn': '',
                'form_id': form_id,
                'record_id': '0',
                'element_id': 'status',
                'form_name': form_name
            }

        # Value code to description mapping
        for _, row in self.permitted_values_df.iterrows():
            element_id = row.get('Element_ID', '')
            value_code = row.get('Value', '')
            value_designation = row.get('Value_Designation', '')

            if pd.isna(element_id) or pd.isna(value_code):
                continue

            try:
                element_id = int(element_id)
                value_code = str(value_code).strip()

                if element_id not in self.value_code_map:
                    self.value_code_map[element_id] = {}

                self.value_code_map[element_id][value_code] = value_designation
            except:
                continue

        print(f"Created mappings for {len(self.column_to_name)} columns")
        print(f"Created value mappings for {len(self.value_code_map)} elements")

    def get_readable_name(self, column_name: str) -> str:
        """
        Get human-readable name for a technical column name.

        Parameters:
        -----------
        column_name : str
            Technical column name (e.g., 'X_433_7_746')

        Returns:
        --------
        str
            Human-readable name or original column name if not found
        """
        return self.column_to_name.get(column_name, column_name)

    def get_column_metadata(self, column_name: str) -> Optional[Dict[str, Any]]:
        """
        Get complete metadata for a column.

        Parameters:
        -----------
        column_name : str
            Technical column name

        Returns:
        --------
        dict or None
            Metadata dictionary
        """
        return self.column_to_metadata.get(column_name)

    def decode_value(self, column_name: str, value: Any) -> str:
        """
        Decode a coded value to its human-readable description.

        Parameters:
        -----------
        column_name : str
            Technical column name
        value : Any
            Coded value

        Returns:
        --------
        str
            Human-readable value or original value as string if not found
        """
        if pd.isna(value) or value == '':
            return ''

        metadata = self.get_column_metadata(column_name)
        if not metadata:
            return str(value)

        element_id = metadata.get('element_id')
        if element_id is None or element_id == 'status':
            return str(value)

        # Get value mapping for this element
        value_map = self.value_code_map.get(element_id, {})
        value_str = str(value).strip()
        # canonical code lookup: a float-formatted code ('1.0') must decode
        # like its integer form ('1')
        if value_str not in value_map and value_str.endswith('.0'):
            canonical = value_str[:-2]
            if canonical in value_map:
                return value_map[canonical]

        return value_map.get(value_str, str(value))

    def get_blood_product_types(self) -> Dict[str, str]:
        """Get mapping of blood product type codes to names."""
        # Element ID 746 is for blood product types
        return self.value_code_map.get(746, {})

    def get_blood_groups(self) -> Dict[str, str]:
        """Get mapping of blood group codes to names."""
        # Element ID 17 is for blood groups (patient)
        # Element ID 19 is for blood groups (product)
        bg = self.value_code_map.get(17, {})
        bg.update(self.value_code_map.get(19, {}))
        return bg

    def get_columns_by_form(self, form_name: str) -> List[str]:
        """Get all column names belonging to a specific form."""
        columns = []
        for col_name, metadata in self.column_to_metadata.items():
            if metadata.get('form_name') == form_name:
                columns.append(col_name)
        return columns

    def get_lab_value_columns(self) -> Dict[str, List[str]]:
        """Get columns for laboratory values (before and after product administration)."""
        lab_columns_before = []
        lab_columns_after = []

        lab_keywords = ['Hb', 'albumin', 'Ferritin', 'Transferrin', 'Fibrinogen',
                       'Quick', 'Platelets', 'Erythropoietin', 'Antithrombin']

        for col_name, metadata in self.column_to_metadata.items():
            designation = metadata.get('designation', '').lower()

            if any(keyword.lower() in designation for keyword in lab_keywords):
                if 'before' in designation or 'prior' in designation:
                    lab_columns_before.append(col_name)
                elif 'after' in designation:
                    lab_columns_after.append(col_name)

        return {
            'before': sorted(lab_columns_before),
            'after': sorted(lab_columns_after)
        }

    def create_readable_dataframe(self, df: pd.DataFrame, decode_values: bool = False) -> pd.DataFrame:
        """
        Create a DataFrame with human-readable column names and optionally decoded values.

        Parameters:
        -----------
        df : pd.DataFrame
            Original DataFrame with technical column names
        decode_values : bool, default False
            If True, also decode coded values to descriptions

        Returns:
        --------
        pd.DataFrame
            DataFrame with readable names
        """
        # Create copy
        df_readable = df.copy()

        # Rename columns
        rename_map = {}
        for col in df.columns:
            readable_name = self.get_readable_name(col)
            # Handle duplicate readable names by appending column identifier
            if readable_name in rename_map.values() and readable_name != col:
                readable_name = f"{readable_name} ({col})"
            rename_map[col] = readable_name

        df_readable = df_readable.rename(columns=rename_map)

        # Decode values if requested
        if decode_values:
            for col in df.columns:
                if col in self.column_to_metadata:
                    metadata = self.column_to_metadata[col]
                    if metadata.get('data_type') == 'enumerated':
                        readable_col = rename_map[col]
                        df_readable[readable_col] = df[col].apply(
                            lambda x: self.decode_value(col, x)
                        )

        return df_readable

    def print_summary(self):
        """Print a summary of the mapping structure."""
        print("\n" + "="*70)
        print("TRANSFUSION REGISTRY MAPPING SUMMARY")
        print("="*70)

        print(f"\nTotal columns mapped: {len(self.column_to_name)}")
        print(f"Total value codes mapped: {sum(len(v) for v in self.value_code_map.values())}")

        print("\n--- Forms ---")
        for form_id, form_name in self.form_id_map.items():
            cols = self.get_columns_by_form(form_name)
            print(f"  {form_name} (Form {form_id}): {len(cols)} columns")

        print("\n--- Data Types ---")
        data_types = {}
        for metadata in self.column_to_metadata.values():
            dt = metadata.get('data_type', 'unknown')
            data_types[dt] = data_types.get(dt, 0) + 1
        for dt, count in sorted(data_types.items()):
            print(f"  {dt}: {count} columns")

        print("\n--- Blood Product Types ---")
        products = self.get_blood_product_types()
        for code, name in sorted(products.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 999):
            print(f"  {code}: {name}")

        print("\n--- Laboratory Values ---")
        lab_cols = self.get_lab_value_columns()
        print(f"  Before administration: {len(lab_cols['before'])} columns")
        print(f"  After administration: {len(lab_cols['after'])} columns")

        print("\n" + "="*70)


def create_mapper(base_path: str = None) -> TransfusionRegistryMapper:
    """
    Create a TransfusionRegistryMapper instance with default file paths.

    Parameters:
    -----------
    base_path : str, optional
        Base directory path. If None, uses current directory's parent.

    Returns:
    --------
    TransfusionRegistryMapper
        Initialized mapper instance
    """
    if base_path is None:
        base_path = Path(__file__).parent.parent
    else:
        base_path = Path(base_path)

    data_dict_path = base_path / "20250227_Datenelemente-Transfusionsregister.csv"
    permitted_values_path = base_path / "20250227_permitted-values-Transfusionsregister.csv"

    return TransfusionRegistryMapper(
        str(data_dict_path),
        str(permitted_values_path)
    )


# Example usage
if __name__ == "__main__":
    # Create mapper
    mapper = create_mapper()

    # Print summary
    mapper.print_summary()

    # Example: Get readable name
    print("\n\nEXAMPLE USAGE:")
    print("-" * 70)
    example_col = "X_433_7_746"
    print(f"\nColumn: {example_col}")
    print(f"Readable name: {mapper.get_readable_name(example_col)}")

    # Get metadata
    metadata = mapper.get_column_metadata(example_col)
    if metadata:
        print(f"Definition: {metadata['definition']}")
        print(f"Data type: {metadata['data_type']}")
        print(f"Element ID: {metadata['element_id']}")

    # Decode values
    print(f"\nDecoding blood product values:")
    for code in ['1', '2', '3', '4']:
        decoded = mapper.decode_value(example_col, code)
        print(f"  Code {code}: {decoded}")

    # Another example
    example_col2 = "X_433_0_17"
    print(f"\n\nColumn: {example_col2}")
    print(f"Readable name: {mapper.get_readable_name(example_col2)}")
    print(f"\nDecoding blood group values:")
    for code in ['A', 'B', 'AB', '0']:
        decoded = mapper.decode_value(example_col2, code)
        print(f"  Code {code}: {decoded}")


# =========================================================================
# Clinical range registry - the single versioned source for permissible
# value ranges in code.
#
# Authoritative specification: physician_value_ranges.csv (package root),
# version 2026-08-21, approved by the study lead. This registry mirrors
# that specification; the test battery compares the two value by value.
# Bounds are inclusive and expressed in the CANONICAL analysis unit of
# each parameter: serum albumin is specified in g/dl (binding; entries
# >= 100 are legacy wrong-scale mg/dl values, converted once and
# audited), platelets in /ul.
#
# Consumers: lab_value_quality.py (central analysis series and screening)
# and data_quality_module4_validity.py (validity screening). Parameter
# bounds must not be defined anywhere else.
#
# Zero floors (study-lead decision 2026-08-21): a table floor of 0 on a
# LABORATORY parameter is the entry floor of the field, not a plausible
# measured value. Documented laboratory values <= 0 are therefore excluded
# as impossible on EVERY path (statistics, quality screening, validity
# module) and reported as data-quality findings - itemized with PID and
# value, counted separately from missing values, and never conflated with
# missingness. Machine-autotransfusion volumes keep their inclusive 0
# floors (a recovered volume of 0 ml is a real quantity).
# =========================================================================
CLINICAL_RANGE_REGISTRY = {
    'version': '2026-08-21',
    'source': ('authoritative range specification physician_value_ranges.csv, '
               'version 2026-08-21, approved by the study lead'),
    'parameters': {
        # demographics
        'height_cm':            {'min': 20,   'max': 220,     'unit': 'cm'},
        'weight_kg':            {'min': 1,    'max': 250,     'unit': 'kg'},  # registry currently records integer kg
        # laboratory values (canonical units)
        'hemoglobin':           {'min': 1.0,  'max': 20.0,    'unit': 'g/dl', 'nonpositive_impossible': True},
        'serum_albumin':        {'min': 0.0,  'max': 7.0,     'unit': 'g/dl', 'nonpositive_impossible': True},
        'ferritin':             {'min': 5,    'max': 5000,    'unit': 'µg/L', 'nonpositive_impossible': True},
        'transferrin':          {'min': 5,    'max': 100,     'unit': '%', 'nonpositive_impossible': True},
        'fibrinogen':           {'min': 0,    'max': 1000,    'unit': 'mg/dl', 'nonpositive_impossible': True},
        'quicks_test':          {'min': 0,    'max': 500,     'unit': '%', 'nonpositive_impossible': True},
        'platelets':            {'min': 1000, 'max': 1000000, 'unit': '/µl', 'nonpositive_impossible': True},
        'epo_plasma':           {'min': 0,    'max': 200,     'unit': 'U/L', 'nonpositive_impossible': True},
        'atiii_activity':       {'min': 30,   'max': 150,     'unit': '%', 'nonpositive_impossible': True},
        # machine autotransfusion
        'mat_wound_blood':      {'min': 0,    'max': 10000,   'unit': 'ml'},
        'mat_wound_hematocrit': {'min': 15,   'max': 65,      'unit': '%'},
        'recovered_rbc_volume': {'min': 0,    'max': 3000,    'unit': 'ml'},
        'recovered_hematocrit': {'min': 15,   'max': 90,      'unit': '%'},
    },
    # EPO (citrated plasma), elements 598/600: the range table records
    # "not widely used, no ranges defined" - documented as not assessed.
    'not_assessed': {
        'epo_citrated_plasma': 'range table: not widely used, no ranges defined',
    },
}


def json_sanitize(obj):
    """
    Make a result structure safe for RFC 8259 JSON export: NaN/Infinity
    become null, numpy scalars become native Python types, containers are
    recursed. Every module's JSON export runs through this one function
    (paired with json.dump(..., allow_nan=False)).
    """
    import datetime as _dt
    import math

    import numpy as _np
    import pandas as _pd

    if isinstance(obj, dict):
        return {k: json_sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_sanitize(v) for v in obj]
    if isinstance(obj, _np.ndarray):
        return [json_sanitize(v) for v in obj.tolist()]
    if isinstance(obj, _np.integer):
        return int(obj)
    # numpy floating FIRST (np.float32 is NOT a Python float subclass)
    if isinstance(obj, (_np.floating, float)):
        f = float(obj)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    if isinstance(obj, _np.bool_):
        return bool(obj)
    # scalar missing markers (pd.NA, pd.NaT) -> null BEFORE the datetime
    # branch (pd.NaT is a datetime subclass and must not become the string
    # "NaT"); guarded so container types can never reach pd.isna()
    try:
        if obj is not None and not isinstance(obj, (str, int, bool)) and _pd.isna(obj):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(obj, (_pd.Timestamp, _np.datetime64, _dt.datetime, _dt.date)):
        return str(obj)
    return obj


def clinical_range(parameter):
    """Return (min, max, unit) for a parameter from the central registry."""
    p = CLINICAL_RANGE_REGISTRY['parameters'][parameter]
    return (p['min'], p['max'], p['unit'])
