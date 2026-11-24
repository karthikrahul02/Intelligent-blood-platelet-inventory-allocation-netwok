# Lab Value Data Quality Module

**Author:** Elina Nuerenberg-Goloub — **Last revised:** 2026-08-18

## Purpose

This module handles unit detection and standardization for laboratory values in transfusion registry data. Blood product registries commonly have unit confusion issues where values are entered in different units (e.g., thousands instead of actual count for platelets, mg/dl instead of the canonical g/dl for albumin).

## Module Components

### 1. lab_value_quality.py

**Key Class**: `LabValueQualityChecker`

**Configuration**: `LAB_VALUE_CONFIG` dictionary with detection rules for each parameter

**Main Methods**:
- `detect_unit_issues(lab_name)` - Analyze value distribution for a parameter
- `get_problematic_records(lab_name)` - Extract records with outlier values
- `get_range_violations(lab_name)` - Flag values outside the plausible clinical range (screened on unit-corrected values)
- `get_cleaned_data(lab_name, exclude_outliers=True)` - Get paired data with outliers removed
- `run_all_checks()` - Check all configured parameters
- `generate_report(output_dir)` - Create text quality report
- `export_problematic_records(output_dir)` - Export CSV for manual review

**Checked parameters** (before/after column pairs): Hemoglobin, Platelets, Quick's test, Fibrinogen, Serum albumin, Ferritin, Transferrin saturation, and Antithrombin activity (before `X_433_7_601`, after `X_433_7_602`, unit %).

**Detection logic notes**:
- A wrong-unit alarm is only raised when wrong-unit values are actually observed in the data — a skewed distribution alone, with zero wrong-unit values present, does not trigger the alarm.
- Clinical plausibility ranges are actively screened for every parameter. All bounds come from the **central physician range registry** (`CLINICAL_RANGE_REGISTRY` in `transfusion_registry_mapping.py`, version 2026-08-21, single source shared with data quality module 4; bounds are inclusive). The configured unit correction (multiply/divide) is applied to POSITIVE values BEFORE screening, so values in a wrong-but-convertible unit are judged on the corrected scale; non-positive values are NEVER scaled on any path — they are excluded as impossible and itemized in the review export.

### 2. run_lab_value_quality.py (Runner Script)

Standalone script to run quality checks independently of visualization.

## Usage

### Standalone Quality Check

```bash
python3 run_lab_value_quality.py <raw_data_path> <output_dir>
```

Example:
```bash
python3 run_lab_value_quality.py "../synthetic test data/test_data_150patients.csv" test_data_150patients
```

This generates:
- `lab_value_quality_report.txt` - Human-readable quality report
- `lab_value_unit_issues.csv` - Problematic records for manual review

### Integration with Visualization

The `visualize_treatments.py` module automatically uses `LabValueQualityChecker` to:
1. Detect unit issues
2. Exclude outlier values from violin plots
3. Display corrected unit labels

```python
from lab_value_quality import LabValueQualityChecker

# Create checker
checker = LabValueQualityChecker(df)

# Get cleaned data for visualization (outliers excluded)
before_data, after_data, unit_label = checker.get_cleaned_data('Platelets', exclude_outliers=True)
```

### Programmatic Usage

```python
from lab_value_quality import LabValueQualityChecker, LAB_VALUE_CONFIG
import pandas as pd

# Load data
df = pd.read_csv('data.csv', sep=';', skiprows=7)

# Create checker
checker = LabValueQualityChecker(df)

# Run all checks
results = checker.run_all_checks()

# Check specific parameter
platelets_result = checker.detect_unit_issues('Platelets')
if platelets_result.get('unit_issue'):
    print(f"Unit issue detected: {platelets_result['recommendation']}")

# Get cleaned data
before, after, unit = checker.get_cleaned_data('Platelets', exclude_outliers=True)

# Get problematic records for review
problematic = checker.get_problematic_records('Platelets')

# Generate full report
checker.generate_report('output_directory')
checker.export_problematic_records('output_directory')
```

## Output Files

### lab_value_quality_report.txt

Text report showing for each lab parameter:
- Total values (before/after counts)
- Value range and median
- Unit issue detection status
- Recommendation if issues found

### lab_value_unit_issues.csv

CSV file with problematic records — both wrong-unit outliers and clinical-range violations — containing:
- Patient identifier (`PID`) and any additional record identifiers present
- Before and after values
- Lab parameter name
- Issue description
- Expected unit
- Likely entered unit (for wrong-unit records) or flagged corrected values (for range violations)

This file should be reviewed by clinical staff to:
1. Verify if values are data entry errors
2. Correct values in the source system if needed
3. Document any legitimate outliers

## Configuration

The `LAB_VALUE_CONFIG` dictionary defines detection rules:

```python
LAB_VALUE_CONFIG = {
    'Platelets': {
        'expected_unit': '/µl',
        'normal_range': (150000, 400000),
        'clinical_range': _registry_range('platelets'),   # physicians' table: 1,000-1,000,000 /µl
        'unit_detection': {
            'threshold': 1000,
            'multiply_by': 1000,
            'wrong_unit': 'thousands/µl',
            'corrected_unit': '/µl (×1000)'
        }
    },
    'Serum albumin': {
        'expected_unit': 'g/dl',
        'normal_range': (3.5, 5.0),
        'clinical_range': _registry_range('serum_albumin'),  # physicians' table: 0-7000 mg/dl = 0-7.0 g/dl
        'unit_detection': {
            'threshold': 100,
            'divide_by': 1000,
            'wrong_unit': 'mg/dl',
            'corrected_unit': 'g/dl'
        }
    },
    # Parameters without unit issues have unit_detection: None
    'Hemoglobin': {
        'expected_unit': 'g/dl',
        'normal_range': (12.0, 17.5),
        'clinical_range': _registry_range('hemoglobin'),  # physicians' table: 1.0-20.0 g/dl
        'unit_detection': None
    },
    # ... other parameters
}
```

### Adding New Parameters

To add quality checks for a new lab parameter:

1. Add column mapping to `LAB_COLUMNS`
2. Add configuration to `LAB_VALUE_CONFIG`
3. Set `unit_detection` to `None` if no issues expected, or configure thresholds

## Workflow Recommendation

### For New Data Exports

1. **Run quality check first**:
   ```bash
   python3 run_lab_value_quality.py ../synthetic test data/test_data_150patients.csv test_data_150patients
   ```

2. **Review the report** (`lab_value_quality_report.txt`)

3. **Review problematic records** (`lab_value_unit_issues.csv`)
   - Share with clinical team for verification
   - Correct source data if needed

4. **Run visualization** (outliers automatically excluded):
   ```bash
   python3 run_visualize_treatments.py test_data_150patients
   ```

## Dependencies

- pandas
- numpy
