# Full Analysis Pipeline

**Author:** Elina Nuerenberg-Goloub — **Last revised:** 2026-08-18

## Purpose

The `run_full_analysis.py` script is a master pipeline that runs all analysis modules in the correct order, automating the complete workflow from raw data export to publication-ready figures.

## Quick Start

```bash
# Run everything (statistics, data quality, visualizations)
python3 run_full_analysis.py "../synthetic test data/test_data_150patients.csv" --data-end-date 2026-08-21

# Interactive mode (select which modules to run)
python3 run_full_analysis.py "../synthetic test data/test_data_150patients.csv" --data-end-date 2026-08-21 --interactive
```

## Usage

> **Note:** `--data-end-date YYYY-MM-DD` (the export date of the analyzed file) is **mandatory** for analysis runs — it censors follow-up eligibility. For non-reportable test runs only, `--allow-derived-end-date` derives the date from the latest observed event.
 Options

| Command | Description |
|---------|-------------|
| `python3 run_full_analysis.py <csv_path>` | Run all modules |
| `python3 run_full_analysis.py <csv_path> --interactive` | Select modules interactively |
| `python3 run_full_analysis.py <csv_path> --skip-quality` | Skip data quality checks |
| `python3 run_full_analysis.py <csv_path> --stats-only` | Only run statistics modules |
| `python3 run_full_analysis.py <csv_path> --viz-only` | Only run visualizations |
| `python3 run_full_analysis.py <csv_path> --enrollment-cutoff YYYY-MM-DD` | Restrict to the cohort enrolled on or before the date (see below) |
| `python3 run_full_analysis.py <csv_path> --cohort-from <reference_csv> --episode-cutoff YYYY-MM-DD` | Restrict to the patients of a reference export, capping clinical data at the date (see below) |
| `python3 run_full_analysis.py <csv_path> --clinical-from <reference_csv>` | Reference-clinical splice: reviewed clinical snapshot + current follow-up (see below) |

### Enrollment cutoff (cohort analysis)

`--enrollment-cutoff YYYY-MM-DD` restricts the analysis to patients whose
first episode date is on or before the given date, while keeping **all**
records of those patients — including follow-up questionnaires completed
after the cutoff. This analyzes a fixed enrollment cohort with the longest
available follow-up (e.g. the pilot cohort in a newer export).

A filtered copy of the export is written next to the input file
(`<name>_cohortYYYYMMDD.csv`) and all modules run on it, so the output
directory name records the cohort definition. Patients without a parseable
episode date on any row cannot be assigned to the cohort; they are excluded
and their PIDs listed in the console output for review.

The filter itself is `enrollment_filter.py` (also runnable standalone) and
is covered by its own test program, `test_enrollment_filter.py`.

Example:

```bash
python3 run_full_analysis.py ../new_export.csv --enrollment-cutoff 2026-01-15
# -> analyzes new_export_cohort20260115.csv, output in new_export_cohort20260115/
```

### Cohort from a reference export (exact pilot cohort)

`--cohort-from <reference_csv>` defines the cohort as **exactly the patients
present in the reference export** (e.g. the export a submitted analysis was
computed from) — including consent-only registrants who have no episode
records and would be invisible to a date-based rule. Combined with
`--episode-cutoff YYYY-MM-DD`:

- **administration rows** are kept only if their **administration date**
  (X_433_7_11) is on or before the date — so an episode that starts before
  the cutoff but continues afterwards contributes only its administrations
  up to the cutoff. Administration rows **without** a date are kept only if
  a corresponding administration exists in the reference export (matched by
  the registry record identifier where filled, otherwise by
  PID + product + dose + unit; each reference row justifies at most one
  row, and a corrected record matches by identifier and keeps its corrected
  values) — undated administrations documented after the reference date are
  therefore excluded rather than riding along under an old episode;
- other clinical rows (episode/record-0 data) are kept by **episode date**;
- **follow-up questionnaire rows are always kept** regardless of date.

The result: treatment data identical in scope to the reference analysis,
follow-up counted through the newer export.

Notes:
- A cohort patient first treated *after* the cap keeps their follow-up rows
  but has no administrations in the filtered data — they remain in the
  registered-without-therapy group, and their questionnaires appear in the
  follow-up module's "follow-up without treatment" review category.
- The run summary quantifies undated administrations (kept via record-ID
  match / kept via content match / dropped as undocumented in the
  reference export, with PIDs), and warns about cohort patients absent
  from the newer export, clinical rows without a parseable episode date,
  and cohort patients left with no rows at all after the cap (each with
  PIDs, for registry review).
