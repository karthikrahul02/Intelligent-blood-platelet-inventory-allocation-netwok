"""
Tests for enrollment_filter.py.

Two parts: a small hand-constructed export in which the correct cohort is
known by design (boundary cases included), and the synthetic 150-patient
dataset, for which the expected cohort is computed independently and
compared with the filter's output.

Run from the "python codes" directory:
    python3 test_enrollment_filter.py
"""
import os
import sys
import tempfile

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from enrollment_filter import filter_by_enrollment_cutoff

passed, failed = [], []


def check(name, cond, detail=''):
    (passed if cond else failed).append(name)
    print(('PASS' if cond else 'FAIL'), name + (f' -- {detail}' if detail else ''))


# ---------------------------------------------------------------- hand-made export
# Patient 1: enrolled before cutoff, has a follow-up row dated AFTER the
#            cutoff -> retained completely (both rows)
# Patient 2: enrolled exactly ON the cutoff -> retained (boundary, <=)
# Patient 3: enrolled after the cutoff -> excluded
# Patient 4: no parseable episode date -> excluded and reported
CUTOFF = '2026-01-15'
header = ['meta line %d\n' % i for i in range(1, 8)]
header.append('"PID";"Episode date";"X_435_0_751"\n')
rows = [
    '1;01/12/2025;\n',
    '1;01/12/2025;2026-03-05\n',   # follow-up completed after the cutoff
    '2;15/01/2026;\n',
    '3;16/01/2026;\n',
    '4;;\n',
]
tmpdir = tempfile.mkdtemp()
src = os.path.join(tmpdir, 'mini.csv')
with open(src, 'w', encoding='utf-8') as f:
    f.writelines(header + rows)

out, stats = filter_by_enrollment_cutoff(src, CUTOFF)

flt = pd.read_csv(out, sep=';', skiprows=7, dtype=str, keep_default_na=False)
check('cohort = patients 1 and 2', sorted(flt['PID'].unique()) == ['1', '2'],
      f"got {sorted(flt['PID'].unique())}")
check('enrollment ON cutoff retained (<=)', '2' in set(flt['PID']))
check('enrolled after cutoff excluded', '3' not in set(flt['PID']))
check('undatable patient excluded and reported',
      '4' not in set(flt['PID']) and stats['undatable_pids'] == ['4'])
check('ALL rows of retained patients kept (incl. follow-up after cutoff)',
      len(flt[flt['PID'] == '1']) == 2 and
      (flt['X_435_0_751'] == '2026-03-05').sum() == 1)
with open(out, encoding='utf-8') as f:
    out_header = [f.readline() for _ in range(8)]
check('first 8 lines copied verbatim', out_header == header)
check('stats counts correct',
      stats['patients_input'] == 4 and stats['patients_retained'] == 2 and
      stats['patients_excluded_after_cutoff'] == 1 and
      stats['patients_excluded_no_enrollment_date'] == 1 and
      stats['rows_input'] == 5 and stats['rows_retained'] == 3)

# ---------------------------------------------------------------- synthetic dataset
def _syn_dir(base):
    for rel in ('../synthetic test data', '..'):
        d = os.path.normpath(os.path.join(base, rel))
        if os.path.exists(os.path.join(d, 'test_data_150patients.csv')):
            return d
    return os.path.normpath(os.path.join(base, '..'))

SYN = os.path.join(_syn_dir(os.path.dirname(os.path.abspath(__file__))),
                   'test_data_150patients.csv')
raw = pd.read_csv(SYN, sep=';', skiprows=7, dtype=str, keep_default_na=False)
enroll = pd.to_datetime(raw['Episode date'], format='%d/%m/%Y').groupby(raw['PID']).min()
cutoff = enroll.quantile(0.5)  # mid-range: some patients before, some after
expected = set(enroll[enroll <= cutoff].index)
check('synthetic enrollment dates span the cutoff',
      0 < len(expected) < raw['PID'].nunique(),
      f"{len(expected)} of {raw['PID'].nunique()} patients on/before "
      f"{cutoff.date()}")

