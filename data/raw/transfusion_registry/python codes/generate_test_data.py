"""
Synthetic Test Data Generator for Transfusion Registry

Generates patients with realistic data and deliberate data quality issues
to validate the robustness of analysis scripts.

All column assignments are cross-checked against the official dictionaries:
- 20250227_Datenelemente-Transfusionsregister.csv  (element URNs/designations)
- 20250227_permitted-values-Transfusionsregister.csv (value codes)
and against the production readers (descriptive_*.py, data_quality_module*.py).

Key eCRF mappings (form_record_element):
  X_433_7_746  (Blood) Product type: 1=RBC 2=FFP 3=PC 4=PPSB 5=Fibrinogen
               6=Eisen i.v. 7=Albumin 8=Erythropoetin 9=ATIII 10=Eisen oral
               11=Maschinelle Autotransfusion
  X_433_7_22   Dosage (value)   - generic, used for EVERY administration
  X_433_7_734  Dosage (units)   - 1=ml, 2=IE(IU), 3=mg
  X_433_7_593/604/605/606/607/608/610/612  Indication per product
               (RBC/FFP/PC/PPSB/Fibrinogen/Iron i.v./Albumin/ATIII)
  X_433_7_613  Product concentration (enumerated 4/5/20/25 %) - Albumin only
  X_433_7_747..750  MAT: wound blood volume / wound blood Hct % /
               recovered RBC volume / recovered Hct %
  X_433_0_17/18    Patient blood group (A/B/AB/0) / Rhesus (1=Rh+ 2=Rh- 0=unk)
  X_433_7_19/20    Product blood group (A/B/AB/0) / Rhesus (1=Rh+ 2=Rh- 0=unk)
  X_433_0_7/8/9/10 Connected to intervention (Y/N) / Date of interventional
               care (YYYY-MM-DD) / Type of intervention (SNOMED integer) /
               Risk of haemorrhage (1=low <500ml, 2=high >=500ml)
  X_435_0_751/741/742/737/740/752  Follow-up: completion date / physical
               capacity (0=refusal,1-5) / CFS (0=refusal,1-9) / problems
               (Y/N/U) / anaemia diagnosed (Y/N/U) / transfusions past year
               (0/1/2/3; 3=refusal)

Input:  header_template.csv, located in the "validation datasets"
        folder next to the code or in the parent folder (8-row export
        header structure: rows 1-7
        metadata + row 8 column headers; contains no patient data)
Output: generated CSV written to the parent folder of this script,
        plus seeded_errors_<n>.json (the validation oracle) next to it.
Both paths are resolved relative to this script's location.

Author: Elina Nuerenberg-Goloub with Claude Sonnet 4.5 by Anthropic
Date: 2025-10-15
Revised on 2026-01-25 by Elina Nuerenberg-Goloub and Claude Opus 4.5
Revised on 2026-08-13: removed hardcoded absolute paths (header template + output location)
Revised on 2026-08-13: remapped ALL data columns to the official dictionary
        (dosage -> 22/734, product codes -> registry scheme, follow-up ->
        741/742/737/740/752, intervention date/type -> 8/9, blood groups ->
        17/18/19/20); disjoint seeded-error pools; new seeded scenarios:
        refusal-0 follow-up answers, negative LOS, compatible-non-identical
        blood pairs, missing dosage; error oracle written to JSON.
"""

import pandas as pd

def _first_existing(base, candidates):
    """Return the first existing path among base-relative candidates.
    The published package groups the synthetic datasets and the validation
    datasets in their own folders next to the code; a flat project layout
    keeps them in the parent folder. Both are supported."""
    for rel in candidates:
        p = os.path.normpath(os.path.join(base, rel))
        if os.path.exists(p):
            return p
    return os.path.normpath(os.path.join(base, candidates[-1]))

import numpy as np
from datetime import datetime, timedelta
import random
import os
import json

# Set random seed for reproducibility
np.random.seed(42)
random.seed(42)

# ============================================================================
# CONFIGURATION
# ============================================================================

# Clinics
CLINICS = [
    "Universitätsklinikum Frankfurt",
    "Klinikum Darmstadt",
    "Verika (Teststandort)"  # Test location - should be filtered out
]
CLINIC_WEIGHTS = [0.50, 0.45, 0.05]  # 5% test location data

# Date range
START_DATE = datetime(2024, 9, 1)
END_DATE = datetime(2026, 1, 15)

# Product types (element 746 permitted values)
PRODUCT_TYPES = {
    1: "Red blood cell concentrate (RBC)",
    2: "Fresh Frozen Plasma (FFP)",
    3: "Platelet concentrate (PC)",
    4: "PPSB",
    5: "Fibrinogen",
    6: "Iron i.v.",
    7: "Albumin",
    8: "Erythropoetin",
    9: "Antithrombin III (ATIII)",
    10: "Oral iron",
    11: "Machine autotransfusion"
}

# Product distribution weights (same overall shape as before, remapped:
# ATIII 8->9, machine autotransfusion 9->11)
PRODUCT_WEIGHTS = {
    1: 0.28,   # RBC most common
    4: 0.21,   # PPSB
    7: 0.18,   # Albumin
    3: 0.11,   # Platelet concentrate
    11: 0.08,  # Machine autotransfusion
    5: 0.07,   # Fibrinogen
    9: 0.03,   # ATIII
    2: 0.02,   # FFP
    6: 0.02,   # Iron i.v.
}

# Dosage unit codes (element 734): 1=ml, 2=IE(IU), 3=mg
UNIT_ML = '1'
UNIT_IU = '2'
UNIT_MG = '3'

# Expected dosage unit per product (dictionary + data_quality_module2)
PRODUCT_UNIT = {
    1: UNIT_ML, 2: UNIT_ML, 3: UNIT_ML, 7: UNIT_ML, 11: UNIT_ML,
    4: UNIT_IU, 9: UNIT_IU, 8: UNIT_IU,
    5: UNIT_MG, 6: UNIT_MG, 10: UNIT_MG,
}

