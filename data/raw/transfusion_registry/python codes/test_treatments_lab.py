"""
Unit tests for descriptive_treatments.py and lab_value_quality.py.

Uses small constructed DataFrames with known expected outputs (ABO/RhD
compatibility matrices, unit normalization, dosage exclusions, alarm and
clinical-range logic). Run from the "python codes" directory:

    python3 test_treatments_lab.py
"""
import sys
import os
import tempfile

import numpy as np
import pandas as pd

PIPELINE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PIPELINE_DIR)

from descriptive_treatments import TreatmentDescriptives
from lab_value_quality import LabValueQualityChecker

PASS = 0
FAIL = 0


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name} {detail}")


def make_td(df_all):
    """Build a TreatmentDescriptives instance without a data loader."""
    td = object.__new__(TreatmentDescriptives)
    td.df_all = df_all.copy()
    product_col = 'X_433_7_746'
    td.df = td.df_all[td.df_all[product_col].notna()].copy()
    td.df_no_product = td.df_all[td.df_all[product_col].isna()].copy()
    td.results = {}
    td.mapper = None
    return td


# --------------------------------------------------------------------------
# 1. ABO compatibility matrices: all 16 recipient x donor pairs per class
# --------------------------------------------------------------------------
print("\n[1] ABO compatibility matrices (16 pairs per product class)")

GROUPS = ['0', 'A', 'B', 'AB']

# Expected RBC matrix: recipient <- allowed donors
EXP_RBC = {
    '0': {'0'},
    'A': {'A', '0'},
    'B': {'B', '0'},
    'AB': {'A', 'B', 'AB', '0'},
}
# Expected plasma (FFP) matrix: REVERSED
EXP_PLASMA = {
    '0': {'0', 'A', 'B', 'AB'},
    'A': {'A', 'AB'},
    'B': {'B', 'AB'},
    'AB': {'AB'},
}

cls_fn = TreatmentDescriptives._classify_abo_compatibility

rbc_ok = True
for p in GROUPS:
    for d in GROUPS:
        got = cls_fn(p, d, 'RBC')
        if p == d:
            exp = 'identical'
        elif d in EXP_RBC[p]:
            exp = 'compatible'
        else:
            exp = 'incompatible'
        if got != exp:
            rbc_ok = False
            print(f"    RBC {p}<-{d}: got {got}, expected {exp}")
check("RBC matrix (16 pairs)", rbc_ok)

plasma_ok = True
for p in GROUPS:
    for d in GROUPS:
        got = cls_fn(p, d, 'plasma')
        if p == d:
            exp = 'identical'
        elif d in EXP_PLASMA[p]:
            exp = 'compatible'
        else:
            exp = 'incompatible'
        if got != exp:
            plasma_ok = False
            print(f"    FFP {p}<-{d}: got {got}, expected {exp}")
check("FFP/plasma matrix (16 pairs, reversed vs RBC)", plasma_ok)

pc_ok = True
for p in GROUPS:
    for d in GROUPS:
        got = cls_fn(p, d, 'PC')
        exp = 'identical' if p == d else 'non_identical'
        if got != exp:
            pc_ok = False
            print(f"    PC {p}<-{d}: got {got}, expected {exp}")
check("PC matrix (identical vs non_identical, never 'incompatible')", pc_ok)

check("Invalid/missing ABO -> not_assessable",
      cls_fn('X', 'A', 'RBC') == 'not_assessable'
      and cls_fn(np.nan, 'A', 'RBC') == 'not_assessable')
check("Float-form '0.0' normalized to '0'",
      cls_fn('0.0', '0', 'RBC') == 'identical'
      and cls_fn('A', '0.0', 'RBC') == 'compatible')

# --------------------------------------------------------------------------
# 2. Blood type statistics on a constructed DataFrame (ABO counts + RhD flag)
# --------------------------------------------------------------------------
print("\n[2] Blood type statistics: counts and RhD flag logic")

