"""
Export the miniature validation datasets as CSV files.

Every hand-constructed dataset used by the test programs (see
Validation_Datasets.pdf for the inventory and the expected results) is
written to the "validation datasets" folder as semicolon-separated CSV, so the
expected values can be recalculated manually in a spreadsheet. File names
follow the inventory numbering (suite_dataset).

The values here are copies of the literal values inside the test
programs; a few key results are re-derived at the end as a consistency
check. The full-size synthetic datasets of suite 3 are not exported here —
they already exist as test_data_100patients.csv / test_data_150patients.csv
with their seeded_errors_*.json answer keys.

Usage:
    python3 export_validation_datasets.py
"""
import os

import numpy as np
import pandas as pd

def _out_dir(base):
    for rel in ('../validation datasets',
                '../LOS analysis validation datasets'):
        d = os.path.normpath(os.path.join(base, rel))
        if os.path.isdir(d):
            return d
    return os.path.normpath(os.path.join(base, '../validation datasets'))

OUT = _out_dir(os.path.dirname(os.path.abspath(__file__)))
os.makedirs(OUT, exist_ok=True)
written = []


def save(name, df):
    path = os.path.join(OUT, name)
    df.to_csv(path, sep=';', index=False)
    written.append(name)


def save_text(name, lines):
    path = os.path.join(OUT, name)
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.writelines(lines)
    written.append(name)


# ===================================================================
# Suite 1 - analysis-module calculations (test_analysis_modules.py)
# ===================================================================

# 1.1 identical duplicate follow-ups (resolve to one record)
save('1_01_duplicate_followups_identical.csv', pd.DataFrame({
    'X_435_0_751': ['2025-03-01', '2025-03-08'],
    'X_435_0_741': ['3', '3'],
    'X_435_0_742': ['2', '2'],
    'days_from_first': [75, 82],
}))

# 1.2 contradictory duplicate follow-ups (exclude both)
save('1_02_duplicate_followups_conflicting.csv', pd.DataFrame({
    'X_435_0_751': ['2025-03-01', '2025-03-08'],
    'X_435_0_741': ['3', '4'],
    'X_435_0_742': ['2', '2'],
    'days_from_first': [75, 82],
}))

# 1.3 indication counting (documented=3, missing=7, '1'+'1.0' merged)
save('1_03_indication_counting.csv', pd.DataFrame({
    'PID': range(10),
    'X_433_7_746': ['1'] * 10,
    'X_433_7_593': ['1', '2', None, None, None, '1.0', None, None, None, None],
}))

# 1.4 length of stay from the same record (patient 1 -> none, patient 2 -> 5)
save('1_04_los_same_record.csv', pd.DataFrame({
    'PID': [1, 1, 2],
    'X_433_0_8': ['2025-01-10', None, '2025-02-01'],
    'X_433_0_753': [None, '2025-03-15', '2025-02-06'],
    'X_433_0_4': ['M', 'M', 'F'],
}))

# 1.5 median precision (6,7,8,9 days -> median 7.5)
base = pd.Timestamp('2025-01-01')
save('1_05_los_median.csv', pd.DataFrame({
    'PID': [1, 2, 3, 4],
    'X_433_0_8': [str(base.date())] * 4,
    'X_433_0_753': [str((base + pd.Timedelta(days=d)).date())
                    for d in (6, 7, 8, 9)],
    'X_433_0_4': ['M'] * 4,
}))

# 1.6 declined answers (code 0 out of the means)
save('1_06_declined_answers.csv', pd.DataFrame({
    'has_followup_3month': [True, True, True, True],
    'X_435_0_741_3month': ['0', '3', '4', '3'],
    'X_435_0_742_3month': ['0', '2', '3', '2'],
}))

# 1.7 outcome answer labels (codes 0,1.0,2,3,7)
save('1_07_outcome_labels.csv', pd.DataFrame({
    'has_followup_3month': [True] * 5,
    'X_435_0_740_3month': ['Y', 'N', 'N', 'U', 'N'],
    'X_435_0_752_3month': ['0', '1.0', '2', '3', '7'],
}))

# 1.8 SNOMED coverage denominator (2 administration rows of 4)
save('1_08_snomed_denominator.csv', pd.DataFrame({
    'PID': [1, 1, 2, 2],
    'X_433_7_746': ['1', None, '2', None],
    'X_433_0_5': ['123', None, '456', None],
}))

# 1.9 temporal patient counts (3 patients, 1 with parseable dosage)
save('1_09_temporal_patients.csv', pd.DataFrame({
    'PID': [1, 2, 3],
    'X_433_7_746': ['1', '1', '2'],
    'year_month': ['2025-01'] * 3,
}))

