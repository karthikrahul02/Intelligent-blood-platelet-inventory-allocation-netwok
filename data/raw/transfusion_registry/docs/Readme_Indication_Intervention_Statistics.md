# Indication and Intervention Descriptive Statistics Module

**Author:** Elina Nuerenberg-Goloub — **Last revised:** 2026-08-18

## Overview

The `descriptive_indications.py` module provides comprehensive descriptive statistics for indications and interventions related to blood product administrations in the transfusion registry. It calculates statistics at **two levels**:

1. **Administration Level**: Statistics for all product administrations (n=1,113 records)
2. **Patient Level**: Statistics aggregated by patient (n=276 unique patients)

## Features

### Administration-Level Statistics

1. **Connection to Planned Intervention**
   - Number and percentage of administrations connected to planned interventional care
   - Number and percentage not connected
   - Missing data count

2. **Hemorrhage Risk (Blutungsrisiko)**
   - Low risk: <500 ml expected blood loss
   - High risk: ≥500 ml expected blood loss
   - Frequency and percentages
   - Missing data count

3. **Indications by Blood Product**
   - Detailed indication distribution for each product type:
     - Red blood cell concentrate (RBC)
     - Fresh Frozen Plasma (FFP)
     - Platelet concentrate (PC)
     - PPSB (Prothrombin Complex Concentrate)
     - Fibrinogen
     - Albumin
     - Iron i.v.
     - Antithrombin III (ATIII)
   - Two percentage calculations:
     - **% of all**: Percentage of all administrations of that product
     - **% of documented**: Percentage among administrations with documented indications

### Patient-Level Statistics

1. **Patients with Planned Interventions**
   - Number and percentage of patients with intervention-connected administrations
   - Number and percentage without intervention connection

2. **Patients by Hemorrhage Risk**
   - Number and percentage of patients with low risk procedures
   - Number and percentage with high risk procedures

## Usage

### Basic Usage

```python
from descriptive_indications import run_indication_intervention_analysis

# Run complete analysis
ind_interv = run_indication_intervention_analysis("your_data.csv", output_dir="results")
```

This will:
1. Load the data
2. Calculate all indication and intervention statistics (both levels)
3. Display summary tables
4. Export results to multiple files

### Advanced Usage

```python
from transfusion_data_loader import TransfusionDataLoader
from descriptive_indications import IndicationInterventionDescriptives

# Load data
loader = TransfusionDataLoader()
loader.load_data("your_data.csv")

# Create analysis object
ind_interv = IndicationInterventionDescriptives(loader)

# Calculate statistics
results = ind_interv.calculate_all()

# Access specific results
print(f"Intervention connection: {results['administration_level']['intervention_connection']['connected_yes']['percent']:.1f}%")
print(f"High hemorrhage risk: {results['administration_level']['hemorrhage_risk']['high_risk']['percent']:.1f}%")

# Get indications for specific product
ek_indications = results['administration_level']['indications_by_product']['Red blood cell concentrate (RBC)']
for indication, data in ek_indications['indications'].items():
    print(f"{indication}: {data['n']} ({data['percent_of_documented']:.1f}%)")

# Create and display tables
admin_table, patient_table = ind_interv.create_summary_tables()
print(admin_table)

# Export results
ind_interv.export_results(output_dir="results")
```

### Quick Start Script

Use the provided `run_indication_analysis.py` script (input CSV and output directory required):

```bash
python3 run_indication_analysis.py "../synthetic test data/test_data_150patients.csv" test_data_150patients
```

## Output Files

The module generates four output files:

### 1. indication_intervention_statistics_detailed.json
Machine-readable JSON with all calculated statistics. Contains:
- Complete administration-level results (intervention connection, hemorrhage risk, detailed indications)
- Complete patient-level results
- All numerical values with full precision

### 2. indication_intervention_statistics_administration_level.txt
Formatted table with administration-level statistics. Includes:
- Intervention connection statistics
- Hemorrhage risk distribution
- Detailed indications by product with percentages

### 3. indication_intervention_statistics_patient_level.txt
Formatted table with patient-level statistics. Includes:
- Patients with/without interventions
- Patients by hemorrhage risk category

### 4. indication_intervention_statistics_combined.txt
Combined file containing both administration-level and patient-level tables.

## Indication Coding by Product

### Erythrocyte Concentrate (EK)
1. Hb <7 g/dl (independent of compensation)
2. Hb 7-8 g/dl (anemic hypoxia signs or risk factors: tachycardia, hypotension, ECG ischemia, lactic acidosis, CHD, heart failure, cerebrovascular disease)
3. Hb 8-10 g/dl (individual assessment, unclear risk-benefit)
4. Massive transfusion
5. Other

### Fresh Frozen Plasma (FFP)
1. Dilutional coagulopathy
2. INR >1.5 with bleeding
3. INR >2.0 pre-intervention
4. Massive transfusion
5. Coagulation factor deficiency
6. Plasmapheresis
7. TTP/HUS
8. Liver failure
9. Other

### Platelet Concentrate (TK)
1. Plt <10,000/µl (prophylactic)
2. Plt <50,000/µl with bleeding/intervention
3. Plt <100,000/µl (CNS/ophthalmology surgery)
4. Thrombocytopenia
5. Thrombocytopathy
6. Platelet inhibition
7. Massive transfusion
8. Platelet function disorder
9. Other

### PPSB
1. Anticoagulant reversal
2. INR >1.5 with bleeding
3. INR >2.0 pre-intervention
4. Acquired coagulation factor deficiency
5. Congenital coagulation factor deficiency
6. Dilutional coagulopathy
7. Massive transfusion
8. Liver failure
9. Other

### Fibrinogen
1. Fibrinogen <1.5 g/l with bleeding
2. Fibrinogen <2.0 g/l pre-intervention
3. Massive transfusion
4. Acquired hypofibrinogenemia
5. Congenital hypofibrinogenemia
6. Dilutional coagulopathy
7. Liver failure
8. DIC
9. Other

### Albumin
1. Hypoalbuminemia with edema/ascites
2. Volume replacement
3. Other

### Iron i.v.
1. Failure of oral iron treatment
2. Continuous excessive blood loss
3. Malabsorption
4. Functional iron deficiency
5. Pregnancy with severe iron deficiency anemia
6. Other

### Antithrombin III (ATIII)
1. AT <70% with heparin resistance
2. AT <50% prophylactic
3. Congenital AT deficiency
4. Acquired AT deficiency
5. Other

## Missing Data Handling

Missing data is reported separately and not included in percentage calculations.

**Implementation notes:**
- Documented/missing counts are computed on the raw values BEFORE any string conversion, so truly missing entries are never counted as documented (a string conversion would turn NaN into the text 'nan')
- Equivalent code representations such as '1' and '1.0' are merged before counting, so the same indication is never split across two rows

## Dependencies

- pandas
- numpy
- transfusion_data_loader (local module)
- transfusion_registry_mapping (local module)

## Integration with Other Modules

This module complements:
- **Biometric Statistics** (`descriptive_biometrics.py`): Patient baseline characteristics
- **Treatment Statistics** (`descriptive_treatments.py`): Product types, dosages, lab values
- **Data Loader** (`transfusion_data_loader.py`): Data import and preprocessing

