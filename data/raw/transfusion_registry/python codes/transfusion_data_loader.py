"""
Transfusion Registry Data Loader Module
========================================

This module provides robust data loading functionality for transfusion registry files.
It handles the complex CSV structure, applies proper data types, integrates with the
mapping module, and provides validation functions.

Author: Elina Nuerenberg-Goloub with Claude Sonnet 4.5 by Anthropic
Date: 2025-10-15
Revised on 2026-01-25 by Elina Nuerenberg-Goloub and Claude Opus 4.5
"""

import os

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Union
from datetime import datetime
import warnings

if int(pd.__version__.split('.')[0]) >= 3:
    warnings.warn(
        f"This pipeline is validated on the pandas 2.3 series "
        f"(requirements.txt pins pandas>=2.3.0,<3.0); you are running "
        f"pandas {pd.__version__}. Results are not guaranteed.")

from transfusion_registry_mapping import TransfusionRegistryMapper, create_mapper


# Time-invariant basic-data fields used to rank candidate index rows
BASIC_DATA_COLUMNS = ['X_541_0_1', 'X_433_0_4', 'X_433_0_2', 'X_433_0_3']


def select_patient_index_rows(df, basic_columns=None):
    """
    One REAL documented row per patient (no per-column compositing).

    ``GroupBy.first()`` takes the first non-missing value per COLUMN, which
    can combine height from one row with weight and sex from others into a
    patient that never existed. This helper instead keeps one actual row
    per patient: rows are ranked by (1) completeness of the time-invariant
    basic-data fields (year of birth, sex, height, weight), (2) episode
    date, (3) original order, and the top row is kept in full. BMI and
    estimated blood volume therefore always come from one and the same
    documented row.
    """
    cols = [c for c in (basic_columns or BASIC_DATA_COLUMNS) if c in df.columns]
    ranked = df.copy()
    ranked['_basic_n'] = ranked[cols].notna().sum(axis=1) if cols else 0
    sort_cols, asc = ['PID', '_basic_n'], [True, False]
    if 'Episode date' in ranked.columns:
        sort_cols.append('Episode date')
        asc.append(True)
    ranked = ranked.sort_values(sort_cols, ascending=asc, kind='stable')
    return ranked.drop_duplicates(subset='PID', keep='first').drop(columns=['_basic_n'])