# 1.10 code normalization
save('1_10_code_normalization.csv', pd.DataFrame({
    'raw_code': ['4.0', '4', '11.0', '11', 'nan'],
    'expected_normalized': ['4', '4', '11', '11', 'nan'],
}))

# 1.11 patient-level denominators (2 patients, 1 with impossible height)
save('1_11_patient_level_denominator.csv', pd.DataFrame({
    'PID': [1, 1, 1, 2, 2],
    'Height': [175, 175, 175, 9999, 9999],
    'X_433_7_11': ['2025-01-01'] * 5,
}))

# 1.12 duplicates only inside real windows
save('1_12_duplicates_by_window.csv', pd.DataFrame({
    'PID': [1, 1, 2, 2, 3, 3],
    'window': ['Unknown', 'Unknown', '3-month', '3-month',
               'Too early (<68 days)', 'Too early (<68 days)'],
}))

# 1.13 biometrics (complete miniature registry export; loads through the
# real data loader; ages/BMIs chosen for spreadsheet recalculation)
meta7 = ['meta line %d\n' % i for i in range(1, 8)]
bio_header = ('"PID";"patient repeat number";"Episode number";"Location";'
              '"Episode date";"Episode description";"FormStatus_541";'
              '"X_541_0_1";"FormStatus_433";"X_433_0_2";"X_433_0_3";'
              '"X_433_0_4";"X_433_7_746";"X_433_7_22";"X_433_7_734"\n')
site = 'Universitätsklinikum Frankfurt'
save_text('1_13_biometrics.csv', meta7 + [bio_header] + [
    f'1;1;1;{site};01/06/2025;ep;open;1955;open;180;81;M;1;500;1\n',
    f'1;1;1;{site};01/06/2025;ep;open;1955;open;180;81;M;1;600;1\n',
    f'2;1;1;{site};01/06/2025;ep;open;1965;open;150;45;F;1;500;1\n',
    f'3;1;1;{site};01/06/2025;ep;open;1975;open;160;64;M;1;;\n',
    f'4;1;1;{site};01/06/2025;ep;open;1945;open;200;120;F;11;;\n',
    f'5;1;1;{site};01/06/2025;ep;open;1985;open;175;70;M;;;\n',
    f'6;1;1;{site};01/06/2025;ep;open;1995;open;165;58;F;;;\n',
])

# 1.14 DQ1 dosage completeness (MAT excluded from the denominator)
save_text('1_14_dq1_completeness.csv', meta7 + [bio_header] + [
    f'1;1;1;{site};01/06/2025;ep;open;1955;open;180;81;M;1;700;1\n',
    f'2;1;1;{site};01/06/2025;ep;open;1965;open;170;60;F;1;500;1\n',
    f'3;1;1;{site};01/06/2025;ep;open;1975;open;160;64;M;1;600;1\n',
    f'4;1;1;{site};01/06/2025;ep;open;1945;open;150;68;F;1;;\n',
    f'5;1;1;{site};01/06/2025;ep;open;1985;open;175;70;M;11;;\n',
    f'6;1;1;{site};01/06/2025;ep;open;1995;open;165;58;F;;;\n',
])

# 1.15 sample without any SNOMED codes (columns present, all empty)
snomed_header = (bio_header.rstrip('\n')
                 + ';"X_433_0_5";"X_433_0_6";"X_433_0_9"\n')
save_text('1_15_snomed_empty.csv', meta7 + [snomed_header] + [
    f'1;1;1;{site};01/06/2025;ep;open;1960;open;180;80;M;1;300;1;;;\n',
    f'2;1;1;{site};01/06/2025;ep;open;1970;open;165;60;F;1;380;1;;;\n',
])


# 1.16 mixed ISO/EU date formats + one unparseable value (loader QC finding)
date_header = '"PID";"Episode date";"X_433_7_746";"X_433_7_11";"X_433_0_753"\n'
save_text('1_16_mixed_date_formats.csv', meta7 + [date_header] + [
    '1;01/12/2025;1;2025-03-05;10/03/2025\n',
    '2;05/12/2025;1;05/04/2025;11/03/2025\n',
    '3;10/12/2025;1;not-a-date;12/03/2025\n',
])

# 1.17 follow-up time anchor (episode, administration, and discharge dates
# all differ; only the administration anchor puts the follow-up in-window)
anchor_header = ('"PID";"Episode date";"X_433_7_746";"X_433_7_11";"X_433_0_753";'
                 '"X_435_0_751";"X_433_0_2";"X_433_0_3";"X_433_0_4";'
                 '"X_433_0_32";"X_433_0_25";"X_541_0_1"\n')