bt_rows = [
    # RBC (product '1'): ABO cases + Rh cases
    dict(PID=1, prod='1',  pabo='A',  dabo='A',  prh='1',   drh='1'),    # identical / not flagged
    dict(PID=2, prod='1',  pabo='A',  dabo='0',  prh='2',   drh='1'),    # compatible / FLAGGED
    dict(PID=3, prod='1',  pabo='A',  dabo='B',  prh='2',   drh='2'),    # INCOMPATIBLE / not flagged
    dict(PID=4, prod='1',  pabo='AB', dabo='0',  prh='0',   drh='1'),    # compatible / Rh not assessable
    dict(PID=5, prod='1.0', pabo='0', dabo='A',  prh='2.0', drh='1.0'),  # INCOMPATIBLE / FLAGGED (float forms)
    # FFP (product '2'): reversed rules, no RhD check
    dict(PID=6, prod='2',  pabo='0',  dabo='AB', prh=None,  drh=None),   # compatible (reversed)
    dict(PID=7, prod='2',  pabo='A',  dabo='0',  prh=None,  drh=None),   # INCOMPATIBLE (reversed)
    dict(PID=8, prod='2',  pabo='AB', dabo='AB', prh=None,  drh=None),   # identical
    dict(PID=9, prod='2',  pabo='B',  dabo='AB', prh=None,  drh=None),   # compatible
    # PC (product '3'): neutral categories, RhD checked
    dict(PID=10, prod='3', pabo='A',  dabo='B',  prh='1',   drh='1'),    # non-identical / not flagged
    dict(PID=11, prod='3', pabo='0',  dabo='0',  prh=None,  drh=None),   # identical
    dict(PID=12, prod='3', pabo='X',  dabo='A',  prh='2',   drh='1'),    # ABO not assessable / FLAGGED
]
df_bt = pd.DataFrame({
    'PID': [r['PID'] for r in bt_rows],
    'X_433_7_746': [r['prod'] for r in bt_rows],
    'X_433_0_17': [r['pabo'] for r in bt_rows],
    'X_433_7_19': [r['dabo'] for r in bt_rows],
    'X_433_0_18': [r['prh'] for r in bt_rows],
    'X_433_7_20': [r['drh'] for r in bt_rows],
    'X_433_7_11': '2025-01-01',
    'X_433_7_22': 500.0,
})
td = make_td(df_bt)
bt = td._calculate_blood_type_statistics()

rbc = bt['Red blood cell concentrate (RBC)']
check("RBC total aggregates '1' and '1.0' (n=5)", rbc['total'] == 5,
      f"got {rbc['total']}")
check("RBC ABO identical=1", rbc['abo']['identical'] == 1, f"got {rbc['abo']['identical']}")
check("RBC ABO compatible_non_identical=2", rbc['abo']['compatible_non_identical'] == 2,
      f"got {rbc['abo']['compatible_non_identical']}")
check("RBC ABO incompatible=2", rbc['abo']['incompatible'] == 2, f"got {rbc['abo']['incompatible']}")
check("RBC incompatible details exported (PIDs 3,5)",
      sorted(d['PID'] for d in rbc['abo']['incompatible_details']) == [3, 5])
check("RBC RhD flagged=2 (incl. float-form codes)", rbc['rh']['rhd_flagged'] == 2,
      f"got {rbc['rh']['rhd_flagged']}")
check("RBC RhD not flagged=2", rbc['rh']['rhd_unflagged'] == 2, f"got {rbc['rh']['rhd_unflagged']}")
check("RBC RhD not assessable=1 (code 0=Unknown)", rbc['rh']['rhd_not_assessable'] == 1,
      f"got {rbc['rh']['rhd_not_assessable']}")
check("RBC RhD flagged details (PIDs 2,5)",
      sorted(d['PID'] for d in rbc['rh']['rhd_flagged_details']) == [2, 5])

ffp = bt['Fresh Frozen Plasma (FFP)']
check("FFP ABO identical=1", ffp['abo']['identical'] == 1)
check("FFP ABO compatible_non_identical=2 (reversed rules)",
      ffp['abo']['compatible_non_identical'] == 2, f"got {ffp['abo']['compatible_non_identical']}")
check("FFP ABO incompatible=1 (A<-0 is plasma-incompatible)",
      ffp['abo']['incompatible'] == 1, f"got {ffp['abo']['incompatible']}")
check("FFP RhD not checked", ffp['rh']['rhd_checked'] is False)

pc = bt['Platelet concentrate (PC)']
check("PC ABO identical=1", pc['abo']['identical'] == 1)
check("PC ABO non_identical=1 (neutral category)", pc['abo']['non_identical'] == 1,
      f"got {pc['abo']['non_identical']}")
check("PC ABO incompatible is None (no mismatch warning)", pc['abo']['incompatible'] is None)
check("PC ABO not_assessable=1 (invalid value)", pc['abo']['not_assessable'] == 1)
check("PC RhD checked and flagged=1", pc['rh']['rhd_checked'] and pc['rh']['rhd_flagged'] == 1)

table = td.create_blood_type_table()
check("Wrong footnote removed from table",
      "identical ABO required" not in table)
check("Table shows PC neutral wording", "preferred but not mandatory" in table)

# --------------------------------------------------------------------------
# 3-8. Gender-stratified + headline statistics on a constructed DataFrame
# --------------------------------------------------------------------------
print("\n[3] Platelet normalization consistency, albumin exclusion, fallback"
      " removal, denominators, code aggregation, non-M/F exclusion")

rows = []


def add_row(pid, gender, prod=None, dose=None, unit=None,
            plt_b=None, plt_a=None, alb_b=None, alb_a=None,
            height=176, weight=94):
    rows.append({
        'PID': pid, 'X_433_0_4': gender, 'X_433_0_2': height, 'X_433_0_3': weight,
        'X_433_7_746': prod, 'X_433_7_22': dose, 'X_433_7_734': unit,
        'X_433_7_37': plt_b, 'X_433_7_587': plt_a,
        'X_433_7_603': alb_b, 'X_433_7_591': alb_a,
    })