out2, stats2 = filter_by_enrollment_cutoff(
    SYN, cutoff.strftime('%Y-%m-%d'), os.path.join(tmpdir, 'syn_filtered.csv'))
flt2 = pd.read_csv(out2, sep=';', skiprows=7, dtype=str, keep_default_na=False)
check('synthetic cohort matches independent computation',
      set(flt2['PID'].unique()) == expected)
check('per-patient row counts unchanged for retained patients',
      flt2.groupby('PID').size().to_dict() ==
      raw[raw['PID'].isin(expected)].groupby('PID').size().to_dict())
check('all values of retained rows unchanged',
      flt2.reset_index(drop=True).equals(
          raw[raw['PID'].isin(expected)].reset_index(drop=True)))
fu_after = raw[raw['PID'].isin(expected) & (raw['X_435_0_751'] != '')].copy()
fu_after_dates = pd.to_datetime(fu_after['X_435_0_751'], errors='coerce')
check('cohort keeps follow-ups completed after the cutoff',
      (fu_after_dates > cutoff).any(),
      f"{int((fu_after_dates > cutoff).sum())} follow-up records after cutoff retained")

# filtered file loads through the standard data loader
from transfusion_data_loader import TransfusionDataLoader
loader = TransfusionDataLoader()  # default base_path: project root (dictionaries)
loader.load_data(out2)
check('filtered file loads through the standard loader',
      set(loader.df_clean['PID'].astype(str).unique()) <= expected)

# ---------------------------------------------------------------- cohort whitelist
# Hand-made January/August export pair.
# January cohort: patient 1 (treated), patient 2 (consent-only, no episode
# date), patient 4 (registered, treated only AFTER the cap in August).
# August additionally has patient 3 (enrolled after January -> dropped).
from enrollment_filter import filter_by_cohort_whitelist

CAP = '2026-01-15'
wl_header = ['meta line %d\n' % i for i in range(1, 8)]
wl_header.append('"PID";"Episode date";"Unique ID (Form_Record_DataElement):";'
                 '"X_433_7_746";"X_433_7_11";"X_433_7_22";"X_435_0_751";"X_435_0_741"\n')
january_rows = [
    '1;01/12/2025;U1;1;2025-12-01;250;;\n',  # dated administration
    '1;01/12/2025;U2;1;;300;;\n',            # UNDATED administration documented
                                             #   in January (record ID U2)
    '1;01/12/2025;;2;;100;;\n',              # undated administration, no record ID
    '2;;U3;;;;;\n',                          # consent-only registrant
    '4;10/01/2026;U4;;;;;\n',                # registered, untreated in January
]
august_rows = [
    '1;01/12/2025;U1;1;2025-12-01;250;;\n',  # pilot administration -> kept
    '1;01/12/2025;U2;1;;350;;\n',            # undated, record ID matches January,
                                             #   dose corrected 300->350 -> kept
                                             #   WITH the corrected value
    '1;01/12/2025;;2;;100;;\n',              # undated, no record ID, content
                                             #   matches January -> kept
    '1;01/12/2025;U9;1;;400;;\n',            # STRADDLING-UNDATED: undated, NOT in
                                             #   January (new record ID, new content)
                                             #   under pre-cap episode -> dropped
    '1;01/12/2025;1;1;2026-02-20;250;;\n',   # straddling dated: pre-cap episode,
                                             #   post-cap administration -> dropped
    '1;20/02/2026;;;;;;\n',                  # post-cap episode record row -> dropped
    '1;01/12/2025;;;;;2026-03-05;3\n',       # follow-up after cap -> kept
    '2;;U3;;;;;\n',                          # consent-only row -> kept (reported)
    '4;10/01/2026;U4;;;;;\n',                # pre-cap episode row, no administration -> kept
    '4;01/02/2026;;1;2026-02-01;200;;\n',    # post-cap dated administration -> dropped
    '4;01/02/2026;;1;;150;;\n',              # UNDATED administration, not documented
                                             #   in January -> dropped (patient must
                                             #   stay untreated)
    '4;01/02/2026;;;;;2026-05-10;4\n',       # late follow-up -> kept
    '3;05/03/2026;;1;2026-03-05;500;;\n',    # not in January cohort -> dropped
]
jan_csv = os.path.join(tmpdir, 'january.csv')
aug_csv = os.path.join(tmpdir, 'august.csv')
with open(jan_csv, 'w', encoding='utf-8') as f:
    f.writelines(wl_header + january_rows)