save_text('1_17_followup_time_anchor.csv', meta7 + [anchor_header] + [
    '1;01/01/2025;1;2025-02-01;2025-01-10;;176;80;M;3;4;1960\n',
    '1;01/01/2025;;;;2025-05-17;;;;;;\n',
    '2;01/01/2025;1;;;;165;60;F;2;3;1955\n',
    '2;01/01/2025;;;;2025-05-17;;;;;;\n',
])

# 1.18 test-location cohort (statistics and figures share the loader cohort)
ver_header = ('"PID";"patient repeat number";"Episode number";"Location";'
              '"Episode date";"X_433_7_746";"X_433_7_22";"X_433_7_734";'
              '"X_433_7_11"\n')
save_text('1_18_test_site_cohort.csv', meta7 + [ver_header] + [
    '1;1;1;Site A;01/12/2025;1;500;1;2025-01-05\n',
    '2;1;1;Site B;01/12/2025;1;300;1;2025-01-20\n',
    '3;1;1;Verika (Teststandort);01/12/2025;1;400;1;2025-01-25\n',
])

# 1.19 product code forms '1'/'1.0' across temporal and completeness tables
forms_header = ('"PID";"Episode date";"X_433_7_746";"X_433_7_22";'
                '"X_433_7_734";"X_433_7_11"\n')
save_text('1_19_code_forms_all_tables.csv', meta7 + [forms_header] + [
    '1;01/12/2025;1;500;1;2025-01-05\n',
    '2;01/12/2025;1.0;300;1.0;2025-01-20\n',
])

# 1.20 intervention Y/N conflict partition (exclusive patient categories)
save('1_20_intervention_conflicts.csv', pd.DataFrame({
    'PID': [1, 1, 2, 2, 3, 4],
    'X_433_0_7': ['Y', 'N', 'Y', 'Y', 'N', 'X'],
}))

# 1.21 ordinal outcomes (transition matrices, CFS direction; derived table)
save('1_21_ordinal_outcomes.csv', pd.DataFrame({
    'has_followup_3month': [True] * 5,
    'X_433_0_32':          ['1', '4', '5', '3', '4'],
    'X_435_0_741_3month':  ['2', '5', '3', '5', '4'],
    'X_433_0_25':          ['5', '3', '4', '2', '6'],
    'X_435_0_742_3month':  ['3', '5', '4', '2', '6'],
}))

# 1.22 interval of 366 days (screening threshold + sensitivity analysis)
save('1_22_interval_366_days.csv', pd.DataFrame({
    'PID': [1, 2, 3],
    'X_433_0_8': ['2025-01-01'] * 3,
    'X_433_0_753': ['2026-01-02', '2025-01-08', '2025-01-10'],
    'X_433_0_4': ['M', 'F', 'M'],
}))


# 1.23 conflicting time-invariant attributes (checked and reported)
conf_header = ('"PID";"Episode date";"X_433_7_746";"X_433_7_22";'
               '"X_433_7_734";"X_433_0_4";"X_433_0_2";"X_433_0_3";'
               '"X_541_0_1"\n')
save_text('1_23_attribute_conflicts.csv', meta7 + [conf_header] + [
    '1;01/12/2025;1;500;1;M;176;80;1960\n',
    '1;01/12/2025;1;300;1;F;180;80;1960\n',
    '2;01/12/2025;1;400;1;F;165;60;1955\n',
])


# 1.24 DQ4 checks every documented row (later impossible height; ATIII
# identity pair; wound-blood hematocrit on MAT rows)
dq4_header = ('"PID";"Episode date";"X_433_7_746";"X_433_7_22";"X_433_7_734";'
              '"X_433_7_11";"X_433_0_2";"X_433_0_3";"X_433_0_4";"X_541_0_1";'
              '"X_433_7_601";"X_433_7_602";"X_433_7_748";"X_433_7_747";'
              '"X_433_7_749";"X_433_7_750";"X_433_7_374";"X_433_7_596"\n')
save_text('1_24_dq4_all_rows.csv', meta7 + [dq4_header] + [
    '1;01/12/2025;1;500;1;2025-01-05;170;80;M;1960;70;70;;;;;;\n',
    '1;01/12/2025;1;300;1;2025-01-20;400;80;M;1960;;;;;;;;\n',
    '2;01/12/2025;11;;;2025-01-21;165;60;F;1955;;;80;500;300;40;;\n',
    '3;01/12/2025;4;1000;2;2025-01-22;172;75;M;1962;;;;;;;0;60\n',
])