# Male patient 1: three RBC administrations in ml (codes '1' and '1.0' mixed)
# with platelet values on MIXED scales (thousands and /ul)
add_row(1, 'M', prod='1',   dose=600, unit='1',   plt_b=170,    plt_a=180)
add_row(1, 'M', prod='1.0', dose=700, unit='1.0', plt_b=250000, plt_a=260000)
add_row(1, 'M', prod='1',   dose=800, unit='1',   plt_b=200,    plt_a=210)
# Male patient 2: albumin pairs (one wrong-unit pair) + more platelets
add_row(2, 'M', prod='7', dose=100, unit='2', plt_b=300000, plt_a=310000, alb_b=3.5, alb_a=4.0)
add_row(2, 'M', prod='7', dose=100, unit='2', plt_b=150,    plt_a=160,    alb_b=2.8, alb_a=3.1)
add_row(2, 'M', prod='7', dose=100, unit='2', plt_b=220,    plt_a=230,    alb_b=3500, alb_a=4000)
# Male patient 3: Fibrinogen doses in mg incl. one implausibly low (< 500)
add_row(3, 'M', prod='5', dose=400,  unit='3')
add_row(3, 'M', prod='5', dose=2000, unit='3')
add_row(3, 'M', prod='5', dose=3000, unit='3')
add_row(3, 'M', prod='5', dose=4000, unit='3')
# Male patient 8: PPSB doses documented only in ml (excluded unit)
add_row(8, 'M', prod='4', dose=2000, unit='1')
add_row(8, 'M', prod='4', dose=3000, unit='1')
add_row(8, 'M', prod='4', dose=4000, unit='1')
# Female patients: F4 treated (RBC), F5 treated (FFP), F6 registered w/o product
add_row(4, 'F', prod='1', dose=500, unit='1', height=165, weight=60)
add_row(5, 'F', prod='2', dose=600, unit='1', height=160, weight=55)
add_row(6, 'F', height=158, weight=52)  # no product
# Non-M/F: patient 7 treated with gender 'D', patient 9 without gender, untreated
add_row(7, 'D', prod='1', dose=450, unit='1')
add_row(9, None)

df_main = pd.DataFrame(rows)
td2 = make_td(df_main)

# --- Code-form aggregation ('1' + '1.0' summed, not overwritten) ---
dist = td2._calculate_product_distribution()
check("Product distribution aggregates '1'+'1.0' (RBC n=5)",
      dist['products']['Red blood cell concentrate (RBC)']['n'] == 5,
      f"got {dist['products']['Red blood cell concentrate (RBC)']['n']}")

dosages = td2._calculate_dosage_statistics()
rbc_ml = dosages['Red blood cell concentrate (RBC)']['ml']
check("Dosage stats aggregate unit forms '1'+'1.0' (RBC ml n=5)",
      rbc_ml['n'] == 5, f"got {rbc_ml['n']}")
check("Dosage mean over aggregated forms",
      abs(rbc_ml['mean'] - np.mean([600, 700, 800, 500, 450])) < 1e-9)

ppp = td2._calculate_products_per_patient()
check("Products-per-patient aggregates code forms (RBC patients=3)",
      ppp['Red blood cell concentrate (RBC)']['n_patients'] == 3,
      f"got {ppp['Red blood cell concentrate (RBC)']['n_patients']}")

# --- Dosage exclusion log exported to CSV ---
tmpdir = tempfile.mkdtemp(prefix="dq_")
from pathlib import Path
td2._export_dosage_exclusions(Path(tmpdir))
excl_path = os.path.join(tmpdir, 'dosage_exclusions.csv')
check("dosage_exclusions.csv written", os.path.exists(excl_path))
if os.path.exists(excl_path):
    excl_df = pd.read_csv(excl_path)
    check("Exclusion log contains PPSB_ml and Fibrinogen_mg rows",
          set(['PPSB_ml', 'Fibrinogen_mg']) <= set(excl_df['Product_Unit']),
          f"got {list(excl_df['Product_Unit'])}")

# --- Albumin headline exclusion ---
labs = td2._calculate_lab_value_statistics()
alb = labs['Serum albumin']
check("Albumin mg/dl pair converted to g/dl and included (n=3)",
      alb['before']['n'] == 3, f"got {alb['before']['n']}")
check("Albumin unit corrections counted (2 values: 3500 and 4000)",
      alb['n_unit_corrected'] == 2, f"got {alb['n_unit_corrected']}")
check("Albumin before mean over converted values (3.5, 2.8, 3.5)",
      abs(alb['before']['mean'] - np.mean([3.5, 2.8, 3.5])) < 1e-9,
      f"got {alb['before']['mean']}")

# --- Platelet normalization consistency headline vs gender section ---
plt_headline = labs['Platelets']
exp_norm_before = [v * 1000 if v < 1000 else v
                   for v in [170, 250000, 200, 300000, 150, 220]]
check("Headline platelet before mean normalized (*1000 where <1000)",
      abs(plt_headline['before']['mean'] - np.mean(exp_norm_before)) < 1e-9,
      f"got {plt_headline['before']['mean']}")

