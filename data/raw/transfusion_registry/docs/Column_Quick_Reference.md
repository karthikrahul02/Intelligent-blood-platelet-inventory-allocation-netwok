# Quick Reference: Key Column Mappings

**Author:** Elina Nuerenberg-Goloub — **Last revised:** 2026-08-18

## Patient Demographics (Form 541 - Basic Data)

| Technical Column | Readable Name | Type | Unit |
|-----------------|---------------|------|------|
| X_541_0_1 | Year of birth | INTEGER | - |

## Patient Characteristics (Form 433 - Entry)

| Technical Column | Readable Name | Type | Unit | Codes |
|-----------------|---------------|------|------|-------|
| X_433_0_753 | Date of discharge | DATE | - | YYYY-MM-DD |
| X_433_0_2 | Height | INTEGER | cm | - |
| X_433_0_3 | Weight | INTEGER | kg | - |
| X_433_0_4 | Sex | enumerated | - | M=Male, F=Female, I=Intersexual |
| X_433_0_17 | Blood group patient | enumerated | - | A, B, AB, 0 |
| X_433_0_18 | Rhesus factor patient | enumerated | - | 1=Rh+, 2=Rh-, 0=Unknown |
| X_433_0_32 | Current physical capacity | enumerated | - | 1-5 MET scale |
| X_433_0_25 | General level of fitness (CFS) | enumerated | - | 1-9 Frailty scale |
| X_433_0_5 | Underlying condition | INTEGER | - | SNOMED CT code |
| X_433_0_6 | Secondary diagnosis | INTEGER | - | SNOMED CT code |

## Product Administration (Form 433 - Record 7)

| Technical Column | Readable Name | Type | Unit | Key Codes |
|-----------------|---------------|------|------|-----------|
| X_433_7_11 | Date of product administration | DATE | - | YYYY-MM-DD |
| X_433_7_746 | (Blood) Product type | enumerated | - | 1=RBC, 2=FFP, 3=PC, 4=PPSB, 5=Fibrinogen, 6=Iron i.v., 7=Albumin, 8=EPO, 9=ATIII, 10=Oral iron, 11=Machine autotransfusion |
| X_433_7_19 | Blood group of product | enumerated | - | A, B, AB, 0 |
| X_433_7_20 | Rhesus factor of product | enumerated | - | 1=Rh+, 2=Rh-, 0=Unknown |
| X_433_7_22 | Dosage (value) | FLOAT | - | Numeric value |
| X_433_7_734 | Dosage (units) | enumerated | - | 1=ml, 2=IU, 3=mg |
| X_433_7_613 | Product concentration | enumerated | - | 4%, 5%, 20%, 25% (albumin) |

## Transfusion Indications (Form 433 - Record 7)

| Technical Column | Readable Name | Product | Type |
|-----------------|---------------|---------|------|
| X_433_7_593 | Indication for transfusion | Red cell concentrate | enumerated |
| X_433_7_604 | Indication for transfusion | FFP | enumerated |
| X_433_7_605 | Indication for transfusion | Platelet concentrate | enumerated |
| X_433_7_606 | Indication for transfusion | PPSB | enumerated |
| X_433_7_607 | Indication for transfusion | Fibrinogen | enumerated |
| X_433_7_608 | Indication for transfusion | Iron i.v. | enumerated |
| X_433_7_610 | Indication for transfusion | Albumin | enumerated |
| X_433_7_612 | Indication for transfusion | ATIII | enumerated |
| X_433_7_594 | Other indication | All products | enumerated |
| X_433_7_595 | Individual indication | All products | STRING |

## Laboratory Values BEFORE Product Administration (Form 433 - Record 7)