# Indication column (element id, form 433 record 7) per product code
INDICATION_ELEMENT = {
    1: '593',   # RBC        (codes 1-5)
    2: '604',   # FFP        (codes 1-9)
    3: '605',   # PC         (codes 1-8)
    4: '606',   # PPSB       (codes 1-9)
    5: '607',   # Fibrinogen (codes 1-9)
    6: '608',   # Iron i.v.  (codes 1-6)
    7: '610',   # Albumin    (codes 1-3)
    9: '612',   # ATIII      (codes 1-5)
}
INDICATION_CODES = {
    1: [1, 2, 3, 4, 5],
    2: list(range(1, 10)),
    3: list(range(1, 9)),
    4: list(range(1, 10)),
    5: list(range(1, 10)),
    6: list(range(1, 7)),
    7: [1, 2, 3],
    9: [1, 2, 3, 4, 5],
}
# RBC indication weights (element 593: Hb-threshold codes)
RBC_INDICATION_WEIGHTS = [0.70, 0.14, 0.13, 0.02, 0.01]

# Blood types (elements 17 / 19: literal codes A, B, AB, 0 - zero, not letter O)
BLOOD_TYPES = ['A', 'B', 'AB', '0']
BLOOD_TYPE_WEIGHTS = [0.41, 0.13, 0.04, 0.42]

# RBC donor->recipient ABO compatibility (product -> allowed patients)
RBC_COMPATIBLE = {
    '0': ['0', 'A', 'B', 'AB'],
    'A': ['A', 'AB'],
    'B': ['B', 'AB'],
    'AB': ['AB'],
}

# RH factor (elements 18 / 20: 1=Rh+, 2=Rh-, 0=Unknown)
RH_FACTORS = ['1', '2']
RH_WEIGHTS = [0.85, 0.15]

# Sex
SEX_CODES = ['M', 'F']
SEX_WEIGHTS = [0.71, 0.29]

# Baseline physical capacity (element 32: codes 1-5, no refusal code)
PHYSICAL_CAPACITY = [1, 2, 3, 4, 5]
PC_WEIGHTS = [0.07, 0.10, 0.40, 0.35, 0.08]

# Clinical Frailty Scale (element 25: codes 1-9)
CFS_VALUES = [1, 2, 3, 4, 5, 6, 7, 8, 9]
CFS_WEIGHTS = [0.05, 0.30, 0.35, 0.15, 0.08, 0.04, 0.02, 0.01, 0.00]

# Connection to intervention (element 7: Y/N)
INTERVENTION_CODES = ['Y', 'N']
INTERVENTION_WEIGHTS = [0.98, 0.02]

# Hemorrhage risk (element 10: 1=low <500ml, 2=high >=500ml)
HEMORRHAGE_RISK = ['2', '1']  # mostly high-risk interventions
HEMORRHAGE_WEIGHTS = [0.96, 0.04]

# Type of intervention (element 9: SNOMED CT procedure codes, INTEGER)
INTERVENTION_SNOMED = ['175905003', '48537004', '419132001', '53059001']

# Albumin product concentration (element 613: enumerated 4/5/20/25 %)
ALBUMIN_CONCENTRATIONS = ['5', '20']

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def random_date(start, end):
    """Generate random date between start and end."""
    delta = end - start
    random_days = random.randint(0, delta.days)
    return start + timedelta(days=random_days)

def generate_patient_demographics(pid, force_negative=False):
    """Generate demographic data for a patient."""
    sex = random.choices(SEX_CODES, weights=SEX_WEIGHTS)[0]

    # Age: mean ~64, SD ~11
    birth_year = int(2025 - np.random.normal(64, 11))
    birth_year = max(1930, min(2005, birth_year))  # Clamp to reasonable range

    # Height and weight based on sex
    if sex == 'M':
        height = int(np.random.normal(178, 8))
        weight = int(np.random.normal(85, 15))
    else:
        height = int(np.random.normal(165, 7))
        weight = int(np.random.normal(70, 14))

    # Clamp to reasonable ranges
    height = max(145, min(210, height))
    weight = max(40, min(150, weight))

    # Deliberate impossible values (seeded 'negative_values' scenario)
    if force_negative:
        if random.random() < 0.5:
            weight = -abs(weight)   # Negative weight (clearly impossible)
        else:
            height = 0              # Zero height

    return {
        'birth_year': birth_year,
        'sex': sex,
        'height': height,
        'weight': weight
    }