- Mutually exclusive with `--enrollment-cutoff`.

Example:

```bash
python3 run_full_analysis.py ../new_export.csv \
    --cohort-from ../reference_export.csv --episode-cutoff 2026-01-15
# -> analyzes new_export_cohortfromreference_export_cap20260115.csv,
#    output in new_export_cohortfromreference_export_cap20260115/
```

### Reference-clinical splice (exact reviewed snapshot + current follow-up)

Date-based caps cannot reconstruct a reviewed data cut exactly when records
are documented retrospectively: an administration *given* inside the window
but *entered* after it passes any date rule. When the analysis must use the
clinical data **exactly as reviewed**, `--clinical-from <reference_csv>`
splices the two exports instead of filtering by date:

- all **non-follow-up rows** are taken **verbatim** from the reference
  export — clinical results are bit-identical in scope to the reference
  analysis (later corrections to clinical fields are deliberately not
  carried over; state the data cut in Methods);
- all **follow-up (form 435) rows** are taken from the current export, for
  reference-cohort patients — follow-up reflects the current state;
- schemas are aligned by column name: the reference columns must be a
  subset of the current export’s (new eCRF elements are allowed, stay
  empty on reference-sourced rows, and are listed in the run summary;
  renamed or removed columns abort the run);
- `--exclude-pids P1,P2` removes patients entirely (e.g., after consent erasure);
  `--exclude-followup-pids P1,P2` keeps their reviewed clinical rows but
  removes their follow-up (partial withdrawal);
  `--reference-followup-pids P1,P2` sources those patients' follow-up rows
  from the **reference** export instead of the current one — for patients
  who withdrew after the reference date and are absent from the current
  export, whose pre-withdrawal responses exist only in the reference
  snapshot. All three appear in the output file name
  (`_exclN`/`_exclfuN`/`_reffuN`) and the run summary.

Example:

```bash
python3 run_full_analysis.py ../new_export.csv --clinical-from ../reference_export.csv
# -> analyzes new_export_clinicalfromreference_export.csv,
#    output in new_export_clinicalfromreference_export/
```

## What It Does

The script runs 18 modules in three phases:

### Phase 1: Statistics Analysis (7 modules)

| Module | Description | Output Files |
|--------|-------------|--------------|
| Biometric Statistics | Patient demographics, BMI, comorbidities | `biometric_descriptives.*` |
| Treatment Statistics | Blood products, dosages, lab values | `treatment_statistics_*.*` |
| Indication Statistics | Indications, interventions, risk | `indication_intervention_statistics_*.*` |
| Follow-up Statistics | 3-month and 1-year outcomes | `followup_statistics.*` |
| Temporal Volume Analysis | Monthly/quarterly volumes | `temporal_volumes_*.*` |
| SNOMED Code Analysis | Diagnoses and procedures | `SNOMED/snomed_*.*` |
| Post-Intervention Time to Discharge | Days from intervention to discharge | `LOS/los_*.*` |

### Phase 2: Data Quality Checks (5 modules)

| Module | Description | Output Files |
|--------|-------------|--------------|
| Completeness Analysis | Missing data assessment | `data quality reporting/data_quality_module1_completeness.*` |
| Dosage Quality | Dosage plausibility | `data quality reporting/data_quality_module2_dosage_*` |
| Follow-up Duplicates | Duplicate detection | `data quality reporting/data_quality_module3_followup_duplicates.*` |
| Data Validity | Value range checks | `data quality reporting/data_quality_module4_validity.*` |
| Lab Value Quality | Unit detection | `lab_value_quality_report.txt`, `lab_value_unit_issues.csv` |

### Phase 3: Visualizations (6 modules)

| Module | Description | Figures Generated |
|--------|-------------|-------------------|
| Biometric Visualizations | Gender distribution, age/BMI violins, age/BMI by sex | 4 PNG files + summary CSV |
| Treatment Visualizations | Products, trends, lab values, lab values by sex, admin frequency by sex | 15+ PNG files |
| Dosage Visualizations | Dosage histograms | up to 7 PNG files + summary CSV |
| Indication Visualizations | Indication/intervention donut charts (one per product) | 8 PNG files + summary CSV |
| Follow-up Visualizations | Outcome comparisons | 5+ PNG files |
| Temporal Volume Visualizations | Volume trends | 20+ PNG files |

Exact figure counts depend on the dataset: plots are only rendered from real input data, and figures with insufficient data are skipped with a warning.

## Output Structure

