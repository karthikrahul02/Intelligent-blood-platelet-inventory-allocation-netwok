# Temporal Volume Analysis

**Author:** Elina Nuerenberg-Goloub — **Last revised:** 2026-08-18

## Purpose

Calculates total volumes/amounts of blood products administered over time, broken down by:
- **Month** (YYYY-MM format)
- **Quarter** (YYYY-Q1, YYYY-Q2, YYYY-Q3, YYYY-Q4)

Essential for tracking blood product usage patterns, identifying seasonal trends, and resource planning.

## Input Requirements

The script requires:
- Raw data CSV file with date and dosage information
- Data dictionaries (automatically loaded)

## Usage

### Basic Usage

```bash
python3 run_temporal_volume_analysis.py <data_file> <output_directory>
```

### Example

```bash
python3 run_temporal_volume_analysis.py "../synthetic test data/test_data_150patients.csv" test_data_150patients
```

This command will:
1. Load data from `../synthetic test data/test_data_150patients.csv`
2. Apply data quality filters (same as treatment analysis)
3. Calculate monthly and quarterly volumes
4. Generate all output files in `test_data_150patients/`

## Output Files

The script generates 8 files:

### JSON Files (1)

#### 1. temporal_volumes_detailed.json
Complete structured data with monthly, quarterly, and overall totals:
- Date range analyzed
- Total records
- Monthly breakdown (all months)
- Quarterly breakdown (all quarters)
- Overall summary

### Text Reports (4)

#### 2. temporal_volumes_monthly.txt
Formatted report showing:
- Each month with total administrations and patients
- For each product-unit:
  - Total amount (ml, IU, or mg)
  - Number of administrations
  - Number of unique patients
  - Mean and median per administration
  - Min and max values

#### 3. temporal_volumes_quarterly.txt
Formatted report showing same structure as monthly but aggregated by quarter (Q1-Q4).

#### 4. temporal_volumes_overall.txt
Summary across all time periods:
- Total amount per product-unit
- Total administrations
- Unique patients

#### 5. temporal_volumes_combined.txt
All three text reports in one file:
- Overall summary (first)
- Quarterly breakdown
- Monthly breakdown

### CSV Files (3)

#### 6. temporal_volumes_monthly.csv
Machine-readable monthly data:

| Month | Product | Unit | Total Amount | N Administrations | N Patients | Mean per Admin | Median per Admin | Min | Max |
|-------|---------|------|--------------|-------------------|------------|----------------|------------------|-----|-----|
| 2024-09 | PPSB | IU | 32000.0 | 17 | 14 | 1882.4 | 1500.0 | 500.0 | 5500.0 |

#### 7. temporal_volumes_quarterly.csv
Machine-readable quarterly data (same columns as monthly, but with Quarter instead of Month).

#### 8. temporal_volumes_overall.csv
Machine-readable overall summary:

| Product | Unit | Total Amount | N Administrations | N Patients |
|---------|------|--------------|-------------------|------------|
| PPSB | IU | 307500.0 | 219 | 196 |

## Metrics Calculated

For each time period (month/quarter), the analysis calculates:

### Volume Metrics
- **Total amount**: Sum of all dosages in the period (ml, IU, or mg)
- **Mean per administration**: Average dose per administration
- **Median per administration**: Median dose (robust to outliers)
- **Min/Max**: Range of individual doses

### Count Metrics
- **N administrations**: Total number of product administrations
- **N patients**: Number of unique patients receiving the product

Per-period administration counts and unique patient counts are computed from **ALL administrations** in the period (any record with a documented product type and date) - not only from records with parseable dosage data. Volume metrics (totals, means, medians) necessarily use only records with valid dosages.

All product classes (codes 1-11) appear in the administration counts, including 8 = Erythropoetin (EPO), 9 = Antithrombin III (ATIII), 10 = Oral iron, and 11 = Machine Autotransfusion; products without dosage data are reported with their administration counts.

## Data Quality

### Filters Applied

The same data quality filters from the treatment analysis are applied:

**Excluded records**:
- PPSB ml: All records (clinically implausible)
- Fibrinogen IU: All records (non-standard unit)
- Fibrinogen mg <500: Specific records (implausibly low)

### Records Included

- **Administration and patient counts**: all records with a documented product type and a valid date
- **Volume calculations**: the subset of those records that also have valid dosage data (after the quality filters above)

Console output shows, for example:
```
Found x records with product and date information
Found y records with dosage information
DATA QUALITY: Excluded 4 PPSB ml records (implausible volumes)
DATA QUALITY: Excluded 1 Fibrinogen IU records (non-standard unit)
DATA QUALITY: Excluded 1 Fibrinogen mg records <500 mg (implausibly low)
After quality filters: z records
```

## Quarter Definitions

- **Q1**: January, February, March
- **Q2**: April, May, June
- **Q3**: July, August, September
- **Q4**: October, November, December

Quarters are calculated from the administration date, not enrollment date.

## Clinical Applications

### Resource Planning
- **Inventory management**: Track monthly usage to inform ordering
- **Budget forecasting**: Estimate costs based on historical volumes
- **Staffing**: Identify high-volume periods requiring additional support

### Trend Analysis
- **Seasonal patterns**: Identify if certain products used more in specific quarters
- **Growth trends**: Track increasing/decreasing usage over time
- **Protocol changes**: Assess impact of new guidelines on product usage

### Quality Monitoring
- **Usage consistency**: Monitor for unexpected spikes or drops
- **Practice patterns**: Compare usage across time periods
- **Appropriateness**: Identify periods with unusual dosing patterns

## Dependencies

Required Python packages:
- pandas
- numpy
- json (standard library)
- csv (standard library)
- pathlib (standard library)

## Integration with Other Analyses

This analysis complements:
- **Treatment analysis** (`descriptive_treatments.py`): Provides overall dosage statistics
- **Follow-up analysis** (`descriptive_followup.py`): Tracks patient outcomes
- **Biometric analysis** (`descriptive_biometrics.py`): Patient characteristics

Combined, these analyses provide comprehensive understanding of:
- Who receives products (biometrics)
- What products are given (treatment)
- When products are administered (temporal volumes)
- What happens to patients (follow-up)
