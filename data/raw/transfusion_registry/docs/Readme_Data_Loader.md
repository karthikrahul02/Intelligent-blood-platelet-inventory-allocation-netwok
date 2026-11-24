# Transfusion Registry Data Loader

**Author:** Elina Nuerenberg-Goloub — **Last revised:** 2026-08-18

## Overview

The `transfusion_data_loader.py` module provides robust loading and preprocessing of transfusion registry data files. It handles the complex multi-row header structure, applies proper data types, validates data quality, and integrates seamlessly with the mapping module.

## Key Features

1. **Correct CSV Parsing**: Automatically handles the 7-row metadata header structure
2. **Data Type Conversion**: Applies appropriate types (INTEGER, FLOAT, DATE, BOOLEAN, enumerated)
3. **Data Validation**: Built-in quality checks for missing data, duplicates, and data integrity
4. **Missing Data Handling**: Proper treatment of empty values and NaN
5. **Integration with Mapper**: Automatic value decoding and readable column names
6. **Analysis-Ready Datasets**: Easy generation of datasets for statistical analysis
7. **Derived Variables**: Calculate age, lab value changes, and other derived measures

## CSV File Structure

The transfusion registry CSV files have a complex structure:

```
Row 1-7:  Metadata (Form IDs, names, record IDs, data element IDs, etc.)
Row 8:    Actual column headers (PID, FormStatus_*, X_*_*_*)
Row 9+:   Data rows
```

The loader automatically skips the first 7 rows and reads from row 8 onward.

## Basic Usage

### Loading Data

```python
from transfusion_data_loader import TransfusionDataLoader

# Create loader instance
loader = TransfusionDataLoader()

# Load data with validation
df = loader.load_data("../synthetic test data/test_data_150patients.csv", validate=True)

# Print summary
loader.print_summary()
```

### Quick Load Function

```python
from transfusion_data_loader import load_transfusion_data

# Convenience function
df, loader = load_transfusion_data("../synthetic test data/test_data_150patients.csv")
```

## Core Functions

### 1. Load Data

```python
df = loader.load_data(file_path="../synthetic test data/test_data_150patients.csv", validate=True)
```

**Parameters:**
- `file_path`: Path to CSV file
- `validate`: Run validation checks (default: True)

**Returns:** Clean DataFrame with proper data types

### 2. Get Patient-Level Data

Extract one row per patient (demographics, baseline characteristics):

```python
df_patients = loader.get_patient_level_data()
```

Includes:
- Basic data (Form 541): Year of birth
- Entry transfusion baseline (Form 433, Record 0): Demographics, clinical assessment
- Follow-up data (Form 435): Patient-reported outcomes

### 3. Get Product-Level Data

Extract product administration data:

```python
df_products = loader.get_product_level_data()
```

Includes all product administration details (Form 433, Record 7):
- Product type, dosage, indication
- Laboratory values before/after
- Blood group matching

### 4. Create Analysis Dataset

Generate analysis-ready data with readable names and decoded values:

```python
df_analysis = loader.create_analysis_dataset(
    decode_values=True,      # Convert codes to descriptions
    readable_names=True      # Use human-readable column names
)
```

**Example:**
- `X_433_7_746` with value `1` becomes column "(Blood) Product type" with value "Erythrozyten-Konzentrat"

### 5. Calculate Patient Age

```python
# Age at episode date
ages = loader.calculate_age()

# Age at specific date
ages = loader.calculate_age(reference_date="2025-01-01")

# Current age
ages = loader.calculate_age(reference_date="now")
```

**Returns:** Pandas Series with patient ages (unrealistic ages set to NaN)

### 6. Calculate Lab Value Changes

Automatically match before/after measurements and calculate changes:

```python
lab_changes = loader.get_lab_value_changes()
```

**Returns:** DataFrame with columns like:
- `Hb_change`: Hemoglobin change (g/dl)
- `Platelets_change`: Platelet count change (/µl)
- `Quick's test_change`: Quick's test change (%)
- `Fibrinogen_change`: Fibrinogen change (mg/dl)
- etc.

