# Transfusion Registry Analysis Suite

**Author:** Elina Nuerenberg-Goloub — **Last revised:** 2026-08-18

## Overview

This suite provides comprehensive tools for analyzing transfusion registry data. It consists of three integrated modules that handle data mapping, loading, and preparation for statistical analysis.

## Modules

### 1. transfusion_registry_mapping.py
**Purpose:** Translates technical column names and codes to human-readable names and descriptions.

**Key Features:**
- Maps 184 columns from 3 forms (Basic data, Entry transfusion, Follow-up)
- Decodes 238 value codes across 52 elements
- Provides metadata (data types, units, definitions)
- Groups columns by form and purpose

**Documentation:** See `Readme_Mapping.md` and `Column_Quick_Reference.md`

### 2. transfusion_data_loader.py
**Purpose:** Loads and preprocesses transfusion registry CSV files.

**Key Features:**
- Handles complex 7-row header structure
- Automatically filters out test location data (Verika)
- Applies proper data types (INTEGER, FLOAT, DATE, BOOLEAN, enumerated)
- Validates data quality
- Calculates derived variables (age, lab value changes)
- Creates analysis-ready datasets

**Documentation:** See `Readme_Data_Loader.md`

## Quick Start

> **Note:** `--data-end-date YYYY-MM-DD` (the export date of the analyzed file) is **mandatory** for analysis runs — it censors follow-up eligibility. For non-reportable test runs only, `--allow-derived-end-date` derives the date from the latest observed event.


### Installation

No installation required. Place all Python files in the same directory.

**Requirements:**
- Python 3.8 or higher
- pandas >= 1.3.0
- numpy >= 1.20.0
- matplotlib >= 3.4.0

### Full Analysis Pipeline (Recommended)

The easiest way to run all analyses is with the master script:

```bash
cd "python codes"
python3 run_full_analysis.py "../synthetic test data/test_data_150patients.csv" --data-end-date 2026-08-21
```

This runs all 18 modules automatically:
- 7 statistics modules (biometrics, treatments, indications, follow-up, temporal volumes, SNOMED codes, LOS)
- 5 data quality modules (completeness, dosage, duplicates, validity, lab values)
- 6 visualization modules (all figures)

Output is saved to a directory named after the input file (e.g., `test_data_150patients/`). The script exits with a non-zero exit code if any module fails, so scripted callers can detect a broken run.

For interactive mode (select which modules to run):
```bash
python3 run_full_analysis.py "../synthetic test data/test_data_150patients.csv" --data-end-date 2026-08-21 --interactive
```

See `Readme_Full_Analysis.md` for detailed documentation.

### Basic Usage

```python
from transfusion_data_loader import TransfusionDataLoader

# Load data
loader = TransfusionDataLoader()
df = loader.load_data("your_data_file.csv")

# View summary
loader.print_summary()

# Create analysis dataset
df_analysis = loader.create_analysis_dataset(
    decode_values=True,
    readable_names=True
)

# Analyze
print(df_analysis['age'].describe())
print(df_analysis['Sex'].value_counts())
```

## File Structure

