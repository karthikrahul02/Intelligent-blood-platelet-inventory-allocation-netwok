# Treatment Descriptive Statistics Module

**Author:** Elina Nuerenberg-Goloub — **Last revised:** 2026-08-18

## Overview

The `descriptive_treatments.py` module provides comprehensive descriptive statistics for haematologic treatment details in the transfusion registry. It calculates statistics at **two levels**:

1. **Administration Level**: Statistics for all product administrations (n=1,113 records)
2. **Patient Level**: Statistics aggregated by patient (n=276 unique patients)

This dual-level approach provides both detailed treatment information and patient-centered perspectives, as recommended for clinical research reporting.

## Features

### Administration-Level Statistics (Record-Level)

1. **Total Administrations**
   - Total number of product administrations
   - Number of unique patients
   - Mean administrations per patient

2. **Product Distribution**
   - Frequency and percentage for each blood product type:
     - Red blood cell concentrate (RBC)
     - Fresh Frozen Plasma (FFP)
     - Platelet concentrate (PC)
     - PPSB (Prothrombin Complex Concentrate)
     - Fibrinogen
     - Iron i.v.
     - Albumin
     - EPO (Erythropoietin)
     - Antithrombin III (ATIII)
     - Oral iron
     - Machine Autotransfusion (Cell Salvage)

3. **Temporal Distribution**
   - Administration dates range
   - Monthly distribution of administrations
   - Missing dates count

4. **Dosage Statistics by Product**
   - Stratified by product type and dosage unit (ml, IU, mg)
   - Mean, SD, median, IQR, range
   - Sample size for each product-unit combination

5. **Indication Statistics**
   - Distribution of indications by product type
   - Decoded indication descriptions
   - Missing data tracking

6. **Laboratory Values (Before → After)**
   - Paired measurements for:
     - Hemoglobin (g/dl)
     - Platelets (/µl)
     - Quick's test (%)
     - Fibrinogen (mg/dl)
     - Serum albumin (g/dl)
     - Ferritin (µg/l)
     - Transferrin saturation (%)
     - Antithrombin activity (%)
   - Statistics for before, after, and change values
   - Normal reference ranges included

### Patient-Level Statistics

1. **Administrations Per Patient**
   - Mean, SD, median, IQR, range
   - Distribution of patients by number of administrations
   - Percentages for each category

2. **Products Received Per Patient**
   - Number and percentage of patients receiving each product
   - Total administrations per product
   - Mean administrations per patient for each product

### Blood Type Compatibility Analysis

Analyzes ABO and RhD blood type documentation for products where compatibility is clinically important:

1. **Products Analyzed**: RBC, FFP, Platelet concentrate
2. **Documentation Rates**:
   - Patient ABO/Rh documented
   - Product ABO/Rh documented
   - Either documented (for blood type availability)
   - Both documented (for compatibility verification)
3. **ABO Compatibility Assessment** (correct transfusion-medicine matrices, applied per product class):
   - **RBC**: the donor product must be compatible with the recipient (group O is the universal RBC donor; AB recipients can receive any group)
   - **FFP/plasma**: the rules are REVERSED relative to red cells (group AB is the universal plasma donor; group O recipients can receive any plasma)
   - **Platelet concentrate (PC)**: reported neutrally as ABO-identical vs. ABO-non-identical, with no incompatibility alarm (ABO-identical PC is preferred but not mandatory)
   - Per product, administrations are counted as: identical / compatible non-identical / incompatible / not assessable (for PC: identical / non-identical / not assessable)
4. **RhD Check** (RBC and PC): an RhD-positive product administered to an RhD-negative patient is flagged
5. **Flagged Case Details** (ABO-incompatible and RhD-flagged records):
   - PID, product type, blood types
   - Administration date and dosage
   - Follow-up outcomes (if available): problems reported, anaemia status, subsequent transfusions

### Normalized Dosages by Gender

Dosages normalized for body size, stratified by sex:

1. **RBC and FFP: Dose per Liter Estimated Blood Volume (EBV)**
   - Estimated blood volume calculated using Nadler's formula:
     - Males: BV (L) = 0.3669 × H³ + 0.03219 × W + 0.6041
     - Females: BV (L) = 0.3561 × H³ + 0.03308 × W + 0.1833
     - H = height in meters, W = weight in kg
   - Unit: ml/L EBV
   - Requires height, weight, and sex data

2. **Other Products: Dose per kg Body Weight**
   - PPSB (IU/kg), Fibrinogen (mg/kg), ATIII (IU/kg), Platelets (ml/kg), Albumin (ml/kg)
   - Requires weight data

### Gender-Stratified Statistics

