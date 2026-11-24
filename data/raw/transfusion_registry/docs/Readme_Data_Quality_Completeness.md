# Data Quality Analysis - Module 1: Completeness

**Author:** Elina Nuerenberg-Goloub — **Last revised:** 2026-08-18

**Purpose**: Analyze completeness of medical staff-entered data across major sections of the transfusion registry.

---

## Overview

This module performs a comprehensive completeness analysis of critical variables entered by medical staff. It identifies missing data patterns that may affect analysis validity and clinical documentation quality.

### Major Sections Analyzed

1. **Demographics** (Patient Level)
   - Age (birth year)
   - Sex
   - Height (cm)
   - Weight (kg) (needed for dosing calculations)
   - Blood group
   - Rh factor

2. **Treatment** (Administration Level)
   - Product type
   - Dosage amount
   - Dosage unit
   - Administration date
   - Note: The dosage amount/unit completeness denominators exclude machine autotransfusion (MAT, product code 11) by design, since MAT has no generic dosage fields; the report carries an explicit note for these variables

3. **Lab Values** (Administration Level)
   - Paired pre/post measurements for:
     - Hemoglobin
     - Platelets
     - Quick's test
     - Fibrinogen
     - Serum albumin
     - Ferritin
     - Transferrin saturation

4. **Indication** (Administration Level)
   - Treatment indication per product
   - Flags both missing and 'other'/'Sonstiges' category as problematic
   - Note: Each product has a different code for "other"

5. **Follow-up Baseline** (Patient Level)
   - Physical capacity (MET)
   - Clinical Frailty Scale (CFS)

6. **MAT - Machine Autotransfusion** (Administration Level - MAT only)
   - Recovered RBC volume
   - Volume of wound blood
   - Recovered hematocrit %
   - Wound blood hematocrit %
   - Note: MAT has no indication column or lab values - uses specific blood recovery documentation

---

## Usage

### Command

```bash
python3 run_data_quality_module1_completeness.py <data_file> <output_directory>
```

### Example

```bash
python3 run_data_quality_module1_completeness.py "../synthetic test data/test_data_150patients.csv" test_data_150patients
```

This will:
1. Load and analyze the data
2. Calculate completeness rates for all critical variables
3. Create subfolder: `test_data_150patients/data quality reporting/`
4. Generate 6 output files in that subfolder

---

## Output Files

All files are saved in: `<output_directory>/data quality reporting/`

### 1. Comprehensive Report (TXT)

**`data_quality_module1_completeness.txt`**
- Combined report with all sections
- Section summary
- Demographics completeness
- Treatment completeness
- Lab values paired completeness
- Indication completeness per product
- Follow-up baseline completeness
- MAT (Machine Autotransfusion) completeness

### 2. Detailed Results (JSON)

**`data_quality_module1_completeness.json`**
- Complete hierarchical results
- All completeness statistics
- Suitable for programmatic access

### 3. CSV Files for Visualization (4 files)

**`data_quality_module1_completeness_variables.csv`**
- Demographics, treatment, follow-up baseline, and MAT variables
- Ready for bar chart visualization

**`data_quality_module1_completeness_lab_values.csv`**
- Lab value paired completeness
- Shows: both present, before only, after only

**`data_quality_module1_completeness_indication.csv`**
- Indication completeness per product
- Includes "other" code per product
- Shows missing and problematic entries

**`data_quality_module1_completeness_summary.csv`**
- Average completeness per section
- Suitable for summary visualization

---

## Interpreting Results

### Completeness Rates

- **≥90%**: Excellent completeness
- **70-89%**: Good completeness, some improvement possible
- **50-69%**: Moderate completeness, data quality concerns
- **<50%**: Poor completeness, significant data quality issues

### Key Metrics

**By Variable:**
- `n_present`: Number of records with data
- `n_missing`: Number of records without data
- `percent_complete`: Completeness rate

**For Lab Values (Paired):**
- `both_present`: Both pre and post values available (ideal for analysis)
- `only_before`: Only pre-treatment value (cannot assess change)
- `only_after`: Only post-treatment value (cannot assess change)
- `percent_paired_complete`: Percentage with both values

**For Indications:**
- `n_missing`: No indication documented
- `n_other`: Indication coded as 'other'/'Sonstiges' (non-specific)
- `n_problematic`: Missing OR 'other' (both reduce analysis value)
- `percent_problematic`: Problematic entries as percentage
- `other_code`: Product-specific code for "other" (varies: 3, 5, 8, or 9)

### Analysis Levels

- **Patient Level**: One record per patient (demographics, baseline measures)
- **Administration Level**: One record per blood product administration (treatment, lab values, indication)

---

## Important Notes

### Treatment Records Only

The analysis correctly identifies and analyzes only actual **treatment records** (records with product type). Records without product type (e.g., follow-up-only or baseline-only records) are excluded from treatment-level analyses.

### Dosage Denominator Excludes MAT

Machine autotransfusion (product code 11) administrations are **excluded from the denominators** of the "Dosage amount" and "Dosage unit" completeness metrics, because MAT has no generic dosage fields by design. The results carry the note "MAT (code 11) administrations excluded from denominator" for these two variables, so dosage completeness reflects only products that actually document a dosage.