with open(aug_csv, 'w', encoding='utf-8') as f:
    f.writelines(wl_header + august_rows)

out3, st3 = filter_by_cohort_whitelist(aug_csv, jan_csv, episode_cutoff=CAP)
flt3 = pd.read_csv(out3, sep=';', skiprows=7, dtype=str, keep_default_na=False)
check('whitelist cohort = January PIDs exactly',
      sorted(flt3['PID'].unique()) == ['1', '2', '4'],
      f"got {sorted(flt3['PID'].unique())}")
check('post-January patient dropped entirely', '3' not in set(flt3['PID']))
check('consent-only patient retained', (flt3['PID'] == '2').sum() == 1)
admin3 = flt3[flt3['X_433_7_746'] != '']
dated = admin3[admin3['X_433_7_11'] != '']
check('straddling episode: only PRE-CAP dated administrations survive',
      (pd.to_datetime(dated['X_433_7_11']) <= pd.Timestamp(CAP)).all() and
      len(dated) == 1,
      f"{len(dated)} dated administration(s) kept")
check('post-cap administration under pre-cap episode date dropped',
      '2026-02-20' not in set(flt3['X_433_7_11']))
check('undated administration matched by record ID kept, with corrected value',
      (admin3['X_433_7_22'] == '350').sum() == 1 and
      st3['admin_undated_kept_by_recordid'] == 1)
check('undated administration matched by content kept',
      (admin3['X_433_7_22'] == '100').sum() == 1 and
      st3['admin_undated_kept_by_content'] == 1)
check('straddling-undated: undated post-Jan administration under pre-Jan '
      'episode dropped',
      '400' not in set(admin3['X_433_7_22']) and
      st3['admin_undated_dropped_unmatched'] == 2 and
      st3['undated_unmatched_pids'] == ['1', '4'])
check('late-treated registrant has NO administrations (stays untreated)',
      ((flt3['PID'] == '4') & (flt3['X_433_7_746'] != '')).sum() == 0)
check('follow-up rows beyond the cap retained (both patients)',
      set(flt3.loc[flt3['X_435_0_751'] != '', 'PID']) == {'1', '4'})
check('undatable clinical row kept and reported',
      st3['clinical_rows_undatable_kept'] == 1 and
      st3['undatable_clinical_pids'] == ['2'])
check('whitelist stats counts',
      st3['cohort_size'] == 3 and st3['patients_retained'] == 3 and
      st3['patients_dropped_not_in_cohort'] == 1 and
      st3['admin_rows_dropped_after_cap'] == 4 and
      st3['clinical_rows_dropped_after_cap'] == 1 and
      st3['admin_rows_retained'] == 3 and
      st3['followup_rows_retained'] == 2)

# consume semantics: two identical undated rows, one January counterpart ->
# exactly one kept
jan4_csv = os.path.join(tmpdir, 'january4.csv')
aug4_csv = os.path.join(tmpdir, 'august4.csv')
with open(jan4_csv, 'w', encoding='utf-8') as f:
    f.writelines(wl_header + ['7;01/12/2025;;3;;2;;\n'])
with open(aug4_csv, 'w', encoding='utf-8') as f:
    f.writelines(wl_header + ['7;01/12/2025;;3;;2;;\n',
                              '7;01/12/2025;;3;;2;;\n'])
_, st_dup = filter_by_cohort_whitelist(aug4_csv, jan4_csv, episode_cutoff=CAP,
                                       output_csv=os.path.join(tmpdir, 'd.csv'))
check('each January row justifies at most one August row',
      st_dup['admin_undated_kept_by_content'] == 1 and
      st_dup['admin_undated_dropped_unmatched'] == 1)