```
transfusion_registry_pipeline_v1.0/
├── README.md                                # This package's landing page
├── Validation.pdf                           # How the pipeline was validated
├── Manifest.sha256                          # Checksums of every file
├── LICENSE-CODE.txt / LICENSE-DOCS-DATA.txt # Licensing (MIT / CC BY 4.0)
├── 20250227_Datenelemente-Transfusionsregister.csv    # Data dictionary
├── 20250227_permitted-values-Transfusionsregister.csv # Permitted values
├── python codes/
│   ├── run_full_analysis.py                 # Master script (runs all modules)
│   ├── transfusion_data_loader.py           # Data loader
│   ├── transfusion_registry_mapping.py      # Dictionary mapping
│   ├── descriptive_*.py                     # Statistics modules
│   ├── data_quality_module*.py              # Data quality modules
│   ├── visualize_*.py                       # Visualization modules
│   ├── run_*.py                             # Individual runner scripts
│   ├── generate_test_data.py                # Synthetic data generator
│   ├── enrollment_filter.py                 # Cohort tools
│   ├── test_analysis_modules.py             # Test program, suite 1 (43)
│   ├── test_treatments_lab.py               # Test program, suite 2 (60)
│   ├── verify_test_data.py                  # Test program, suite 3 (66)
│   ├── test_enrollment_filter.py            # Test program, suite 4 (56)
│   └── export_validation_datasets.py        # Regenerates validation datasets/
├── synthetic test data/
│   ├── test_data_100patients.csv            # Synthetic dataset (100 patients)
│   ├── test_data_150patients.csv            # Synthetic dataset (150 patients)
│   └── seeded_errors_*.json                 # Answer keys of planted errors
├── validation datasets/
│   ├── Validation_Datasets.pdf              # Inventory of all datasets
│   ├── header_template.csv                  # Export header (no data)
│   └── 1_01 ... 4_13 *.csv                  # Miniature hand-check datasets
├── docs/                                    # This documentation
└── screenshots/                             # Patient portal walkthrough
```

The synthetic datasets live in `synthetic test data/` and are used in all
example commands. Real registry exports are private and are not part of the
public package.

## Data Structure

### CSV File Format

Transfusion registry CSV files have a specific structure:

```
Rows 1-7:  Metadata (Form IDs, names, data element IDs, etc.)
Row 8:     Column headers (PID, FormStatus_*, X_*_*_*)
Row 9+:    Data rows
```

The loader automatically handles this structure.

### Column Naming Convention

Technical columns follow the pattern: `X_{FormID}_{RecordID}_{ElementID}`

Examples:
- `X_541_0_1`: Year of birth (Form 541, Basic data)
- `X_433_7_746`: Blood product type (Form 433, Record 7)
- `X_435_0_737`: Problems related to transfusion (Form 435, Follow-up)

### Forms

1. **Form 541: Basic Data** - Patient demographics
2. **Form 433: Entry Transfusion** - Product administration details
   - Record 0: Patient characteristics at entry
   - Record 7: Product administrations (repeatable)
3. **Form 435: Follow-up** - Patient-reported outcomes

## Common Analysis Tasks

### 1. Descriptive Statistics

```python
from transfusion_data_loader import TransfusionDataLoader

loader = TransfusionDataLoader()
df = loader.load_data("../synthetic test data/test_data_150patients.csv")

# Age distribution
ages = loader.calculate_age()
print(f"Age: {ages.mean():.1f} ± {ages.std():.1f} years")

# Sex distribution
df_analysis = loader.create_analysis_dataset(decode_values=True, readable_names=True)
print(df_analysis['Sex'].value_counts())

# Product distribution
print(df_analysis['(Blood) Product type'].value_counts())
```

### 2. Hemoglobin Response

```python
# Calculate lab value changes
lab_changes = loader.get_lab_value_changes()

# Analyze Hb response
hb_change = lab_changes['Hb_change'].dropna()
print(f"Hb change: {hb_change.mean():.2f} ± {hb_change.std():.2f} g/dl")

# By product type
df_with_changes = df.merge(lab_changes[['PID', 'Hb_change']], on='PID')
df_analysis = loader.create_analysis_dataset(decode_values=True, readable_names=True)
df_analysis['Hb_change'] = df_with_changes['Hb_change']

hb_by_product = df_analysis.groupby('(Blood) Product type')['Hb_change'].agg(['mean', 'std', 'count'])
print(hb_by_product)
```

### 3. Clinical Frailty Analysis

```python
# Get frailty scale distribution
cfs_col = [col for col in df_analysis.columns if 'CFS' in col][0]
print(df_analysis[cfs_col].value_counts())

# Analyze outcomes by frailty
outcomes_by_frailty = df_analysis.groupby(cfs_col)['Hb_change'].describe()
print(outcomes_by_frailty)
```

### 4. Subgroup Analysis