Analyzes treatment patterns and laboratory values stratified by sex:

1. **Administrations Per Patient by Sex**
   - Number of patients and total administrations per sex
   - Mean, SD, median, IQR, range

2. **Products Per Patient by Sex**
   - Which products each sex receives
   - Percentage of patients receiving each product

3. **Laboratory Values Before Administration by Sex**
   - Hemoglobin, Platelets, Quick's test, Fibrinogen, Serum albumin, Antithrombin activity
   - Mean, SD, median, IQR, range for each sex
   - Important because normal ranges differ by sex

## Usage

### Basic Usage

```python
from descriptive_treatments import run_treatment_analysis

# Run complete analysis
treatment = run_treatment_analysis("your_data.csv", output_dir="results")
```

This will:
1. Load the data
2. Calculate all treatment statistics (both levels)
3. Display summary tables
4. Export results to multiple files

### Advanced Usage

```python
from transfusion_data_loader import TransfusionDataLoader
from descriptive_treatments import TreatmentDescriptives

# Load data
loader = TransfusionDataLoader()
loader.load_data("your_data.csv")

# Create analysis object
treatment = TreatmentDescriptives(loader)

# Calculate statistics
results = treatment.calculate_all()

# Access specific results
print(f"Total administrations: {results['administration_level']['total_count']['total_administrations']}")
print(f"Mean per patient: {results['patient_level']['administration_frequency']['statistics']['mean']:.1f}")

# Get product distribution
products = results['administration_level']['products']['products']
for product_name, data in products.items():
    print(f"{product_name}: {data['n']} ({data['percent']:.1f}%)")

# Get lab values
hb_data = results['administration_level']['lab_values']['Hemoglobin']
print(f"Hemoglobin change: {hb_data['change']['mean']:.2f} ± {hb_data['change']['sd']:.2f} g/dl")

# Create and display tables
admin_table, patient_table = treatment.create_summary_tables()
print(admin_table)
print(patient_table)

# Export results
treatment.export_results(output_dir="results")
```

### Quick Start Script

Use the provided `run_treatment_analysis.py` script (input CSV and output directory required):

```bash
python3 run_treatment_analysis.py "../synthetic test data/test_data_150patients.csv" test_data_150patients
```

## Output Files

The module generates the following output files:

### 1. treatment_statistics_detailed.json
Machine-readable JSON with all calculated statistics. Contains:
- Complete administration-level results
- Complete patient-level results
- All numerical values with full precision

Example structure:
```json
{
  "administration_level": {
    "total_count": {...},
    "products": {...},
    "temporal": {...},
    "dosages": {...},
    "indications": {...},
    "lab_values": {...}
  },
  "patient_level": {
    "patient_count": {...},
    "products_per_patient": {...},
    "administration_frequency": {...}
  }
}
```

### 2. treatment_statistics_administration_level.txt
Formatted table with administration-level statistics. Includes:
- Product distribution
- Temporal distribution by month
- Dosage statistics by product and unit
- Laboratory values before/after with changes

### 3. treatment_statistics_patient_level.txt
Formatted table with patient-level statistics. Includes:
- Administrations per patient (distribution)
- Products received per patient
- Patient-centered treatment patterns

### 4. treatment_statistics_combined.txt
Combined file containing both administration-level and patient-level tables. Useful for comprehensive reporting.

### 5. data_completeness_by_product.txt / .csv
Data completeness analysis showing documentation rates per product:
- Total administrations, dosage documentation, indication documentation
- Primary lab value before/after documentation rates

### 6. autotransfusion_statistics.txt / .csv
Machine Autotransfusion (Cell Salvage) specific statistics:
- Wound blood volume, hematocrit
- Recovered RBC volume, hematocrit

### 7. blood_type_compatibility.txt / .csv
Blood type documentation and compatibility analysis:
- ABO and RhD documentation rates for RBC, FFP, PC
- Per product: identical / compatible non-identical / incompatible / not assessable counts (PC reported neutrally as identical / non-identical)
- RhD check results (RBC and PC): flagged / unflagged / not assessable

### 8. blood_type_incompatible_for_review.csv
Detailed list of ABO-incompatible and RhD-flagged administrations for clinical review (only written if such records exist):
- PID, product, issue, patient/product ABO and Rh types
- Administration date, dosage
- Follow-up outcomes (if available)

### 9. gender_stratified_statistics.txt
Gender-stratified analysis:
- Administrations per patient by sex
- Laboratory values before administration by sex

### 10. lab_values_by_gender.csv
Lab values stratified by sex for further analysis:
- n, mean, SD, median, IQR, range per lab value per sex