class TransfusionDataLoader:
    """
    Main data loader class for transfusion registry files.

    This class handles:
    - Loading CSV files with correct header row
    - Data type conversion
    - Missing data handling
    - Integration with mapping module
    - Data validation
    - Wide-to-long format conversion for repeatable records
    """

    def __init__(self, mapper: Optional[TransfusionRegistryMapper] = None,
                 base_path: Optional[str] = None):
        """
        Initialize the data loader.

        Parameters:
        -----------
        mapper : TransfusionRegistryMapper, optional
            Pre-initialized mapper instance. If None, will create one.
        base_path : str, optional
            Base directory path for data files
        """
        if mapper is None:
            self.mapper = create_mapper(base_path)
        else:
            self.mapper = mapper
        self.unparseable_dates = []  # data-quality findings from date parsing
        self.patient_attribute_conflicts = []  # conflicting time-invariant attributes
        self.integer_field_decimals = []  # decimal values in INTEGER-declared fields

        self.base_path = Path(base_path) if base_path else Path.cwd()

        # Store loaded data
        self.df_raw = None
        self.df_clean = None
        self.metadata = {}

    def load_data(self, file_path: str, validate: bool = True) -> pd.DataFrame:
        """
        Load transfusion registry data from CSV file.

        The CSV structure has 7 metadata rows before the actual header (row 8).
        Data starts from row 9.

        Parameters:
        -----------
        file_path : str
            Path to the CSV file
        validate : bool, default True
            Whether to run validation checks after loading

        Returns:
        --------
        pd.DataFrame
            Loaded data with proper types
        """
        print(f"Loading data from: {file_path}")

        # Read the CSV file starting from row 8 (0-indexed row 7) as header
        # Row 8 contains: PID, patient repeat number, Episode number, Location,
        # Episode date, Episode description, Unique ID, FormStatus_*, X_*_*_*
        self.df_raw = pd.read_csv(
            file_path,
            sep=';',
            encoding='utf-8-sig',
            skiprows=7,  # Skip first 7 metadata rows
            low_memory=False
        )

        print(f"Loaded {len(self.df_raw)} records with {len(self.df_raw.columns)} columns")

        # Store metadata about the file
        self.metadata['file_path'] = file_path
        self.metadata['load_timestamp'] = datetime.now()
        self.metadata['n_records'] = len(self.df_raw)
        self.metadata['n_columns'] = len(self.df_raw.columns)

        # Clean the data
        self.df_clean = self._clean_data(self.df_raw.copy())

        # Apply data types
        self.df_clean = self._apply_data_types(self.df_clean)

        # Check time-invariant patient attributes for conflicting entries
        self._check_patient_attribute_conflicts()

        # Validate if requested
        if validate:
            self._validate_data()

        print("Data loading complete")

        return self.df_clean

    # Time-invariant patient attributes: documented once per patient on the
    # basic-data form. Downstream patient-level reductions take the first
    # non-missing value per patient, which is only safe when a patient does
    # not carry contradictory entries — so conflicts are detected here and
    # reported as a data-quality finding.
    TIME_INVARIANT_ATTRIBUTES = {
        'X_433_0_4': 'sex',
        'X_433_0_2': 'height',
        'X_433_0_3': 'weight',
        'X_541_0_1': 'year of birth',
    }

    def _check_patient_attribute_conflicts(self) -> None:
        """
        Flag patients whose time-invariant attributes (sex, height, weight,
        year of birth) carry more than one distinct non-missing value across
        their rows. Findings are collected in
        ``self.patient_attribute_conflicts`` as
        {'PID', 'column', 'attribute', 'values'} and reported with a warning;
        the values themselves are left unchanged (patient-level statistics
        keep using the first documented value).
        """
        self.patient_attribute_conflicts = []
        df = self.df_clean
        if df is None or 'PID' not in df.columns:
            return
        for col, attribute in self.TIME_INVARIANT_ATTRIBUTES.items():
            if col not in df.columns:
                continue
            nunique = df.groupby('PID')[col].nunique(dropna=True)
            for pid in nunique.index[nunique > 1]:
                values = sorted(
                    df.loc[df['PID'] == pid, col].dropna().unique().astype(str))
                self.patient_attribute_conflicts.append(
                    {'PID': pid, 'column': col, 'attribute': attribute,
                     'values': values})
        if self.patient_attribute_conflicts:
            n_patients = len({c['PID'] for c in self.patient_attribute_conflicts})
            warnings.warn(
                f"{n_patients} patient(s) carry conflicting time-invariant "
                f"attribute entries (see loader.patient_attribute_conflicts); "
                f"patient-level statistics use the first documented value")


    def export_qc_findings(self, output_dir: str) -> str:
        """
        Persist the loader's data-quality findings (unparseable date values
        and conflicting time-invariant patient attributes) as CSV so they
        are part of every run's artifacts rather than living only in memory.

        Returns the path of the written CSV (empty string if nothing to write
        - an empty findings file is still written so the absence of findings
        is documented, not silent).
        """
        import csv as _csv
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, 'loader_qc_findings.csv')
        with open(path, 'w', encoding='utf-8', newline='') as f:
            w = _csv.writer(f)
            w.writerow(['finding_type', 'column', 'PID', 'value', 'detail'])
            for u in self.unparseable_dates:
                w.writerow(['unparseable_date', u['column'], u['PID'],
                            u['raw_value'],
                            'non-empty value matches neither YYYY-MM-DD nor '
                            'DD/MM/YYYY; set to missing in the analysis'])
            for c in self.patient_attribute_conflicts:
                w.writerow(['attribute_conflict', c['column'], c['PID'],
                            ' / '.join(c['values']),
                            f"conflicting {c['attribute']} entries; patient-level "
                            f"statistics use the first documented value"])
            for d in self.integer_field_decimals:
                w.writerow(['decimal_in_integer_field', d['column'], d['PID'],
                            d['raw_value'],
                            'decimal value in an INTEGER-declared field; kept '
                            'unchanged (column analyzed as float)'])
        n = (len(self.unparseable_dates) + len(self.patient_attribute_conflicts)
             + len(self.integer_field_decimals))
        print(f"  Loader QC findings exported: {path} ({n} finding(s))")
        return path

    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean the raw data.

        Parameters:
        -----------
        df : pd.DataFrame
            Raw data

        Returns:
        --------
        pd.DataFrame
            Cleaned data
        """
        print("Cleaning data...")

        # Strip whitespace from column names
        df.columns = df.columns.str.strip()

        # Replace empty strings with NaN
        df = df.replace(r'^\s*$', np.nan, regex=True)

        # Strip whitespace from string columns
        for col in df.columns:
            if df[col].dtype == 'object':
                try:
                    df[col] = df[col].str.strip()
                except AttributeError:
                    # Column doesn't support string operations
                    pass

        # Filter out test location data (Verika)
        if 'Location' in df.columns:
            n_before = len(df)
            df = df[df['Location'] != 'Verika (Teststandort)']
            n_removed = n_before - len(df)
            if n_removed > 0:
                print(f"  Excluded {n_removed} rows from test location (Verika)")

        return df

    def _apply_data_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply correct data types based on metadata from mapper.

        Parameters:
        -----------
        df : pd.DataFrame
            Cleaned data

        Returns:
        --------
        pd.DataFrame
            Data with correct types
        """
        print("Applying data types...")

        # Administrative columns - handle explicitly
        admin_cols = {
            'PID': 'str',
            'patient repeat number': 'Int64',
            'Episode number': 'Int64',
            'Location': 'str',
            'Episode date': 'str',  # Will parse separately
            'Episode description': 'str'
        }

        for col, dtype in admin_cols.items():
            if col in df.columns:
                try:
                    if dtype == 'str':
                        df[col] = df[col].astype(str)
                    elif dtype == 'Int64':
                        df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
                except Exception as e:
                    warnings.warn(f"Could not convert {col} to {dtype}: {e}")

        # Parse Episode date - same dual-format rule as the DATE elements
        # (both formats may mix within the column; unparseable non-empty
        # values are collected as data-quality findings)
        if 'Episode date' in df.columns:
            raw = df['Episode date'].replace({'nan': None, 'None': None, '': None})
            parsed = pd.to_datetime(raw, format='%d/%m/%Y', errors='coerce')
            alt = pd.to_datetime(raw, format='%Y-%m-%d', errors='coerce')
            parsed = parsed.fillna(alt)
            bad = raw.notna() & parsed.isna()
            if bad.any():
                pid_series = df['PID'] if 'PID' in df.columns else raw.index
                for pid, val in zip(pid_series[bad], raw[bad]):
                    self.unparseable_dates.append(
                        {'column': 'Episode date', 'PID': pid, 'raw_value': val})
                warnings.warn(
                    f"Episode date: {int(bad.sum())} non-empty value(s) could "
                    f"not be parsed and were set to missing "
                    f"(see loader.unparseable_dates)")
            df['Episode date'] = parsed

        # Apply types to form columns based on metadata
        for col in df.columns:
            if col.startswith('X_') or col.startswith('FormStatus_'):
                metadata = self.mapper.get_column_metadata(col)

                if metadata:
                    data_type = metadata.get('data_type', '')

                    try:
                        if data_type == 'INTEGER':
                            # Cast to Int64 only when every documented value is
                            # actually integral. Decimal values (e.g. thousands-
                            # scale platelet entries, or decimal weights should
                            # the registry permit them in the future) are KEPT
                            # unchanged as float64 and recorded as a QC finding
                            # instead of failing the cast with a bare warning.
                            nums = pd.to_numeric(df[col], errors='coerce')
                            nonint = nums.notna() & (nums % 1 != 0)
                            if nonint.any():
                                pid_series = df['PID'] if 'PID' in df.columns else nums.index
                                for pid, val in zip(pid_series[nonint], df.loc[nonint, col]):
                                    self.integer_field_decimals.append(
                                        {'column': col, 'PID': pid, 'raw_value': val})
                                df[col] = nums
                            else:
                                df[col] = nums.astype('Int64')

                        elif data_type == 'FLOAT':
                            df[col] = pd.to_numeric(df[col], errors='coerce')

                        elif data_type == 'DATE':
                            # Parse both supported formats against the
                            # ORIGINAL values (never re-parse a coerced
                            # series); collect unparseable non-empty raw
                            # values as a data-quality finding
                            raw = df[col]
                            parsed = pd.to_datetime(raw, format='%Y-%m-%d', errors='coerce')
                            alt = pd.to_datetime(raw, format='%d/%m/%Y', errors='coerce')
                            parsed = parsed.fillna(alt)
                            bad = raw.notna() & parsed.isna()
                            if bad.any():
                                for pid, val in zip(df.loc[bad, 'PID'], raw[bad]):
                                    self.unparseable_dates.append(
                                        {'column': col, 'PID': pid, 'raw_value': val})
                                warnings.warn(
                                    f"{col}: {int(bad.sum())} non-empty date value(s) "
                                    f"could not be parsed and were set to missing "
                                    f"(see loader.unparseable_dates)")
                            df[col] = parsed

                        elif data_type == 'BOOLEAN':
                            # Convert various boolean representations
                            df[col] = df[col].map({
                                'true': True, 'True': True, 'TRUE': True, 't': True, 'T': True,
                                'false': False, 'False': False, 'FALSE': False, 'f': False, 'F': False,
                                'yes': True, 'Yes': True, 'YES': True, 'y': True, 'Y': True,
                                'no': False, 'No': False, 'NO': False, 'n': False, 'N': False,
                                '1': True, '0': False, 1: True, 0: False
                            })

                        elif data_type in ['enumerated', 'STRING']:
                            # Keep as string
                            if not df[col].isna().all():
                                df[col] = df[col].astype(str)
                                df[col] = df[col].replace('nan', np.nan)

                    except Exception as e:
                        warnings.warn(f"Could not convert {col} ({data_type}): {e}")

        return df

    def _validate_data(self):
        """
        Run validation checks on loaded data.
        """
        print("\nRunning validation checks...")

        issues = []

        # Check for required columns
        required_cols = ['PID', 'Episode number']
        missing_required = [col for col in required_cols if col not in self.df_clean.columns]
        if missing_required:
            issues.append(f"Missing required columns: {missing_required}")

        # Check for duplicate PIDs with same episode
        if 'PID' in self.df_clean.columns and 'Episode number' in self.df_clean.columns:
            duplicates = self.df_clean[['PID', 'Episode number']].duplicated()
            if duplicates.any():
                n_duplicates = duplicates.sum()
                issues.append(f"Found {n_duplicates} duplicate PID-Episode combinations")

        # Check data completeness for key variables
        key_vars = ['X_541_0_1', 'X_433_0_4', 'X_433_7_746']  # Birth year, sex, product type
        for var in key_vars:
            if var in self.df_clean.columns:
                missing_pct = (self.df_clean[var].isna().sum() / len(self.df_clean)) * 100
                if missing_pct > 50:
                    var_name = self.mapper.get_readable_name(var)
                    issues.append(f"High missingness in {var_name} ({var}): {missing_pct:.1f}%")

        # Check date validity
        date_cols = [col for col in self.df_clean.columns
                    if col.startswith('X_') and self.mapper.get_column_metadata(col)
                    and self.mapper.get_column_metadata(col).get('data_type') == 'DATE']

        for col in date_cols:
            if col in self.df_clean.columns:
                valid_dates = self.df_clean[col].notna()
                if valid_dates.any():
                    future_dates = self.df_clean.loc[valid_dates, col] > pd.Timestamp.now()
                    if future_dates.any():
                        var_name = self.mapper.get_readable_name(col)
                        issues.append(f"Future dates found in {var_name} ({col})")

        # Print validation results
        if issues:
            print("\nValidation Issues Found:")
            for i, issue in enumerate(issues, 1):
                print(f"  {i}. {issue}")
        else:
            print("  All validation checks passed")

        self.metadata['validation_issues'] = issues
        self.metadata['validation_passed'] = len(issues) == 0

    def get_patient_level_data(self) -> pd.DataFrame:
        """
        Extract patient-level data (one row per patient).

        This includes basic data (Form 541) and non-repeatable entry data (Form 433).

        Returns:
        --------
        pd.DataFrame
            Patient-level data
        """
        if self.df_clean is None:
            raise ValueError("No data loaded. Call load_data() first.")

        # Get columns for patient-level data
        patient_cols = ['PID', 'patient repeat number', 'Episode number',
                       'Location', 'Episode date', 'Episode description']

        # Add Basic data columns (Form 541)
        patient_cols.extend([col for col in self.df_clean.columns
                           if col.startswith('X_541_') or col == 'FormStatus_541'])

        # Add non-repeatable Entry columns (Form 433, record 0)
        patient_cols.extend([col for col in self.df_clean.columns
                           if col.startswith('X_433_0_') or col == 'FormStatus_433'])

        # Add Follow-up columns (Form 435)
        patient_cols.extend([col for col in self.df_clean.columns
                           if col.startswith('X_435_') or col == 'FormStatus_435'])

        # Filter to existing columns
        patient_cols = [col for col in patient_cols if col in self.df_clean.columns]

        return self.df_clean[patient_cols].copy()

    def get_product_level_data(self) -> pd.DataFrame:
        """
        Extract product administration data (one row per product administration).

        This converts the wide format (multiple product columns) to long format
        (one row per product).

        Returns:
        --------
        pd.DataFrame
            Product-level data in long format
        """
        if self.df_clean is None:
            raise ValueError("No data loaded. Call load_data() first.")

        # In the current structure, each row can have multiple products
        # For proper analysis, we need to identify which products were given
        # This requires looking at X_433_7_746 (product type) and related columns

        # For now, return the data with product columns (Record 7)
        # A more sophisticated approach would parse multiple products per patient

        product_cols = ['PID', 'Episode number', 'Episode date']

        # Add all product administration columns (Record 7)
        product_cols.extend([col for col in self.df_clean.columns
                           if col.startswith('X_433_7_')])

        # Filter to existing columns
        product_cols = [col for col in product_cols if col in self.df_clean.columns]

        # Filter to rows where product was administered
        df_products = self.df_clean[product_cols].copy()
        df_products = df_products[df_products['X_433_7_746'].notna()]

        return df_products

    def create_analysis_dataset(self, decode_values: bool = True,
                               readable_names: bool = True) -> pd.DataFrame:
        """
        Create a dataset ready for statistical analysis.

        Parameters:
        -----------
        decode_values : bool, default True
            Whether to decode enumerated values to descriptions
        readable_names : bool, default True
            Whether to use human-readable column names

        Returns:
        --------
        pd.DataFrame
            Analysis-ready dataset
        """
        if self.df_clean is None:
            raise ValueError("No data loaded. Call load_data() first.")

        df_analysis = self.df_clean.copy()

        # Decode values if requested
        if decode_values:
            for col in df_analysis.columns:
                if col.startswith('X_') or col.startswith('FormStatus_'):
                    metadata = self.mapper.get_column_metadata(col)
                    if metadata and metadata.get('data_type') == 'enumerated':
                        df_analysis[col] = df_analysis[col].apply(
                            lambda x: self.mapper.decode_value(col, x) if pd.notna(x) else np.nan
                        )

        # Rename columns if requested
        if readable_names:
            rename_map = {}
            for col in df_analysis.columns:
                readable = self.mapper.get_readable_name(col)
                if readable != col:
                    # Handle duplicates
                    if readable in rename_map.values():
                        readable = f"{readable} ({col})"
                    rename_map[col] = readable

            df_analysis = df_analysis.rename(columns=rename_map)

        return df_analysis

    def calculate_age(self, reference_date: Optional[Union[str, pd.Timestamp]] = None) -> pd.Series:
        """
        Calculate patient age from birth year.

        Parameters:
        -----------
        reference_date : str or pd.Timestamp, optional
            Reference date for age calculation. If None, uses Episode date.
            Can be 'now' for current date.

        Returns:
        --------
        pd.Series
            Patient ages
        """
        if self.df_clean is None:
            raise ValueError("No data loaded. Call load_data() first.")

        birth_year_col = 'X_541_0_1'

        if birth_year_col not in self.df_clean.columns:
            raise ValueError(f"Birth year column {birth_year_col} not found")

        birth_year = pd.to_numeric(self.df_clean[birth_year_col], errors='coerce')

        # Determine reference date
        if reference_date == 'now':
            ref_year = pd.Timestamp.now().year
        elif reference_date is None:
            # Use Episode date if available
            if 'Episode date' in self.df_clean.columns:
                ref_year = self.df_clean['Episode date'].dt.year
            else:
                ref_year = pd.Timestamp.now().year
        else:
            ref_year = pd.to_datetime(reference_date).year

        age = ref_year - birth_year

        # Set unrealistic ages to NaN
        age = age.where((age >= 0) & (age <= 120))

        return age

    def get_lab_value_changes(self) -> pd.DataFrame:
        """
        Calculate changes in laboratory values (after - before).

        Returns:
        --------
        pd.DataFrame
            DataFrame with lab value changes
        """
        if self.df_clean is None:
            raise ValueError("No data loaded. Call load_data() first.")

        lab_cols = self.mapper.get_lab_value_columns()

        changes = pd.DataFrame(index=self.df_clean.index)
        changes['PID'] = self.df_clean['PID']

        # Match before and after columns
        for before_col in lab_cols['before']:
            # Find corresponding after column
            # Extract lab name from before column
            before_name = self.mapper.get_readable_name(before_col)

            for after_col in lab_cols['after']:
                after_name = self.mapper.get_readable_name(after_col)

                # Check if they measure the same thing
                # Remove 'before'/'after'/'prior to'/'prior' and 'product administration'
                before_base = (before_name.replace('before product administration', '')
                                         .replace('prior to product administration', '')
                                         .replace('before', '')
                                         .replace('prior', '')
                                         .strip())
                after_base = (after_name.replace('after product administration', '')
                                       .replace('after', '')
                                       .strip())

                if before_base.lower() == after_base.lower():
                    # Calculate change
                    before_vals = pd.to_numeric(self.df_clean[before_col], errors='coerce')
                    after_vals = pd.to_numeric(self.df_clean[after_col], errors='coerce')

                    change_col = f"{before_base}_change"
                    changes[change_col] = after_vals - before_vals

                    break

        return changes

    def print_summary(self):
        """
        Print a comprehensive summary of loaded data.
        """
        if self.df_clean is None:
            print("No data loaded")
            return

        print("\n" + "="*70)
        print("TRANSFUSION REGISTRY DATA SUMMARY")
        print("="*70)

        print(f"\nFile: {self.metadata.get('file_path', 'Unknown')}")
        print(f"Loaded: {self.metadata.get('load_timestamp', 'Unknown')}")
        print(f"Records: {self.metadata['n_records']}")
        print(f"Columns: {self.metadata['n_columns']}")

        # Patient information
        if 'PID' in self.df_clean.columns:
            n_patients = self.df_clean['PID'].nunique()
            print(f"\nUnique patients: {n_patients}")

        # Age distribution
        try:
            ages = self.calculate_age()
            print(f"\nAge: {ages.mean():.1f} ± {ages.std():.1f} years (n={ages.notna().sum()})")
            print(f"  Range: {ages.min():.0f} - {ages.max():.0f} years")
        except (ValueError, KeyError, TypeError):
            pass  # Age calculation not possible with current data

        # Sex distribution
        sex_col = 'X_433_0_4'
        if sex_col in self.df_clean.columns:
            sex_counts = self.df_clean[sex_col].value_counts()
            print(f"\nSex distribution:")
            for code, count in sex_counts.items():
                decoded = self.mapper.decode_value(sex_col, code)
                pct = (count / len(self.df_clean)) * 100
                print(f"  {decoded}: {count} ({pct:.1f}%)")

        # Product type distribution
        product_col = 'X_433_7_746'
        if product_col in self.df_clean.columns:
            product_counts = self.df_clean[product_col].value_counts()
            print(f"\nBlood product distribution:")
            for code, count in product_counts.items():
                if pd.notna(code):
                    decoded = self.mapper.decode_value(product_col, code)
                    pct = (count / self.df_clean[product_col].notna().sum()) * 100
                    print(f"  {decoded}: {count} ({pct:.1f}%)")

        # Missing data summary
        print(f"\nMissing data summary (top 10 columns):")
        missing = self.df_clean.isna().sum()
        missing_pct = (missing / len(self.df_clean)) * 100
        missing_df = pd.DataFrame({
            'Column': missing.index,
            'Missing': missing.values,
            'Percent': missing_pct.values
        })
        missing_df = missing_df[missing_df['Missing'] > 0].sort_values('Missing', ascending=False).head(10)

        for _, row in missing_df.iterrows():
            readable = self.mapper.get_readable_name(row['Column'])
            if len(readable) > 50:
                readable = readable[:47] + "..."
            print(f"  {readable}: {row['Missing']} ({row['Percent']:.1f}%)")

        # Validation status
        print(f"\nValidation: {'PASSED' if self.metadata.get('validation_passed', False) else 'ISSUES FOUND'}")

        print("\n" + "="*70)


