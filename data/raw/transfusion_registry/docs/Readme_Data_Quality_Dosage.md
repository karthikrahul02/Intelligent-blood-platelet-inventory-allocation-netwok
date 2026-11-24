# Data Quality Analysis - Module 2: Dosage Consistency

**Author:** Elina Nuerenberg-Goloub — **Last revised:** 2026-08-18

**Purpose**: Check dosage data for unit consistency, missing values, and identify anomalies across blood products.

---

## Overview

This module performs dosage consistency analysis for all blood products in the transfusion registry. It identifies unit mismatches, missing dosage values, and prepares data for clinical review.

### Checks Performed

1. **Unit Consistency**
   - Verifies each product uses its standard unit
   - Flags records with non-standard units for review
   - Products checked: RBC, FFP, PC, PPSB, Fibrinogen, Albumin, ATIII

2. **Missing Dosages**
   - Identifies records with missing dosage amount
   - Identifies records with missing dosage unit
   - Reports by product for prioritization

3. **Extreme Values** (not in this release)
   - A statistical outlier screen for dosage amounts is intentionally
     not part of this release; it would require clinically defined
     per-product dosage ranges. The implemented plausibility rules
     (standard units per product, the fibrinogen minimum) are
     described above.

4. **Dosage Statistics**
   - Min, max, median, mean per product
   - Calculated only for records with standard units

---

## Usage

### Command

```bash
python3 run_data_quality_module2_dosage.py <data_file> <output_directory>
```

### Example

```bash
python3 run_data_quality_module2_dosage.py "../synthetic test data/test_data_150patients.csv" test_data_150patients
```

This will:
1. Load and analyze the data
2. Check unit consistency across products
3. Identify missing dosage values
4. Calculate dosage statistics
5. Create subfolder: `test_data_150patients/data quality reporting/`
6. Generate output files in that subfolder

---

## Output Files

All files are saved in: `<output_directory>/data quality reporting/`

### 1. Comprehensive Report (TXT)

**`data_quality_module2_dosage_consistency.txt`**
- Summary statistics
- Dosage statistics by product table
- Unit consistency issues table

### 2. Detailed Results (JSON)

**`data_quality_module2_dosage_consistency.json`**
- Complete hierarchical results
- All unit issues with details
- All missing dosage records
- Summary statistics by product
- Suitable for programmatic access

### 3. Clinic Follow-up CSVs

**`data_quality_module2_non_standard_units.csv`**
- Records using non-standard units
- Columns: PID, Admin_Date, Product, Issue, Value, Current_Unit, Standard_Unit

**`data_quality_module2_missing_dosages.csv`**
- Records with missing dosage information
- Columns: PID, Admin_Date, Product, Missing_Field

### 4. Summary CSVs

**`data_quality_module2_missing_dosages_summary.csv`**
- Missing dosages aggregated by product

**`data_quality_module2_dosage_statistics.csv`**
- Complete dosage statistics per product

---

## Standard Units by Product

| Product | Standard Unit | Unit Code |
|---------|---------------|-----------|
| Red blood cell concentrate (RBC) | ml | 1 |
| Fresh Frozen Plasma (FFP) | ml | 1 |
| Platelet concentrate (PC) | ml | 1 |
| PPSB | IU | 2 |
| Fibrinogen | mg | 3 |
| Albumin | ml | 1 |
| Antithrombin III (ATIII) | IU | 2 |

This follows the registry-wide unit convention: RBC, FFP, PC, albumin (and MAT volumes) are recorded in ml (code 1); PPSB, EPO, and ATIII in IE/IU (code 2); fibrinogen, iron i.v., and oral iron in mg (code 3). Every product code 1-10 has a checked unit convention (the conventions for iron i.v., EPO, and oral iron were confirmed clinically on 2026-08-21); machine autotransfusion (11) is documented as not applicable.

**Note**: MAT (Machine Autotransfusion, product code 11) is excluded from dosage analysis as it uses different metrics (volumes, hematocrit).

**Robust code matching**: Product and unit codes are normalized before comparison, so integer and float representations of the same code (e.g. `4` and `4.0`) always match. Unit checks cannot be silently skipped by a representation difference.

---

## Data Quality Filters

The following exclusions are applied automatically:

| Product | Unit | Action | Reason |
|---------|------|--------|--------|
| PPSB | ml | Flag as non-standard | Clinically implausible (PPSB is dosed in IU) |
| Fibrinogen | IU | Flag as non-standard | Non-standard unit (should be mg) |

---

## Interpreting Results

### Unit Consistency Issues

Records flagged with non-standard units may indicate:
- **Data entry error**: Wrong unit selected in dropdown
- **Unit confusion**: Clinician entered value in different unit than selected
- **System issue**: Default unit not matching clinical practice

### Missing Dosages

Missing dosage information affects:
- **Dosing analysis**: Cannot calculate per-kg dosing
- **Cost analysis**: Cannot estimate product usage
- **Quality metrics**: Incomplete documentation

### Dosage Statistics

Statistics are calculated only for records with:
- Standard unit for that product
- Non-missing dosage value

This ensures statistics reflect clinically meaningful data.

---

## Related Modules

- **Module 1**: Completeness (missing data rates per variable)
- **Module 3**: Follow-up duplicates (timing, duplicate detection)
- **Module 4**: Validity (clinical plausibility ranges for lab values)

---

## Technical Notes

### Data Source

- Treatment-level data (Form 433, Record 7)
- MAT records (product code 11) excluded

### Column Mappings

| Parameter | Column Code |
|-----------|-------------|
| Product type | X_433_7_746 |
| Dosage amount | X_433_7_22 |
| Dosage unit | X_433_7_734 |
| Admin date | X_433_7_11 |

### Unit Codes

| Code | Unit |
|------|------|
| 1 | ml |
| 2 | IU |
| 3 | mg |

Codes are matched after normalization, so `1` and `1.0` are treated identically.

---

## Contact

For questions about this analysis or to provide clinical dosage ranges, please contact the study team.