def generate_lab_values(product_type, with_errors=False, error_type=None):
    """Generate lab values before and after administration.

    Lab columns per dictionary:
      RBC: Hb 614/615 | PC: platelets 37/587 | PPSB: Quick 374/596
      Fibrinogen: 585/586 | Albumin: 603/591 | ATIII: antithrombin 601/602
      Iron: ferritin 736/735 + transferrin saturation 589/590
    """
    labs = {}

    if product_type == 1:  # RBC
        # Hemoglobin (g/dl)
        hb_before = round(np.random.normal(7.7, 0.9), 1)
        hb_after = round(hb_before + np.random.normal(1.1, 0.5), 1)

        # Introduce errors
        if with_errors:
            if error_type == 'hb_extreme_low':
                # below the physicians' range floor of 1.0 g/dl
                hb_before = round(np.random.uniform(0.2, 0.9), 1)
            elif error_type == 'hb_extreme_high':
                hb_before = round(np.random.uniform(22, 30), 1)
            elif error_type == 'hb_negative':
                hb_before = -7.5
            elif error_type == 'hb_zero':
                hb_before = 0

        labs['hb_before'] = hb_before
        labs['hb_after'] = hb_after

    elif product_type == 3:  # Platelet concentrate
        # Platelets - normally in thousands (e.g., 150 = 150,000/µl)
        plt_before = int(np.random.normal(160, 70))
        plt_after = int(plt_before + np.random.normal(30, 20))

        if with_errors:
            if error_type == 'plt_wrong_unit':
                # Entered as absolute number instead of thousands
                plt_before = plt_before * 1000
            elif error_type == 'plt_extreme_low':
                # 0.2-0.8 on the thousands scale -> 200-800 /ul after
                # correction, below the physicians' floor of 1,000 /ul
                plt_before = round(np.random.uniform(0.2, 0.8), 1)
            elif error_type == 'plt_extreme_high':
                # raw /ul entry above the physicians' ceiling of 1,000,000
                plt_before = int(np.random.uniform(1200000, 3000000))
            elif error_type == 'plt_negative':
                plt_before = -150

        labs['plt_before'] = plt_before
        labs['plt_after'] = plt_after

    elif product_type == 4:  # PPSB
        # Quick's test (%)
        quick_before = int(np.random.normal(70, 13))
        quick_after = int(quick_before + np.random.normal(15, 8))

        if with_errors:
            if error_type == 'quick_extreme_low':
                quick_before = int(np.random.uniform(510, 620))
            elif error_type == 'quick_extreme_high':
                quick_before = int(np.random.uniform(700, 900))
            # planted extremes must stay above the physicians' ceiling of
            # 500 % - no clamping on error rows
            labs['quick_before'] = quick_before
            labs['quick_after'] = max(0, min(200, quick_after))
        else:
            labs['quick_before'] = max(0, min(250, quick_before))
            labs['quick_after'] = max(0, min(200, quick_after))

    elif product_type == 5:  # Fibrinogen
        # Fibrinogen (mg/dl)
        fib_before = int(np.random.normal(195, 65))
        fib_after = int(fib_before + np.random.normal(100, 40))

        if with_errors:
            if error_type == 'fib_extreme_low':
                # just above the physicians' ceiling of 1,000 mg/dl
                fib_before = int(np.random.uniform(1100, 1400))
            elif error_type == 'fib_extreme_high':
                fib_before = int(np.random.uniform(1500, 3000))

        labs['fib_before'] = fib_before
        labs['fib_after'] = fib_after

    elif product_type == 7:  # Albumin
        # Serum albumin (g/dl)
        alb_before = round(np.random.normal(2.65, 0.5), 2)
        alb_after = round(alb_before + np.random.normal(0.3, 0.2), 2)

        if with_errors:
            if error_type == 'alb_wrong_unit':
                # Entered in mg/dl instead of g/dl
                alb_before = alb_before * 1000
            elif error_type == 'alb_extreme_low':
                # just above the physicians' ceiling of 7.0 g/dl
                alb_before = round(np.random.uniform(7.2, 7.9), 2)
            elif error_type == 'alb_extreme_high':
                alb_before = round(np.random.uniform(8, 15), 2)

        labs['alb_before'] = alb_before
        labs['alb_after'] = alb_after

    elif product_type == 9:  # ATIII (element 601/602: antithrombin activity %)
        at_before = int(np.random.normal(65, 15))
        at_after = int(at_before + np.random.normal(25, 10))

        labs['at_before'] = max(0, min(150, at_before))
        labs['at_after'] = max(0, min(150, at_after))

    elif product_type in (6, 10):  # Iron i.v. / oral iron
        # Ferritin (µg/l) - iron-deficient before, slightly higher after
        fer_before = int(np.random.uniform(5, 30))
        fer_after = int(fer_before + np.random.uniform(20, 150))
        # Transferrin saturation (%)
        tsat_before = int(np.random.uniform(5, 18))
        tsat_after = int(tsat_before + np.random.uniform(5, 20))

        labs['ferritin_before'] = fer_before
        labs['ferritin_after'] = fer_after
        labs['tsat_before'] = tsat_before
        labs['tsat_after'] = min(100, tsat_after)

    return labs

def generate_dosage(product_type, with_errors=False, error_type=None):
    """Generate dosage for a product.

    Returns dict with:
      'amount' -> X_433_7_22  (Dosage value)
      'unit'   -> X_433_7_734 (Dosage units: 1=ml, 2=IE, 3=mg)
    plus MAT-specific fields (747/748/749/750) for product 11 and
    'concentration' (X_433_7_613) for albumin.
    """
    dosages = {}

    if product_type == 1:  # RBC (ml)
        dose_ml = int(np.random.choice([250, 300, 500, 750, 1000], p=[0.2, 0.4, 0.25, 0.1, 0.05]))
        dosages['amount'] = dose_ml
        dosages['unit'] = UNIT_ML

    elif product_type == 2:  # FFP (ml)
        dose_ml = int(np.random.choice([200, 400, 600, 800], p=[0.3, 0.4, 0.2, 0.1]))
        dosages['amount'] = dose_ml
        dosages['unit'] = UNIT_ML

    elif product_type == 3:  # Platelet concentrate (ml)
        dose_ml = int(np.random.normal(300, 100))
        dose_ml = max(100, min(600, dose_ml))
        dosages['amount'] = dose_ml
        dosages['unit'] = UNIT_ML

    elif product_type == 4:  # PPSB (IU)
        dose_iu = int(np.random.normal(1500, 500))
        dose_iu = max(500, min(4000, dose_iu))

        if with_errors and error_type == 'ppsb_wrong_unit':
            # Entered in ml instead of IU (PPSB is reconstituted in 20-50ml):
            # wrong unit code 1 (ml) with an ml-sized amount
            dosages['amount'] = int(np.random.uniform(20, 50))
            dosages['unit'] = UNIT_ML
        else:
            dosages['amount'] = dose_iu
            dosages['unit'] = UNIT_IU

    elif product_type == 5:  # Fibrinogen (mg)
        dose_g = round(np.random.normal(2, 0.8), 1)
        dose_g = max(1, min(4, dose_g))
        dose_mg = int(dose_g * 1000)

        if with_errors and error_type == 'fib_wrong_unit':
            # Entered in IU instead of mg (fibrinogen doesn't use IU):
            # wrong unit code 2 (IE) with an IU-looking amount
            dosages['amount'] = int(np.random.uniform(100, 500))
            dosages['unit'] = UNIT_IU
        elif with_errors and error_type == 'fib_too_low':
            # Implausibly low dose (<500 mg), unit correct
            dosages['amount'] = int(np.random.uniform(50, 400))
            dosages['unit'] = UNIT_MG
        else:
            dosages['amount'] = dose_mg
            dosages['unit'] = UNIT_MG

    elif product_type == 6:  # Iron i.v. (mg)
        dose_mg = int(np.random.choice([100, 200, 500, 1000], p=[0.2, 0.3, 0.3, 0.2]))
        dosages['amount'] = dose_mg
        dosages['unit'] = UNIT_MG

    elif product_type == 7:  # Albumin (ml of 5%/20% solution)
        dose_ml = int(np.random.normal(100, 40))
        dose_ml = max(50, min(250, dose_ml))
        dosages['amount'] = dose_ml
        dosages['unit'] = UNIT_ML
        dosages['concentration'] = random.choice(ALBUMIN_CONCENTRATIONS)

    elif product_type == 9:  # ATIII (IU)
        dose_iu = int(np.random.normal(1000, 300))
        dose_iu = max(500, min(2000, dose_iu))
        dosages['amount'] = dose_iu
        dosages['unit'] = UNIT_IU

    elif product_type == 11:  # Machine autotransfusion
        recovered_ml = int(np.random.normal(400, 150))
        recovered_ml = max(100, min(1000, recovered_ml))
        wound_blood_ml = int(recovered_ml * np.random.uniform(1.5, 3))
        wound_blood_ml = max(200, min(2000, wound_blood_ml))
        # Element 747: volume of wound blood (ml)
        dosages['wound_blood_ml'] = wound_blood_ml
        # Element 748: hematocrit percentage of wound blood (%)
        dosages['wound_blood_hct'] = int(np.random.uniform(10, 30))
        # Element 749: recovered RBC volume (ml)
        dosages['recovered_ml'] = recovered_ml
        # Element 750: recovered hematocrit percentage (%)
        dosages['recovered_hct'] = int(np.random.uniform(50, 70))
        # Retransfused volume also documented as generic dosage in ml
        dosages['amount'] = recovered_ml
        dosages['unit'] = UNIT_ML

    return dosages