gs = td2._calculate_gender_stratified_statistics()
plt_male = gs['lab_values_before']['Male']['Platelets']
check("Gender section keeps ALL platelet values (n=6, none dropped)",
      plt_male['n'] == 6, f"got {plt_male['n']}")
check("Gender section platelet mean matches headline normalization",
      abs(plt_male['mean'] - np.mean(exp_norm_before)) < 1e-9,
      f"got {plt_male['mean']} vs {np.mean(exp_norm_before)}")
check("Gender section platelet unit is '/µl'", plt_male['unit'] == '/µl')
check("Gender section platelet min on /µl scale (150000)",
      plt_male['min'] == 150000.0, f"got {plt_male['min']}")

# --- No fallback to wrong-unit doses in normalized dosages ---
male_norm = gs['dosages_normalized']['Male']
check("Albumin (doses only in IU, expected ml) SKIPPED - no fallback",
      'Albumin' not in male_norm, f"keys: {list(male_norm.keys())}")
check("PPSB (doses only in ml, excluded unit) SKIPPED",
      'PPSB' not in male_norm, f"keys: {list(male_norm.keys())}")
check("RBC normalized present (correct unit, EBV available)",
      'Red blood cell concentrate (RBC)' in male_norm)
if 'Red blood cell concentrate (RBC)' in male_norm:
    check("RBC normalized n=3 (all ml doses of patient 1)",
          male_norm['Red blood cell concentrate (RBC)']['n'] == 3)
fib = male_norm.get('Fibrinogen')
check("Fibrinogen normalized applies <500mg exclusion (n=3)",
      fib is not None and fib['n'] == 3,
      f"got {fib}")
if fib is not None:
    check("Fibrinogen normalized min = 2000/94 mg/kg (400 excluded)",
          abs(fib['min'] - 2000 / 94) < 1e-9, f"got {fib['min']}")

# --- Gender percent denominator = treated patients of that gender ---
f_products = gs['products_per_patient']['Female']
rbc_f = f_products['Red blood cell concentrate (RBC)']
check("Female RBC percent_of_gender = 50% (1 of 2 TREATED females, not 1 of 3)",
      abs(rbc_f['percent_of_gender'] - 50.0) < 1e-9,
      f"got {rbc_f['percent_of_gender']}")
check("n_gender_treated=2 and n_gender_total_registry=3 kept explicit",
      rbc_f['n_gender_treated'] == 2 and rbc_f['n_gender_total_registry'] == 3)

# --- Non-M/F exclusion counted and stored ---
excl = gs['excluded_non_mf']
check("Non-M/F patients excluded count stored (registry=2)",
      excl['n_patients_registry'] == 2, f"got {excl}")
check("Non-M/F treated patients counted (=1)",
      excl['n_treated_patients'] == 1, f"got {excl}")

# --------------------------------------------------------------------------
# 9-11. lab_value_quality.py
# --------------------------------------------------------------------------
print("\n[4] lab_value_quality: PID export, albumin alarm guard, clinical range")

n_norm = 10
df_lab = pd.DataFrame({
    'PID': list(range(2000, 2000 + n_norm + 2)),
    # Serum albumin: 10 normal pairs, one wrong-unit (3500), one normal
    'X_433_7_603': [3.5, 4.0, 3.8, 4.2, 3.6, 4.1, 3.9, 4.4, 3.7, 4.3, 3500.0, 3.4],
    'X_433_7_591': [3.6, 4.1, 3.9, 4.3, 3.7, 4.2, 4.0, 4.5, 3.8, 4.4, 4000.0, 3.5],
    # Platelets: thousands-scale values, one full-count, one NEGATIVE (impossible)
    'X_433_7_37':  [170.0, 200.0, 250.0, 300.0, 150.0, 220.0, 180.0, 260.0,
                    240.0, 210.0, 250000.0, -50.0],
    'X_433_7_587': [180.0, 210.0, 260.0, 310.0, 160.0, 230.0, 190.0, 270.0,
                    250.0, 220.0, 260000.0, 200.0],
})

checker = LabValueQualityChecker(df_lab)
check("Default patient ID column resolves to 'PID'", checker.patient_id_col == 'PID')

alb_res = checker.detect_unit_issues('Serum albumin')
check("Albumin unit issue flagged when n_above>0 and majority correct",
      alb_res['unit_issue'] is True, f"got {alb_res}")

# All-normal albumin: no alarm despite pct_below > 90
df_ok = df_lab.copy()
df_ok.loc[10, 'X_433_7_603'] = 3.5
df_ok.loc[10, 'X_433_7_591'] = 4.0
checker_ok = LabValueQualityChecker(df_ok)
alb_ok = checker_ok.detect_unit_issues('Serum albumin')
check("Albumin NO alarm when zero wrong-unit values (n_above=0)",
      alb_ok['unit_issue'] is False, f"got status={alb_ok.get('status')}")

