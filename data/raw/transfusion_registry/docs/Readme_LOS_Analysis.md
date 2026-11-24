# Post-Intervention Time to Discharge — Analysis Module

**Author:** Elina Nuerenberg-Goloub — **Last revised:** 2026-08-21

## Overview

The `descriptive_los.py` module calculates the interval from the surgical intervention to hospital discharge, in days. The registry export records no hospital admission date, so this interval is the **post-intervention time to discharge**, not the full hospital length of stay; all outputs label it accordingly. (Internal variable names and the output folder keep the historical `LOS` abbreviation for continuity.)

| Field | Column | Description |
|-------|--------|-------------|
| Intervention Date | X_433_0_8 | Date of surgical intervention |
| Discharge Date | X_433_0_753 | Date of discharge from hospital |

**Calculation:** `discharge_date - intervention_date` (in days)

Both dates are taken from the **same record**: the interval is computed row-wise, so an intervention date from one episode is never paired with a discharge date from a different episode. Rows are then ranked per patient (complete same-record date pairs first, then rows with any date, chronological within each rank) and exactly **one episode per patient** is kept.

## Usage

### Basic Usage

```bash
python3 run_los_analysis.py <output_directory>
```

### Example

```bash
python3 run_los_analysis.py test_data_150patients
```

This will:
1. Load data from `../synthetic test data/test_data_150patients.csv`
2. Calculate the time-to-discharge statistics
3. Create `test_data_150patients/LOS/` directory
4. Export all results

## Output Files

All outputs are saved to the `LOS/` subdirectory:

| File | Description |
|------|-------------|
| `los_analysis.json` | Machine-readable complete results |
| `los_analysis.txt` | Human-readable summary table |
| `los_patient_data.csv` | Patient-level interval data |

### los_patient_data.csv

Patient-level data for further analysis:

| Column | Description |
|--------|-------------|
| patient_id | Unique patient identifier |
| intervention_date | Date of surgical intervention |
| discharge_date | Date of hospital discharge |
| days_intervention_to_discharge | Calculated interval in days |
| gender | Patient gender (Male/Female) |
| in_primary_analysis | Boolean flag: interval enters the primary statistic |
| exclusion_reason | Why a value is not in the primary statistic (empty when included): `dates incomplete`, `negative interval`, or over the 365-day screening threshold |

## Statistics Provided

### Coverage Analysis

- **Intervention date coverage**: How many patients have a documented intervention date
- **Discharge date coverage**: How many patients have a documented discharge date
- **Valid intervals calculable**: Patients with both dates and a plausible interval

### Overall Time-to-Discharge Statistics

- **N**: Number of patients with a valid interval
- **Mean (SD)**: Mean interval with standard deviation
- **Median [IQR]**: Median with interquartile range
- **Range**: Minimum to maximum interval

Medians and quartiles are reported to one decimal place (they can be half-days), overall and in the gender-stratified statistics.

### Gender-Stratified Statistics

Same statistics as overall, calculated separately for male and female patients.

### Threshold Sensitivity Analysis

Intervals above the 365-day screening threshold are **not silently discarded**: each one is listed individually (patient identifier and days), and the summary statistics are reported both **with and without** the threshold, so the effect of the exclusion on the right tail of the distribution is visible. The threshold is a screening rule — an interval of more than one year between intervention and discharge is rare and reviewed as a potential documentation error rather than silently retained.

### Discharge Documentation by Product Status

Compares discharge documentation rates between:
- **Patients WITH blood products**: Those who received at least one blood product administration
- **Patients WITHOUT blood products**: Registered patients with no blood product documentation

This analysis helps identify whether incomplete records (no discharge date) are associated with treatment status.

## Data Quality Filters

The module applies the following filters to the primary statistic:

| Filter | Threshold | Rationale |
|--------|-----------|-----------|
| Minimum interval | >= 0 days | Negative values indicate data errors and are excluded as invalid |
| Maximum interval | <= 365 days | Screening threshold; values above it are listed individually and analyzed in the sensitivity section |

Excluded records are reported in the coverage statistics, itemized in `los_patient_data.csv` with their exclusion reason, and — for the 365-day threshold — carried into the sensitivity analysis.

## Integration with Analysis Pipeline

This module integrates with the existing analysis pipeline:

```
run_treatment_analysis.py     → Treatment statistics
run_visualize_treatments.py   → Treatment visualizations
run_snomed_analysis.py        → SNOMED code analysis
run_los_analysis.py           → Post-intervention time to discharge
```

Typical workflow:
```bash
# Run all analyses
python3 run_treatment_analysis.py "../synthetic test data/test_data_150patients.csv" test_data_150patients
python3 run_visualize_treatments.py test_data_150patients
python3 run_snomed_analysis.py test_data_150patients
python3 run_los_analysis.py test_data_150patients
```

## Dependencies

- pandas
- numpy
- transfusion_data_loader (local module)

## Related Documentation

- `Readme_Treatment_Statistics.md` - Treatment analysis module
- `Readme_Treatment_Visualization.md` - Visualization module
- `Readme_SNOMED_Analysis.md` - SNOMED code analysis module
