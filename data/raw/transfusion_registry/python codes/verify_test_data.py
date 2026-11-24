"""Verification of regenerated synthetic datasets against the dictionary
and the seeded-error oracle JSONs."""
import json
import os
import sys
import pandas as pd

# Data files (test_data_*.csv, seeded_errors_*.json) live in the project root,
# one level above this script's directory ("python codes/").
def _first_existing(base, candidates):
    for rel in candidates:
        p = os.path.normpath(os.path.join(base, rel))
        if os.path.exists(os.path.join(p, 'test_data_150patients.csv')):
            return p
    return os.path.normpath(os.path.join(base, candidates[-1]))

ROOT = _first_existing(os.path.dirname(os.path.abspath(__file__)),
                       ['../synthetic test data', '..'])

RBC_COMPATIBLE = {
    '0': ['0', 'A', 'B', 'AB'],
    'A': ['A', 'AB'],
    'B': ['B', 'AB'],
    'AB': ['AB'],
}

failures = []

def check(name, cond, detail=''):
    status = 'PASS' if cond else 'FAIL'
    print(f"  [{status}] {name}" + (f" -- {detail}" if detail else ''))
    if not cond:
        failures.append(name)

def verify(n):
    csv_path = os.path.join(ROOT, f'test_data_{n}patients.csv')
    oracle_path = os.path.join(ROOT, f'seeded_errors_{n}.json')
    with open(oracle_path, encoding='utf-8') as f:
        oracle = json.load(f)
    errors = oracle['errors']

    print(f"\n===== Dataset n={n}: {os.path.basename(csv_path)} =====")
    df = pd.read_csv(csv_path, sep=';', skiprows=7, dtype=str, encoding='utf-8')
    print(f"  rows={len(df)}, cols={len(df.columns)}, patients={df['PID'].nunique()}")
    check('patient count', df['PID'].nunique() == n)

    df['PID_i'] = df['PID'].astype(int)

    # --- product codes in 1..11 ---
    prods = df['X_433_7_746'].dropna()
    valid = prods.astype(float).astype(int).isin(range(1, 12))
    check('all product codes in 1..11', valid.all(),
          f"codes present: {sorted(prods.astype(float).astype(int).unique())}")

    # --- every administration has dosage value + unit except seeded missing ---
    admin = df[df['X_433_7_746'].notna()].copy()
    missing_dose = admin[admin['X_433_7_22'].isna() | admin['X_433_7_734'].isna()]
    missing_pids = set(missing_dose['PID_i'])
    check('dosage 22+734 filled except seeded missing',
          missing_pids == set(errors['missing_dosage']),
          f"missing-dosage rows belong to PIDs {sorted(missing_pids)}; oracle {errors['missing_dosage']}")
    units = admin['X_433_7_734'].dropna().astype(float).astype(int)
    check('unit codes in {1,2,3}', units.isin([1, 2, 3]).all())

    # unit codes correct per product except seeded wrong-unit patients
    expected_unit = {1: 1, 2: 1, 3: 1, 7: 1, 11: 1, 4: 2, 9: 2, 5: 3, 6: 3, 10: 3}
    ad = admin[admin['X_433_7_22'].notna()].copy()
    ad['prod'] = ad['X_433_7_746'].astype(float).astype(int)
    ad['unit'] = ad['X_433_7_734'].astype(float).astype(int)
    ad['exp'] = ad['prod'].map(expected_unit)
    bad_unit = ad[ad['unit'] != ad['exp']]
    bad_pids = set(bad_unit['PID_i'])
    seeded_wrong = set(errors['ppsb_wrong_unit']) | set(errors['fib_wrong_unit'])
    check('non-standard units only on seeded wrong-unit patients',
          bad_pids == seeded_wrong,
          f"non-standard-unit PIDs {sorted(bad_pids)}; oracle {sorted(seeded_wrong)}")
    ppsb_bad = bad_unit[bad_unit['prod'] == 4]
    check('PPSB wrong-unit rows use code 1 (ml)',
          (ppsb_bad['unit'] == 1).all() and len(ppsb_bad) == len(errors['ppsb_wrong_unit']))
    fib_bad = bad_unit[bad_unit['prod'] == 5]
    check('Fibrinogen wrong-unit rows use code 2 (IE)',
          (fib_bad['unit'] == 2).all() and len(fib_bad) == len(errors['fib_wrong_unit']))
    fib_ok = ad[(ad['prod'] == 5) & (ad['unit'] == 3)]
    low_fib = set(fib_ok[fib_ok['X_433_7_22'].astype(float) < 500]['PID_i'])
    check('fibrinogen <500mg only on seeded patients',
          low_fib == set(errors['fib_too_low']),
          f"{sorted(low_fib)} vs oracle {errors['fib_too_low']}")

    # --- MAT rows carry 747-750 ---
    mat = admin[admin['X_433_7_746'].astype(float).astype(int) == 11]
    check('MAT rows have 747/748/749/750 filled',
          len(mat) > 0 and all(mat[c].notna().all() for c in
              ['X_433_7_747', 'X_433_7_748', 'X_433_7_749', 'X_433_7_750']),
          f"{len(mat)} MAT administrations")

    # --- follow-up rows have 741/742/737/740/752 filled ---
    fu = df[df['X_435_0_751'].notna()]
    fu_ok = all(fu[c].notna().all() for c in
                ['X_435_0_741', 'X_435_0_742', 'X_435_0_737', 'X_435_0_740', 'X_435_0_752'])
    check('follow-up rows have 741/742/737/740/752 filled', fu_ok, f"{len(fu)} follow-up rows")
    check('737/740 codes in Y/N/U',
          fu['X_435_0_737'].isin(['Y', 'N', 'U']).all() and fu['X_435_0_740'].isin(['Y', 'N', 'U']).all())
    check('741 codes in 0-5', fu['X_435_0_741'].astype(float).isin(range(0, 6)).all())
    check('742 codes in 0-9', fu['X_435_0_742'].astype(float).isin(range(0, 10)).all())
    check('752 codes in 0-3', fu['X_435_0_752'].astype(float).isin(range(0, 4)).all())

    # refusal-0 seeded
    refusal_pids = set(fu[(fu['X_435_0_741'].astype(float) == 0) |
                          (fu['X_435_0_742'].astype(float) == 0)]['PID_i'])
    check('refusal-0 answers exactly on seeded patients',
          refusal_pids == set(errors['followup_refusal_zero']),
          f"{sorted(refusal_pids)} vs oracle {errors['followup_refusal_zero']}")

    # identical duplicates: same outcome fields, different dates, both in 68-113d window
    fu_cols = [c for c in df.columns if c.startswith('X_435_') and c != 'X_435_0_751']
    admin_dates = pd.to_datetime(admin['X_433_7_11'])
    first_admin = admin.assign(d=admin_dates).groupby('PID_i')['d'].min()
    ok_dup = True
    for pid in errors['duplicate_identical']:
        rows = fu[fu['PID_i'] == pid]
        dates = pd.to_datetime(rows['X_435_0_751'])
        days = (dates - first_admin[pid]).dt.days
        same_outcomes = all(rows[c].fillna('').nunique() == 1 for c in fu_cols)
        ok_dup &= (len(rows) == 2 and dates.nunique() == 2 and same_outcomes
                   and days.between(68, 113).all())
    check('identical duplicates: 2 in-window rows, equal answers, different dates', ok_dup)

    ok_con = True
    for pid in errors['duplicate_conflicting']:
        rows = fu[fu['PID_i'] == pid]
        days = (pd.to_datetime(rows['X_435_0_751']) - first_admin[pid]).dt.days
        differs = any(rows[c].fillna('').nunique() > 1 for c in fu_cols)
        ok_con &= (len(rows) == 2 and differs and days.between(68, 113).all())
    check('conflicting duplicates: 2 in-window rows with differing answers', ok_con)

    ok_early = all(
        (pd.to_datetime(fu[fu['PID_i'] == p]['X_435_0_751']) - first_admin[p]).dt.days.lt(68).all()
        and len(fu[fu['PID_i'] == p]) == 1
        for p in errors['followup_too_early'])
    check('too-early follow-ups <68 days', ok_early)
    ok_between = all(
        (pd.to_datetime(fu[fu['PID_i'] == p]['X_435_0_751']) - first_admin[p]).dt.days.between(114, 272).all()
        for p in errors['followup_between'])
    check('between-window follow-ups in 114-272 days', ok_between)

    # --- intervention date parses; LOS positive except seeded ---
    idate = pd.to_datetime(df['X_433_0_8'], format='%Y-%m-%d', errors='coerce')
    check('X_433_0_8 parses as YYYY-MM-DD dates',
          idate.notna().sum() == df['X_433_0_8'].notna().sum(),
          f"{df['X_433_0_8'].notna().sum()} values, all parseable")
    check('X_433_0_9 is SNOMED integer', df['X_433_0_9'].dropna().str.fullmatch(r'\d+').all())
    check('X_433_0_10 in {1,2}', df['X_433_0_10'].dropna().isin(['1', '2']).all())
    ddate = pd.to_datetime(df['X_433_0_753'], errors='coerce')
    both = df[idate.notna() & ddate.notna()].copy()
    both['los'] = (ddate - idate).dt.days
    neg_pids = set(both[both['los'] < 0]['PID_i'])
    check('negative LOS exactly on seeded patients',
          neg_pids == set(errors['negative_los']),
          f"{sorted(neg_pids)} vs oracle {errors['negative_los']}")

    # --- blood types ---
    for col in ['X_433_0_17', 'X_433_7_19']:
        check(f'{col} ABO codes valid (A/B/AB/0)',
              df[col].dropna().isin(['A', 'B', 'AB', '0']).all())
    for col in ['X_433_0_18', 'X_433_7_20']:
        check(f'{col} Rh codes valid (0/1/2)',
              df[col].dropna().astype(float).astype(int).isin([0, 1, 2]).all())

    pairs = df[df['X_433_0_17'].notna() & df['X_433_7_19'].notna() &
               (df['X_433_7_746'].astype(float) == 1)].copy()
    pairs['incompat'] = pairs.apply(
        lambda r: r['X_433_0_17'] not in RBC_COMPATIBLE[r['X_433_7_19']], axis=1)
    incompat_pids = set(pairs[pairs['incompat']]['PID_i'])
    check('RBC ABO-incompatible pairs exactly on seeded patients',
          incompat_pids == set(errors['blood_type_incompatible']),
          f"{sorted(incompat_pids)} vs oracle {errors['blood_type_incompatible']}")
    nonident = pairs[(~pairs['incompat']) & (pairs['X_433_0_17'] != pairs['X_433_7_19'])]
    check('compatible-non-identical pairs present and on seeded patients',
          set(nonident['PID_i']) == set(errors['blood_type_compatible_nonidentical']),
          f"{sorted(set(nonident['PID_i']))} vs oracle {errors['blood_type_compatible_nonidentical']}")

    # --- Verika share ---
    verika = df[df['Location'] == 'Verika (Teststandort)']
    check('Verika test-location patients present',
          set(verika['PID_i']) == set(errors['test_location']))

    # --- indications land in per-product columns ---
    ind_map = {1: 'X_433_7_593', 2: 'X_433_7_604', 3: 'X_433_7_605', 4: 'X_433_7_606',
               5: 'X_433_7_607', 6: 'X_433_7_608', 7: 'X_433_7_610', 9: 'X_433_7_612'}
    ok_ind = True
    for code, col in ind_map.items():
        sub = admin[admin['X_433_7_746'].astype(float).astype(int) == code]
        if len(sub):
            ok_ind &= sub[col].notna().all()
    check('indication codes filled in correct per-product columns', ok_ind)
    check('X_433_7_593 codes in 1-5 (RBC Hb thresholds)',
          df['X_433_7_593'].dropna().astype(float).isin(range(1, 6)).all())

    # --- product concentration 613 only albumin, codes 4/5/20/25 ---
    conc = admin[admin['X_433_7_613'].notna()]
    check('613 (product concentration) only on albumin, codes in {4,5,20,25}',
          (conc['X_433_7_746'].astype(float) == 7).all() and
          conc['X_433_7_613'].astype(float).isin([4, 5, 20, 25]).all())

    return df

for n in (100, 150):
    verify(n)

# --- loader smoke test ---
print("\n===== Loader smoke test (test_data_100patients.csv) =====")
# The pipeline modules live next to this script ("python codes/").
CODE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CODE_DIR)
os.chdir(CODE_DIR)
from transfusion_data_loader import TransfusionDataLoader
loader = TransfusionDataLoader()  # dictionaries resolve next to the code folder
loader.load_data(os.path.join(ROOT, 'test_data_100patients.csv'))
dfc = loader.df_clean
print(f"  loaded clean rows: {len(dfc)}, patients: {dfc['PID'].nunique()}")
check('loader ran without crash', True)
check('Verika filter removed test location',
      (dfc['Location'] != 'Verika (Teststandort)').all() if 'Location' in dfc.columns else False,
      f"remaining locations: {sorted(dfc['Location'].dropna().unique())}")

print("\n" + "=" * 60)
if failures:
    print(f"RESULT: {len(failures)} FAILURES: {failures}")
    sys.exit(1)
print("RESULT: ALL CHECKS PASSED")