# Clinical range screening
viol = checker.get_range_violations('Platelets')
check("Negative platelet count range-flagged", len(viol) == 1
      and viol.iloc[0]['PID'] == 2011, f"got {len(viol)} rows")
check("Thousands-scale platelets NOT range-flagged (corrected first)",
      2000 not in list(viol.get('PID', [])) and len(viol) == 1)
viol_alb = checker.get_range_violations('Serum albumin')
check("Albumin 3500 mg/dl NOT range-flagged (corrects to 3.5 g/dl)",
      len(viol_alb) == 0, f"got {len(viol_alb)} rows")

outdir = tempfile.mkdtemp(prefix="labq_")
report_path = checker.generate_report(outdir)
export_path = checker.export_problematic_records(outdir)
exported = pd.read_csv(export_path)
check("Problematic-records export carries PID column", 'PID' in exported.columns)
check("Wrong-unit albumin record present with its PID",
      2010 in exported.loc[exported['lab_parameter'] == 'Serum albumin', 'PID'].values)
range_rows = exported[exported['issue'].str.contains('clinical range', case=False, na=False)]
check("Range-flagged record in problematic-records export (PID 2011)",
      2011 in range_rows['PID'].values, f"got {list(range_rows.get('PID', []))}")
with open(report_path) as fh:
    report_text = fh.read()
check("Report documents range-flagged values",
      'Clinical range screening' in report_text and '-50' in report_text)
check("Report shows PID of range-flagged record", 'PID=2011' in report_text)

# --------------------------------------------------------------------------
# 12. Laboratory scale contract (dataset 2_05)
# --------------------------------------------------------------------------
print("\n[6] Laboratory scale contract: negatives never scaled, one-time unit conversion")

df_scale = pd.DataFrame({
    'PID': [1, 2, 3, 4, 5, 6],
    'X_433_7_746': ['1'] * 6,
    'X_433_7_37':  [-150.0, -13000.0, 150.0, 150000.0, None, None],
    'X_433_7_603': [None, None, None, None, 4.0, 4000.0],
})
lab_scale = LabValueQualityChecker(df_scale)
plt_series = lab_scale.get_analysis_series('Platelets', before_col='X_433_7_37')
pb = plt_series['before']
plt_audit = plt_series['audit']['X_433_7_37']
check("Negative platelets audited as nonpositive exclusions (n=2)",
      plt_audit['n_excluded_nonpositive'] == 2,
      f"got {plt_audit}")
check("Negative platelets excluded from the analysis series (NaN)",
      pd.isna(pb.iloc[0]) and pd.isna(pb.iloc[1]))
check("Negatives never scaled (no -150000/-13000000; analysis min > 0)",
      pb.min() > 0, f"got min {pb.min()}")
check("Platelets 150 (thousand scale) converted exactly once -> 150000/ul",
      pb.iloc[2] == 150000.0, f"got {pb.iloc[2]}")
check("Platelets 150000/ul left unchanged", pb.iloc[3] == 150000.0,
      f"got {pb.iloc[3]}")
check("Both platelet forms give the same analysis value",
      pb.iloc[2] == pb.iloc[3])
check("Exactly one platelet unit correction audited",
      plt_audit['n_unit_corrected'] == 1,
      f"got {plt_audit}")

alb_series = lab_scale.get_analysis_series('Serum albumin', before_col='X_433_7_603')
ab = alb_series['before']
check("Albumin 4.0 g/dl left unchanged", ab.iloc[4] == 4.0, f"got {ab.iloc[4]}")
check("Albumin 4000 (mg/dl scale) converted to 4.0 g/dl",
      ab.iloc[5] == 4.0, f"got {ab.iloc[5]}")
alb_audit = alb_series['audit']['X_433_7_603']
check("Albumin conversion audited (n_unit_corrected=1)",
      alb_audit['n_unit_corrected'] == 1,
      f"got {alb_audit}")
check("Albumin analysis unit is the canonical g/dl",
      alb_series['unit'] == 'g/dl', f"got {alb_series['unit']}")

# --------------------------------------------------------------------------
# 13. Review-export field integrity (dataset 2_06)
# --------------------------------------------------------------------------
print("\n[7] Review export: code decoding, dose-0 visibility, CSV field safety")
import csv as _csv
import glob as _glob
import io as _io

df_rev = pd.DataFrame({
    'PID': [21, 21, 22, 22, 23, 23, 24, 24, 24],
    'X_433_0_4': ['M', 'M', 'F', 'F', 'M', 'M', 'F', 'F', 'F'],
    'X_433_0_2': [176.0] * 9, 'X_433_0_3': [94.0] * 9,
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
})
td_rev = make_td(df_rev)
rev_dir = tempfile.mkdtemp(prefix="rev_")
td_rev.calculate_all()
td_rev.export_results(rev_dir)
rev_files = _glob.glob(os.path.join(rev_dir, '**', 'blood_type_incompatible_for_review.csv'),
                       recursive=True)