```python
# Filter to specific product type
erythrocyte_patients = df_analysis[df_analysis['(Blood) Product type'].str.contains('Erythrozyten', na=False)]

# Filter to elderly patients
elderly = df_analysis[df_analysis['age'] >= 65]

# Filter to first transfusion only
df_first = df_analysis.sort_values(['PID', 'Episode date']).groupby('PID').first()
```

### 5. Export for Statistical Software

```python
# For any statistical software (CSV)
df_analysis.to_csv("data_for_analysis.csv", index=False)

# With specific variables only
vars_for_analysis = ['PID', 'age', 'Sex', '(Blood) Product type',
                     'Hb_change', 'Platelets_change']
df_subset = df_analysis[vars_for_analysis]
df_subset.to_csv("regression_data.csv", index=False)
```

## Integration with Statistical Analysis

### Prepare for Modeling

```python
import pandas as pd

# Create dummy variables
df_model = pd.get_dummies(df_analysis,
                          columns=['Sex', '(Blood) Product type'],
                          drop_first=True)

# Select predictors and outcome
X = df_model[['age', 'Sex_Weiblich', ...]]
y = df_model['Hb_change']

# Handle missing data
complete_cases = X.notna().all(axis=1) & y.notna()
X_clean = X[complete_cases]
y_clean = y[complete_cases]
```

### Calculate Summary Tables

```python
# Table 1: Baseline characteristics
table1_vars = ['age', 'Sex', 'Height', 'Weight']
table1 = df_analysis[table1_vars].describe(include='all')

# Table 2: Product administration
product_col = '(Blood) Product type'
table2 = df_analysis[product_col].value_counts()

# Table 3: Laboratory changes
lab_changes_summary = lab_changes[['Hb_change', 'Platelets_change']].describe()
```

## Data Validation

The loader automatically validates:
- Required columns present
- Duplicate records (expected for repeatable products)
- High missingness in key variables
- Date validity (no future dates)
- Data type conversions

Access validation results:

```python
if loader.metadata['validation_passed']:
    print("Validation passed")
else:
    print("Issues found:")
    for issue in loader.metadata['validation_issues']:
        print(f"  - {issue}")
```

## Example Workflow

```python
# 1. Load and validate
from transfusion_data_loader import TransfusionDataLoader
loader = TransfusionDataLoader()
df = loader.load_data("data.csv")
loader.print_summary()

# 2. Calculate derived variables
df['age'] = loader.calculate_age()
lab_changes = loader.get_lab_value_changes()
df = df.merge(lab_changes, on='PID')

# 3. Create analysis dataset
df_analysis = loader.create_analysis_dataset(
    decode_values=True,
    readable_names=True
)

# 4. Perform analysis
results = df_analysis.groupby('Sex')['Hb_change'].describe()
print(results)

# 5. Export results
df_analysis.to_csv("analysis_data.csv", index=False)
results.to_csv("summary_by_sex.csv")
```

## Statistical Modules

  This data loader provides the foundation for the following statistical
  analysis modules:

  ### Implemented Modules

  1. **Biometric Statistics** (`descriptive_biometrics.py`)
     - Patient-level demographic characteristics
     - Age, gender, BMI distributions
     - Comorbidities and risk factors
     - Baseline clinical measures (physical capacity, frailty)

  2. **Treatment Statistics** (`descriptive_treatments.py`)
     - Blood product administration patterns
     - Temporal distribution of transfusions
     - Dosages by product type
     - Laboratory values (pre/post transfusion)
     - Administrations per patient
     - Blood type compatibility analysis (RBC, FFP, PC)
     - Gender-stratified statistics (administrations, lab values)
     - Weight-adjusted dosages (dose per kg body weight) by gender

  3. **Indication and Intervention Statistics**
  (`descriptive_indications.py`)
     - Connection to planned interventional procedures
     - Hemorrhage risk classification
     - Transfusion indications by product type
     - Administration-level and patient-level statistics

  4. **Follow-Up Statistics** (`descriptive_followup.py`)
     - Dual timepoint analysis (3-month and 1-year)
     - Completion rates with timepoint-specific eligibility
     - Patient-reported outcomes (physical capacity, frailty)
     - Adverse events tracking
     - Clinical outcomes (anaemia, repeat transfusions)
     - Baseline vs. follow-up comparisons
     - Duplicate handling: identical duplicates resolved, conflicting duplicates excluded and exported for review

  5. **Lab Value Data Quality** (`lab_value_quality.py`)
     - Unit inconsistency detection in laboratory values
     - Automatic outlier identification and exclusion
     - Corrected unit labels for visualization
     - Export of problematic records for manual review
     - Integration with treatment visualization module

  6. **SNOMED Code Analysis** (`descriptive_snomed.py`)
     - Coverage statistics for SNOMED-coded fields
     - Primary diagnosis, secondary diagnosis, intervention/procedure
     - Top codes by frequency (for manual lookup)
     - Output designed for verification at https://browser.ihtsdotools.org/

  7. **Post-Intervention Time to Discharge** (`descriptive_los.py`)
     - Days from intervention to discharge (the export has no admission date, so this is not the full hospital stay)
     - Gender-stratified LOS statistics
     - LOS distribution categories (same day, short, typical, extended, prolonged)
     - Discharge documentation by product status