### Product-Specific "Other" Codes

Each blood product has a **different code** for "other"/"Sonstiges" indication:

| Product | "Other" Code |
|---------|-------------|
| Red blood cell concentrate (RBC) | 5 |
| Fresh Frozen Plasma (FFP) | 9 |
| Platelet concentrate (PC) | 8 |
| PPSB | 9 |
| Fibrinogen | 9 |
| Albumin | 3 |
| Antithrombin III (ATIII) | 5 |

### MAT (Machine Autotransfusion) - Unique Documentation

MAT is fundamentally different from other blood products:
- **No indication column** - The surgery itself is the indication
- **No lab values** - MAT is about blood recovery during surgery, not transfusion based on lab triggers
- **Specific blood recovery fields**:
  - Recovered RBC volume
  - Volume of wound blood
  - Recovered hematocrit %
  - Wound blood hematocrit %

MAT documentation focuses on the blood recovery process rather than transfusion indications or efficacy lab values.

---

## Clinical Relevance

### Critical for Safety

- **Blood group & Rh factor**: Essential for transfusion safety
- **Height & Weight**: Needed for accurate dosing calculations (especially weight-based dosing)
- **Administration date**: Required for temporal analysis

### Critical for Efficacy Analysis

- **Paired lab values**: Needed to assess treatment response
- **Indication**: Required to evaluate appropriate use (non-specific "other" limits insight)
- **Baseline follow-up measures**: Needed for outcome comparisons

### Critical for Completeness

- **Product type & dosage**: Core treatment documentation
- **Sex & age**: Essential demographic characteristics

---

## Example Results (historical validation run)

> **Note (2026-08-13)**: The figures below come from a validation run that predates the August 2026 code revision (which, among other changes, removed MAT administrations from the dosage completeness denominators). They are kept for illustration only.

### Section Summary

| Section | Average Completeness | Key Finding |
|---------|---------------------|-------------|
| **Treatment** | 94.8% | Excellent core documentation |
| **Indication** | 79.8% | Good overall, but some products have high "other" rates |
| **MAT (Machine Autotransfusion)** | 76.0% | Good documentation of blood recovery process |
| **Demographics** | 74.4% | Blood group and Rh factor need improvement |
| **Follow-up Baseline** | 57.7% | Moderate completeness |
| **Lab Values (Paired)** | 56.4% | Moderate - calculated per clinically relevant product |

### Key Findings

**Excellent (≥90%):**
- Age: 100% ✓
- Sex: 99% ✓
- Height: 97.6% ✓
- Weight: 99% ✓
- Product type: 100% ✓
- Administration date: 100% ✓
- Dosage amount: 90% ✓
- Dosage unit: 90% ✓
- MAT - Recovered RBC volume: 100% ✓
- Hemoglobin (for EK): 90.9% paired ✓

**Good (70-89%):**
- EK indication: 96% non-problematic ✓
- MAT - Volume of wound blood: 82.7% ✓

**Concerning (<70%):**
- Rh factor: 8.4% complete (critical gap!)
- Blood group: 42.5% complete
- TK indication: 63% non-problematic (37% problematic)
- PPSB indication: 73% non-problematic (27% problematic)
- Albumin indication: 81% non-problematic (19% problematic)
- Fibrinogen indication: 78% non-problematic (22% problematic)
- MAT - Wound blood hematocrit %: 60.0%
- MAT - Recovered hematocrit %: 61.3%
- Platelets (for TK): 52.3% paired
- Fibrinogen lab (for Fibrinogen): 43.5% paired
- Serum albumin (for Albumin): 34.4% paired

---

## Next Steps

### After Reviewing Completeness Results

1. **Identify priority variables** with concerning missingness
2. **Investigate causes**:
   - Are "other" indications truly non-classifiable or could documentation be improved?
   - Why is Rh factor so rarely documented?
   - Why are paired lab values so uncommon?
3. **Consider data collection improvements**:
   - Make critical fields mandatory in data entry forms
   - Provide training on specific indication documentation
   - Implement paired lab value collection protocols
4. **Related modules**:
   - Module 2: Dosage consistency (unit validation; the extreme-value screen is reported as NOT ASSESSED pending clinically defined per-product ranges)
   - Module 3: Follow-up duplicates and timing
   - Module 4: Data validity (clinical plausibility ranges)

---

## Technical Notes

### Data Quality Filters

This completeness analysis uses **raw data** without exclusions to assess true documentation patterns. It differs from other analysis modules that apply data quality filters (e.g., excluding PPSB ml, Fibrinogen IU).

### Missing Data Definition

- **Missing**: `NaN`, `None`, empty string, or not present
- **Present**: Any non-missing value (including 0)

### Calculation Methods

- **Demographics & Follow-up Baseline**: Patient-level (first record per patient)
- **Treatment**: Administration-level (all treatment records with product type)
- **Lab Values**: Paired completeness per clinically relevant product (both pre AND post required)
- **Indication**: Product-specific (only relevant products analyzed, product-specific "other" codes)
- **MAT**: Administration-level for MAT only (blood recovery-specific fields)

---

## Contact

For questions about this analysis or to request additional completeness metrics, please contact the study team.