check("Blood-type review CSV written", bool(rev_files))
if rev_files:
    with open(rev_files[0], newline='') as fh:
        rev_rows = list(_csv.reader(fh))
    rev_hdr = rev_rows[0]
    rev = {r[0]: dict(zip(rev_hdr, r)) for r in rev_rows[1:]}
    check("Follow-up code Y decoded to 'Yes' in the review export",
          rev['21']['Problems_Reported'] == 'Yes',
          f"got {rev['21']['Problems_Reported']!r}")
    check("Follow-up code U decoded to 'Cannot answer'",
          rev['22']['Problems_Reported'] == 'Cannot answer',
          f"got {rev['22']['Problems_Reported']!r}")
    check("752 code 3 decoded to 'Cannot answer'",
          rev['22']['Subsequent_Transfusions'] == 'Cannot answer',
          f"got {rev['22']['Subsequent_Transfusions']!r}")
    check("Dose 0 stays visible in the export (not blanked)",
          rev['21']['Dosage'] == '0.0', f"got {rev['21']['Dosage']!r}")
    check("Free text with comma and line break survives unchanged",
          rev['21']['Problem_Details'] == 'Problem, nach Gabe\nZeile zwei',
          f"got {rev['21']['Problem_Details']!r}")
    check("Columns do not shift around the free-text field (5 records, all fields)",
          len(rev_rows) == 6 and all(len(r) == len(rev_hdr) for r in rev_rows[1:]))
    rows24 = [dict(zip(rev_hdr, r)) for r in rev_rows[1:] if r[0] == '24']
    check("One questionnaire, two flagged administrations: SAME schedule anchored "
          "on the FIRST administration (never re-anchored per administration)",
          len(rows24) == 2
          and all(r['Followup_Window'] == '3-month (vs first administration)'
                  for r in rows24)
          and all(r['Followup_Date'] == '2025-04-01' for r in rows24))
    check("Questionnaire from BEFORE the administration never reported as its follow-up",
          rev['23']['Has_Followup'] == 'No'
          and rev['23']['Followup_Window'] == 'no post-administration follow-up'
          and rev['23']['Problems_Reported'] == ''
          and rev['23']['Followup_Date'] == '')

# --------------------------------------------------------------------------
# 14. Data-quality JSON conformance (dataset 2_07)
# --------------------------------------------------------------------------
print("\n[8] DQ2 export: single observation per product, dose 0, RFC-conformant JSON")
import json as _json

_meta7 = ['meta line %d\n' % i for i in range(1, 8)]
dq_dir = tempfile.mkdtemp(prefix="dq2_")
dq_csv = os.path.join(dq_dir, 'single_obs.csv')
with open(dq_csv, 'w') as f:
    f.writelines(_meta7 + [
        '"PID";"Episode date";"X_433_7_746";"X_433_7_22";"X_433_7_734";"X_433_7_11"\n',
        '31;01/12/2025;5;0;3;2025-01-05\n',
        '32;01/12/2025;4;2500;2;2025-01-06\n',
    ])
from data_quality_module2_dosage import run_dosage_analysis
dq_out = os.path.join(dq_dir, 'out')
os.makedirs(dq_out)
run_dosage_analysis(dq_csv, dq_out)
dq_json_path = os.path.join(dq_out, 'data quality reporting',
                            'data_quality_module2_dosage_consistency.json')
dq_text = open(dq_json_path).read()
check("DQ2 JSON contains no literal NaN/Infinity", 'NaN' not in dq_text and 'Infinity' not in dq_text)


def _reject_constant(c):
    raise ValueError(f"non-RFC JSON constant: {c}")


dq_data = _json.loads(dq_text, parse_constant=_reject_constant)
check("DQ2 JSON parses under a strict RFC 8259 parser", isinstance(dq_data, dict))
check("Dose 0 counted as documented, not missing",
      dq_data['missing_dosages']['total_missing'] == 0,
      f"got {dq_data['missing_dosages']}")
dq_stats_csv = os.path.join(dq_out, 'data quality reporting',
                            'data_quality_module2_dosage_statistics.csv')
stats_df = pd.read_csv(dq_stats_csv)
fib_row = stats_df[stats_df['product_name'] == 'Fibrinogen'].iloc[0]
ppsb_row = stats_df[stats_df['product_name'] == 'PPSB'].iloc[0]
check("Dose 0 visible in the statistics table (Fibrinogen min=0)",
      fib_row['min'] == 0.0 and fib_row['n_with_dosage'] == 1)
check("Single observation: std left empty, never the text NaN",
      pd.isna(ppsb_row['std']) and 'NaN' not in open(dq_stats_csv).read())

# --------------------------------------------------------------------------
# 15. Physicians' range registry boundaries (dataset 2_08)
# --------------------------------------------------------------------------
print("\n[9] Range registry: inclusive physician bounds, one central source")
from transfusion_registry_mapping import CLINICAL_RANGE_REGISTRY, clinical_range
from lab_value_quality import LAB_VALUE_CONFIG

check("Registry carries source and version",
      CLINICAL_RANGE_REGISTRY['version'] == '2026-08-21'
      and 'physician' in CLINICAL_RANGE_REGISTRY['source'])