# a cohort patient whose only rows are post-cap clinical rows must be
# reported as vanished (they would silently shrink the denominator)
jan3_csv = os.path.join(tmpdir, 'january3.csv')
aug3_csv = os.path.join(tmpdir, 'august3.csv')
with open(jan3_csv, 'w', encoding='utf-8') as f:
    f.writelines(wl_header + january_rows + ['5;01/11/2025;;1;2025-11-01;100;;\n'])
with open(aug3_csv, 'w', encoding='utf-8') as f:
    f.writelines(wl_header + august_rows + ['5;20/03/2026;;1;2026-03-20;100;;\n'])
_, st_van = filter_by_cohort_whitelist(aug3_csv, jan3_csv, episode_cutoff=CAP,
                                       output_csv=os.path.join(tmpdir, 'v.csv'))
check('cohort patient with all rows beyond cap reported as vanished',
      st_van['cohort_pids_no_rows_after_cap'] == ['5'])

# missing-from-data warning: a cohort patient absent from the newer export
jan2_csv = os.path.join(tmpdir, 'january2.csv')
with open(jan2_csv, 'w', encoding='utf-8') as f:
    f.writelines(wl_header + january_rows + ['9;01/10/2025;;;;;;\n'])
_, st_missing = filter_by_cohort_whitelist(aug_csv, jan2_csv, episode_cutoff=CAP,
                                           output_csv=os.path.join(tmpdir, 'm.csv'))
check('cohort patient absent from data reported',
      st_missing['cohort_pids_missing_from_data'] == ['9'])

# Synthetic pair: 100-patient dataset as reference cohort, 150-patient as data
out4, st4 = filter_by_cohort_whitelist(
    SYN, os.path.join(os.path.dirname(SYN), 'test_data_100patients.csv'),
    episode_cutoff=cutoff.strftime('%Y-%m-%d'),
    output_csv=os.path.join(tmpdir, 'syn_whitelist.csv'))
flt4 = pd.read_csv(out4, sep=';', skiprows=7, dtype=str, keep_default_na=False)
ref_pids = set(pd.read_csv(os.path.join(os.path.dirname(SYN),
                                        'test_data_100patients.csv'),
                           sep=';', skiprows=7, dtype=str,
                           keep_default_na=False, usecols=['PID'])['PID'])
check('synthetic whitelist cohort = reference PID set',
      set(flt4['PID'].unique()) <= ref_pids and
      st4['patients_dropped_not_in_cohort'] == 50)
c435_syn = [c for c in flt4.columns if c.startswith('X_435_')]
is_fu4 = (flt4[c435_syn] != '').any(axis=1)
ad4 = pd.to_datetime(flt4['X_433_7_11'], errors='coerce')
ep4 = pd.to_datetime(flt4['Episode date'], format='%d/%m/%Y', errors='coerce')
check('synthetic: no dated administrations beyond the cap',
      (ad4[~is_fu4].dropna() <= cutoff).all())
check('synthetic: no other clinical rows beyond the cap',
      (ep4[~is_fu4 & ad4.isna()] <= cutoff).all())
# independent recomputation of the expected filtered frame
raw_fu = (raw[[c for c in raw.columns if c.startswith('X_435_')]] != '').any(axis=1)
raw_adm_cols = [c for c in raw.columns if c.startswith('X_433_7_')]
raw_is_admin = ~raw_fu & (raw[raw_adm_cols] != '').any(axis=1)
raw_ad = pd.to_datetime(raw['X_433_7_11'], errors='coerce')
raw_ep = pd.to_datetime(raw['Episode date'], format='%d/%m/%Y', errors='coerce')
check('synthetic: every administration row carries an administration date',
      (~(raw_is_admin & raw_ad.isna())).all())
ep_ok = (raw_ep <= cutoff) | raw_ep.isna()
adm_ok = raw_ad <= cutoff  # no undated administrations in the synthetic data
exp_mask = raw['PID'].isin(ref_pids) & (
    raw_fu | (raw_is_admin & adm_ok) | (~raw_is_admin & ~raw_fu & ep_ok))