def generate_followup_data(pid, first_admin_date, error_config=None):
    """Generate follow-up data for a patient.

    Protocol windows (must match descriptive_followup / module 3):
      3-month: 68-113 days after first administration
      1-year:  273-455 days after first administration
    """
    followups = []

    # Calculate days from first admin to data end
    days_to_end = (END_DATE - first_admin_date).days

    # Determine if patient should have follow-ups
    has_3month = days_to_end >= 68 and random.random() < 0.15   # 15% completion rate
    has_1year = days_to_end >= 280 and random.random() < 0.12   # 12% completion rate

    # Check for deliberate error scenarios
    if error_config:
        if error_config.get('followup_too_early'):
            # Follow-up too early (< 68 days)
            fu_date = first_admin_date + timedelta(days=random.randint(30, 60))
            followups.append(generate_single_followup(pid, fu_date, '3month'))
            return followups

        if error_config.get('followup_between_windows'):
            # Follow-up between windows (114-272 days)
            fu_date = first_admin_date + timedelta(days=random.randint(120, 250))
            followups.append(generate_single_followup(pid, fu_date, '3month'))
            return followups

        if error_config.get('duplicate_identical'):
            # Two identical follow-ups in the SAME 3-month window (68-113d):
            # all outcome answers equal, only the completion date differs
            # (the date column is excluded from the duplicate comparison).
            fu_date = first_admin_date + timedelta(days=random.randint(70, 95))
            fu_data = generate_single_followup(pid, fu_date, '3month')
            followups.append(fu_data.copy())
            fu_data2 = fu_data.copy()
            fu_data2['followup_date'] = fu_date + timedelta(days=random.randint(5, 14))
            followups.append(fu_data2)
            return followups

        if error_config.get('duplicate_conflicting'):
            # Two conflicting follow-ups in same 3-month window (68-113d)
            fu_date1 = first_admin_date + timedelta(days=random.randint(70, 85))
            fu_date2 = first_admin_date + timedelta(days=random.randint(90, 105))
            fu1 = generate_single_followup(pid, fu_date1, '3month')
            fu2 = generate_single_followup(pid, fu_date2, '3month')
            # Make sure they have different outcome values
            fu2['physical_capacity'] = fu1['physical_capacity'] % 5 + 1
            fu2['cfs'] = (fu1['cfs'] + 1) if fu1['cfs'] < 9 else fu1['cfs'] - 1
            followups.append(fu1)
            followups.append(fu2)
            return followups

        if error_config.get('refusal_zero'):
            # Guaranteed in-window 3-month follow-up with refusal answers:
            # element 741 / 742 code 0 = "Kann / möchte ich nicht beantworten"
            fu_date = first_admin_date + timedelta(days=random.randint(70, 110))
            fu = generate_single_followup(pid, fu_date, '3month')
            fu['physical_capacity'] = 0
            fu['cfs'] = 0
            fu['transfusions'] = 3  # 752 code 3 = refusal
            followups.append(fu)
            return followups

    # Normal follow-up generation
    if has_3month:
        fu_offset = random.randint(70, min(110, max(70, days_to_end)))
        fu_date = first_admin_date + timedelta(days=fu_offset)
        followups.append(generate_single_followup(pid, fu_date, '3month'))

    if has_1year:
        fu_offset = random.randint(280, min(420, max(280, days_to_end)))
        fu_date = first_admin_date + timedelta(days=fu_offset)
        followups.append(generate_single_followup(pid, fu_date, '1year'))

    return followups

def generate_single_followup(pid, fu_date, timepoint):
    """Generate a single follow-up record (form 435 answer codes)."""
    # Physical capacity at follow-up (element 741: 1-5; 0=refusal seeded separately)
    pc = random.choices([1, 2, 3, 4, 5], weights=[0.06, 0.05, 0.35, 0.45, 0.09])[0]

    # CFS at follow-up (element 742: 1-9; 0=refusal seeded separately)
    cfs = random.choices(CFS_VALUES[:6], weights=[0.03, 0.50, 0.30, 0.12, 0.04, 0.01])[0]

    # Problems related to blood product (element 737: Y/N/U)
    problems = random.choices(['Y', 'N', 'U'], weights=[0.08, 0.85, 0.07])[0]

    # Which problems (element 616: 1-6, only if problems == Y)
    problems_detail = random.randint(1, 6) if problems == 'Y' else None

    # Anemia diagnosed (element 740: Y/N/U)
    anemia = random.choices(['Y', 'N', 'U'], weights=[0.30, 0.63, 0.07])[0]

    # Blood test in past year (element 739: Y/N/U)
    blood_test = random.choices(['Y', 'N', 'U'], weights=[0.60, 0.35, 0.05])[0]

    # Newly diagnosed disease (element 745: Y/N/U)
    new_disease = random.choices(['Y', 'N', 'U'], weights=[0.25, 0.70, 0.05])[0]

    # Blood transfusions in past year (element 752: 0=none,1=one,2=more,3=refusal)
    transfusions = random.choices([0, 1, 2, 3], weights=[0.45, 0.35, 0.15, 0.05])[0]

    return {
        'pid': pid,
        'followup_date': fu_date,
        'timepoint': timepoint,
        'physical_capacity': pc,
        'cfs': cfs,
        'problems': problems,
        'problems_detail': problems_detail,
        'anemia': anemia,
        'blood_test': blood_test,
        'new_disease': new_disease,
        'transfusions': transfusions
    }