### 7. Print Summary

Comprehensive data summary:

```python
loader.print_summary()
```

Displays:
- File information
- Number of records and patients
- Age distribution
- Sex distribution
- Blood product distribution
- Top missing data columns
- Validation status

## Data Validation

Automatic validation checks:

1. **Required Columns**: PID, Episode number present
2. **Duplicate Detection**: Duplicate PID-Episode combinations (expected for repeatable records)
3. **Completeness**: High missingness warnings for key variables
4. **Date Validity**: Future dates flagged
5. **Time-Invariant Attributes**: patients whose sex, height, weight, or year of birth carry more than one distinct value across rows are itemized in `loader.patient_attribute_conflicts` (PID, attribute, values) and reported with a warning; patient-level statistics use one real documented index row per patient
6. **Persistent QC findings**: `loader.export_qc_findings(dir)` writes `loader_qc_findings.csv` (unparseable dates and attribute conflicts, with PID and raw value); the full runner writes it into every run's `data quality reporting/` folder. The administrative `Episode date` column is parsed with the same dual-format rule as the DATE elements
5. **Data Integrity**: Type conversion errors logged

Access validation results:

```python
validation_passed = loader.metadata['validation_passed']
validation_issues = loader.metadata['validation_issues']
```

## Complete Example Workflow

```python
from transfusion_data_loader import TransfusionDataLoader
import pandas as pd

# Initialize
loader = TransfusionDataLoader()

# Load data
print("Loading transfusion registry data...")
df = loader.load_data("../synthetic test data/test_data_150patients.csv")

# Display summary
loader.print_summary()

# Calculate patient ages
df['age'] = loader.calculate_age()

# Get lab value changes
lab_changes = loader.get_lab_value_changes()

# Merge lab changes with main data
df = df.merge(lab_changes[['PID', 'Hb_change']], on='PID', how='left')

# Create analysis dataset with readable names
df_analysis = loader.create_analysis_dataset(
    decode_values=True,
    readable_names=True
)

# Example analysis: Hb response by product type
hb_by_product = df_analysis.groupby('(Blood) Product type')['Hb_change'].agg([
    'count', 'mean', 'std', 'median'
])
print("\nHb change by product type:")
print(hb_by_product)

# Example analysis: Age distribution by sex
age_by_sex = df_analysis.groupby('Sex')['age'].describe()
print("\nAge distribution by sex:")
print(age_by_sex)

# Save analysis dataset
df_analysis.to_csv("analysis_dataset.csv", index=False)
```

## Working with Repeatable Records

The data structure allows multiple product administrations per patient (repeatable Record 7 in Form 433). This means:

1. **One patient can have multiple rows** - one for each product administration
2. **PID-Episode duplicates are expected** - not an error
3. **Product-level analysis** should use all rows
4. **Patient-level analysis** may need aggregation or filtering

### Example: Analyze First Transfusion Only

```python
# Get first transfusion per patient
df_first = df.sort_values(['PID', 'Episode date']).groupby('PID').first().reset_index()

# Now analyze patient characteristics at first transfusion
```

### Example: Count Products Per Patient

```python
products_per_patient = df.groupby('PID').size()
print(f"Mean products per patient: {products_per_patient.mean():.1f}")
```

## Data Type Conversion

The loader automatically converts columns based on metadata:

| Metadata Type | Python Type | Notes |
|--------------|-------------|-------|
| INTEGER | Int64 | Nullable integer |
| FLOAT | float64 | Standard float |
| DATE | datetime64 | Parsed as YYYY-MM-DD or DD/MM/YYYY (both formats may mix within one column; each value is parsed against the original string). Non-empty values that match neither format are set to missing and collected in `loader.unparseable_dates` (column, PID, raw value) as a data-quality finding |
| BOOLEAN | bool | Handles true/false, yes/no, 1/0, t/f |
| enumerated | str | Kept as string (or decoded) |
| STRING | str | Free text |

Missing values are represented as `np.nan` or `pd.NA` (for Int64).

## Handling Missing Data