check('synthetic: filtered frame equals independent recomputation',
      flt4.reset_index(drop=True).equals(raw[exp_mask].reset_index(drop=True)))

# ---------------------------------------------------------------- splice mode
# Clinical rows verbatim from the reference export, follow-up rows from the
# current export (reuses the hand-made January/August pair).
from enrollment_filter import splice_reference_clinical

out5, st5 = splice_reference_clinical(aug_csv, jan_csv)
flt5 = pd.read_csv(out5, sep=';', skiprows=7, dtype=str, keep_default_na=False)
jan = pd.read_csv(jan_csv, sep=';', skiprows=7, dtype=str, keep_default_na=False)
jan_fu = (jan[[c for c in jan.columns if c.startswith('X_435_')]] != '').any(axis=1)
flt5_fu = (flt5[[c for c in flt5.columns if c.startswith('X_435_')]] != '').any(axis=1)
check('splice: clinical rows equal reference verbatim',
      flt5[~flt5_fu].reset_index(drop=True).equals(
          jan[~jan_fu].reset_index(drop=True)))
check('splice: January clinical values govern (corrected Aug dose 350 absent, '
      'Jan dose 300 present)',
      '350' not in set(flt5['X_433_7_22']) and
      (flt5['X_433_7_22'] == '300').sum() == 1)
check('splice: Aug-only administrations absent (dose 400 and patient 4 admins)',
      '400' not in set(flt5['X_433_7_22']) and
      ((flt5['PID'] == '4') & (flt5['X_433_7_746'] != '')).sum() == 0)
check('splice: follow-up rows come from current export (both late follow-ups)',
      sorted(flt5.loc[flt5_fu, 'X_435_0_751']) == ['2026-03-05', '2026-05-10'])
check('splice: current-only patient dropped',
      '3' not in set(flt5['PID']) and st5['current_only_patients_dropped'] == 1)
check('splice: late-treated patient flagged as follow-up-without-clinical? no '
      '(has Jan registration row); counts correct',
      st5['followup_pids_without_clinical_rows'] == [] and
      st5['clinical_rows_from_reference'] == 5 and
      st5['followup_rows_from_current'] == 2)
with open(out5, encoding='utf-8') as f:
    check('splice: output header matches the current export schema',
          [f.readline() for _ in range(8)] == wl_header)

# schema evolution: the current export gained an eCRF element (and both
# exports carry a trailing empty padding column, position-named by pandas)
jan6_csv = os.path.join(tmpdir, 'january6.csv')
aug6_csv = os.path.join(tmpdir, 'august6.csv')
meta7 = ['meta line %d\n' % i for i in range(1, 8)]
with open(jan6_csv, 'w', encoding='utf-8') as f:
    f.writelines(meta7 + ['"PID";"Episode date";"X_433_7_746";\n',
                          '1;01/12/2025;1;\n'])
with open(aug6_csv, 'w', encoding='utf-8') as f:
    f.writelines(meta7 + ['"PID";"Episode date";"X_433_7_746";"X_433_0_999";\n',
                          '1;20/02/2026;2;77;\n'])
out7, st7 = splice_reference_clinical(aug6_csv, jan6_csv,
                                      output_csv=os.path.join(tmpdir, 'ev.csv'))
ev = pd.read_csv(out7, sep=';', skiprows=7, dtype=str, keep_default_na=False)
check('splice schema evolution: reference-subset accepted, output in current '
      'schema with new column empty on reference rows',
      'X_433_0_999' in ev.columns and len(ev) == 1 and
      ev.at[0, 'X_433_7_746'] == '1' and ev.at[0, 'X_433_0_999'] == '')
check('splice schema evolution: current-only columns reported',
      st7['current_only_columns'] == ['X_433_0_999'])
with open(out7, encoding='utf-8') as f:
    check('splice schema evolution: header taken from the current export',
          [f.readline() for _ in range(8)][7] ==
          '"PID";"Episode date";"X_433_7_746";"X_433_0_999";\n')