| Technical Column | Readable Name | Type | Unit | Normal Range (Adult) |
|-----------------|---------------|------|------|----------------------|
| X_433_7_614 | Hb prior to product administration | FLOAT | g/dl | M: 13.5-17.5, F: 12-16 |
| X_433_7_37 | Platelets before product administration | INTEGER | /µl | 150,000-400,000 |
| X_433_7_374 | Quick's test before product administration | INTEGER | % | 70-120 |
| X_433_7_585 | Fibrinogen before product administration | FLOAT | mg/dl | 200-400 |
| X_433_7_603 | Serum albumin before product administration | FLOAT | g/dl | 3.5-5.0 |
| X_433_7_736 | Ferritin before product administration | FLOAT | µg/l | M: 20-250, F: 10-120 |
| X_433_7_589 | Transferrin saturation before product administration | FLOAT | % | 20-50 |
| X_433_7_597 | Erythropoietin (Plasma) before product administration | FLOAT | U/l | 4-26 |
| X_433_7_598 | Erythropoietin (Citrated Plasma) before product administration | FLOAT | mg/dl | - |
| X_433_7_601 | Antithrombin activity before product administration | FLOAT | % | 80-120 |

## Laboratory Values AFTER Product Administration (Form 433 - Record 7)

| Technical Column | Readable Name | Type | Unit |
|-----------------|---------------|------|------|
| X_433_7_615 | Hb after product administration | FLOAT | g/dl |
| X_433_7_587 | Platelets after product administration | INTEGER | /µl |
| X_433_7_596 | Quick's test after product administration | INTEGER | % |
| X_433_7_586 | Fibrinogen after product administration | FLOAT | mg/dl |
| X_433_7_591 | Serum albumin after product administration | FLOAT | g/dl |
| X_433_7_735 | Ferritin after product administration | FLOAT | µg/l |
| X_433_7_590 | Transferrin saturation after product administration | FLOAT | % |
| X_433_7_599 | Erythropoietin (Plasma) after product administration | FLOAT | U/l |
| X_433_7_600 | Erythropoietin (Citrated Plasma) after product administration | FLOAT | mg/dl |
| X_433_7_602 | Antithrombin activity after product administration | FLOAT | % |

## Autologous Blood Recovery (Form 433 - Record 7)

| Technical Column | Readable Name | Type | Unit |
|-----------------|---------------|------|------|
| X_433_7_747 | Volume of wound blood | FLOAT | ml |
| X_433_7_748 | Hematocrit percentage of wound blood | FLOAT | % |
| X_433_7_749 | Recovered RBC volume | FLOAT | ml |
| X_433_7_750 | Recovered hematocrit percentage | FLOAT | % |

## Intervention Details (Form 433)

| Technical Column | Readable Name | Type | Unit | Codes |
|-----------------|---------------|------|------|-------|
| X_433_0_7 | Connected to interventional care | enumerated | - | Y=Yes, N=No |
| X_433_0_8 | Date of interventional care | DATE | - | YYYY-MM-DD |
| X_433_0_9 | Type of intervention | INTEGER | - | SNOMED CT code |
| X_433_0_10 | Risk of haemorrhage | enumerated | - | 1=low (<500ml), 2=high (≥500ml) |

## Follow-up Key Variables (Form 435)

| Technical Column | Readable Name | Type | Codes |
|-----------------|---------------|------|-------|
| X_435_0_751 | Date of completion | DATE | YYYY-MM-DD |
| X_435_0_737 | Problems related to blood product | enumerated | 0=Cannot answer, 1=No, 2=Yes |
| X_435_0_616 | Which problems? | enumerated | Multiple options available |
| X_435_0_752 | Blood transfusions in past year | enumerated | 0=none, 1=one, 2=more than one, 99=Cannot answer |
| X_435_0_740 | Has anaemia been diagnosed? | enumerated | 0=Cannot answer, 1=Yes, 2=No |
| X_435_0_741 | Current physical capacity | enumerated | 1-6 scale (patient-reported) |
| X_435_0_742 | General fitness/frailty (CFS) | enumerated | 1-9 scale (patient-reported) |

## Follow-up: Disease Categories (Form 435)

Each category has a filter element (BOOLEAN) followed by specific diseases (BOOLEAN):

