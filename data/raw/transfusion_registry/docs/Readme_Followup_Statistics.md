# Follow-Up Descriptive Statistics Module

**Author:** Elina Nuerenberg-Goloub — **Last revised:** 2026-08-18

## Overview

The `descriptive_followup.py` module provides comprehensive descriptive statistics for follow-up data at **two timepoints** from the transfusion registry:
- **First follow-up (3-month)**: 68-113 days post-first-transfusion
- **Second follow-up (1-year)**: 273-455 days post-first-transfusion

These windows are locked to the manuscript Methods text and are the single source of truth for this module (they also match `data_quality_module3_followup_duplicates.py`).

It correctly accounts for timepoint-specific eligibility and calculates patient-level statistics including completion rates, patient-reported outcomes, adverse events, and baseline-follow-up comparisons **separately for each timepoint**.

**Key Features**:
- Classifies follow-ups by timing from first blood product
- Correctly calculates completion rates using only eligible patients for each timepoint
- Provides separate outcome analysis for 3-month and 1-year follow-ups
- Enables longitudinal comparison between timepoints
- Handles duplicate follow-ups: identical duplicates resolved, conflicting duplicates excluded

## Features

### 1. Follow-Up Classification by Timing

- **3-month follow-up**: 68-113 days from first blood product (±3 weeks from 90 days)
- **1-year follow-up**: 273-455 days from first blood product (±3 months from 365 days)
- Automatic classification of all follow-up records
- Separate tracking of unclassified follow-ups (outside timing windows)

### 1b. Duplicate Follow-Up Handling

When patients have multiple follow-up records within the same time window, records are compared on questionnaire **content only** — the completion date (`X_435_0_751`) is deliberately excluded from the comparison, so two records that differ only in completion date count as identical duplicates:

| Scenario | Action | Result |
|----------|--------|--------|
| **Identical duplicates** (same content) | Keep one record | Logged as "resolved duplicate" |
| **Conflicting duplicates** (different content) | Exclude ALL records | Exported to `conflicting_followup_duplicates.csv` |

**Conflicting duplicates** are records where the same patient has different values for follow-up variables (other than the completion date) within the same window. These cannot be reliably resolved programmatically and require manual review to determine which record is correct.

### 2. Follow-Up Completion Rates (Timepoint-Specific)

**For each timepoint:**
- **Eligibility criterion** (patient has entered the follow-up window):
  - 3-month: First blood product ≥68 days before data collection end
  - 1-year: First blood product ≥273 days before data collection end
- **Time anchor**: all windows are measured from the administration date (`X_433_7_11`); there is no fallback to episode or discharge dates, and patients without any administration date are reported as not time-classifiable
- Total patients vs. eligible patients for each timepoint
- Completion rate among eligible patients only
- Not-yet-eligible patients identified and excluded from denominator

### 3. Respondent Demographics (Per Timepoint)

**For each timepoint separately:**
- **Age**: Mean, SD, median, IQR, range
- **Gender**: Distribution by sex
- **Comparison**: Respondents vs. non-respondents demographics

### 4. Patient-Reported Outcomes (Per Timepoint)

**For each timepoint separately:**
- **Physical Capacity**: Self-reported activity level (`X_435_0_741`)
- **Clinical Frailty Scale (CFS)**: Patient-reported frailty (`X_435_0_742`, 1-9 scale)
- Distribution and summary statistics for each measure. Both scales are **ordinal** (the physical-capacity codes 1-5 index the categories 1, 3, 4, 10, and >10 MET and are not MET values; the CFS is a 1-9 grade scale): the distribution and median/IQR are the primary summaries, means of the category codes are labeled exploratory, and the baseline-vs-follow-up comparison reports a full transition matrix plus improved/unchanged/worsened counts
- **Refusal handling**: Code 0 ("cannot/will not answer") is not a scale value for either measure. Refusals are counted separately as "Refused to answer" and excluded from means, medians, and the scale distribution statistics

### 5. Adverse Events (Per Timepoint)

**For each timepoint separately:**
- **Blood Product Problems**: Frequency of reported problems related to transfusion
- Yes/No/Refused to answer distribution

### 6. Clinical Outcomes (Per Timepoint)

**For each timepoint separately:**
- **Anaemia Diagnosed**: Proportion of patients diagnosed with anaemia after transfusion
- **Past Year Transfusions** (`X_435_0_752`): Frequency of repeat transfusions. Codes: 0 = None, 1 = One, 2 = More than one, 3 = Cannot answer. Any unexpected codes are reported in an "Other/unexpected code" bucket rather than silently dropped, so the distribution always sums to the total

### 7. Baseline vs. Follow-Up Comparison (Per Timepoint)

