# Biometric Descriptive Statistics Module

**Author:** Elina Nuerenberg-Goloub — **Last revised:** 2026-08-18

## Overview

The `descriptive_biometrics.py` module provides comprehensive descriptive statistics for patient biometric properties. It follows medical research standards for presenting baseline characteristics in clinical studies.

**Important:** All statistics are calculated at the **patient level** (one observation per patient), not at the transfusion episode level. This is appropriate for describing baseline patient characteristics in a cohort with repeated measurements.

The module distinguishes **transfused** from **non-transfused** patients: the main statistics table covers transfusion patients only, while patients without any blood product administration are reported in a separate summary (count, data availability, and age using the same episode-year reference).

## Features

### Calculated Statistics

1. **Total Patient Count**
   - Unique patients (n=276 in example)
   - Total transfusion records (n=1,113 in example)
   - Patient-level records (n=276, one per patient)
   - Records per patient (mean=4.0 in example)

2. **Age**
   - Overall: Mean, SD, median, IQR, range
   - By gender: Mean, SD, median, range for Male and Female
   - Missing data count

3. **Gender Distribution**
   - Male, Female, Intersex/Diverse
   - Not provided
   - Frequencies and percentages

4. **Body Mass Index (BMI)**
   - Overall statistics
   - Statistics by gender (Male, Female, Intersex/Diverse)
   - Mean, SD, median, IQR, range
   - Calculated from height and weight
   - Unrealistic values (<10 or >60 kg/m²) excluded

5. **Blood Group**
   - A, B, AB, 0
   - Not provided
   - Frequencies and percentages

6. **Rh Factor**
   - Positive (Rh+)
   - Negative (Rh-)
   - Unknown
   - Not provided
   - Frequencies and percentages

## Usage

### Basic Usage

```python
from descriptive_biometrics import run_biometric_analysis

# Run complete analysis
bio = run_biometric_analysis("your_data.csv", output_dir="results")
```

This will:
1. Load the data
2. Calculate all biometric statistics
3. Export results to CSV, text, and JSON files
4. Display summary table

### Advanced Usage

```python
from transfusion_data_loader import TransfusionDataLoader
from descriptive_biometrics import BiometricDescriptives

# Load data
loader = TransfusionDataLoader()
loader.load_data("your_data.csv")

# Create analysis object
bio = BiometricDescriptives(loader)

# Calculate statistics
results = bio.calculate_all()

# Access specific results
print(f"Mean age: {results['age']['mean']:.1f} years")
print(f"Male patients: {results['gender']['Male']['n']}")
print(f"Mean BMI (males): {results['bmi']['by_gender']['Male']['mean']:.1f}")

# Create summary table
summary_table = bio.create_summary_table()
print(summary_table)

# Export results
bio.export_results(output_dir="results")
```

### Working with Results

```python
# Access detailed results
bio = run_biometric_analysis("data.csv")

# Age statistics
age_stats = bio.results['age']
print(f"Age: {age_stats['mean']:.1f} ± {age_stats['sd']:.1f} years")
print(f"Median: {age_stats['median']:.1f} years")
print(f"IQR: {age_stats['q25']:.1f}-{age_stats['q75']:.1f} years")

# Gender distribution
gender_stats = bio.results['gender']
for gender_label, gender_data in gender_stats.items():
    if gender_label not in ['total', 'total_with_data']:
        print(f"{gender_label}: {gender_data['n']} ({gender_data['percent']:.1f}%)")

# BMI by gender
bmi_stats = bio.results['bmi']
for gender, bmi_data in bmi_stats['by_gender'].items():
    print(f"BMI ({gender}): {bmi_data['mean']:.1f} ± {bmi_data['sd']:.1f} kg/m²")
```

## Output Files

The module generates three output files:

### 1. biometric_descriptives.csv
CSV format for importing into statistical software or Excel. Contains:
- Variable names
- Categories
- Statistics

### 2. biometric_descriptives.txt
Formatted text report suitable for inclusion in research reports. Contains:
- Complete formatted table
- Legend explaining abbreviations
- Publication-ready format