# exclusions: erasure removes entirely; partial withdrawal keeps clinical only
_, st_ex = splice_reference_clinical(
    aug_csv, jan_csv, exclude_pids=['2'],
    output_csv=os.path.join(tmpdir, 'ex.csv'))
ex = pd.read_csv(os.path.join(tmpdir, 'ex.csv'), sep=';', skiprows=7,
                 dtype=str, keep_default_na=False)
check('splice: --exclude-pids removes the patient entirely',
      '2' not in set(ex['PID']) and st_ex['excluded_pids'] == ['2'])
_, st_fu = splice_reference_clinical(
    aug_csv, jan_csv, exclude_followup_pids=['4'],
    output_csv=os.path.join(tmpdir, 'exfu.csv'))
exfu = pd.read_csv(os.path.join(tmpdir, 'exfu.csv'), sep=';', skiprows=7,
                   dtype=str, keep_default_na=False)
check('splice: --exclude-followup-pids keeps clinical rows, drops follow-up',
      ((exfu['PID'] == '4').sum() == 1 and
       (exfu.loc[exfu['PID'] == '4', 'X_435_0_751'] == '').all()))

# withdrawn-after-reference patients: all rows (clinical AND follow-up)
# sourced from the reference export via reference_followup_pids
jan5_csv = os.path.join(tmpdir, 'january5.csv')
aug5_csv = os.path.join(tmpdir, 'august5.csv')
with open(jan5_csv, 'w', encoding='utf-8') as f:
    f.writelines(wl_header + [
        '6;01/12/2025;;1;2025-12-05;100;;\n',   # withdrawn patient: clinical
        '6;01/12/2025;;;;;2026-01-10;3\n',      # withdrawn patient: pre-withdrawal
                                                #   follow-up (exists ONLY here)
        '8;01/12/2025;;1;2025-12-06;90;;\n',    # ordinary patient: clinical
        '8;01/12/2025;;;;;2026-01-05;1\n',      # ordinary patient: early follow-up
    ])
with open(aug5_csv, 'w', encoding='utf-8') as f:
    f.writelines(wl_header + [                  # patient 6 absent (withdrawn)
        '8;01/12/2025;;1;2025-12-06;90;;\n',
        '8;01/12/2025;;;;;2026-04-01;2\n',      # ordinary patient: current follow-up
    ])
_, st_wd = splice_reference_clinical(
    aug5_csv, jan5_csv, reference_followup_pids=['6'],
    output_csv=os.path.join(tmpdir, 'wd.csv'))
wd = pd.read_csv(os.path.join(tmpdir, 'wd.csv'), sep=';', skiprows=7,
                 dtype=str, keep_default_na=False)
check('splice: withdrawn patient keeps reference clinical AND reference '
      'follow-up rows',
      ((wd['PID'] == '6') & (wd['X_433_7_746'] != '')).sum() == 1 and
      set(wd.loc[wd['PID'] == '6', 'X_435_0_751']) - {''} == {'2026-01-10'} and
      st_wd['followup_rows_from_reference'] == 1)
check('splice: ordinary patient still gets follow-up from the current export',
      set(wd.loc[wd['PID'] == '8', 'X_435_0_751']) - {''} == {'2026-04-01'})
_, st_nowd = splice_reference_clinical(
    aug5_csv, jan5_csv, output_csv=os.path.join(tmpdir, 'nowd.csv'))
nowd = pd.read_csv(os.path.join(tmpdir, 'nowd.csv'), sep=';', skiprows=7,
                   dtype=str, keep_default_na=False)
check('splice: without reference_followup_pids the withdrawn patient has no '
      'follow-up rows',
      (nowd.loc[nowd['PID'] == '6', 'X_435_0_751'] == '').all())

# duplicated header labels (e.g. one "Unique ID" column per form) plus
# multiple empty padding columns, and several current-only new elements
from enrollment_filter import _dedupe_labels

check('dedupe: duplicate labels get deterministic occurrence suffixes',
      _dedupe_labels(['PID', 'U', 'U', 'U']) ==
      ['PID', 'U', 'U__dup1', 'U__dup2'])
