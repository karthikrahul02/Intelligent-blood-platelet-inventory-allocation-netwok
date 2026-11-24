# Data Quality Analysis - Module 4: Data Validity

**Author:** Elina Nuerenberg-Goloub — **Last revised:** 2026-08-18

**Purpose**: Check if values fall within clinically plausible ranges and detect potential data entry errors.

---

## Overview

All value bounds come from the central physician range registry (`CLINICAL_RANGE_REGISTRY` in `transfusion_registry_mapping.py`, version 2026-08-21) — the single versioned source shared with the laboratory quality module. Every documented value is checked (patient-level results count each patient once, but a later impossible entry is never hidden by an earlier valid one).

This module performs validity checks to identify values outside clinically acceptable ranges and detects potential copy-paste errors where before/after lab values are identical.

### Checks Performed

1. **Demographics** (Patient Level)
   - Height (20-220 cm)
   - Weight (1-250 kg)
   - Age (0-120 years)

2. **Lab Values** (Administration Level)
   - Hemoglobin before/after (1-20 g/dl)
   - Platelets before/after (1,000-1,000,000 /μL, after unit normalization)
   - Quick's Test before/after (0-500 %)
   - Fibrinogen before/after (0-1000 mg/dl)
   - Serum Albumin before/after (0-7.0 g/dl, canonical unit)
   - Ferritin before/after (5-5000 μg/L)
   - Transferrin before/after (5-100 %)
   - Erythropoietin (Plasma) before/after (0-200 U/L)
   - Antithrombin III activity before/after (30-150 %)

3. **Identical Before/After Values** (Administration Level)
   - Detects records where before = after exactly
   - Flags potential copy-paste errors during data entry
   - Checked for: Hemoglobin, Serum Albumin, Ferritin, Transferrin, Fibrinogen, Quick's Test, Platelets, Antithrombin III activity

4. **MAT Values** (Administration Level - MAT only)
   - Wound blood volume (0-10000 ml)
   - Wound blood hematocrit (15-65 %)
   - Recovered RBC volume (0-3000 ml)
   - Recovered hematocrit (15-90 %)

---

## Usage

### Command

```bash
python3 run_data_quality_module4_validity.py <data_file> <output_directory>
```

### Example

```bash
python3 run_data_quality_module4_validity.py "../synthetic test data/test_data_150patients.csv" test_data_150patients
```

This will:
1. Load and analyze the data
2. Check all values against validity ranges
3. Detect identical before/after values
4. Create subfolder: `test_data_150patients/data quality reporting/`
5. Generate output files in that subfolder

---

## Output Files

All files are saved in: `<output_directory>/data quality reporting/`

### 1. Comprehensive Report (TXT)

**`data_quality_module4_validity.txt`**
- Summary statistics
- Demographics validity table
- Lab values validity table
- Identical before/after values table
- MAT values validity table

### 2. Detailed Results (JSON)

**`data_quality_module4_validity.json`**
- Complete hierarchical results
- All validity check statistics
- Identical before/after records
- Suitable for programmatic access

### 3. Clinic Follow-up CSV

**`data_quality_module4_invalid_values.csv`**
- Consolidated list of all invalid values for clinic review
- Columns: PID, Admin_Date, Section, Parameter, Value, Valid_Range, Unit, Issue
- Includes both out-of-range values and identical before/after records

---

## Validity Ranges (Official Registry)

### Demographics

| Parameter | Min | Max | Unit |
|-----------|-----|-----|------|
| Height | 20 | 220 | cm |
| Weight | 1 | 250 | kg |
| Age | 0 | 120 | years |

### Lab Values

| Parameter | Min | Max | Unit |
|-----------|-----|-----|------|
| Hemoglobin | 1 | 20 | g/dl |
| Platelets | 1,000 | 1,000,000 | /μL |
| Quick's Test | 0 | 500 | % |
| Fibrinogen | 0 | 1000 | mg/dl |
| Serum Albumin | 0 | 7.0 | g/dl |
| Ferritin | 5 | 5000 | μg/L |
| Transferrin | 5 | 100 | % |
| EPO (Plasma) | 0 | 200 | U/L |
| Antithrombin III activity | 30 | 150 | % |

### MAT Values

| Parameter | Min | Max | Unit |
|-----------|-----|-----|------|
| Wound blood volume | 0 | 10000 | ml |
| Wound blood hematocrit | 15 | 65 | % |
| Recovered RBC volume | 0 | 3000 | ml |
| Recovered hematocrit | 15 | 90 | % |

**Note**: Recovered hematocrit range expanded from 15-65% to 15-90% per approval by Dr Jan Kloka (2025-12-17). 

---

## Interpreting Results

### Validity Check Results

Each parameter check reports:
- `valid_range`: Acceptable value range
- `actual_range`: Min-max values found in data
- `n_present`: Number of records with data
- `n_invalid`: Number of values outside valid range
- `percent_invalid`: Percentage of invalid values

**Patient-level denominators**: Patient-level checks (height, weight, age) are computed on one row per patient — the data is deduplicated by PID before checking — so `n_present` and the percentages are patient counts, not row counts.

### Identical Before/After

Records where lab values are exactly the same before and after treatment may indicate:
- **Copy-paste error**: Same value entered twice by mistake
- **Lab not measured**: "After" value copied from "before"
- **Genuine no change**: Possible but unusual after treatment

---

## Common Issues Detected

### 1. Platelet Unit Entry Errors

The registry expects platelet values in **x1000/μL** format:
- Correct entry: `229` (meaning 229,000/μL)
- Incorrect entry: `229000` (entered as raw /μL)

Values like 97000, 229000, 283000 indicate the clinician entered raw lab values instead of converting to x1000/μL format.

### 2. Identical Before/After Lab Values

Commonly flagged parameters:
- Hemoglobin (should increase after EK transfusion)
- Serum Albumin (should increase after Albumin infusion)
- Fibrinogen (should increase after Fibrinogen administration)
- Quick's Test (should increase after FFP/PPSB)

---

## Related Modules

- **Module 1**: Completeness (missing data rates)
- **Module 2**: Dosage consistency (unit validation, non-standard units)
- **Module 3**: Follow-up duplicates and timing

---

## Technical Notes

### Data Sources

- Demographics: Patient-level data (Form 433, Record 0)
- Lab values: Administration-level data (Form 433, Record 7)
- MAT values: MAT records only (Product code 11)

### Reference Date

The reference/export date used by the module (e.g. for age calculation) is **derived from the data** as the maximum episode date — it is never hardcoded, so the module stays correct for any export.

### Column Mappings

| Parameter | Column Code |
|-----------|-------------|
| Admin Date | X_433_7_11 |
| Hemoglobin before | X_433_7_614 |
| Hemoglobin after | X_433_7_615 |
| Platelets before | X_433_7_37 |
| Platelets after | X_433_7_587 |
| Quick's Test before | X_433_7_374 |
| Quick's Test after | X_433_7_596 |
| Fibrinogen before | X_433_7_585 |
| Fibrinogen after | X_433_7_586 |
| MAT wound blood volume | X_433_7_747 |
| Recovered RBC volume | X_433_7_749 |
| Recovered hematocrit | X_433_7_750 |

---

## Range Change Process

Any changes to validity ranges must be:
1. Documented with clinical rationale
2. Presented to decision makers/physicians
3. Approved before implementation

See: `<output_directory>/data quality reporting/RANGE_CHANGE_PROPOSALS.md`

---

## Contact

For questions about this analysis or to request additional validity checks, please contact the study team.