# ===================================================================
# Suite 2 - treatment and laboratory logic (test_treatments_lab.py)
# ===================================================================

# 2.1 expected ABO classification for all 16 pairs per product class
GROUPS = ['0', 'A', 'B', 'AB']
EXP_RBC = {'0': {'0'}, 'A': {'A', '0'}, 'B': {'B', '0'},
           'AB': {'A', 'B', 'AB', '0'}}
EXP_PLASMA = {'0': {'0', 'A', 'B', 'AB'}, 'A': {'A', 'AB'},
              'B': {'B', 'AB'}, 'AB': {'AB'}}
rows = []
for p in GROUPS:
    for d in GROUPS:
        rows.append({
            'patient_abo': p, 'product_abo': d,
            'expected_RBC': ('identical' if p == d else
                             'compatible' if d in EXP_RBC[p] else
                             'incompatible'),
            'expected_plasma': ('identical' if p == d else
                                'compatible' if d in EXP_PLASMA[p] else
                                'incompatible'),
            'expected_PC': 'identical' if p == d else 'non_identical',
        })
save('2_01_abo_expected_classifications.csv', pd.DataFrame(rows))

# 2.2 blood-group statistics and RhD flag (12 administrations)
bt_rows = [
    dict(PID=1,  prod='1',   pabo='A',  dabo='A',  prh='1',   drh='1'),
    dict(PID=2,  prod='1',   pabo='A',  dabo='0',  prh='2',   drh='1'),
    dict(PID=3,  prod='1',   pabo='A',  dabo='B',  prh='2',   drh='2'),
    dict(PID=4,  prod='1',   pabo='AB', dabo='0',  prh='0',   drh='1'),
    dict(PID=5,  prod='1.0', pabo='0',  dabo='A',  prh='2.0', drh='1.0'),
    dict(PID=6,  prod='2',   pabo='0',  dabo='AB', prh=None,  drh=None),
    dict(PID=7,  prod='2',   pabo='A',  dabo='0',  prh=None,  drh=None),
    dict(PID=8,  prod='2',   pabo='AB', dabo='AB', prh=None,  drh=None),
    dict(PID=9,  prod='2',   pabo='B',  dabo='AB', prh=None,  drh=None),
    dict(PID=10, prod='3',   pabo='A',  dabo='B',  prh='1',   drh='1'),
    dict(PID=11, prod='3',   pabo='0',  dabo='0',  prh=None,  drh=None),
    dict(PID=12, prod='3',   pabo='X',  dabo='A',  prh='2',   drh='1'),
]
save('2_02_blood_type_statistics.csv', pd.DataFrame({
    'PID': [r['PID'] for r in bt_rows],
    'X_433_7_746': [r['prod'] for r in bt_rows],
    'X_433_0_17': [r['pabo'] for r in bt_rows],
    'X_433_7_19': [r['dabo'] for r in bt_rows],
    'X_433_0_18': [r['prh'] for r in bt_rows],
    'X_433_7_20': [r['drh'] for r in bt_rows],
    'X_433_7_11': '2025-01-01',
    'X_433_7_22': 500.0,
}))

# 2.3 dosage, unit handling, gender stratification (17 rows, 9 patients)
rows = []


def add_row(pid, gender, prod=None, dose=None, unit=None,
            plt_b=None, plt_a=None, alb_b=None, alb_a=None,
            height=176, weight=94):
    rows.append({
        'PID': pid, 'X_433_0_4': gender, 'X_433_0_2': height,
        'X_433_0_3': weight, 'X_433_7_746': prod, 'X_433_7_22': dose,
        'X_433_7_734': unit, 'X_433_7_37': plt_b, 'X_433_7_587': plt_a,
        'X_433_7_603': alb_b, 'X_433_7_591': alb_a,
    })


