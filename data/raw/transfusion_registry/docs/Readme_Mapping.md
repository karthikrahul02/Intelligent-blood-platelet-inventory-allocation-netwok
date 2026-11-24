# Transfusion Registry Mapping Module

**Author:** Elina Nuerenberg-Goloub — **Last revised:** 2026-08-18

## Overview

The `transfusion_registry_mapping.py` module provides comprehensive mapping functionality for the transfusion registry data. It translates technical column names (like `X_433_7_746`) into human-readable names (like "(Blood) Product type") and decodes numeric codes to their descriptions.

## Files Required

- `20250227_Datenelemente-Transfusionsregister.csv` - Data elements dictionary
- `20250227_permitted-values-Transfusionsregister.csv` - Permitted values dictionary
- `test_data_150patients.csv` - Synthetic test dataset (for testing; located in the project root)

## Key Features

### 1. Column Name Mapping
Converts technical column names to readable names:
- `X_433_7_746` → "(Blood) Product type"
- `X_433_0_17` → "Blood group patient"
- `X_433_7_614` → "Hb prior to product administration"

### 2. Value Decoding
Translates coded values to descriptions:
- Blood products: `1` → "Erythrozyten-Konzentrat"
- Blood groups: `A`, `B`, `AB`, `0`
- Clinical frailty scale: `1-9` → Detailed descriptions

### 3. Metadata Access
Provides data type, unit, and validation information for each column

### 4. Data Organization
Groups columns by:
- Form (Basic data, Entry transfusion/blood products, Follow-up)
- Type (lab values before/after, demographics, etc.)

## Usage Examples

### Basic Usage

```python
from transfusion_registry_mapping import create_mapper

# Create mapper instance
mapper = create_mapper()

# Print summary of available mappings
mapper.print_summary()
```

### Get Human-Readable Column Names

```python
# Get readable name for a column
column = "X_433_7_746"
readable_name = mapper.get_readable_name(column)
print(f"{column} → {readable_name}")
# Output: X_433_7_746 → (Blood) Product type
```

### Decode Values

```python
# Decode a blood product code
column = "X_433_7_746"
value = "1"
decoded = mapper.decode_value(column, value)
print(f"Product code {value} = {decoded}")
# Output: Product code 1 = Erythrozyten-Konzentrat
```

### Get Column Metadata

```python
# Get complete metadata for a column
metadata = mapper.get_column_metadata("X_433_7_614")
print(f"Name: {metadata['designation']}")
print(f"Definition: {metadata['definition']}")
print(f"Data type: {metadata['data_type']}")
print(f"Unit: {metadata['unit']}")
```

### Work with DataFrames

```python
import pandas as pd

# Load data (skip the 7 metadata rows so row 8 becomes the header)
df = pd.read_csv("../synthetic test data/test_data_150patients.csv", sep=';', skiprows=7)

# Create DataFrame with readable column names
df_readable = mapper.create_readable_dataframe(df, decode_values=True)

# Now you can work with readable names
print(df_readable['(Blood) Product type'].value_counts())
```

### Get Specific Column Groups

```python
# Get all laboratory value columns
lab_cols = mapper.get_lab_value_columns()
print("Before administration:", lab_cols['before'])
print("After administration:", lab_cols['after'])

# Get columns by form
basic_cols = mapper.get_columns_by_form('Basic data')
entry_cols = mapper.get_columns_by_form('Entry transfusion / blood products')
followup_cols = mapper.get_columns_by_form('Follow-up')
```

### Get Reference Tables

```python
# Blood product types
products = mapper.get_blood_product_types()
for code, name in products.items():
    print(f"{code}: {name}")

# Blood groups
blood_groups = mapper.get_blood_groups()
for code, name in blood_groups.items():
    print(f"{code}: {name}")
```

## Data Structure

### Column Naming Convention

Technical columns follow the pattern: `X_{FormID}_{RecordID}_{ElementID}`

- **FormID**: Identifies the form (541=Basic data, 433=Entry transfusion, 435=Follow-up)
- **RecordID**: Usually 0 for non-repeatable, 7 for repeatable "Administered products" record
- **ElementID**: Unique identifier for the data element (from URN)

### Forms

The data is organized into three main forms:

1. **Form 541: Basic data** (2 columns)
   - Patient demographics (year of birth)

2. **Form 433: Entry transfusion / blood products** (58 columns)
   - Patient characteristics (height, weight, sex, blood group)
   - Clinical assessments (frailty scale, physical capacity)
   - Product administration details (date, type, dosage, indication)
   - Laboratory values (Hb, platelets, Quick, etc.) before and after
   - Intervention details

3. **Form 435: Follow-up** (124 columns)
   - Follow-up questionnaire responses
   - Problems related to transfusion
   - Disease diagnoses organized by body system
   - Patient-reported outcomes

### Data Types

- **INTEGER**: Whole numbers (age, SNOMED codes)
- **FLOAT**: Decimal numbers (lab values, dosages)
- **DATE**: Dates in YYYY-MM-DD format
- **STRING**: Free text
- **BOOLEAN**: true/false or yes/no
- **enumerated**: Coded values with predefined options

## Important Clinical Variables

### Blood Product Types (Element 746)
- 1: Red blood cell concentrate (RBC)
- 2: Fresh Frozen Plasma (FFP)
- 3: Platelet concentrate (PC)
- 4: PPSB
- 5: Fibrinogen
- 6: Iron i.v.
- 7: Albumin
- 8: EPO
- 9: Antithrombin III (ATIII)
- 10: Oral iron
- 11: Machine Autotransfusion (Cell Salvage)

### Laboratory Values

**Before Product Administration:**
- Hb (Element 614): Hemoglobin in g/dl
- Platelets (Element 37): in /µl
- Quick test (Element 374): in %
- Fibrinogen (Element 585): in mg/dl
- Serum albumin (Element 603): in g/dl
- Ferritin (Element 736): in µg/l
- Transferrin saturation (Element 589): in %
- Erythropoietin Plasma (Element 597): in U/l
- Antithrombin activity (Element 601): in %

**After Product Administration:**
- Corresponding "after" elements with same lab parameters

### Clinical Frailty Scale (CFS, Element 25)
1. Very Fit
2. Well
3. Managing Well
4. Vulnerable
5. Mildly frail
6. Moderately frail
7. Severely frail
8. Very severely frail
9. Terminally ill

### Indications for Transfusion

Different indication elements exist for each product type:
- Element 593: Red cell concentrate indications
- Element 604: FFP indications
- Element 605: Platelet concentrate indications
- Element 606: PPSB indications
- Element 607: Fibrinogen indications
- Element 610: Albumin indications
- Element 612: ATIII indications

## Best Practices

1. **Always use the mapper** when working with raw data files
2. **Decode values** for analysis and reporting to ensure human-readable results
3. **Check metadata** to understand data types and units before calculations
4. **Use column groups** to efficiently select related variables
5. **Document your code** with both technical and readable column names for reproducibility

## For Future Statistical Modules

When creating analysis modules:

1. Import and initialize the mapper at the beginning
2. Use `get_lab_value_columns()` to pair before/after measurements
3. Use `get_columns_by_form()` to organize analyses by data collection stage
4. Use `decode_value()` when creating tables or plots
5. Include metadata in your results (units, definitions)

## Example: Complete Analysis Workflow

```python
import pandas as pd
from transfusion_registry_mapping import create_mapper

# Initialize
mapper = create_mapper()

# Load data (skip the 7 metadata rows so row 8 becomes the header)
df = pd.read_csv("../synthetic test data/test_data_150patients.csv", sep=';', skiprows=7)

# Get lab value columns
lab_cols = mapper.get_lab_value_columns()

# Analyze Hemoglobin changes
hb_before_col = [c for c in lab_cols['before'] if 'Hb' in mapper.get_readable_name(c)][0]
hb_after_col = [c for c in lab_cols['after'] if 'Hb' in mapper.get_readable_name(c)][0]

# Calculate change
df['hb_change'] = pd.to_numeric(df[hb_after_col], errors='coerce') - \
                  pd.to_numeric(df[hb_before_col], errors='coerce')

# Group by product type with decoded names
product_col = "X_433_7_746"
df['product_name'] = df[product_col].apply(lambda x: mapper.decode_value(product_col, x))

# Analyze
summary = df.groupby('product_name')['hb_change'].describe()
print(summary)
```