## Automated Tests

Four automated test suites in `python codes/` verify the analysis logic against the synthetic datasets:

- `test_analysis_modules.py` - 42 comparisons for the analysis and data-quality modules
- `test_treatments_lab.py` - 60 checks of treatment statistics and lab value handling
- `verify_test_data.py` - 66 checks across both synthetic datasets (`test_data_150patients.csv`, `test_data_100patients.csv`)
- `test_enrollment_filter.py` - 56 comparisons for the cohort tools

A summary of the validation results is maintained in `Validation.pdf` at the project root.

## Support and Documentation

- **Full analysis pipeline**: `Readme_Full_Analysis.md` (recommended starting point)
- **Mapping reference**: `Readme_Mapping.md`
- **Data loader guide**: `Readme_Data_Loader.md`
- **Synthetic data generator**: `Readme_Test_Data_Generator.md`
- **Column quick reference**: `Column_Quick_Reference.md`
- **Lab value quality**: `Readme_Lab_Value_Quality.md`
- **SNOMED code analysis**: `Readme_SNOMED_Analysis.md`
- **Clinical value ranges (source and decisions)**: `Readme_Clinical_Ranges.md`
- **Post-intervention time to discharge**: `Readme_LOS_Analysis.md`
- **Biometric statistics**: `Readme_Biometric_Statistics.md`
- **Treatment statistics**: `Readme_Treatment_Statistics.md`
- **Indication and intervention statistics**: `Readme_Indication_Intervention_Statistics.md`
- **Follow-up statistics**: `Readme_Followup_Statistics.md`
- **Temporal volume analysis**: `Readme_Temporal_Volume_Analysis.md`
- **Data quality — completeness**: `Readme_Data_Quality_Completeness.md`
- **Data quality — dosage**: `Readme_Data_Quality_Dosage.md`
- **Data quality — follow-up duplicates**: `Readme_Data_Quality_Followup_Duplicates.md`
- **Data quality — validity**: `Readme_Data_Quality_Validity.md`
- **Biometric visualizations**: `Readme_Biometric_Visualization.md`
- **Treatment visualizations**: `Readme_Treatment_Visualization.md`
- **Dosage visualizations**: `Readme_Dosage_Visualization.md`
- **Indication visualizations**: `Readme_Indication_Visualization.md`
- **Follow-up visualizations**: `Readme_Followup_Visualization.md`
- **Temporal volume visualizations**: `Readme_Temporal_Volume_Visualization.md`

## Version Information

- **Mapping Module**: Version 2.0 (2025-10-15)
- **Data Loader**: Version 1.1 (2026-01-26) - Added test location filtering
- **Python**: 3.12 (tested)
- **Dependencies**: pandas >= 2.3.0, < 3.0; numpy >= 2.0.0; matplotlib >= 3.10.0 (see `python codes/requirements.txt`)