add_row(1, 'M', prod='1',   dose=600, unit='1',   plt_b=170,    plt_a=180)
add_row(1, 'M', prod='1.0', dose=700, unit='1.0', plt_b=250000, plt_a=260000)
add_row(1, 'M', prod='1',   dose=800, unit='1',   plt_b=200,    plt_a=210)
add_row(2, 'M', prod='7', dose=100, unit='2', plt_b=300000, plt_a=310000, alb_b=3.5, alb_a=4.0)
add_row(2, 'M', prod='7', dose=100, unit='2', plt_b=150,    plt_a=160,    alb_b=2.8, alb_a=3.1)
add_row(2, 'M', prod='7', dose=100, unit='2', plt_b=220,    plt_a=230,    alb_b=3500, alb_a=4000)
add_row(3, 'M', prod='5', dose=400,  unit='3')
add_row(3, 'M', prod='5', dose=2000, unit='3')
add_row(3, 'M', prod='5', dose=3000, unit='3')
add_row(3, 'M', prod='5', dose=4000, unit='3')
add_row(8, 'M', prod='4', dose=2000, unit='1')
add_row(8, 'M', prod='4', dose=3000, unit='1')
add_row(8, 'M', prod='4', dose=4000, unit='1')
add_row(4, 'F', prod='1', dose=500, unit='1', height=165, weight=60)
add_row(5, 'F', prod='2', dose=600, unit='1', height=160, weight=55)
add_row(6, 'F', height=158, weight=52)
add_row(7, 'D', prod='1', dose=450, unit='1')
add_row(9, None)
save('2_03_dosage_gender_units.csv', pd.DataFrame(rows))

# 2.4 laboratory value quality (12 patients)
save('2_04_lab_value_quality.csv', pd.DataFrame({
    'PID': list(range(2000, 2012)),
    'X_433_7_603': [3.5, 4.0, 3.8, 4.2, 3.6, 4.1, 3.9, 4.4, 3.7, 4.3, 3500.0, 3.4],
    'X_433_7_591': [3.6, 4.1, 3.9, 4.3, 3.7, 4.2, 4.0, 4.5, 3.8, 4.4, 4000.0, 3.5],
    'X_433_7_37':  [170.0, 200.0, 250.0, 300.0, 150.0, 220.0, 180.0, 260.0,
                    240.0, 210.0, 250000.0, -50.0],
    'X_433_7_587': [180.0, 210.0, 260.0, 310.0, 160.0, 230.0, 190.0, 270.0,
                    250.0, 220.0, 260000.0, 200.0],
}))


# 2.5 laboratory scale contract (negatives never scaled; one-time conversion)
save('2_05_lab_scale_contract.csv', pd.DataFrame({
    'PID': [1, 2, 3, 4, 5, 6],
    'X_433_7_746': ['1'] * 6,
    'X_433_7_37':  [-150.0, -13000.0, 150.0, 150000.0, None, None],
    'X_433_7_603': [None, None, None, None, 4.0, 4000.0],
}))

# 2.6 review-export integrity (code decoding, dose 0, free text containing a
# comma and a line break; the free-text field is quoted in the deposited file)
save('2_06_review_export_integrity.csv', pd.DataFrame({
    'PID': [21, 21, 22, 22, 23, 23, 24, 24, 24],
    'X_433_0_4': ['M', 'M', 'F', 'F', 'M', 'M', 'F', 'F', 'F'],
    'X_433_0_2': [176.0] * 9,
    'X_433_0_3': [94.0] * 9,
    'X_433_7_746': ['1', None, '1', None, '1', None, '1', '1', None],
    'X_433_0_17': ['A', None, 'A', None, 'A', None, 'A', 'A', None],
    'X_433_7_19': ['B', None, 'B', None, 'B', None, 'B', 'B', None],
    'X_433_0_18': ['1', None, '1', None, '1', None, '1', '1', None],
    'X_433_7_20': ['1', None, '1', None, '1', None, '1', '1', None],
    'X_433_7_11': ['2025-01-01', None, '2025-01-02', None, '2025-06-01', None,
                   '2025-01-01', '2025-06-01', None],
    'X_433_7_22': [0.0, None, 500.0, None, 400.0, None, 300.0, 350.0, None],
    'X_433_7_734': ['1', None, '1', None, '1', None, '1', '1', None],
    'X_435_0_751': [None, '2025-04-01', None, '2025-04-02', None, '2025-03-01',
                    None, None, '2025-04-01'],
    'X_435_0_737': [None, 'Y', None, 'U', None, 'Y', None, None, 'N'],
    'X_435_0_616': [None, 'Problem, nach Gabe\nZeile zwei', None, None, None, 'Vorereignis',
                    None, None, None],
    'X_435_0_740': [None, 'N', None, 'U', None, 'N', None, None, 'N'],
    'X_435_0_752': [None, '2', None, '3', None, '1', None, None, '0'],
}))

# 2.7 single observation per product + dose 0 (JSON/statistics exports)
save_text('2_07_single_observation_product.csv', meta7 + [
    '"PID";"Episode date";"X_433_7_746";"X_433_7_22";"X_433_7_734";"X_433_7_11"\n',
    '31;01/12/2025;5;0;3;2025-01-05\n',
    '32;01/12/2025;4;2500;2;2025-01-06\n',
])


