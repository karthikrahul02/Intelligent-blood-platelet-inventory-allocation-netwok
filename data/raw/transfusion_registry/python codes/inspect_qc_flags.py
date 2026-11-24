"""
Closed-environment inspection helper for delta-run QC flags.

Prints, for a given export CSV:
  1. The five patients with the most product administrations - product mix,
     number of distinct administration dates, date span, and episode count -
     to judge whether an extreme administration count is clinically plausible
     (e.g. a long ICU course) or a data entry issue.
  2. Patients whose computed age at first episode is implausible (< 0 or
     > 110 years), from year of birth (X_541_0_1) vs. first episode year -
     these distort age means/SDs (an SD in the hundreds indicates one such
     record).
  3. Age computability in the non-transfusion cohort (patients without any
     product administration).

Output contains PIDs and aggregated counts only; run it inside the closed
registry environment and keep the output there.

Usage:
    python3 inspect_qc_flags.py <export_csv>
    python3 inspect_qc_flags.py "../synthetic test data/test_data_150patients.csv"
"""
import os
import sys

import pandas as pd

PRODUCT_NAMES = {
    '1': 'RBC', '2': 'FFP', '3': 'PC', '4': 'PPSB', '5': 'Fibrinogen',
    '6': 'Iron i.v.', '7': 'Albumin', '8': 'Erythropoetin', '9': 'ATIII',
    '10': 'Oral iron', '11': 'MAT',
}


def norm(s):
    return s.astype(str).str.replace(r'\.0$', '', regex=True)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    csv = sys.argv[1]
    if not os.path.exists(csv):
        print(f"Error: file not found: {csv}")
        sys.exit(1)

    df = pd.read_csv(csv, sep=';', skiprows=7, dtype=str,
                     keep_default_na=False, encoding='utf-8')
    df = df[df['Location'] != 'Verika (Teststandort)']

    admin = df[df['X_433_7_746'] != ''].copy()
    admin['product'] = norm(admin['X_433_7_746']).map(PRODUCT_NAMES).fillna('?')

    print("=" * 70)
    print("1. TOP 5 PATIENTS BY ADMINISTRATION COUNT")
    print("=" * 70)
    top = admin.groupby('PID').size().sort_values(ascending=False).head(5)
    for pid, n in top.items():
        rows = admin[admin['PID'] == pid]
        mix = rows['product'].value_counts().to_dict()
        dates = pd.to_datetime(rows['X_433_7_11'], errors='coerce').dropna()
        span = (f"{dates.min().date()} to {dates.max().date()} "
                f"({(dates.max() - dates.min()).days + 1} days, "
                f"{dates.dt.date.nunique()} distinct days)") if len(dates) else "no dates"
        episodes = rows['Episode number'].nunique()
        print(f"\nPID {pid}: {n} administrations across {episodes} episode(s)")
        print(f"  products: {mix}")
        print(f"  administration dates: {span}")
    print("\nInterpretation: many administrations on many distinct days across a")
    print("long stay can be a plausible intensive course; a large count on one")
    print("or few days, or duplicated identical rows, suggests a data issue.")

    print()
    print("=" * 70)
    print("2. IMPLAUSIBLE AGE RECORDS (age at first episode < 0 or > 110)")
    print("=" * 70)
    birth = pd.to_numeric(df['X_541_0_1'], errors='coerce').groupby(df['PID']).first()
    ep_year = pd.to_datetime(df['Episode date'], format='%d/%m/%Y',
                             errors='coerce').dt.year.groupby(df['PID']).min()
    age = ep_year - birth
    bad = age[(age < 0) | (age > 110)]
    if bad.empty:
        print("None found.")
    else:
        for pid, a in bad.items():
            print(f"PID {pid}: year of birth {birth[pid]:.0f}, first episode "
                  f"{ep_year[pid]:.0f} -> age {a:.0f} years  <- REVIEW IN REGISTRY")
    n_missing = int(age.isna().sum())
    if n_missing:
        print(f"({n_missing} patient(s) with missing birth year or episode date)")

    print()
    print("=" * 70)
    print("3. NON-TRANSFUSION COHORT AGE COMPUTABILITY")
    print("=" * 70)
    treated = set(admin['PID'].unique())
    untreated = sorted(set(df['PID'].unique()) - treated)
    if not untreated:
        print("No patients without administrations.")
    else:
        u_age = age[age.index.isin(untreated)]
        print(f"Patients without any product administration: {len(untreated)}")
        print(f"  with computable age (birth year + episode date): "
              f"{int(u_age.notna().sum())}")
        print(f"  without: {int(u_age.isna().sum())}")


if __name__ == '__main__':
    main()