check("Lab config and DQ4 draw the same platelet bounds from the registry",
      LAB_VALUE_CONFIG['Platelets']['clinical_range'] == (1000, 1000000)
      and clinical_range('platelets') == (1000, 1000000, '/µl'))

df_bounds = pd.DataFrame({
    'PID': [1, 2, 3, 4, 5, 6, 7, 8],
    'X_433_7_746': ['1'] * 8,
    # Hb: floor 1.0 / ceiling 20.0 valid; just outside invalid
    'X_433_7_614': [1.0, 20.0, 0.9, 20.1, None, None, None, None],
    # Platelets: floor 1000 / ceiling 1000000 valid; just outside invalid
    'X_433_7_37':  [None, None, None, None, 1000.0, 1000000.0, 1000001.0, None],
})
lab_b = LabValueQualityChecker(df_bounds)
hb = lab_b.get_analysis_series('Hemoglobin', before_col='X_433_7_614')['before']
check("Hb 1.0 and 20.0 g/dl are VALID (inclusive physician bounds)",
      hb.iloc[0] == 1.0 and hb.iloc[1] == 20.0)
check("Hb 0.9 and 20.1 g/dl are excluded as implausible",
      pd.isna(hb.iloc[2]) and pd.isna(hb.iloc[3]))
plt_b = lab_b.get_analysis_series('Platelets', before_col='X_433_7_37')['before']
check("Platelets 1,000 and 1,000,000 /ul are VALID (physicians' floor lowered)",
      plt_b.iloc[4] == 1000.0 and plt_b.iloc[5] == 1000000.0)
check("Platelets 1,000,001 /ul excluded as implausible", pd.isna(plt_b.iloc[6]))
check("ATIII physician bounds 30-150 % in config",
      LAB_VALUE_CONFIG['Antithrombin activity']['clinical_range'] == (30, 150))

# Registry vs the DEPOSITED machine-readable physician table - value by value
_ranges_csv = None
for _cand in (os.path.join(PIPELINE_DIR, '..', 'physician_value_ranges.csv'),):
    if os.path.exists(_cand):
        _ranges_csv = _cand
        break
check("Deposited physician_value_ranges.csv found", _ranges_csv is not None)
if _ranges_csv:
    with open(_ranges_csv, newline='', encoding='utf-8') as fh:
        _rows = [r for r in _csv.reader(fh, delimiter=';')
                 if r and not r[0].startswith('#')]
    _hdr = _rows[0]
    _tab = [dict(zip(_hdr, r)) for r in _rows[1:]]
    check("Physician table carries all 15 registry parameters",
          sorted(r['parameter'] for r in _tab)
          == sorted(CLINICAL_RANGE_REGISTRY['parameters'].keys()))
    _mism = []
    for r in _tab:
        _reg = CLINICAL_RANGE_REGISTRY['parameters'][r['parameter']]
        if (float(_reg['min']) != float(r['min'])
                or float(_reg['max']) != float(r['max'])
                or bool(_reg.get('nonpositive_impossible'))
                != (r['nonpositive_impossible'] == 'yes')):
            _mism.append(r['parameter'])
    check("Registry bounds match the deposited physician table value by value",
          not _mism, f"mismatches: {_mism}")

# Zero floors BEHAVIOR: a documented 0 is impossible on BOTH paths, and it is
# a finding (documented value), never conflated with a missing value
df_zero = pd.DataFrame({
    'PID': [71, 72, 73, 74],
    'X_433_7_746': ['1'] * 4,
    'X_433_7_374': [0.0, 1.0, None, None],    # Quick: 0 impossible, 1 valid
    'X_433_7_596': [50.0, 50.0, None, None],
    'X_433_7_585': [None, None, 0.0, None],   # fibrinogen: 0 impossible
    'X_433_7_586': [None, None, 100.0, None],
    'X_433_7_603': [None, None, None, 0.0],   # albumin: 0 impossible
    'X_433_7_591': [None, None, None, 3.5],
})
lab_z = LabValueQualityChecker(df_zero)
qs = lab_z.get_analysis_series("Quick's test", before_col='X_433_7_374')
check("Quick 0 excluded from the analysis, Quick 1 kept (floor exclusive at zero)",
      pd.isna(qs['before'].iloc[0]) and qs['before'].iloc[1] == 1.0)
check("Quick 0 counted as NON-POSITIVE finding, not as missing",
      qs['audit']['X_433_7_374']['n_excluded_nonpositive'] == 1
      and qs['audit']['X_433_7_374']['n_raw'] == 2)
qv_z = lab_z.get_range_violations("Quick's test")
check("QC range screening flags the documented Quick 0 (same verdict as statistics)",
      len(qv_z) == 1 and qv_z.iloc[0]['PID'] == 71)
fv_z = lab_z.get_range_violations('Fibrinogen')
av_z = lab_z.get_range_violations('Serum albumin')
check("Fibrinogen 0 and albumin 0 flagged as impossible in QC",
      len(fv_z) == 1 and fv_z.iloc[0]['PID'] == 73
      and len(av_z) == 1 and av_z.iloc[0]['PID'] == 74)