# 2.8 physicians' range boundaries (inclusive bounds from the range registry)
save('2_08_range_boundaries.csv', pd.DataFrame({
    'PID': [1, 2, 3, 4, 5, 6, 7, 8, 71, 72, 73, 74],
    'X_433_7_746': ['1'] * 12,
    'X_433_7_614': [1.0, 20.0, 0.9, 20.1] + [None] * 8,
    'X_433_7_37':  [None] * 4 + [1000.0, 1000000.0, 1000001.0, None] + [None] * 4,
    'X_433_7_374': [None] * 8 + [0.0, 1.0, None, None],
    'X_433_7_596': [None] * 8 + [50.0, 50.0, None, None],
    'X_433_7_585': [None] * 10 + [0.0, None],
    'X_433_7_586': [None] * 10 + [100.0, None],
    'X_433_7_603': [None] * 11 + [0.0],
    'X_433_7_591': [None] * 11 + [3.5],
}))

# 2.9 QC artifact integrity (negative platelet next to correct-unit values)
# and EBV same-row rule (height, weight, sex on three different rows)
save('2_09_qc_artifacts_and_ebv.csv', pd.DataFrame({
    'PID': [41, 42, 51, 51, 51, 52],
    'X_433_7_746': ['1', '1', '1', None, None, '1'],
    'X_433_7_37': [-150.0, 200.0, None, None, None, None],
    'X_433_7_587': [210000.0, 210.0, None, None, None, None],
    'X_433_0_2': [None, None, 176.0, None, None, 176.0],
    'X_433_0_3': [None, None, None, 94.0, None, 94.0],
    'X_433_0_4': [None, None, None, None, 'M', 'M'],
}))

# 2.10 dosage unit and missing-dose checks for iron i.v., EPO, oral iron
save_text('2_10_products_6_8_10.csv', meta7 + [
    '"PID";"Episode date";"X_433_7_746";"X_433_7_22";"X_433_7_734";"X_433_7_11"\n',
    '61;01/12/2025;6;100;1;2025-01-05\n',
    '62;01/12/2025;8;;;2025-01-06\n',
    '63;01/12/2025;10;100;2;2025-01-07\n',
    '64;01/12/2025;6;200;3;2025-01-08\n',
])

# ===================================================================
# Suite 4 - cohort tools (test_enrollment_filter.py)
# The tool inputs are complete miniature registry exports; the deposited
# files render the same records in the full export header (the tests
# construct compact equivalents with identical values).
# ===================================================================

# 4.1 miniature export for the enrollment cutoff (cutoff 2026-01-15)
save_text('4_01_enrollment_cutoff_mini.csv', meta7 + [
    '"PID";"Episode date";"X_435_0_751"\n',
    '1;01/12/2025;\n',
    '1;01/12/2025;2026-03-05\n',
    '2;15/01/2026;\n',
    '3;16/01/2026;\n',
    '4;;\n',
])

# 4.3 / 4.10 January/August export pair (cap 2026-01-15)
wl_header = ('"PID";"Episode date";"Unique ID (Form_Record_DataElement):";'
             '"X_433_7_746";"X_433_7_11";"X_433_7_22";"X_435_0_751";"X_435_0_741"\n')
january_rows = [
    '1;01/12/2025;U1;1;2025-12-01;250;;\n',
    '1;01/12/2025;U2;1;;300;;\n',
    '1;01/12/2025;;2;;100;;\n',
    '2;;U3;;;;;\n',
    '4;10/01/2026;U4;;;;;\n',
]
august_rows = [
    '1;01/12/2025;U1;1;2025-12-01;250;;\n',
    '1;01/12/2025;U2;1;;350;;\n',
    '1;01/12/2025;;2;;100;;\n',
    '1;01/12/2025;U9;1;;400;;\n',
    '1;01/12/2025;1;1;2026-02-20;250;;\n',
    '1;20/02/2026;;;;;;\n',
    '1;01/12/2025;;;;;2026-03-05;3\n',
    '2;;U3;;;;;\n',
    '4;10/01/2026;U4;;;;;\n',
    '4;01/02/2026;;1;2026-02-01;200;;\n',
    '4;01/02/2026;;1;;150;;\n',
    '4;01/02/2026;;;;;2026-05-10;4\n',
    '3;05/03/2026;;1;2026-03-05;500;;\n',
]
save_text('4_03a_january_reference.csv', meta7 + [wl_header] + january_rows)
save_text('4_03b_august_current.csv', meta7 + [wl_header] + august_rows)

