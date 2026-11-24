# SNOMED Code Analysis Module

**Author:** Elina Nuerenberg-Goloub — **Last revised:** 2026-08-18

## Overview

The `descriptive_snomed.py` module provides coverage and frequency analysis for SNOMED CT coded fields in the transfusion registry:

| Field | Column | Description |
|-------|--------|-------------|
| Primary Diagnosis | X_433_0_5 | Main diagnosis for transfusion indication |
| Secondary Diagnosis | X_433_0_6 | Comorbidities and secondary conditions |
| Intervention/Procedure | X_433_0_9 | Surgical procedure SNOMED code |

## What is SNOMED CT?

SNOMED CT (Systematized Nomenclature of Medicine - Clinical Terms) is an international standardized clinical terminology. Codes are numeric identifiers (e.g., `53741008` = Coronary arteriosclerosis).

**Official browser:** https://browser.ihtsdotools.org/

## Usage

### Basic Usage

```bash
python3 run_snomed_analysis.py <output_directory>
```

### Example

```bash
python3 run_snomed_analysis.py test_data_150patients
```

This will:
1. Load data from `../synthetic test data/test_data_150patients.csv`
2. Calculate coverage and frequency statistics
3. Create `test_data_150patients/SNOMED/` directory
4. Export all results

## Output Files

All outputs are saved to the `SNOMED/` subdirectory:

| File | Description |
|------|-------------|
| `snomed_analysis.json` | Machine-readable complete results |
| `snomed_analysis.txt` | Human-readable summary table |
| `snomed_codes_for_lookup.csv` | Top codes with lookup URLs for manual annotation |
| `snomed_all_codes.csv` | Complete list of all codes with frequencies |

### snomed_codes_for_lookup.csv

This file is designed for manual annotation:

| Column | Description |
|--------|-------------|
| field | Which SNOMED field (Primary Diagnosis, Secondary Diagnosis, Intervention) |
| snomed_code | The SNOMED CT code |
| n_records | Number of administration records (one patient may have multiple records) |
| n_patients | Number of unique patients with this code |
| percent_of_patients | Percentage of total patient cohort |
| description | **Empty - fill in manually after lookup** |
| lookup_url | Direct link to SNOMED browser for this code |

**Important:** `n_records` counts administrations (a patient with 4 transfusions = 4 records), while `n_patients` counts unique patients.

**Workflow:**
1. Open the CSV in Excel or similar
2. Click each `lookup_url` to open the SNOMED browser
3. Copy the official description into the `description` column
4. Save for documentation

**Note:** The `lookup_url` values are constructed from the standard SNOMED browser URL pattern (`https://browser.ihtsdotools.org/?perspective=full&conceptId1={code}`). The script does not fetch data from the SNOMED API - descriptions must be looked up manually. 

Careful!!! when using the SNOMED API, it disconnects when too many reading attempts are made without time pause (e.g., 10 seconds). Read about it before automated access attempts.

## Statistics Provided

### Coverage Analysis

For each SNOMED field:
- **Administration level**: How many administration records have the field documented. The denominator is the set of administration rows (rows with a documented product type, `X_433_7_746` not null) - follow-up and baseline-only rows are excluded so they do not dilute the percentage
- **Patient level**: How many patients have at least one documented value (denominator: all unique patients)

### Frequency Analysis

For each SNOMED code, the module reports:
- **n_records**: Number of administration records (one patient with multiple transfusions appears multiple times)
- **n_patients**: Number of unique patients (the clinically relevant count)
- **percent_of_patients**: Percentage of total patient cohort

Top 5 codes per field are displayed, with complete lists exported to CSV.

## Integration with Analysis Pipeline

This module integrates with the existing analysis pipeline:

```
run_treatment_analysis.py     → Treatment statistics
run_visualize_treatments.py   → Treatment visualizations
run_snomed_analysis.py        → SNOMED code analysis (NEW)
```

Typical workflow:
```bash
# Run all analyses
python3 run_treatment_analysis.py "../synthetic test data/test_data_150patients.csv" test_data_150patients
python3 run_visualize_treatments.py test_data_150patients
python3 run_snomed_analysis.py test_data_150patients
```

## Dependencies

- pandas
- numpy
- transfusion_data_loader (local module)

## Related Documentation

- `Readme_Treatment_Statistics.md` - Treatment analysis module
- `Readme_Treatment_Visualization.md` - Visualization module