# ============================================================================
# MAIN DATA GENERATION
# ============================================================================

def generate_test_dataset(n_patients=100, output_file='test_data_100patients.csv'):
    """Generate complete test dataset with deliberate errors."""

    # Re-seed so each generated dataset is independently reproducible
    np.random.seed(42)
    random.seed(42)

    print("=" * 70)
    print("SYNTHETIC TEST DATA GENERATOR")
    print("=" * 70)
    print(f"\nGenerating {n_patients} patients with deliberate data quality issues...")

    # Read header rows from the header-only template (rows 1-7 metadata + row 8 column headers)
    _base = os.path.dirname(os.path.abspath(__file__))
    source_file = _first_existing(_base, [
        '../validation datasets/header_template.csv',
        '../LOS analysis validation datasets/header_template.csv',
        '../header_template.csv'])
    print(f"\nReading header structure from: {source_file}")

    with open(source_file, 'r', encoding='utf-8') as f:
        header_lines = [f.readline() for _ in range(8)]

    # Parse column names from row 8
    columns = header_lines[7].strip().split(';')
    columns = [c.strip('"') for c in columns]
    print(f"Found {len(columns)} columns")

    # Initialize data list
    all_rows = []

    # Track error assignments for reporting (this is the validation oracle)
    error_assignments = {
        'test_location': [],
        'ppsb_wrong_unit': [],
        'fib_wrong_unit': [],
        'fib_too_low': [],
        'missing_dosage': [],
        'plt_wrong_unit': [],
        'alb_wrong_unit': [],
        'hb_extreme': [],
        'quick_extreme': [],
        'fib_lab_extreme': [],
        'alb_lab_extreme': [],
        'plt_lab_extreme': [],
        'negative_values': [],
        'followup_too_early': [],
        'followup_between': [],
        'duplicate_identical': [],
        'duplicate_conflicting': [],
        'followup_refusal_zero': [],
        'blood_type_incompatible': [],
        'blood_type_compatible_nonidentical': [],
        'negative_los': [],
        'missing_values': []
    }

    # ------------------------------------------------------------------
    # Assign seeded errors to DISJOINT patient pools so the JSON oracle
    # counts are exact (no patient carries two competing seeded errors).
    # ------------------------------------------------------------------
    pool = list(range(1000, 1000 + n_patients))
    random.shuffle(pool)

    def take(n):
        return [pool.pop() for _ in range(n)]

    test_location_pids = take(5)          # Verika test location
    ppsb_error_pids = take(4)             # PPSB dosed with unit code 1 (ml)
    fib_unit_error_pids = take(3)         # Fibrinogen dosed with unit code 2 (IE)
    fib_low_error_pids = take(3)          # Fibrinogen < 500 mg
    missing_dosage_pids = take(2)         # Administration without dosage value/unit
    plt_unit_error_pids = take(5)         # Platelet lab value x1000 (>= 1000)
    alb_unit_error_pids = take(5)         # Albumin lab value in mg/dl (>= 100)
    hb_extreme_pids = take(4)             # Extreme Hb values
    quick_extreme_pids = take(3)          # Extreme Quick's test
    fib_lab_extreme_pids = take(3)        # Extreme fibrinogen lab
    alb_lab_extreme_pids = take(3)        # Extreme albumin lab
    plt_lab_extreme_pids = take(3)        # Extreme platelet lab
    negative_value_pids = take(3)         # Negative/zero anthropometrics + negative Hb
    followup_early_pids = take(3)         # Follow-up < 68 days
    followup_between_pids = take(2)       # Follow-up 114-272 days
    duplicate_identical_pids = take(3)    # Identical duplicates (dates differ)
    duplicate_conflicting_pids = take(5)  # Conflicting duplicates
    refusal_zero_pids = take(3)           # Follow-up refusal code 0 in 741/742
    blood_incompatible_pids = take(3)     # ABO-INCOMPATIBLE RBC transfusion
    blood_compatible_pids = take(2)       # Compatible but non-identical (no flag!)
    negative_los_pids = take(3)           # Intervention date AFTER discharge

    # Patients whose seeded error requires at least one administration
    needs_admin = set(
        ppsb_error_pids + fib_unit_error_pids + fib_low_error_pids +
        missing_dosage_pids + plt_unit_error_pids + alb_unit_error_pids +
        hb_extreme_pids + quick_extreme_pids + fib_lab_extreme_pids +
        alb_lab_extreme_pids + plt_lab_extreme_pids + negative_value_pids +
        followup_early_pids + followup_between_pids +
        duplicate_identical_pids + duplicate_conflicting_pids +
        refusal_zero_pids + blood_incompatible_pids + blood_compatible_pids +
        negative_los_pids
    )

    # First-administration product forced per scenario
    forced_product = {}
    for p in ppsb_error_pids + quick_extreme_pids:
        forced_product[p] = 4   # PPSB
    for p in fib_unit_error_pids + fib_low_error_pids + fib_lab_extreme_pids:
        forced_product[p] = 5   # Fibrinogen
    for p in plt_unit_error_pids + plt_lab_extreme_pids:
        forced_product[p] = 3   # Platelet concentrate
    for p in alb_unit_error_pids + alb_lab_extreme_pids:
        forced_product[p] = 7   # Albumin
    for p in (hb_extreme_pids + negative_value_pids + missing_dosage_pids +
              blood_incompatible_pids + blood_compatible_pids):
        forced_product[p] = 1   # RBC

    missing_value_pids = set()

    # Generate patients
    for i in range(n_patients):
        pid = 1000 + i
        patient_repeat = i + 1

        # Determine clinic
        if pid in test_location_pids:
            clinic = "Verika (Teststandort)"
            error_assignments['test_location'].append(pid)
        else:
            clinic = random.choices(CLINICS[:2], weights=[0.55, 0.45])[0]

        # Generate demographics
        demo = generate_patient_demographics(pid, force_negative=(pid in negative_value_pids))
        if pid in negative_value_pids:
            error_assignments['negative_values'].append(pid)

        # Generate episode date (start of episode)
        episode_date = random_date(START_DATE, END_DATE - timedelta(days=30))

        # Determine number of administrations for this patient (1-8, weighted)
        n_admins = random.choices([1, 2, 3, 4, 5, 6, 7, 8],
                                   weights=[0.25, 0.25, 0.20, 0.12, 0.08, 0.05, 0.03, 0.02])[0]

        # Some patients have no products (non-transfusion patients) - about 15%
        # (never for patients carrying an administration-dependent seeded error)
        if pid not in needs_admin and random.random() < 0.15:
            n_admins = 0

        # Patient blood group / rhesus (elements 17 / 18)
        patient_blood_type = random.choices(BLOOD_TYPES, weights=BLOOD_TYPE_WEIGHTS)[0]
        patient_rh = random.choices(RH_FACTORS, weights=RH_WEIGHTS)[0]
        if random.random() < 0.03:
            patient_rh = '0'  # Unknown

        # Seeded blood-type scenarios override the patient/product ABO pair
        product_blood_type_forced = None
        if pid in blood_incompatible_pids:
            # Genuinely INCOMPATIBLE per RBC donor->recipient rules
            patient_blood_type, product_blood_type_forced = random.choice([
                ('0', 'A'), ('0', 'B'), ('A', 'B'), ('B', 'A'), ('A', 'AB'),
            ])
        elif pid in blood_compatible_pids:
            # Compatible but NON-IDENTICAL - a correct check must NOT flag these
            patient_blood_type, product_blood_type_forced = random.choice([
                ('A', '0'), ('AB', 'A'), ('B', '0'), ('AB', 'B'),
            ])

        # Generate baseline clinical data
        physical_capacity = random.choices(PHYSICAL_CAPACITY, weights=PC_WEIGHTS)[0]
        cfs = random.choices(CFS_VALUES[:6], weights=[w/sum(CFS_WEIGHTS[:6]) for w in CFS_WEIGHTS[:6]])[0]

        # Primary diagnosis (element 5) and secondary diagnosis (element 6):
        # SNOMED CT codes (INTEGER)
        primary_dx = random.choice(['53741008', '60573004', '726018006', '11851006', '414545008'])
        secondary_dx = random.choice(['38341003', '44054006', '714153000', ''])

        # Interventional care (elements 7/8/9/10)
        intervention = random.choices(INTERVENTION_CODES, weights=INTERVENTION_WEIGHTS)[0]
        if pid in negative_los_pids:
            intervention = 'Y'  # needs an intervention date
        hemorrhage_risk = random.choices(HEMORRHAGE_RISK, weights=HEMORRHAGE_WEIGHTS)[0]
        intervention_snomed = random.choice(INTERVENTION_SNOMED)

        # Intervention date shortly after episode start; discharge afterwards,
        # so LOS = discharge - intervention is positive for normal patients
        intervention_date = episode_date + timedelta(days=random.randint(0, 3))
        discharge_date = intervention_date + timedelta(days=random.randint(5, 30))
        if pid in negative_los_pids:
            # Deliberate error: intervention documented AFTER discharge
            intervention_date = discharge_date + timedelta(days=random.randint(3, 20))
            error_assignments['negative_los'].append(pid)

        # ------------------------------------------------------------------
        # Shared record-0 (baseline) fields written on every row of a patient
        # ------------------------------------------------------------------
        def apply_baseline(row):
            row['PID'] = str(pid)
            row['patient repeat number'] = str(patient_repeat)
            row['Episode number'] = '1'
            row['Location'] = clinic
            row['Episode date'] = episode_date.strftime('%d/%m/%Y')
            row['FormStatus_541'] = 'open'
            row['X_541_0_1'] = str(demo['birth_year'])
            row['FormStatus_433'] = 'open'
            row['X_433_0_753'] = discharge_date.strftime('%Y-%m-%d')  # Date of discharge
            row['X_433_0_2'] = str(demo['height'])
            row['X_433_0_3'] = str(demo['weight'])
            row['X_433_0_4'] = demo['sex']
            row['X_433_0_5'] = primary_dx
            row['X_433_0_6'] = secondary_dx
            row['X_433_0_32'] = str(physical_capacity)
            row['X_433_0_25'] = str(cfs)
            row['X_433_0_17'] = patient_blood_type      # Blood group patient
            row['X_433_0_18'] = patient_rh              # Rhesus factor patient
            row['X_433_0_7'] = intervention             # Connected to interventional care
            if intervention == 'Y':
                row['X_433_0_8'] = intervention_date.strftime('%Y-%m-%d')  # DATE of interventional care
                row['X_433_0_9'] = intervention_snomed  # TYPE of intervention (SNOMED)
                row['X_433_0_10'] = hemorrhage_risk     # Risk of haemorrhage
            return row

        # If no administrations, create single row for patient
        if n_admins == 0:
            row = apply_baseline(create_empty_row(columns))
            all_rows.append(row)
            continue

        # Generate administrations
        admin_dates = sorted([episode_date + timedelta(days=random.randint(0, 14))
                             for _ in range(n_admins)])

        for admin_idx, admin_date in enumerate(admin_dates):
            # Select product type - forced product for error patients on first admin
            if admin_idx == 0 and pid in forced_product:
                product_type = forced_product[pid]
            else:
                product_type = random.choices(list(PRODUCT_WEIGHTS.keys()),
                                              weights=list(PRODUCT_WEIGHTS.values()))[0]

            # Determine if this administration has errors
            dosage_error = None
            lab_error = None
            missing_dosage = False

            if admin_idx == 0:
                if pid in ppsb_error_pids:
                    dosage_error = 'ppsb_wrong_unit'
                    error_assignments['ppsb_wrong_unit'].append(pid)
                elif pid in fib_unit_error_pids:
                    dosage_error = 'fib_wrong_unit'
                    error_assignments['fib_wrong_unit'].append(pid)
                elif pid in fib_low_error_pids:
                    dosage_error = 'fib_too_low'
                    error_assignments['fib_too_low'].append(pid)
                elif pid in missing_dosage_pids:
                    missing_dosage = True
                    error_assignments['missing_dosage'].append(pid)

                if pid in plt_unit_error_pids:
                    lab_error = 'plt_wrong_unit'
                    error_assignments['plt_wrong_unit'].append(pid)
                elif pid in alb_unit_error_pids:
                    lab_error = 'alb_wrong_unit'
                    error_assignments['alb_wrong_unit'].append(pid)
                elif pid in hb_extreme_pids:
                    lab_error = random.choice(['hb_extreme_low', 'hb_extreme_high'])
                    error_assignments['hb_extreme'].append(pid)
                elif pid in quick_extreme_pids:
                    lab_error = random.choice(['quick_extreme_low', 'quick_extreme_high'])
                    error_assignments['quick_extreme'].append(pid)
                elif pid in fib_lab_extreme_pids:
                    lab_error = random.choice(['fib_extreme_low', 'fib_extreme_high'])
                    error_assignments['fib_lab_extreme'].append(pid)
                elif pid in alb_lab_extreme_pids:
                    lab_error = random.choice(['alb_extreme_low', 'alb_extreme_high'])
                    error_assignments['alb_lab_extreme'].append(pid)
                elif pid in plt_lab_extreme_pids:
                    lab_error = random.choice(['plt_extreme_low', 'plt_extreme_high'])
                    error_assignments['plt_lab_extreme'].append(pid)
                elif pid in negative_value_pids:
                    lab_error = 'hb_negative'  # negative lab value on RBC admin

                if pid in blood_incompatible_pids:
                    error_assignments['blood_type_incompatible'].append(pid)
                elif pid in blood_compatible_pids:
                    error_assignments['blood_type_compatible_nonidentical'].append(pid)

            # Generate dosage
            dosage = generate_dosage(product_type, with_errors=(dosage_error is not None),
                                    error_type=dosage_error)

            # Generate lab values
            labs = generate_lab_values(product_type, with_errors=(lab_error is not None),
                                       error_type=lab_error)

            # Create row with shared baseline fields
            row = apply_baseline(create_empty_row(columns))

            # Product administration (Form 433, Record 7)
            row['X_433_7_11'] = admin_date.strftime('%Y-%m-%d')
            row['X_433_7_746'] = str(product_type)

            # Generic dosage pair (elements 22 + 734) for EVERY administration
            if not missing_dosage:
                if 'amount' in dosage:
                    row['X_433_7_22'] = str(dosage['amount'])
                    row['X_433_7_734'] = dosage['unit']

            # Indication for transfusion / product administration (per product)
            if product_type in INDICATION_ELEMENT:
                ind_col = f"X_433_7_{INDICATION_ELEMENT[product_type]}"
                if product_type == 1:
                    ind_code = random.choices(INDICATION_CODES[1], weights=RBC_INDICATION_WEIGHTS)[0]
                else:
                    ind_code = random.choice(INDICATION_CODES[product_type])
                row[ind_col] = str(ind_code)

            # Product-specific columns
            if product_type == 1:  # RBC
                row['X_433_7_614'] = str(labs.get('hb_before', ''))
                row['X_433_7_615'] = str(labs.get('hb_after', ''))

            elif product_type == 3:  # Platelet concentrate
                row['X_433_7_37'] = str(labs.get('plt_before', ''))
                row['X_433_7_587'] = str(labs.get('plt_after', ''))

            elif product_type == 4:  # PPSB
                row['X_433_7_374'] = str(labs.get('quick_before', ''))
                row['X_433_7_596'] = str(labs.get('quick_after', ''))

            elif product_type == 5:  # Fibrinogen
                row['X_433_7_585'] = str(labs.get('fib_before', ''))
                row['X_433_7_586'] = str(labs.get('fib_after', ''))

            elif product_type == 7:  # Albumin
                row['X_433_7_603'] = str(labs.get('alb_before', ''))
                row['X_433_7_591'] = str(labs.get('alb_after', ''))
                row['X_433_7_613'] = dosage.get('concentration', '')  # Product concentration (%)

            elif product_type == 9:  # ATIII - antithrombin ACTIVITY (601/602)
                row['X_433_7_601'] = str(labs.get('at_before', ''))
                row['X_433_7_602'] = str(labs.get('at_after', ''))

            elif product_type in (6, 10):  # Iron: ferritin + transferrin saturation
                row['X_433_7_736'] = str(labs.get('ferritin_before', ''))
                row['X_433_7_735'] = str(labs.get('ferritin_after', ''))
                row['X_433_7_589'] = str(labs.get('tsat_before', ''))
                row['X_433_7_590'] = str(labs.get('tsat_after', ''))

            elif product_type == 11:  # Machine autotransfusion (747-750)
                row['X_433_7_747'] = str(dosage.get('wound_blood_ml', ''))
                row['X_433_7_748'] = str(dosage.get('wound_blood_hct', ''))
                row['X_433_7_749'] = str(dosage.get('recovered_ml', ''))
                row['X_433_7_750'] = str(dosage.get('recovered_hct', ''))

            # Product blood group / rhesus (elements 19 / 20) for RBC/FFP/PC
            if product_type in (1, 2, 3):
                if admin_idx == 0 and product_blood_type_forced is not None:
                    row['X_433_7_19'] = product_blood_type_forced
                    row['X_433_7_20'] = patient_rh if patient_rh in ('1', '2') else '1'
                elif random.random() < 0.35:
                    # Routinely documented identical (compatible) product
                    row['X_433_7_19'] = patient_blood_type
                    row['X_433_7_20'] = patient_rh

            # Add some missing values randomly (5-15% per field)
            if random.random() < 0.10:
                row['X_433_0_5'] = ''  # Missing primary diagnosis
                missing_value_pids.add(pid)
            if random.random() < 0.08:
                row['X_433_0_32'] = ''  # Missing physical capacity

            all_rows.append(row)

        # Generate follow-up data
        first_admin = admin_dates[0] if admin_dates else episode_date

        # Check for follow-up errors
        fu_error_config = None
        if pid in followup_early_pids:
            fu_error_config = {'followup_too_early': True}
            error_assignments['followup_too_early'].append(pid)
        elif pid in followup_between_pids:
            fu_error_config = {'followup_between_windows': True}
            error_assignments['followup_between'].append(pid)
        elif pid in duplicate_identical_pids:
            fu_error_config = {'duplicate_identical': True}
            error_assignments['duplicate_identical'].append(pid)
        elif pid in duplicate_conflicting_pids:
            fu_error_config = {'duplicate_conflicting': True}
            error_assignments['duplicate_conflicting'].append(pid)
        elif pid in refusal_zero_pids:
            fu_error_config = {'refusal_zero': True}
            error_assignments['followup_refusal_zero'].append(pid)

        followups = generate_followup_data(pid, first_admin, error_config=fu_error_config)

        # Add follow-up rows (Form 435)
        for fu in followups:
            row = apply_baseline(create_empty_row(columns))
            row['FormStatus_435'] = 'open'
            row['X_435_0_751'] = fu['followup_date'].strftime('%Y-%m-%d')  # Date of completion
            row['X_435_0_741'] = str(fu['physical_capacity'])  # Physical capacity (0=refusal)
            row['X_435_0_742'] = str(fu['cfs'])                # CFS (0=refusal)
            row['X_435_0_737'] = fu['problems']                # Problems related to product
            if fu['problems_detail'] is not None:
                row['X_435_0_616'] = str(fu['problems_detail'])  # Which problems
            row['X_435_0_740'] = fu['anemia']                  # Anaemia diagnosed
            row['X_435_0_739'] = fu['blood_test']              # Blood test past year
            row['X_435_0_745'] = fu['new_disease']             # Newly diagnosed disease
            row['X_435_0_752'] = str(fu['transfusions'])       # Transfusions past year

            all_rows.append(row)

    error_assignments['missing_values'] = sorted(missing_value_pids)

    # Convert to DataFrame
    df = pd.DataFrame(all_rows)

    # Ensure column order matches original
    df = df[columns]

    # Write output file
    output_dir = _first_existing(os.path.dirname(os.path.abspath(__file__)),
                                 ['../synthetic test data', '..'])
    output_path = os.path.join(output_dir, output_file)

    # Write header rows first
    with open(output_path, 'w', encoding='utf-8') as f:
        for line in header_lines[:7]:
            f.write(line)

    # Append data (including header row)
    df.to_csv(output_path, mode='a', index=False, sep=';', quoting=1)

    # Write the seeded-error oracle to JSON next to the dataset
    oracle_path = os.path.join(output_dir, f'seeded_errors_{n_patients}.json')
    oracle = {
        'n_patients': n_patients,
        'output_file': output_file,
        'counts': {k: len(v) for k, v in error_assignments.items()},
        'errors': {k: sorted(v) for k, v in error_assignments.items()},
    }
    with open(oracle_path, 'w', encoding='utf-8') as f:
        json.dump(oracle, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 70}")
    print("DATA GENERATION COMPLETE")
    print(f"{'=' * 70}")
    print(f"\nOutput file: {output_path}")
    print(f"Seeded-error oracle: {oracle_path}")
    print(f"Total rows: {len(df)}")
    print(f"Total patients: {n_patients}")

    # Report on errors introduced
    print(f"\n{'=' * 70}")
    print("DELIBERATE DATA QUALITY ISSUES INTRODUCED")
    print(f"{'=' * 70}")

    print(f"\n1. TEST LOCATION (should be filtered out):")
    print(f"   {len(error_assignments['test_location'])} patients: PIDs {error_assignments['test_location']}")

    print(f"\n2. DOSAGE ERRORS (elements 22/734):")
    print(f"   PPSB with unit code 1=ml (not IU): {len(set(error_assignments['ppsb_wrong_unit']))} patients")
    print(f"   Fibrinogen with unit code 2=IE (not mg): {len(set(error_assignments['fib_wrong_unit']))} patients")
    print(f"   Fibrinogen <500mg: {len(set(error_assignments['fib_too_low']))} patients")
    print(f"   Missing dosage value+unit: {len(set(error_assignments['missing_dosage']))} patients")

    print(f"\n3. LAB VALUE ERRORS:")
    print(f"   Platelets wrong unit (x1000): {len(set(error_assignments['plt_wrong_unit']))} patients")
    print(f"   Albumin wrong unit (mg/dl): {len(set(error_assignments['alb_wrong_unit']))} patients")
    print(f"   Hemoglobin extreme values: {len(set(error_assignments['hb_extreme']))} patients")
    print(f"   Quick's test extreme: {len(set(error_assignments['quick_extreme']))} patients")
    print(f"   Fibrinogen lab extreme: {len(set(error_assignments['fib_lab_extreme']))} patients")
    print(f"   Albumin lab extreme: {len(set(error_assignments['alb_lab_extreme']))} patients")
    print(f"   Platelets lab extreme: {len(set(error_assignments['plt_lab_extreme']))} patients")
    print(f"   Negative/zero values: {len(set(error_assignments['negative_values']))} patients")

    print(f"\n4. FOLLOW-UP TIMING ERRORS:")
    print(f"   Too early (<68 days): {len(set(error_assignments['followup_too_early']))} patients")
    print(f"   Between windows (114-272d): {len(set(error_assignments['followup_between']))} patients")

    print(f"\n5. FOLLOW-UP DUPLICATES (in-window, 68-113d):")
    print(f"   Identical duplicates (dates differ): {len(set(error_assignments['duplicate_identical']))} patients")
    print(f"   Conflicting duplicates: {len(set(error_assignments['duplicate_conflicting']))} patients")

    print(f"\n6. FOLLOW-UP REFUSALS (code 0 in 741/742):")
    print(f"   {len(set(error_assignments['followup_refusal_zero']))} patients")

    print(f"\n7. BLOOD TYPE SCENARIOS (elements 17 vs 19):")
    print(f"   ABO-INCOMPATIBLE (must be flagged): {len(set(error_assignments['blood_type_incompatible']))} patients")
    print(f"   Compatible non-identical (must NOT be flagged): {len(set(error_assignments['blood_type_compatible_nonidentical']))} patients")

    print(f"\n8. NEGATIVE LOS (intervention date after discharge):")
    print(f"   {len(set(error_assignments['negative_los']))} patients")

    print(f"\n9. MISSING VALUES:")
    print(f"   Random missing: ~10% of various fields")

    return output_path, error_assignments


def create_empty_row(columns):
    """Create an empty row dictionary with all columns."""
    return {col: '' for col in columns}


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    generate_test_dataset(
        n_patients=100,
        output_file='test_data_100patients.csv'
    )

    generate_test_dataset(
        n_patients=150,
        output_file='test_data_150patients.csv'
    )

    print(f"\n{'=' * 70}")
    print("NEXT STEPS")
    print(f"{'=' * 70}")
    print("\nRun the full analysis to validate scripts:")
    print(f"  cd 'python codes'")
    print(f"  python3 run_full_analysis.py ../test_data_100patients.csv")
    print("\nExpected: All scripts should complete without errors.")
    print("Review output for correct handling of data quality issues.")