- **X_435_0_707**: Head (filter)
  - X_435_0_619 to X_435_0_634: Specific head/neurological diseases

- **X_435_0_708**: Lung (filter)
  - X_435_0_635 to X_435_0_644: Specific lung diseases

- **X_435_0_709**: Cardiovascular system (filter)
  - X_435_0_645 to X_435_0_651: Specific cardiovascular diseases

- **X_435_0_710**: Skin system (filter)
  - X_435_0_652 to X_435_0_656: Specific skin diseases

- **X_435_0_711**: Digestive system (filter)
  - X_435_0_657 to X_435_0_662: Specific digestive diseases

- **X_435_0_712**: Hormonal system (filter)
  - X_435_0_663 to X_435_0_668: Specific hormonal diseases

- **X_435_0_713**: Musculoskeletal system (filter)
  - X_435_0_669 to X_435_0_673: Specific musculoskeletal diseases

- **X_435_0_714**: Urinary system (filter)
  - X_435_0_674 to X_435_0_678: Specific urinary diseases

- **X_435_0_715**: Immune system (filter)
  - X_435_0_679 to X_435_0_682: Specific immune diseases

- **X_435_0_716**: Hematological system (filter)
  - X_435_0_684 to X_435_0_687: Specific blood diseases

- **X_435_0_717**: Lymphatic system (filter)
  - X_435_0_688 to X_435_0_692: Specific lymphatic diseases

- **X_435_0_718**: Mental disorders (filter)
  - X_435_0_693 to X_435_0_697: Specific mental disorders

- **X_435_0_719**: Infection (filter)
  - X_435_0_698 to X_435_0_706: Specific infections

## Common Analysis Patterns

### Hemoglobin Response Analysis
```python
hb_before = 'X_433_7_614'
hb_after = 'X_433_7_615'
df['hb_change'] = df[hb_after] - df[hb_before]
```

### Product Type Analysis
```python
product_col = 'X_433_7_746'
df_products = df.groupby(product_col).size()
```

### Transfusion Indication Analysis
```python
# For red cell concentrates
indication_col = 'X_433_7_593'
```

### Clinical Frailty Scale Analysis
```python
cfs_entry = 'X_433_0_25'  # At entry
cfs_followup = 'X_435_0_742'  # At follow-up (patient-reported)
```

### Adverse Events Analysis
```python
problems = 'X_435_0_737'
problem_types = 'X_435_0_616'
```

## Abbreviations

- **EK**: Erythrozyten-Konzentrat (Red blood cell concentrate)
- **FFP**: Fresh Frozen Plasma
- **TK**: Thrombozytenkonzentrat (Platelet concentrate)
- **PPSB**: Prothrombin Complex Concentrate
- **EPO**: Erythropoietin
- **ATIII**: Antithrombin III
- **CFS**: Clinical Frailty Scale
- **MET**: Metabolic Equivalent of Task
- **Hb**: Hemoglobin
- **RBC**: Red Blood Cells

## Python Usage Example

```python
from transfusion_registry_mapping import create_mapper
import pandas as pd

# Initialize mapper
mapper = create_mapper()

# Load data (skip the 7 metadata rows so row 8 becomes the header)
df = pd.read_csv("../synthetic test data/test_data_150patients.csv", sep=';', skiprows=7)

# Get readable name
print(mapper.get_readable_name('X_433_7_746'))
# Output: (Blood) Product type

# Decode value
print(mapper.decode_value('X_433_7_746', '1'))
# Output: Erythrozyten-Konzentrat

# Get all lab columns
lab_cols = mapper.get_lab_value_columns()
print("Before:", lab_cols['before'])
print("After:", lab_cols['after'])
```


**Unit contract — serum albumin:** the canonical analysis unit is **g/dl**
(decided 2026-08-20). The official data dictionary entry currently declares
mg/dl for these elements; a correction request to the registry data
management is pending. Values entered on the mg/dl scale (>= 100) are
converted to g/dl by the central lab normalization, with the conversion
counted in the analysis audit trail.