```
test_data_150patients/                 # Named after input CSV
├── biometric_descriptives.csv
├── biometric_descriptives.txt
├── biometric_descriptives_detailed.json
├── treatment_statistics_detailed.json
├── treatment_statistics_combined.txt
├── indication_intervention_statistics_detailed.json
├── followup_statistics_detailed.json
├── temporal_volumes_detailed.json
├── data quality reporting/
│   ├── data_quality_module1_completeness.txt / .json / *.csv
│   ├── data_quality_module2_dosage_consistency.txt / .json / *.csv
│   ├── data_quality_module3_followup_duplicates.txt / .json / *.csv
│   └── data_quality_module4_validity.txt / .json / *.csv
├── lab_value_quality_report.txt
├── lab_value_unit_issues.csv
├── SNOMED/
│   ├── snomed_analysis.json
│   ├── snomed_analysis.txt
│   ├── snomed_codes_for_lookup.csv
│   └── snomed_all_codes.csv
├── LOS/
│   ├── los_analysis.json
│   ├── los_analysis.txt
│   └── los_patient_data.csv
└── figures/
    ├── biometric_gender_distribution.png
    ├── biometric_violins.png
    ├── biometric_age_by_gender.png
    ├── biometric_bmi_by_gender.png
    ├── treatment_product_distribution.png
    ├── treatment_temporal_trends.png
    ├── treatment_administration_frequency.png
    ├── treatment_administration_frequency_by_gender.png
    ├── treatment_administration_frequency_by_gender_percent.png
    ├── lab_value_*.png (before/after)
    ├── lab_value_*_by_gender.png
    ├── dosage_*.png
    ├── indication_*.png
    ├── followup_*.png
    └── monthly_*.png, quarterly_*.png
```

## Interactive Mode

When you run with `--interactive`, you can select which modules to run:

```
Statistics Modules:
----------------------------------------
  1. Biometric Statistics
     Patient demographics, physical characteristics, comorbidities
  2. Treatment Statistics
     Blood product administration, dosages, lab values
  ...

  A. Run ALL statistics modules
  S. SKIP all statistics modules

Select modules (e.g., 1,3,4 or A for all, S to skip):
```

This is useful when:
- Re-running only specific analyses after corrections
- Skipping time-consuming modules during development
- Running only visualizations after statistics are complete

## Error Handling

- If a module fails, the script continues with remaining modules
- Failed modules are reported in the summary
- Visualizations are skipped if their required input files are missing
- If any module failed, the script exits with a non-zero exit code, so scripted callers (e.g., CI or validation harnesses) can detect a broken run

## Typical Workflow

### For a New Data Export

```bash
# 1. Place the CSV in the project root (e.g., test_data_150patients.csv)

# 2. Run full analysis
cd "python codes"
python3 run_full_analysis.py "../synthetic test data/test_data_150patients.csv" --data-end-date 2026-08-21

# 3. Review output in test_data_150patients/ directory
```

### For Re-running Specific Modules

```bash
# Interactive mode to select modules
python3 run_full_analysis.py "../synthetic test data/test_data_150patients.csv" --data-end-date 2026-08-21 --interactive

# Or just visualizations (if statistics already done)
python3 run_full_analysis.py "../synthetic test data/test_data_150patients.csv" --data-end-date 2026-08-21 --viz-only
```

### For Quick Testing

```bash
# Skip data quality checks for faster execution
python3 run_full_analysis.py "../synthetic test data/test_data_150patients.csv" --data-end-date 2026-08-21 --skip-quality
```

## Performance

Typical execution times on a standard laptop:

| Phase | Time |
|-------|------|
| Statistics (7 modules) | ~3-4 seconds |
| Data Quality (5 modules) | ~1-2 seconds |
| Visualizations (6 modules) | ~3-4 seconds |
| **Total** | **~7-10 seconds** |

## Dependencies

All dependencies are the same as the individual modules:
- pandas
- numpy
- matplotlib
- json, csv, datetime (standard library)

## Troubleshooting

### "Module not found" error

Ensure all Python files are in the same directory:
```bash
ls *.py | wc -l  # Should show all module files
```

### Visualization module skipped

Check that the required statistics module ran successfully:
```bash
ls test_data_150patients/*.json  # Should show all JSON files
```

### Data quality module failed

Some data quality modules may fail on empty datasets or unusual data patterns. Check the error message and verify data file integrity.

## Related Documentation

- `Readme.md` - Main project overview
- `Readme_Treatment_Visualization.md` - Treatment visualization details
- `Readme_Lab_Value_Quality.md` - Lab value quality methodology
- `Readme_SNOMED_Analysis.md` - SNOMED code analysis
- `Readme_LOS_Analysis.md` - Post-intervention time to discharge
