# Data Quality Analysis - Module 3: Follow-up Duplicates

**Author:** Elina Nuerenberg-Goloub — **Last revised:** 2026-08-18

**Purpose**: Identify duplicate follow-up surveys and assess follow-up completion rates.

---

## Overview

This module analyzes follow-up survey timing and identifies data quality issues:
- **Duplicate follow-ups**: Multiple surveys within the same time window
- **Outside windows**: Follow-ups outside expected timeframes
- **Completion rates**: How many eligible patients completed each follow-up window

### Follow-up Time Windows

**3-Month Window**: 68-113 days
- Target: ~90 days post-first treatment
- Tolerance: ±3 weeks (expanded by 1 day to 68 to capture edge cases)

**1-Year Window**: 273-455 days
- Target: ~365 days post-first treatment
- Tolerance: ±3 months

**Expected**: 1 follow-up per window per patient
**Problem**: Multiple follow-ups in the same window

### Duplicate Handling in Statistics Module

The `descriptive_followup.py` statistics module now handles same-window duplicates automatically. Records are compared on questionnaire **content only** (the completion date `X_435_0_751` is excluded from the comparison):
- **Identical duplicates** (same content): One record kept, logged as "resolved"
- **Conflicting duplicates** (different content): ALL records excluded from analysis, exported to `conflicting_followup_duplicates.csv` for manual review

This data quality module identifies duplicates for reporting purposes; the statistics module determines how they affect analysis.

**Important**:
- Baseline date is the **first blood product date** (first treatment), NOT discharge date
- Windows were slightly expanded to capture follow-ups at 112-113 days and 273 days that were marginally outside original ranges

---

## Usage

### Command

```bash
python3 run_data_quality_module3_followup_duplicates.py <data_file> <output_directory>
```

### Example

```bash
python3 run_data_quality_module3_followup_duplicates.py "../synthetic test data/test_data_150patients.csv" test_data_150patients
```

This will:
1. Identify follow-up records (FormStatus_435 = "open")
2. Establish baseline date for each patient (first treatment date)
3. Calculate days from baseline to follow-up completion date
4. Categorize follow-ups into time windows
5. Detect duplicates within the same window (3-month and 1-year windows only)
6. Calculate current eligibility and completion rates (as of a reference date derived from the data)
7. Generate output files in `test_data_150patients/data quality reporting/`

---

## Output Files

All files are saved in: `<output_directory>/data quality reporting/`

### 1. Comprehensive Report (TXT)

**`data_quality_module3_followup_duplicates.txt`**
- Summary statistics
- Completion rates by window
- List of duplicate situations

### 2. Detailed Results (JSON)

**`data_quality_module3_followup_duplicates.json`**
- Complete hierarchical results
- All statistics in structured format
- Includes `reference_date`: the eligibility reference date derived from the data (maximum of baseline and follow-up completion dates), not a hardcoded export date

### 3. CSV Files (4 files)

**`data_quality_module3_all_followups.csv`**
- All follow-up records with window categorization
- Columns: PID, Completion_Date, Baseline_Date, Days_From_Baseline, Window

**`data_quality_module3_same_window_duplicates.csv`**
- Patients with duplicate follow-ups in SAME window (PROBLEMATIC)
- Shows: PID, window, number of follow-ups
- These require investigation - which survey to use?

**`data_quality_module3_patients_both_windows.csv`**
- Patients with follow-ups in BOTH 3-month and 1-year windows (EXPECTED)
- Shows: PID, n_different_windows
- This is the expected pattern - not a problem

**`data_quality_module3_outside_windows.csv`**
- Follow-ups outside expected timeframes
- Columns: PID, Completion_Date, Days_From_Baseline, Window
- Too early, between windows, or too late

**Note**: Patient-level completion and eligibility details are in the JSON file. CSV exports focus on identifying problematic cases (duplicates, outside windows) that require investigation.

---

## Technical Notes

### Baseline Date Determination

For each patient, baseline date is determined as:
- **First treatment date** (earliest episode date with blood product)
- This is the FIRST row for each patient with product administration
- All timing calculations are from this first treatment date
- NOT discharge date, NOT last treatment date

### Follow-up Date Determination

Follow-up timing is based on:
- **Completion date** (field X_435_0_751: "Date of completion")
- This is when the patient actually filled out the follow-up survey
- NOT the episode date (which may be missing or unreliable for follow-up forms)
- All 51 follow-up forms have completion dates

### Window Categorization

Each follow-up is categorized based on days from first treatment to completion date:
- **3-month**: 68-113 days from baseline (target: 90 days, expanded to include 112-113 day follow-ups)
- **1-year**: 273-455 days from baseline (target: 365 days, expanded to include 273-day follow-ups)
- **Too early**: <68 days
- **Between windows**: 114-272 days
- **Too late**: >455 days
- **Unknown**: No baseline date or completion date available

### Follow-up Record Identification

Follow-up records identified as:
- Records with **FormStatus_435 = "open"** (Follow-up form exists)
- Indicates structured follow-up survey form
- Contains questions about pregnancy, new diagnoses, outcomes
- All 51 follow-up forms contain substantial data (104-109 of 122 fields filled)
- **Important**: Patients may receive multiple blood products during extended hospital stays - those are treatment records (product type present), NOT follow-ups

### Duplicate Detection

Two types of duplicates distinguished:

**Same-Window Duplicates (PROBLEMATIC):**
- Same patient (PID)
- Same window — counted only within the two real protocol windows (3-month, 1-year)
- >1 follow-up in that window
- Labels such as "Unknown", "Too early", or "Between windows" are not windows and are never flagged as same-window duplicates
- Requires decision on which survey to use

**Both-Windows Completed (EXPECTED):**
- Same patient (PID)
- Follow-ups in BOTH 3-month AND 1-year windows
- This is the desired longitudinal pattern
- NOT a data quality issue

### Current Eligibility Calculation

Current eligibility is determined as of a **reference date derived from the data** (the maximum of all baseline dates and follow-up completion dates) — never a hardcoded export date. The derived date is reported in the results as `reference_date`:
- Calculate days_since_baseline = reference_date - first_treatment_date
- 3-month eligible: 68 ≤ days_since_baseline ≤ 113
- 1-year eligible: 273 ≤ days_since_baseline ≤ 455
- Used to calculate completion rates among currently eligible patients

---

## Contact

For questions about this analysis or to clarify follow-up survey documentation, please contact the study team.