check('dedupe: unique labels unchanged',
      _dedupe_labels(['PID', 'A', 'B']) == ['PID', 'A', 'B'])

jan7_csv = os.path.join(tmpdir, 'january7.csv')
aug7_csv = os.path.join(tmpdir, 'august7.csv')
UID = '"Unique ID (Form_Record_DataElement):"'
jan7_header = (f'"PID";{UID};"Episode date";{UID};"X_433_7_746";{UID};;\n')
aug7_header = (f'"PID";{UID};"Episode date";{UID};"X_433_7_746";{UID};'
               f'"X_433_0_900";"X_435_0_901";"X_541_0_902";;\n')
with open(jan7_csv, 'w', encoding='utf-8') as f:
    f.writelines(meta7 + [jan7_header, '1;u1;01/12/2025;u2;1;u3;;\n'])
with open(aug7_csv, 'w', encoding='utf-8') as f:
    f.writelines(meta7 + [aug7_header,
                          '1;u1;20/02/2026;u2;2;u3;n1;;n3;;\n'])
out8, st8 = splice_reference_clinical(aug7_csv, jan7_csv,
                                      output_csv=os.path.join(tmpdir, 'dup.csv'))
dup = pd.read_csv(out8, sep=';', skiprows=7, dtype=str, keep_default_na=False)
check('splice duplicated labels: triplicated per-form column aligned, clinical '
      'values from reference',
      len(dup) == 1 and dup.at[0, 'X_433_7_746'] == '1' and
      list(dup.iloc[0, [1, 3, 5]]) == ['u1', 'u2', 'u3'])
check('splice duplicated labels: three current-only elements empty on '
      'reference rows',
      all(dup.at[0, c] == '' for c in
          ['X_433_0_900', 'X_435_0_901', 'X_541_0_902']) and
      len(st8['current_only_columns']) == 3)
with open(out8, encoding='utf-8') as f:
    check('splice duplicated labels: output header is the current export '
          'header verbatim',
          [f.readline() for _ in range(8)][7] == aug7_header)

# schema mismatch must fail loudly
bad_csv = os.path.join(tmpdir, 'badschema.csv')
with open(bad_csv, 'w', encoding='utf-8') as f:
    f.writelines(['meta line %d\n' % i for i in range(1, 8)] +
                 ['"PID";"Episode date";"X_433_7_746"\n', '1;01/12/2025;1\n'])
try:
    splice_reference_clinical(bad_csv, jan_csv,
                              output_csv=os.path.join(tmpdir, 'bad_out.csv'))
    check('splice: schema mismatch raises', False)
except ValueError:
    check('splice: schema mismatch raises', True)

# synthetic pair: independent recomputation
out6, st6 = splice_reference_clinical(
    SYN, os.path.join(os.path.dirname(SYN), 'test_data_100patients.csv'),
    output_csv=os.path.join(tmpdir, 'syn_splice.csv'))
flt6 = pd.read_csv(out6, sep=';', skiprows=7, dtype=str, keep_default_na=False)
ref100 = pd.read_csv(os.path.join(os.path.dirname(SYN),
                                  'test_data_100patients.csv'),
                     sep=';', skiprows=7, dtype=str, keep_default_na=False)
r_fu = (ref100[[c for c in ref100.columns if c.startswith('X_435_')]] != '').any(axis=1)
c_fu = (raw[[c for c in raw.columns if c.startswith('X_435_')]] != '').any(axis=1)
exp6 = pd.concat([ref100[~r_fu],
                  raw[c_fu & raw['PID'].isin(set(ref100['PID']))]],
                 ignore_index=True)
check('splice synthetic: output equals independent recomputation',
      flt6.equals(exp6))
check('splice synthetic: follow-up rows sourced from the current export',
      st6['followup_rows_from_current'] ==
      int((c_fu & raw['PID'].isin(set(ref100['PID']))).sum()))

print(f"\nTOTAL: {len(passed)} passed, {len(failed)} failed")
sys.exit(1 if failed else 0)