# --------------------------------------------------------------------------
# 16. Negative values in QC artifacts; EBV same-row rule (dataset 2_09)
# --------------------------------------------------------------------------
print("\n[10] QC artifacts: negatives never scaled; EBV never composited")

df_negqc = pd.DataFrame({
    'PID': [41, 42],
    'X_433_7_746': ['1', '1'],
    'X_433_7_37': [-150.0, 200.0],
    'X_433_7_587': [210000.0, 210.0],
})
lab_n = LabValueQualityChecker(df_negqc)
neg_dir = tempfile.mkdtemp(prefix="negqc_")
lab_n.generate_report(neg_dir)
lab_n.export_problematic_records(neg_dir)
qc_texts = ''
for fn in os.listdir(neg_dir):
    qc_texts += open(os.path.join(neg_dir, fn), encoding='utf-8').read()
check("No artifact contains a scaled negative (-150000)",
      '-150000' not in qc_texts and '-1.5e' not in qc_texts)
check("Artifacts state the negative is never scaled",
      'never scaled' in qc_texts)
with open(os.path.join(neg_dir, 'lab_value_unit_issues.csv'), newline='') as fh:
    qc_rows = list(_csv.DictReader(fh))
check("Values already in /ul (210000) never themselves flagged",
      all('210000' not in (r.get('flagged_values') or '') for r in qc_rows))

df_ebv = pd.DataFrame({
    'PID': [51, 51, 51],
    'X_433_7_746': ['1', None, None],
    'X_433_0_2': [176.0, None, None],
    'X_433_0_3': [None, 94.0, None],
    'X_433_0_4': [None, None, 'M'],
})
td_ebv = make_td(df_ebv)
import contextlib as _ctx
import io as _io
with _ctx.redirect_stdout(_io.StringIO()):
    ebv_series = td_ebv._calculate_estimated_blood_volume()
check("Height, weight, sex on three different rows -> NO EBV (no composite)",
      pd.isna(ebv_series.loc[51]))
df_ebv_ok = pd.DataFrame({
    'PID': [52],
    'X_433_7_746': ['1'],
    'X_433_0_2': [176.0], 'X_433_0_3': [94.0], 'X_433_0_4': ['M'],
})
with _ctx.redirect_stdout(_io.StringIO()):
    ebv_ok = make_td(df_ebv_ok)._calculate_estimated_blood_volume()
check("Same-row height/weight/sex -> EBV computed",
      pd.notna(ebv_ok.loc[52]) and 4.0 < ebv_ok.loc[52] < 8.0)

# --------------------------------------------------------------------------
# 17. DQ2 unit and missing-dose checks for products 6, 8, 10 (dataset 2_10)
# --------------------------------------------------------------------------
print("\n[11] DQ2: iron i.v., EPO, and oral iron are checked")

_meta7b = ['meta line %d\n' % i for i in range(1, 8)]
d_prod = tempfile.mkdtemp(prefix="dq2b_")
prod_csv = os.path.join(d_prod, 'products.csv')
with open(prod_csv, 'w') as f:
    f.writelines(_meta7b + [
        '"PID";"Episode date";"X_433_7_746";"X_433_7_22";"X_433_7_734";"X_433_7_11"\n',
        '61;01/12/2025;6;100;1;2025-01-05\n',   # iron i.v. dosed in ml (wrong; expect mg)
        '62;01/12/2025;8;;;2025-01-06\n',        # EPO with missing dose
        '63;01/12/2025;10;100;2;2025-01-07\n',   # oral iron dosed in IU (wrong; expect mg)
        '64;01/12/2025;6;200;3;2025-01-08\n',    # iron i.v. correctly in mg
    ])
from data_quality_module2_dosage import run_dosage_analysis as _run_dq2
_dq2_out = os.path.join(d_prod, 'out')
os.makedirs(_dq2_out)
import contextlib as _ctx2
with _ctx2.redirect_stdout(_io.StringIO()):
    dq2b = _run_dq2(prod_csv, _dq2_out)
issues_b = dq2b.results['unit_consistency']['issues']
wrong_pids = sorted(str(i['PID']) for i in issues_b)
check("Wrong units for iron i.v. (ml) and oral iron (IU) flagged",
      wrong_pids == ['61', '63'], f"got {wrong_pids}")
check("Correct mg dose for iron i.v. NOT flagged",
      '64' not in wrong_pids)
check("Missing EPO dose counted as missing",
      dq2b.results['missing_dosages']['total_missing'] == 1,
      f"got {dq2b.results['missing_dosages']}")
cov_b = dq2b.results['unit_check_coverage']
check("Coverage matrix: products 6, 8, 10 now 'checked'",
      all(cov_b[c]['status'] == 'checked' for c in ('6', '8', '10')))

# --------------------------------------------------------------------------
print("\n" + "=" * 60)
print(f"RESULTS: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