```python
# Check missing data per column
missing_summary = df.isna().sum()
missing_pct = (missing_summary / len(df)) * 100

# Columns with >50% missing
high_missing = missing_pct[missing_pct > 50]
print(high_missing)

# Filter to complete cases for specific variables
vars_of_interest = ['X_433_7_746', 'X_433_7_614', 'X_433_7_615']
df_complete = df[vars_of_interest].dropna()
```
```

## Integration with Statistical Analysis

### Descriptive Statistics

```python
# Get analysis dataset
df_analysis = loader.create_analysis_dataset(decode_values=True, readable_names=True)

# Continuous variables
continuous_vars = ['age', 'Hb_change', 'Height', 'Weight']
print(df_analysis[continuous_vars].describe())

# Categorical variables
categorical_vars = ['Sex', '(Blood) Product type']
for var in categorical_vars:
    print(f"\n{var}:")
    print(df_analysis[var].value_counts())
```

### Prepare for Regression Models

```python
import pandas as pd

# Create dummy variables
df_model = pd.get_dummies(df_analysis,
                          columns=['Sex', '(Blood) Product type'],
                          drop_first=True)

# Handle missing data
df_model = df_model.dropna(subset=['Hb_change', 'age'])

# Ready for modeling
X = df_model[['age', 'Sex_Weiblich', ...]]
y = df_model['Hb_change']
```

### Export for SPSS/Stata/R

```python
# CSV for universal import
df_analysis.to_csv("data_for_analysis.csv", index=False)

# For R
df_analysis.to_csv("data_for_analysis.csv", index=False)

# For Stata (requires statsmodels)
# from statsmodels.iolib.smpickle import save_pickle
# Or use CSV which Stata can import

# For SPSS (use pyreadstat if needed)
# import pyreadstat
# pyreadstat.write_sav(df_analysis, "data_for_analysis.sav")
```

## Troubleshooting

### Issue: Column not found

**Problem:** `KeyError: 'X_433_7_746'`

**Solution:** Check if column exists in your file:
```python
print(df.columns.tolist())
# or
'X_433_7_746' in df.columns
```

### Issue: Data type conversion error

**Problem:** Warning about type conversion failure

**Solution:** Check raw values:
```python
print(df_raw['X_433_7_614'].value_counts())
```

### Issue: Validation fails

**Problem:** Validation issues reported

**Solution:** Review issues:
```python
print(loader.metadata['validation_issues'])
```

### Issue: Empty DataFrame returned

**Problem:** `get_product_level_data()` returns empty

**Solution:** Check if product type column has values:
```python
print(df['X_433_7_746'].value_counts())
```

## Best Practices

1. **Always validate** data after loading
2. **Check the summary** before analysis
3. **Handle missing data** appropriately for your analysis
4. **Document transformations** in your analysis code
5. **Save intermediate datasets** for reproducibility
6. **Use readable names** in final outputs
7. **Version control** your analysis scripts

## Advanced Usage

### Custom Validation Rules

Add custom validation to the workflow:

```python
loader = TransfusionDataLoader()
df = loader.load_data("../synthetic test data/test_data_150patients.csv")

# Custom check: Hb values should be reasonable
hb_col = 'X_433_7_614'
unrealistic_hb = (df[hb_col] < 3) | (df[hb_col] > 20)
if unrealistic_hb.any():
    print(f"Warning: {unrealistic_hb.sum()} unrealistic Hb values found")
```

### Batch Processing Multiple Files

```python
from pathlib import Path

data_dir = Path("data")
all_files = list(data_dir.glob("202*.csv"))

dfs = []
for file in all_files:
    loader = TransfusionDataLoader()
    df = loader.load_data(str(file), validate=False)
    df['source_file'] = file.name
    dfs.append(df)

# Combine all data
df_combined = pd.concat(dfs, ignore_index=True)
```

## Dependencies

Required packages:
- pandas >= 1.3.0
- numpy >= 1.20.0
- Python >= 3.8

The module imports from `transfusion_registry_mapping.py`, which must be in the same directory or in Python path.