**For each timepoint separately:**
- **Physical Capacity**: Changes from baseline to follow-up
- **Clinical Frailty Scale**: Changes in frailty status
- Number of patients improved, unchanged, or worsened
- Refusal answers (code 0) at follow-up are excluded from the paired change scores
- Enables comparison of recovery trajectories between 3-month and 1-year timepoints

## Usage

### Basic Usage

```python
from descriptive_followup import run_followup_analysis

# Run complete analysis
followup = run_followup_analysis("your_data.csv", output_dir="results")
```

This will:
1. Load the data
2. Determine timepoint-specific eligibility (3-month and 1-year)
3. Calculate all follow-up statistics
4. Display summary table
5. Export results to files

### Advanced Usage

```python
from transfusion_data_loader import TransfusionDataLoader
from descriptive_followup import FollowUpDescriptives
from datetime import datetime

# Load data
loader = TransfusionDataLoader()
loader.load_data("your_data.csv")

# Create analysis object with specific end date
followup = FollowUpDescriptives(loader, data_end_date=datetime(2025, 10, 13))

# Calculate statistics
results = followup.calculate_all()

# Access specific results
print(f"Completion rate: {results['completion']['completion_rate']['percent']:.1f}%")
print(f"Eligible patients: {results['completion']['eligible_patients']}")
print(f"Completed: {results['completion']['completed_followups']}")

# Get respondent demographics
resp_age = results['respondent_demographics']['respondents']['age']
print(f"Respondent mean age: {resp_age['mean']:.1f} years")

# Get patient-reported outcomes (ordinal scale: median/IQR are primary;
# the mean of the category codes is exploratory only)
if 'physical_capacity' in results['patient_reported_outcomes']:
    pc = results['patient_reported_outcomes']['physical_capacity']
    print(f"Physical capacity median: {pc['median']:.1f} "
          f"[IQR {pc['q25']:.1f}-{pc['q75']:.1f}]")
    print(f"  (exploratory code mean: {pc['mean']:.1f})")

# Get baseline vs follow-up comparison (primary: direction counts and
# transition matrix, never a mean of the MET category codes)
if 'physical_capacity' in results['baseline_followup_comparison']:
    comp = results['baseline_followup_comparison']['physical_capacity']
    print(f"Improved: {comp['change']['improved']} patients")
    print(f"Unchanged: {comp['change']['unchanged']} patients")
    print(f"Worsened: {comp['change']['worsened']} patients")
    print(f"Transitions: {comp['transition_matrix']}")

# Create and display table
table = followup.create_summary_table()
print(table)

# Export results
followup.export_results(output_dir="results")
```

### Quick Start Script

Use the provided `run_followup_analysis.py` script:

```bash
python3 run_followup_analysis.py <input_csv_path> <output_directory>
```

Example:

```bash
python3 run_followup_analysis.py "../synthetic test data/test_data_150patients.csv" test_data_150patients
```

## Eligibility Calculation

### Timepoint-Specific Eligibility Rules

Patients are eligible for each timepoint's analysis if sufficient time has passed:

**3-Month Follow-Up:**
- First blood product ≥68 days before data collection end date
- Example: If data ends Oct 13, 2025, eligible if first administration before Aug 6, 2025
- Follow-up window: 68-113 days from first blood product

**1-Year Follow-Up:**
- First blood product ≥273 days before data collection end date
- Example: If data ends Oct 13, 2025, eligible if first administration on or before Jan 13, 2025
- Follow-up window: 273-455 days from first blood product

If no explicit `data_end_date` is provided, the data collection end date is derived from the data itself (latest administration or follow-up completion date).

## Output Files

The module generates up to three output files:

### 1. followup_statistics_detailed.json
Machine-readable JSON with all calculated statistics. Contains:
- Completion statistics with eligibility details
- Respondent demographics (age, gender)
- Patient-reported outcomes
- Adverse events
- Clinical outcomes
- Baseline-follow-up comparisons
- Duplicate resolution summary

### 2. followup_statistics.txt
Formatted summary table with all statistics in publication-ready format.

### 3. conflicting_followup_duplicates.csv (if conflicts exist)
Export of patients with conflicting duplicate follow-ups for manual review. Contains:
- `PID`: Patient identifier
- `window`: Time window (3-month or 1-year)
- `record_number`: Which duplicate (1, 2, etc.)
- `followup_date`: Date of the follow-up record
- `days_from_first`: Days since first blood product
- `differing_columns`: List of columns with different values
- Actual values for each differing column

## Dependencies

- pandas
- numpy
- transfusion_data_loader (local module)
- datetime

## Integration with Other Modules

This module complements:
- **Biometric Statistics** (`descriptive_biometrics.py`): Baseline patient characteristics
- **Treatment Statistics** (`descriptive_treatments.py`): Transfusion details for followed patients
- **Indication Statistics** (`descriptive_indications.py`): Clinical indications for transfusions