### 11. dosages_normalized_by_gender.csv / .txt
Normalized dosages stratified by sex:
- RBC and FFP: ml/L EBV (Nadler's formula)
- Other products: dose per kg body weight
- Includes normalization method column ("ebv_nadler" or "per_kg")
- Only doses documented in the product's expected unit are normalized, and the same data-quality exclusion rules as the primary dosage tables are applied

### 12. dosage_exclusions.csv
Log of the dosage data-quality exclusions, one row per applied rule (product/unit combination):
- Product_Unit, Original_N, Excluded_N, Retained_N, Reason

## Statistical Methods

### Administration-Level Analysis

**Product Distribution:**
- Frequencies and percentages calculated from all administrations
- Missing/not documented values reported separately

**Temporal Analysis:**
- Monthly aggregation using administration dates
- Date range reported
- Missing dates tracked

**Dosage Analysis:**
- Stratified by product type and dosage unit
- Standard descriptive statistics (mean, SD, median, IQR, range)
- Handles multiple units per product (e.g., Fibrinogen in both IU and mg)
- Data-quality exclusions applied: PPSB in ml (implausible for a reconstituted product), Fibrinogen in IU (non-standard unit), Fibrinogen doses < 500 mg (implausibly low)
- All exclusions are logged and exported to `dosage_exclusions.csv`; the normalized-dose tables apply the same exclusion rules

**Laboratory Values:**
- **Paired analysis**: Only includes records with both before AND after measurements
- Calculates change as: After - Before
- Reports number of unpaired measurements separately
- Includes normal reference ranges for clinical interpretation

**Indications:**
- Decoded using data dictionary mappings
- Calculated per product type
- Missing data reported

### Patient-Level Analysis

**Administrations Per Patient:**
- Counts all administrations per unique patient ID
- Provides distribution showing how many patients received 1, 2, 3, ... administrations
- Clinically relevant for understanding treatment intensity

**Products Per Patient:**
- Each patient counted once per product type
- Percentage relative to total patient cohort
- Mean administrations calculated among those who received the product

## Data Quality and Unit Conversions

### Lab Value Unit Detection

The visualization module integrates with `lab_value_quality.py` to detect and handle unit inconsistencies in laboratory values.

**Detected Issues**:

| Lab Parameter | Problem | Detection Method | Action |
|---------------|---------|------------------|--------|
| Platelets | Values entered in thousands/µl instead of /µl | Positive values < 1000 | Multiply by 1,000 once; report on the /µl scale (correction audited) |
| Serum albumin | Some values entered in mg/dl instead of g/dl | Values ≥ 100 | Divide by 1,000 once; report in g/dl (correction audited) |

**How It Works**:
1. `LabValueQualityChecker` analyzes value distributions
2. Detects dominant unit based on thresholds
3. Flags minority-unit values as outliers
4. Excludes outliers from visualizations
5. Exports problematic records for manual clinical review

**Quality Check Files**:
- `lab_value_quality_report.txt` - Human-readable summary
- `lab_value_unit_issues.csv` - Records requiring manual review

**Documentation**: See `Readme_Lab_Value_Quality.md` for detailed methodology.

### Unit Handling in the Statistics Module

The statistics module itself applies two unit-consistency rules, identically in the headline lab value tables and in the gender-stratified section:

- **Platelets**: a single ×1000 normalization - positive values < 1,000 (entered in thousands/µl) are multiplied by 1,000 so all values are reported on the /µl scale; non-positive and clinically implausible values are excluded, and every correction and exclusion is counted in the audit fields of the results
- **Serum albumin**: values ≥ 100 in the g/dl field (entered in mg/dl) are divided by 1,000 and included on the canonical g/dl scale; the conversions are counted in the audit fields

Both rules come from the central analysis series in `lab_value_quality.py` (order: numeric parse → exclude non-positive values, never scale them → one-time unit correction → clinical plausibility gate), so the statistics, the quality report, and the figures all draw on the same values.

The `lab_value_quality.py` module additionally provides distribution-based detection and exports problematic records for clinical review.

## Missing Data Handling

Missing data is reported separately and not included in percentage calculations.

## Dependencies

- pandas
- numpy
- transfusion_data_loader (local module)
- transfusion_registry_mapping (local module)

## Integration with Other Modules

This module complements:
- **Biometric Statistics** (`descriptive_biometrics.py`): Provides patient baseline characteristics
- **Data Loader** (`transfusion_data_loader.py`): Handles data import and preprocessing
- **Mapping** (`transfusion_registry_mapping.py`): Decodes product and indication codes
- **Lab Value Quality** (`lab_value_quality.py`): Detects unit inconsistencies in lab values
- **Treatment Visualization** (`visualize_treatments.py`): Creates publication-quality figures