### 3. biometric_descriptives_detailed.json
Machine-readable JSON with all calculated values. Useful for:
- Further processing
- Integration with other tools
- Archiving detailed results

## Patient-Level vs Record-Level Analysis

### Why Patient-Level Statistics?

In the transfusion registry, patients can have multiple transfusion episodes (records). For baseline characteristics (age, gender, BMI, blood group), we should report each patient only once to avoid:

1. **Pseudoreplication**: Counting the same patient multiple times inflates sample size
2. **Bias**: Patients with more transfusions would be over-represented
3. **Inappropriate inference**: Baseline characteristics are patient properties, not episode properties

### How It Works

The module:
1. Sorts all records by patient ID and date
2. Takes **one real documented row** per patient (the row with the most complete basic data; earliest episode on ties) — never a per-column composite of several rows
3. Calculates statistics on this patient-level dataset
4. Reports both total patients (276) and total records (1,113) for context
5. Itemizes patients whose time-invariant attributes (sex, height, weight, year of birth) carry conflicting values across rows — the report section "Conflicting basic-data entries" lists each conflict with PID, attribute, and values, and the statistics use the first documented value

## Example Output

```
==================================================================
DESCRIPTIVE STATISTICS: BIOMETRIC PROPERTIES
==================================================================

                 Variable           Category                    Statistic
    Total unique patients                                         n = 276
Total transfusion records                                        n = 1113
                     Note          Statistics below calculated at patient level
              Age (years)                                                         n = 275
                                   Mean (SD)                                  64.4 (10.8)
                                Median [IQR]                             66.0 [58.5-72.0]
                                       Range                                        21-87
                   Gender                                                         n = 273
                                        Male                                  199 (72.9%)
                                      Female                                   74 (27.1%)
                            Intersex/Diverse                                     0 (0.0%)
                                Not provided                                     3 (1.1%)
              BMI (kg/m²)            Overall                                      n = 269
                                   Mean (SD)                                   26.8 (4.9)
                                Median [IQR]                             25.8 [23.7-29.7]
                                       Range                                    16.7-48.9
                                     By Male                                      n = 197
                                   Mean (SD)                                   27.0 (4.0)
                                Median [IQR]                             26.2 [24.3-29.7]
                                       Range                                    18.4-38.4
                                   By Female                                       n = 72
                                   Mean (SD)                                   26.4 (6.6)
                                Median [IQR]                             24.6 [21.7-29.5]
                                       Range                                    16.7-48.9
              Blood Group                                                         n = 117
                                           A                                   48 (41.0%)
                                           B                                   14 (12.0%)
                                          AB                                     3 (2.6%)
                                           0                                   52 (44.4%)
                                Not provided                                  159 (57.6%)
                Rh Factor                                                          n = 22
                                    Positive                                   14 (63.6%)
                                    Negative                                     1 (4.5%)
                                     Unknown                                    7 (31.8%)
                                Not provided                                  254 (92.0%)
```

## Statistical Methods

### Age Calculation
- Calculated from year of birth
- Reference date: Episode date (episode year), for ALL cohorts - including non-transfused patients - so ages are comparable and do not drift with the analysis run date
- For non-transfused patients without an episode date, the latest episode year in the full dataset is used as fallback
- Ages outside 0-120 years excluded as unrealistic

### BMI Calculation
- Formula: Weight (kg) / Height² (m²)
- Height converted from cm to meters
- BMI values outside 10-60 kg/m² excluded as unrealistic
- Calculated separately for each gender group

### Missing Data Handling
- Missing values explicitly reported
- Percentages calculated from available data only
- "Not provided" category shown separately

### Presentation Format
- Continuous variables: Mean (SD), Median [IQR], Range
- Categorical variables: n (%)
- Standard deviation (SD) to 1 decimal place
- Percentages to 1 decimal place

## Dependencies

- pandas
- numpy
- transfusion_data_loader (local module)
- transfusion_registry_mapping (local module)