# 4.6 duplicate-consumption pair
save_text('4_06a_consume_reference.csv',
          meta7 + [wl_header, '7;01/12/2025;;3;;2;;\n'])
save_text('4_06b_consume_current.csv',
          meta7 + [wl_header, '7;01/12/2025;;3;;2;;\n',
                   '7;01/12/2025;;3;;2;;\n'])

# 4.7 patient with all rows beyond the cap (adds patient 5 to the pair)
save_text('4_07a_vanished_reference.csv',
          meta7 + [wl_header] + january_rows + ['5;01/11/2025;;1;2025-11-01;100;;\n'])
save_text('4_07b_vanished_current.csv',
          meta7 + [wl_header] + august_rows + ['5;20/03/2026;;1;2026-03-20;100;;\n'])

# 4.8 reference patient absent from the current export (adds patient 9)
save_text('4_08_missing_patient_reference.csv',
          meta7 + [wl_header] + january_rows + ['9;01/10/2025;;;;;;\n'])

# 4.5 repeated header labels + new elements
UID = '"Unique ID (Form_Record_DataElement):"'
save_text('4_05a_duplicate_labels_reference.csv', meta7 + [
    f'"PID";{UID};"Episode date";{UID};"X_433_7_746";{UID};;\n',
    '1;u1;01/12/2025;u2;1;u3;;\n',
])
save_text('4_05b_duplicate_labels_current.csv', meta7 + [
    f'"PID";{UID};"Episode date";{UID};"X_433_7_746";{UID};'
    f'"X_433_0_900";"X_435_0_901";"X_541_0_902";;\n',
    '1;u1;20/02/2026;u2;2;u3;n1;;n3;;\n',
])

# 4.11 withdrawn-patient pair
save_text('4_11a_withdrawn_reference.csv', meta7 + [wl_header,
    '6;01/12/2025;;1;2025-12-05;100;;\n',
    '6;01/12/2025;;;;;2026-01-10;3\n',
    '8;01/12/2025;;1;2025-12-06;90;;\n',
    '8;01/12/2025;;;;;2026-01-05;1\n',
])
save_text('4_11b_withdrawn_current.csv', meta7 + [wl_header,
    '8;01/12/2025;;1;2025-12-06;90;;\n',
    '8;01/12/2025;;;;;2026-04-01;2\n',
])

# 4.12 schema evolution pair
save_text('4_12a_schema_evolution_reference.csv', meta7 + [
    '"PID";"Episode date";"X_433_7_746";\n',
    '1;01/12/2025;1;\n',
])
save_text('4_12b_schema_evolution_current.csv', meta7 + [
    '"PID";"Episode date";"X_433_7_746";"X_433_0_999";\n',
    '1;20/02/2026;2;77;\n',
])

# 4.13 genuinely incompatible schemas (missing columns in the current file)
save_text('4_13_schema_violation_current.csv', meta7 + [
    '"PID";"Episode date";"X_433_7_746"\n',
    '1;01/12/2025;1\n',
])

# ===================================================================
# Render every registry-format dataset in the FULL export header
# (header_template.csv, 189 columns; non-relevant fields empty), so all
# deposited datasets share the same header as a real registry export.
# Derived-table datasets (intermediate tables inside the computation) and
# the deliberately non-standard schema-drift files keep their own headers.
# ===================================================================
TEMPLATE = os.path.join(OUT, 'header_template.csv')
with open(TEMPLATE, encoding='utf-8') as f:
    tmpl_lines = [f.readline() for _ in range(8)]
tmpl_cols = [c.strip().strip('"') for c in tmpl_lines[7].rstrip('\n').split(';')]