def load_transfusion_data(file_path: str, base_path: Optional[str] = None,
                         validate: bool = True) -> Tuple[pd.DataFrame, TransfusionDataLoader]:
    """
    Convenience function to load transfusion registry data.

    Parameters:
    -----------
    file_path : str
        Path to the CSV file
    base_path : str, optional
        Base directory for mapper files
    validate : bool, default True
        Whether to validate data after loading

    Returns:
    --------
    tuple
        (DataFrame with clean data, DataLoader instance)
    """
    loader = TransfusionDataLoader(base_path=base_path)
    df = loader.load_data(file_path, validate=validate)

    return df, loader


# Example usage
if __name__ == "__main__":
    # Example: Load data (update filename to current export)
    data_file = "../test_data_150patients.csv"

    loader = TransfusionDataLoader()
    df = loader.load_data(data_file)

    # Print summary
    loader.print_summary()

    # Example: Get analysis dataset
    print("\n\nCreating analysis dataset...")
    df_analysis = loader.create_analysis_dataset(
        decode_values=True,
        readable_names=True
    )
    print(f"Analysis dataset shape: {df_analysis.shape}")

    # Example: Calculate ages
    print("\n\nCalculating patient ages...")
    ages = loader.calculate_age()
    print(ages.describe())

    # Example: Get lab value changes
    print("\n\nCalculating lab value changes...")
    lab_changes = loader.get_lab_value_changes()
    print(f"Lab changes dataset shape: {lab_changes.shape}")

    # Show Hb changes
    if 'Hb_change' in lab_changes.columns:
        hb_change = lab_changes['Hb_change'].dropna()
        print(f"\nHb change: {hb_change.mean():.2f} ± {hb_change.std():.2f} g/dl")