REGISTRY_FORMAT = [
    '1_03_indication_counting.csv', '1_04_los_same_record.csv',
    '1_05_los_median.csv', '1_08_snomed_denominator.csv',
    '1_13_biometrics.csv', '1_14_dq1_completeness.csv',
    '1_15_snomed_empty.csv',
    '1_16_mixed_date_formats.csv', '1_17_followup_time_anchor.csv',
    '1_18_test_site_cohort.csv', '1_19_code_forms_all_tables.csv',
    '1_20_intervention_conflicts.csv', '1_22_interval_366_days.csv',
    '1_23_attribute_conflicts.csv', '1_24_dq4_all_rows.csv',
    '2_02_blood_type_statistics.csv', '2_03_dosage_gender_units.csv',
    '2_04_lab_value_quality.csv', '2_05_lab_scale_contract.csv',
    '2_06_review_export_integrity.csv', '2_07_single_observation_product.csv',
    '2_08_range_boundaries.csv', '2_09_qc_artifacts_and_ebv.csv',
    '2_10_products_6_8_10.csv',
    '4_01_enrollment_cutoff_mini.csv',
    '4_03a_january_reference.csv', '4_03b_august_current.csv',
    '4_06a_consume_reference.csv', '4_06b_consume_current.csv',
    '4_07a_vanished_reference.csv', '4_07b_vanished_current.csv',
    '4_08_missing_patient_reference.csv',
    '4_11a_withdrawn_reference.csv', '4_11b_withdrawn_current.csv',
]
for name in REGISTRY_FORMAT:
    path = os.path.join(OUT, name)
    with open(path, encoding='utf-8') as f:
        first = f.readline()
    skip = 7 if first.startswith('meta line') else 0
    df = pd.read_csv(path, sep=';', skiprows=skip, dtype=str,
                     keep_default_na=False)
    unknown = [c for c in df.columns if c not in tmpl_cols]
    assert not unknown, (name, unknown)
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.writelines(tmpl_lines)
        def _field(v):
            if any(ch in v for ch in (';', '"', '\n', '\r')):
                return '"' + v.replace('"', '""') + '"'
            return v

        for _, row in df.iterrows():
            f.write(';'.join(_field(row[c]) if c in df.columns else ''
                             for c in tmpl_cols) + '\n')

# ===================================================================
# consistency checks against the documented expected values
# ===================================================================
d = pd.read_csv(os.path.join(OUT, '1_05_los_median.csv'), sep=';', skiprows=7)
los = (pd.to_datetime(d['X_433_0_753']) - pd.to_datetime(d['X_433_0_8'])).dt.days
assert los.median() == 7.5, los.median()

d = pd.read_csv(os.path.join(OUT, '1_06_declined_answers.csv'), sep=';')
vals = pd.to_numeric(d['X_435_0_741_3month'])
assert abs(vals[vals >= 1].mean() - (3 + 4 + 3) / 3) < 1e-9

d = pd.read_csv(os.path.join(OUT, '1_13_biometrics.csv'), sep=';', skiprows=7,
                dtype=str)
per_patient = d.drop_duplicates('PID')
treated = per_patient[per_patient['X_433_7_746'].notna()]
ages = 2025 - pd.to_numeric(treated['X_541_0_1'])
assert ages.mean() == 65.0 and ages.median() == 65.0, (ages.mean(), ages.median())

d = pd.read_csv(os.path.join(OUT, '1_14_dq1_completeness.csv'), sep=';',
                skiprows=7, dtype=str)
adm = d[d['X_433_7_746'].notna()]
rel = adm[adm['X_433_7_746'] != '11']
assert len(rel) == 4 and rel['X_433_7_22'].notna().sum() == 3  # 75%

d = pd.read_csv(os.path.join(OUT, '2_03_dosage_gender_units.csv'), sep=';',
                skiprows=7, dtype=str)
rbc = pd.to_numeric(d.loc[d['X_433_7_746'].isin(['1', '1.0']), 'X_433_7_22'])
assert abs(rbc.mean() - np.mean([600, 700, 800, 500, 450])) < 1e-9


d = pd.read_csv(os.path.join(OUT, '1_22_interval_366_days.csv'), sep=';',
                skiprows=7)
iv = (pd.to_datetime(d['X_433_0_753']) - pd.to_datetime(d['X_433_0_8'])).dt.days
assert sorted(iv) == [7, 9, 366] and iv[iv <= 365].mean() == 8.0

d = pd.read_csv(os.path.join(OUT, '2_05_lab_scale_contract.csv'), sep=';',
                skiprows=7)
plt_vals = pd.to_numeric(d['X_433_7_37'], errors='coerce').dropna()
conv = plt_vals[plt_vals > 0].apply(lambda v: v * 1000 if v < 1000 else v)
assert set(conv) == {150000.0} and (plt_vals <= 0).sum() == 2

d = pd.read_csv(os.path.join(OUT, '2_06_review_export_integrity.csv'), sep=';',
                skiprows=7)
_texts = set(d['X_435_0_616'].dropna())
assert _texts == {'Problem, nach Gabe\nZeile zwei', 'Vorereignis'}, _texts
assert 0.0 in pd.to_numeric(d['X_433_7_22'], errors='coerce').values

print(f"exported {len(written)} files to {OUT}")
for name in written:
    print(" ", name)
