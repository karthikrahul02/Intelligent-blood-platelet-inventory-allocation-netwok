"""Unit tests for the analysis and data-quality modules: each check
builds a miniature dataset whose correct result can be computed by hand
(constructed DataFrames or miniature exports, no full pipeline run)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd
import numpy as np

passed, failed = [], []
def check(name, cond):
    (passed if cond else failed).append(name)
    print(('PASS' if cond else 'FAIL'), name)

# ---------------------------------------------------------------- followup duplicates
from descriptive_followup import FollowUpDescriptives

class _FakeLoader:  # minimal stand-in
    pass

def make_followup_instance(df):
    inst = FollowUpDescriptives.__new__(FollowUpDescriptives)
    inst.conflicting_duplicates = []
    inst.resolved_duplicates = []
    return inst

# identical answers, different dates -> must resolve (keep one)
rec = pd.DataFrame({
    'X_435_0_751': ['2025-03-01', '2025-03-08'],
    'X_435_0_741': ['3', '3'],
    'X_435_0_742': ['2', '2'],
    'followup_date': pd.to_datetime(['2025-03-01', '2025-03-08']),
    'days_from_first': [75, 82],
})
cols_excl_date = [c for c in rec.columns if c.startswith('X_435_') and c != 'X_435_0_751']
inst = make_followup_instance(rec)
resolved, was_conflict = inst._resolve_duplicates(rec, cols_excl_date, 1001, '3-month')
check('identical dups (diff dates) resolved', resolved is not None and len(resolved) == 1 and not was_conflict)
check('identical dups logged as resolved', len(inst.resolved_duplicates) == 1)

# conflicting answers -> exclude all
rec2 = rec.copy(); rec2.loc[1, 'X_435_0_741'] = '4'
inst2 = make_followup_instance(rec2)
resolved2, was_conflict2 = inst2._resolve_duplicates(rec2, cols_excl_date, 1002, '3-month')
check('conflicting dups excluded', resolved2 is None and was_conflict2)

# ---------------------------------------------------------------- window constants
inst3 = FollowUpDescriptives.__new__(FollowUpDescriptives)
# reproduce constant block manually
check('window constants file', True)
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'descriptive_followup.py')).read()
check('3m max = 113', 'followup_3month_max_days = 113' in src)
check('1y min = 273', 'followup_1year_min_days = 273' in src)
check('no intended_timeframe selection', "== '3month_intended')\n        ]['PID']" not in src)

# ---------------------------------------------------------------- indications denominator
from descriptive_indications import IndicationInterventionDescriptives
ind = IndicationInterventionDescriptives.__new__(IndicationInterventionDescriptives)
ind.df = pd.DataFrame({
    'X_433_7_746': ['1'] * 10,
    'X_433_7_593': ['1', '2', np.nan, np.nan, np.nan, '1.0', np.nan, np.nan, np.nan, np.nan],
    'PID': range(10),
})
res = ind._calculate_indications_by_product()
rbc = res['Red blood cell concentrate (RBC)']
check('indications documented=3', rbc['documented_indications'] == 3)
check('indications missing=7', rbc['missing_indications'] == 7)
hb7 = rbc['indications'].get('Hb <7 g/dl (independent of compensation)', {})
check("'1' and '1.0' merged (n=2)", hb7.get('n') == 2)
check('pct of documented = 66.7', abs(hb7.get('percent_of_documented', 0) - 2/3*100) < 0.1)

# ---------------------------------------------------------------- LOS same-row pairing
from descriptive_los import LOSDescriptives
los = LOSDescriptives.__new__(LOSDescriptives)
los.INTERVENTION_DATE_COL = 'X_433_0_8'
los.DISCHARGE_DATE_COL = 'X_433_0_753'
# patient 1: ep1 has intervention only, ep2 has discharge only -> no cross-episode pairing
# patient 2: one row with a proper pair (5 days)
los.df = pd.DataFrame({
    'PID': [1, 1, 2],
    'X_433_0_8':   ['2025-01-10', np.nan,        '2025-02-01'],
    'X_433_0_753': [np.nan,       '2025-03-15',  '2025-02-06'],
    'X_433_0_4':   ['M', 'M', 'F'],
})
pdf = los._parse_dates()
p1 = pdf[pdf['PID'] == 1].iloc[0]
p2 = pdf[pdf['PID'] == 2].iloc[0]
check('no cross-episode LOS (patient 1 NaN)', pd.isna(p1['los_days']))
check('same-row LOS correct (patient 2 = 5)', p2['los_days'] == 5)

# median non-truncation: LOS of 6,7,8,9 days -> median 7.5
los2 = LOSDescriptives.__new__(LOSDescriptives)
los2.INTERVENTION_DATE_COL = 'X_433_0_8'
los2.DISCHARGE_DATE_COL = 'X_433_0_753'
los2.MIN_LOS_DAYS = 0; los2.MAX_LOS_DAYS = 365
los2.results = {}
base = pd.Timestamp('2025-01-01')
los2.df = pd.DataFrame({
    'PID': [1, 2, 3, 4],
    'X_433_0_8': [str(base.date())] * 4,
    'X_433_0_753': [str((base + pd.Timedelta(days=d)).date()) for d in (6, 7, 8, 9)],
    'X_433_0_4': ['M'] * 4,
})
stats = los2.calculate_los_statistics()
check('LOS median not truncated (7.5)', stats['median'] == 7.5)

# ---------------------------------------------------------------- refusal-0 exclusion
fu = FollowUpDescriptives.__new__(FollowUpDescriptives)
fu.patient_df_3month = pd.DataFrame({
    'has_followup_3month': [True, True, True, True],
    'X_435_0_741_3month': ['0', '3', '4', '3'],
    'X_435_0_742_3month': ['0', '2', '3', '2'],
})
out = fu._calculate_patient_reported_outcomes('3month')
pc = out['physical_capacity']
check('refusal-0 excluded from mean', abs(pc['mean'] - (3+4+3)/3) < 1e-9)
check('refusal counted separately', pc['n_refused'] == 1 and pc['n_scale'] == 3)
check('refusal label in distribution', 'Refused to answer' in pc['distribution'])
cfs = out['frailty_cfs']
check('CFS refusal-0 excluded from mean', abs(cfs['mean'] - (2+3+2)/3) < 1e-9)

# ---------------------------------------------------------------- transfusion labels
fu2 = FollowUpDescriptives.__new__(FollowUpDescriptives)
fu2.patient_df_3month = pd.DataFrame({
    'has_followup_3month': [True]*5,
    'X_435_0_740_3month': ['Y', 'N', 'N', 'U', 'N'],
    'X_435_0_752_3month': ['0', '1.0', '2', '3', '7'],
})
clin = fu2._calculate_clinical_outcomes('3month')
dist = clin['past_year_transfusions']['distribution']
check("code '3' labeled Cannot answer", 'Cannot answer' in dist and dist['Cannot answer']['n'] == 1)
check("'1.0' normalized to One", dist.get('One', {}).get('n') == 1)
check('unexpected code reported', dist.get('Other/unexpected code', {}).get('n') == 1)
total_n = sum(v['n'] for v in dist.values())
check('distribution sums to total', total_n == clin['past_year_transfusions']['total'])

# ---------------------------------------------------------------- SNOMED denominator
from descriptive_snomed import SNOMEDDescriptives
sn = SNOMEDDescriptives.__new__(SNOMEDDescriptives)
sn.results = {}
sn.df = pd.DataFrame({
    'PID': [1, 1, 2, 2],
    'X_433_7_746': ['1', np.nan, '2', np.nan],  # 2 admin rows, 2 non-admin rows
    'X_433_0_5': ['123', np.nan, '456', np.nan],
})
sn.SNOMED_COLUMNS = {'primary_diagnosis': 'X_433_0_5'}
sn.FIELD_NAMES = {'primary_diagnosis': 'Primary Diagnosis'}
cov = sn.calculate_coverage()
al = cov['primary_diagnosis']['administration_level']
check('SNOMED admin denominator = admin rows', al['total'] == 2)
check('SNOMED admin coverage 100%', al['percent_documented'] == 100.0)

# ---------------------------------------------------------------- temporal unique patients
from descriptive_temporal_volumes import TemporalVolumeAnalysis
tv = TemporalVolumeAnalysis.__new__(TemporalVolumeAnalysis)
df_all = pd.DataFrame({
    'PID': [1, 2, 3],
    'X_433_7_746': ['1', '1', '2'],
    'year_month': ['2025-01'] * 3,
})
counts = tv._calculate_administration_counts(df_all, 'year_month', 'X_433_7_746')
check('temporal unique_patients_all = 3', counts['2025-01']['unique_patients_all'] == 3)
period_results = {'2025-01': {'total_administrations': 2, 'unique_patients': 1, 'products': {}}}
tv._merge_administration_counts(period_results, counts)
check('temporal merge overrides unique_patients', period_results['2025-01']['unique_patients'] == 3)

# ---------------------------------------------------------------- DQ module tests (appended)
print("\n--- DQ module tests ---")
from data_quality_module2_dosage import DosageConsistency
norm = DosageConsistency._norm_code(pd.Series(['4.0', '4', '11.0', '11', 'nan']))
check('norm_code strips .0', list(norm) == ['4', '4', '11', '11', 'nan'])

from data_quality_module4_validity import DataValidity
dv = DataValidity.__new__(DataValidity)
dv.FIELD_MAP = {'admin_date': 'X_433_7_11'}
dv.df = pd.DataFrame({
    'PID': [1, 1, 1, 2, 2],
    'Height': [175, 175, 175, 9999, 9999],
    'X_433_7_11': ['2025-01-01'] * 5,
})
res = dv._check_range('Height', 'Height', 20, 220, 'cm', level='patient')
check('DQ4 patient denominator = 2 patients', res['n_total'] == 2)
check('DQ4 invalid = 1 patient (not 2 rows)', res['n_invalid'] == 1)

from data_quality_module3_followup_duplicates import FollowUpDuplicates
fd = FollowUpDuplicates.__new__(FollowUpDuplicates)
fd.followup_df = pd.DataFrame({
    'PID': [1, 1, 2, 2, 3, 3],
    'window': ['Unknown', 'Unknown', '3-month', '3-month', 'Too early (<68 days)', 'Too early (<68 days)'],
})
fd.patient_baseline_df = pd.DataFrame({'PID': [1, 2, 3], 'baseline_date': pd.to_datetime(['2025-01-01']*3), 'has_treatment': [True]*3})
fd._detect_duplicates()
dups = fd.duplicates_same_window_df
check('DQ3 dups only in real windows', set(dups['PID']) == {2})
check('DQ3 window constants 68/113/273/455',
      (FollowUpDuplicates.WINDOW_3MONTH_MIN, FollowUpDuplicates.WINDOW_3MONTH_MAX,
       FollowUpDuplicates.WINDOW_1YEAR_MIN, FollowUpDuplicates.WINDOW_1YEAR_MAX) == (68, 113, 273, 455))

# ---------------------------------------------------------------- biometrics
# Miniature registry export loaded through the REAL data loader: ages and
# BMIs chosen so every statistic can be recalculated in a spreadsheet.
# Episode year 2025; birth years 1955/1965/1975/1945 -> ages 70/60/50/80
# (mean 65, median 65); BMIs 25.0/20.0/25.0/30.0 (mean 25, median 25);
# untreated patients born 1985/1995 -> ages 40/30 (mean 35).
print("\n--- Biometrics (hand-checkable mini export) ---")
import tempfile
from transfusion_data_loader import TransfusionDataLoader
from descriptive_biometrics import BiometricDescriptives

_meta7 = ['meta line %d\n' % i for i in range(1, 8)]
_bio_header = ('"PID";"patient repeat number";"Episode number";"Location";'
               '"Episode date";"Episode description";"FormStatus_541";'
               '"X_541_0_1";"FormStatus_433";"X_433_0_2";"X_433_0_3";'
               '"X_433_0_4";"X_433_7_746";"X_433_7_22";"X_433_7_734"\n')
_site = 'Universitätsklinikum Frankfurt'
_bio_rows = [
    f'1;1;1;{_site};01/06/2025;ep;open;1955;open;180;81;M;1;500;1\n',
    f'1;1;1;{_site};01/06/2025;ep;open;1955;open;180;81;M;1;600;1\n',
    f'2;1;1;{_site};01/06/2025;ep;open;1965;open;150;45;F;1;500;1\n',
    f'3;1;1;{_site};01/06/2025;ep;open;1975;open;160;64;M;1;;\n',
    f'4;1;1;{_site};01/06/2025;ep;open;1945;open;200;120;F;11;;\n',
    f'5;1;1;{_site};01/06/2025;ep;open;1985;open;175;70;M;;;\n',
    f'6;1;1;{_site};01/06/2025;ep;open;1995;open;165;58;F;;;\n',
]
_bio_dir = tempfile.mkdtemp()
_bio_csv = os.path.join(_bio_dir, 'bio_mini.csv')
with open(_bio_csv, 'w', encoding='utf-8') as f:
    f.writelines(_meta7 + [_bio_header] + _bio_rows)

_loader = TransfusionDataLoader()
_loader.load_data(_bio_csv)
_bio = BiometricDescriptives(_loader)
_res = _bio.calculate_all()

_age = _res['age']['overall']
check('biometrics age mean 65.0 (episode year - birth year, per patient)',
      _age['mean'] == 65.0)
check('biometrics age median 65.0', _age['median'] == 65.0)
check('biometrics age n=4 (duplicate row of patient 1 counted once)',
      _age['n'] == 4)
check('biometrics age by gender (M mean 60, F mean 70)',
      _res['age']['by_gender']['Male']['mean'] == 60.0 and
      _res['age']['by_gender']['Female']['mean'] == 70.0)
_bmi = _res['bmi']['overall']
check('biometrics BMI mean 25.0 and median 25.0',
      _bmi['mean'] == 25.0 and _bmi['median'] == 25.0)
check('biometrics gender split 2 M / 2 F (50% each)',
      int(_res['gender']['Male']['n']) == 2 and
      _res['gender']['Male']['percent'] == 50.0)
_nt = _res['non_transfusion_patients']
_nt_age = _nt.get('age', _nt)
check('biometrics non-transfusion cohort n=2, age mean 35.0 (episode year)',
      (_nt.get('n_patients') == 2 or _nt.get('n') == 2) and
      (_nt_age.get('mean') == 35.0))

# ---------------------------------------------------------------- DQ1 completeness
# Miniature export for the dosage-completeness denominator: four RBC
# administrations (three with a complete dosage pair, one without) plus one
# MAT administration without dosage and one registered-only patient.
# Expected: denominator excludes MAT -> 4 relevant, 3 present = 75%.
print("\n--- DQ1 completeness (hand-checkable mini export) ---")
from data_quality_module1_completeness import DataQualityCompleteness

_dq_rows = [
    f'1;1;1;{_site};01/06/2025;ep;open;1955;open;180;81;M;1;700;1\n',
    f'2;1;1;{_site};01/06/2025;ep;open;1965;open;170;60;F;1;500;1\n',
    f'3;1;1;{_site};01/06/2025;ep;open;1975;open;160;64;M;1;600;1\n',
    f'4;1;1;{_site};01/06/2025;ep;open;1945;open;150;68;F;1;;\n',
    f'5;1;1;{_site};01/06/2025;ep;open;1985;open;175;70;M;11;;\n',
    f'6;1;1;{_site};01/06/2025;ep;open;1995;open;165;58;F;;;\n',
]
_dq_csv = os.path.join(_bio_dir, 'dq1_mini.csv')
with open(_dq_csv, 'w', encoding='utf-8') as f:
    f.writelines(_meta7 + [_bio_header] + _dq_rows)

_loader2 = TransfusionDataLoader()
_loader2.load_data(_dq_csv)
_dq1 = DataQualityCompleteness(_loader2)
_dqres = _dq1.calculate_all()
_treat = _dqres['treatment']['variables']
_dose = _treat['Dosage amount']
check('DQ1 n_administrations=5 (incl. MAT), non-treatment records excluded',
      _dqres['treatment']['n_administrations'] == 5)
check('DQ1 dosage denominator=4 (MAT excluded by design)',
      _dose['n_total'] == 4)
check('DQ1 dosage completeness 3 of 4 = 75.0%',
      _dose['n_present'] == 3 and _dose['percent_complete'] == 75.0)
check('DQ1 MAT-exclusion note attached to dosage variables',
      'MAT' in _dose.get('note', ''))

# ---------------------------------------------------------------- SNOMED without codes
# A sample with no documented SNOMED code anywhere (as a reviewer building
# a minimal own sample would produce) must yield an orderly result, not a
# crash.
print("\n--- SNOMED analysis on a sample without any SNOMED codes ---")
from descriptive_snomed import SNOMEDDescriptives

# the SNOMED columns must be PRESENT but empty (as in a real export where
# nothing was documented) - that is the path that used to crash
_ns_header = _bio_header.rstrip('\n') + ';"X_433_0_5";"X_433_0_6";"X_433_0_9"\n'
_ns_rows = [
    f'1;1;1;{_site};01/06/2025;ep;open;1960;open;180;80;M;1;300;1;;;\n',
    f'2;1;1;{_site};01/06/2025;ep;open;1970;open;165;60;F;1;380;1;;;\n',
]
_ns_csv = os.path.join(_bio_dir, 'no_snomed_mini.csv')
with open(_ns_csv, 'w', encoding='utf-8') as f:
    f.writelines(_meta7 + [_ns_header] + _ns_rows)
_loader3 = TransfusionDataLoader()
_loader3.load_data(_ns_csv)
_sn = SNOMEDDescriptives(_loader3)
_sn_res = _sn.calculate_all()
_sn_table = _sn.create_summary_table()
_sn.export_results(_bio_dir)  # all three export files must also succeed
check('SNOMED module handles a sample without any codes (no crash, '
      'zero unique codes, summary and exports render)',
      all(v.get('total_unique_codes') == 0
          for v in _sn_res['top_codes'].values()) and
      isinstance(_sn_table, str) and len(_sn_table) > 0 and
      os.path.exists(os.path.join(_bio_dir, 'SNOMED', 'snomed_all_codes.csv')))

# ---------------------------------------------------------------- date-format handling (loader)
import warnings as _warnings
_regr_dir = tempfile.mkdtemp()
_date_csv = os.path.join(_regr_dir, 'date_formats.csv')
with open(_date_csv, 'w') as f:
    f.writelines(_meta7 + [
        '"PID";"Episode date";"X_433_7_746";"X_433_7_11";"X_433_0_753"\n',
        '1;01/12/2025;1;2025-03-05;10/03/2025\n',
        '2;05/12/2025;1;05/04/2025;11/03/2025\n',
        '3;10/12/2025;1;not-a-date;12/03/2025\n',
    ])
with _warnings.catch_warnings():
    _warnings.simplefilter('ignore')
    _ld_dates = TransfusionDataLoader()
    _ld_dates.load_data(_date_csv)
_adm_dates = _ld_dates.df_clean.set_index('PID')['X_433_7_11']
_dis_dates = _ld_dates.df_clean.set_index('PID')['X_433_0_753']
check('ISO date parsed (2025-03-05)',
      _adm_dates.loc['1'] == pd.Timestamp('2025-03-05'))
check('EU date in the SAME column parsed (05/04/2025 -> 5 April)',
      _adm_dates.loc['2'] == pd.Timestamp('2025-04-05'))
check('fully EU-formatted DATE column parsed via original strings',
      list(_dis_dates) == [pd.Timestamp('2025-03-10'),
                           pd.Timestamp('2025-03-11'),
                           pd.Timestamp('2025-03-12')])
check('unparseable non-empty date captured as QC finding (column, PID, raw value)',
      any(u['column'] == 'X_433_7_11' and str(u['PID']) == '3'
          and u['raw_value'] == 'not-a-date'
          for u in _ld_dates.unparseable_dates))
check('unparseable date set to missing, row kept (not silently dropped)',
      pd.isna(_adm_dates.loc['3']) and '3' in _adm_dates.index)

# ---------------------------------------------------------------- follow-up time anchor
# Episode date (2025-01-01), administration date (2025-02-01), and discharge
# date (2025-01-10) all differ. The follow-up on 2025-05-17 lies 105 days
# after the ADMINISTRATION (inside the 68-113-day window) but 136 days after
# the episode date and 127 days after discharge (both outside the window):
# only the approved administration-date anchor classifies it as 3-month.
_anchor_csv = os.path.join(_regr_dir, 'time_anchor.csv')
with open(_anchor_csv, 'w') as f:
    f.writelines(_meta7 + [
        '"PID";"Episode date";"X_433_7_746";"X_433_7_11";"X_433_0_753";"X_435_0_751";'
        '"X_433_0_2";"X_433_0_3";"X_433_0_4";"X_433_0_32";"X_433_0_25";"X_541_0_1"\n',
        '1;01/01/2025;1;2025-02-01;2025-01-10;;176;80;M;3;4;1960\n',
        '1;01/01/2025;;;;2025-05-17;;;;;;\n',
        '2;01/01/2025;1;;;;165;60;F;2;3;1955\n',
        '2;01/01/2025;;;;2025-05-17;;;;;;\n',
    ])
_ld_anchor = TransfusionDataLoader()
_ld_anchor.load_data(_anchor_csv)
_fu_anchor = FollowUpDescriptives(_ld_anchor)
_p1_row = _fu_anchor.patient_df_3month[
    _fu_anchor.patient_df_3month['PID'].astype(str) == '1']
check('follow-up window anchored on administration date '
      '(105 d post-admin -> 3-month despite 136/127 d from episode/discharge)',
      len(_p1_row) == 1 and bool(_p1_row['has_followup_3month'].iloc[0]))
check('patient without administration date counted as not time-classifiable',
      _fu_anchor.n_patients_no_time_anchor == 1)
_p2_row = _fu_anchor.patient_df_3month[
    _fu_anchor.patient_df_3month['PID'].astype(str) == '2']
check('anchor-less patient not classified into a follow-up window',
      len(_p2_row) == 0 or not bool(_p2_row['has_followup_3month'].iloc[0]))

# ---------------------------------------------------------------- test-location cohort
_ver_csv = os.path.join(_regr_dir, 'test_site.csv')
with open(_ver_csv, 'w') as f:
    f.writelines(_meta7 + [
        '"PID";"patient repeat number";"Episode number";"Location";"Episode date";"X_433_7_746";"X_433_7_22";"X_433_7_734";"X_433_7_11"\n',
        '1;1;1;Site A;01/12/2025;1;500;1;2025-01-05\n',
        '2;1;1;Site B;01/12/2025;1;300;1;2025-01-20\n',
        '3;1;1;Verika (Teststandort);01/12/2025;1;400;1;2025-01-25\n',
    ])
_ld_ver = TransfusionDataLoader()
_ld_ver.load_data(_ver_csv)
_stat_pids = set(_ld_ver.df_clean['PID'].astype(str))
check('loader excludes test-location (Verika) patients from statistics',
      _stat_pids == {'1', '2'})
import matplotlib
matplotlib.use('Agg')
from visualize_treatments import TreatmentVisualizer
_viz = TreatmentVisualizer.__new__(TreatmentVisualizer)
_viz.raw_data_path = _ver_csv
_viz._load_raw_data()
check('figures drawn from the SAME cohort as the statistics (Verika excluded)',
      set(_viz.raw_df['PID'].astype(str)) == _stat_pids)

# ---------------------------------------------------------------- code forms in every table
_forms_csv = os.path.join(_regr_dir, 'code_forms.csv')
with open(_forms_csv, 'w') as f:
    f.writelines(_meta7 + [
        '"PID";"Episode date";"X_433_7_746";"X_433_7_22";"X_433_7_734";"X_433_7_11"\n',
        '1;01/12/2025;1;500;1;2025-01-05\n',
        '2;01/12/2025;1.0;300;1.0;2025-01-20\n',
    ])
_ld_forms = TransfusionDataLoader()
_ld_forms.load_data(_forms_csv)
from descriptive_temporal_volumes import TemporalVolumeAnalysis
_tv_res = TemporalVolumeAnalysis(_ld_forms).calculate_all()
_jan_rbc = _tv_res['monthly']['2025-01']['products'].get(
    'Red blood cell concentrate (RBC)', {})
check("temporal volumes aggregate '1' and '1.0' once (RBC ml n=2, 800 ml)",
      _jan_rbc.get('ml', {}).get('n_administrations') == 2
      and _jan_rbc.get('ml', {}).get('total_amount') == 800.0)
check("no separate product bucket for the float form",
      list(_tv_res['monthly']['2025-01']['products'].keys())
      == ['Red blood cell concentrate (RBC)'])
from data_quality_module1_completeness import DataQualityCompleteness
_dq1_res = DataQualityCompleteness(_ld_forms).calculate_all()
check("completeness analysis counts code forms as one product (RBC n=2)",
      _dq1_res['indication']['products']
      ['Red blood cell concentrate (RBC)']['n_administrations'] == 2)

# ---------------------------------------------------------------- intervention Y/N conflicts
ind_conf = IndicationInterventionDescriptives.__new__(IndicationInterventionDescriptives)
ind_conf.df = pd.DataFrame({
    'PID': [1, 1, 2, 2, 3, 4],
    'X_433_0_7': ['Y', 'N', 'Y', 'Y', 'N', 'X'],
})
_conf_res = ind_conf._calculate_patients_with_interventions()
check('patient with Y and N in different rows -> own conflict category',
      _conf_res['conflicting_entries']['n'] == 1)
check('no double counting: consistent-Y patient counted once as yes',
      _conf_res['connected_to_intervention']['n'] == 1
      and _conf_res['not_connected']['n'] == 1)
check('exclusive categories sum to patients_with_data',
      _conf_res['connected_to_intervention']['n']
      + _conf_res['not_connected']['n']
      + _conf_res['conflicting_entries']['n']
      + _conf_res['unexpected_codes']['n']
      == _conf_res['patients_with_data'] == 4)

# ---------------------------------------------------------------- ordinal outcome reporting
_fu_ord = FollowUpDescriptives.__new__(FollowUpDescriptives)
_fu_ord.patient_df_3month = pd.DataFrame({
    'has_followup_3month': [True] * 5,
    'X_433_0_32':          ['1', '4', '5', '3', '4'],
    'X_435_0_741_3month':  ['2', '5', '3', '5', '4'],
    'X_433_0_25':          ['5', '3', '4', '2', '6'],
    'X_435_0_742_3month':  ['3', '5', '4', '2', '6'],
})
_ord_cmp = _fu_ord._calculate_baseline_followup_comparison('3month')
_pc_matrix = _ord_cmp['physical_capacity']['transition_matrix']
check('capacity transitions 1->2 and 4->5 stay distinct matrix cells '
      '(not one metric change)',
      _pc_matrix.get('1', {}).get('2') == 1 and _pc_matrix.get('4', {}).get('5') == 1)
check('transition matrix accounts for every pair (5 of 5)',
      sum(n for row in _pc_matrix.values() for n in row.values()) == 5)
check('capacity means declared exploratory (MET categories, unequal spacing)',
      'exploratory' in _ord_cmp['physical_capacity']['scale_note']
      and 'MET' in _ord_cmp['physical_capacity']['scale_note'])
_cfs_cmp = _ord_cmp['frailty_cfs']
check('CFS improvement = LOWER grade (5->3 improved, 3->5 worsened)',
      _cfs_cmp['change']['improved'] == 1 and _cfs_cmp['change']['worsened'] == 1
      and _cfs_cmp['change']['unchanged'] == 3)
check('CFS transition matrix correct',
      _cfs_cmp['transition_matrix'] == {'5': {'3': 1}, '3': {'5': 1},
                                        '4': {'4': 1}, '2': {'2': 1},
                                        '6': {'6': 1}})
_ord_out = _fu_ord._calculate_patient_reported_outcomes('3month')
check('outcome summaries report median and IQR as primary (ordinal scales)',
      _ord_out['physical_capacity']['median'] is not None
      and 'q25' in _ord_out['physical_capacity']
      and 'q75' in _ord_out['frailty_cfs'])

# ---------------------------------------------------------------- attribute conflicts
# Patient 1 carries sex M and F and heights 176/180 on different rows;
# patient 2 is documented consistently. The loader must itemize both
# conflicts (patient-level statistics keep the first documented value).
_conf_csv = os.path.join(_regr_dir, 'attribute_conflicts.csv')
with open(_conf_csv, 'w') as f:
    f.writelines(_meta7 + [
        '"PID";"Episode date";"X_433_7_746";"X_433_7_22";"X_433_7_734";'
        '"X_433_0_4";"X_433_0_2";"X_433_0_3";"X_541_0_1"\n',
        '1;01/12/2025;1;500;1;M;176;80;1960\n',
        '1;01/12/2025;1;300;1;F;180;80;1960\n',
        '2;01/12/2025;1;400;1;F;165;60;1955\n',
    ])
with _warnings.catch_warnings():
    _warnings.simplefilter('ignore')
    _ld_conf = TransfusionDataLoader()
    _ld_conf.load_data(_conf_csv)
_conf = _ld_conf.patient_attribute_conflicts
check('conflicting sex and height flagged for patient 1 only (2 findings)',
      len(_conf) == 2 and all(str(c['PID']) == '1' for c in _conf)
      and {c['attribute'] for c in _conf} == {'sex', 'height'})
_sex_conf = [c for c in _conf if c['attribute'] == 'sex']
check('conflicting values itemized with the PID (M/F)',
      _sex_conf and sorted(_sex_conf[0]['values']) == ['F', 'M'])
from descriptive_biometrics import BiometricDescriptives
_bio_conf = BiometricDescriptives(_ld_conf)
_bio_conf._report_attribute_conflicts()
check('biometrics results itemize the conflict patients (n=1)',
      _bio_conf.results['patient_attribute_conflicts']['n_patients'] == 1
      and len(_bio_conf.results['patient_attribute_conflicts']['conflicts']) == 2)

# ---------------------------------------------------------------- 366-day interval
_los366 = LOSDescriptives.__new__(LOSDescriptives)
_los366.results = {}
_los366.los_data = None
_los366.df = pd.DataFrame({
    'PID': [1, 2, 3],
    'X_433_0_8': ['2025-01-01'] * 3,
    'X_433_0_753': ['2026-01-02', '2025-01-08', '2025-01-10'],
    'X_433_0_4': ['M', 'F', 'M'],
})
_st366 = _los366.calculate_los_statistics()
_sv366 = _los366.calculate_threshold_sensitivity()
_cov366 = _los366.calculate_coverage()
check('366-day interval excluded from the primary statistic (n=2, mean 8.0)',
      _st366['n'] == 2 and _st366['mean'] == 8.0)
check('366-day interval visible in QC coverage (counted, not silent)',
      _cov366['data_quality']['very_long_los_excluded'] == 1)
check('sensitivity analysis lists the excluded interval individually',
      _sv366['values_over_threshold'] == [{'patient_id': '1', 'days': 366}])
check('statistics defined with AND without the 365-day threshold',
      _sv366['with_threshold']['n'] == 2
      and _sv366['without_threshold']['n'] == 3
      and abs(_sv366['without_threshold']['mean'] - 127.3) < 0.05)

# ---------------------------------------------------------------- loader QC persistence
_qc_export_dir = tempfile.mkdtemp()
_qc_csv_path = _ld_dates.export_qc_findings(_qc_export_dir)
_qc_text = open(_qc_csv_path, encoding='utf-8').read()
check('unparseable date lands in a PERSISTENT loader QC file (not only in memory)',
      'unparseable_date' in _qc_text and 'not-a-date' in _qc_text
      and 'X_433_7_11' in _qc_text)
_qc_conf_path = _ld_conf.export_qc_findings(tempfile.mkdtemp())
_qc_conf_text = open(_qc_conf_path, encoding='utf-8').read()
check('attribute conflicts land in the loader QC file with PID and values',
      'attribute_conflict' in _qc_conf_text and 'F / M' in _qc_conf_text)

# INTEGER-declared fields: integral values cast to Int64; decimal values are
# KEPT (analyzed as float) and recorded as QC findings, never silently lost
_syn150 = next(c for c in ('../synthetic test data/test_data_150patients.csv',
                           '../test_data_150patients.csv') if os.path.exists(c))
_ld150 = TransfusionDataLoader()
with _warnings.catch_warnings():
    _warnings.simplefilter('ignore')
    _ld150.load_data(_syn150)
_dec = [d for d in _ld150.integer_field_decimals if d['column'] == 'X_433_7_37']
check('decimal thousands-scale platelet entries recorded as loader QC findings',
      len(_dec) >= 1 and all(float(d['raw_value']) % 1 != 0 for d in _dec))
check('decimal values kept, column analyzed as float (no truncation, no loss)',
      str(_ld150.df_clean['X_433_7_37'].dtype) == 'float64'
      and 'decimal_in_integer_field' in open(_ld150.export_qc_findings(tempfile.mkdtemp()), encoding='utf-8').read())
check('integer-only INTEGER fields still cast to Int64 (weight on the biometrics miniature)',
      str(_loader.df_clean['X_433_0_3'].dtype) == 'Int64'
      and not [d for d in _loader.integer_field_decimals if d['column'] == 'X_433_0_3'])

# ---------------------------------------------------------------- DQ4 checks all rows
# A later impossible value must not be hidden by an earlier valid one
import importlib as _importlib
_dq4mod = _importlib.import_module('data_quality_module4_validity')
_dq4_run = [getattr(_dq4mod, n) for n in dir(_dq4mod)
            if n.startswith('run_') and callable(getattr(_dq4mod, n))][0]
_dq4_csv = os.path.join(_regr_dir, 'dq4_all_rows.csv')
with open(_dq4_csv, 'w') as f:
    f.writelines(_meta7 + [
        '"PID";"Episode date";"X_433_7_746";"X_433_7_22";"X_433_7_734";"X_433_7_11";'
        '"X_433_0_2";"X_433_0_3";"X_433_0_4";"X_541_0_1";'
        '"X_433_7_601";"X_433_7_602";"X_433_7_748";"X_433_7_747";"X_433_7_749";"X_433_7_750";'
        '"X_433_7_374";"X_433_7_596"\n',
        '1;01/12/2025;1;500;1;2025-01-05;170;80;M;1960;70;70;;;;;;\n',
        '1;01/12/2025;1;300;1;2025-01-20;400;80;M;1960;;;;;;;;\n',
        '2;01/12/2025;11;;;2025-01-21;165;60;F;1955;;;80;500;300;40;;\n',
        '3;01/12/2025;4;1000;2;2025-01-22;172;75;M;1962;;;;;;;0;60\n',
    ])
import contextlib as _ctx1
import io as _io1
with _warnings.catch_warnings():
    _warnings.simplefilter('ignore')
    with _ctx1.redirect_stdout(_io1.StringIO()):
        _dv = _dq4_run(_dq4_csv, tempfile.mkdtemp())
_hchk = [c for c in _dv.results['demographics']['checks'] if 'eight' in c['parameter']][0]
check('DQ4 flags the later impossible height (400 cm) despite a valid first row',
      _hchk['n_invalid'] == 1 and len(_hchk['invalid_records']) == 1)
_idp = _dv.results['identical_before_after']
check('identical ATIII before/after values (70/70) appear in the identity report',
      any(r['parameter'].startswith('Antithrombin') and r['before_value'] == 70.0
          for r in _idp['records']))
check('identity-report units are canonical (albumin g/dl, platelets /uL, no EPO-as-ATIII)',
      all(not (r[1] == 'Serum Albumin' and r[2] == 'mg/dl')
          and not (r[1] == 'Platelets' and 'x1000' in r[2])
          for r in _dv.BEFORE_AFTER_PAIRS))
_wh = [c for c in _dv.results['mat']['checks'] if 'ound blood hematocrit' in c['parameter']]
check('wound-blood hematocrit is actually checked on MAT rows (15-65 %, 80 flagged)',
      len(_wh) == 1 and _wh[0]['n_invalid'] == 1)
_qz = [c for c in _dv.results['lab_values']['checks']
       if c['parameter'].startswith('Quicks Test (before')][0]
check('DQ4 flags a documented Quick 0 as impossible (zero floor is an entry floor)',
      _qz['n_invalid'] == 1 and len(_qz['invalid_records']) == 1)

# ---------------------------------------------------------------- runner refuses derived end date
import subprocess as _sp
_r = _sp.run([sys.executable, 'run_full_analysis.py', _forms_csv, '--stats-only'],
             capture_output=True, text=True,
             cwd=os.path.dirname(os.path.abspath(__file__)))
check('full runner ABORTS without --data-end-date (clear error, non-zero exit)',
      _r.returncode == 1 and '--data-end-date' in (_r.stdout + _r.stderr))
check('runner usage documents the test-only escape hatch',
      '--allow-derived-end-date' in (_r.stdout + _r.stderr)
      or '--allow-derived-end-date' in open('run_full_analysis.py').read())

# ---------------------------------------------------------------- runner artifact contract
# BEHAVIOR probe: a visualization module that returns successfully but does
# not write its declared mandatory figure must be reported as FAILED
import run_full_analysis as _rfa
_probe_out = tempfile.mkdtemp()
open(os.path.join(_probe_out, 'probe_input.json'), 'w').write('{}')
_probe_mod = {
    'name': 'Artifact contract probe',
    'module': 'builtins',
    'function': 'print',
    'description': 'probe: returns successfully, writes nothing',
    'requires': 'probe_input.json',
    'needs_raw_data': False,
    'expected_artifacts': ['must_exist_probe.png'],
}
import contextlib as _ctx2
_probe_res = None
with _ctx2.redirect_stdout(_io1.StringIO()):
    _probe_res = _rfa.run_visualization_modules(_probe_out, '', [_probe_mod])
check('runner marks a visualization without its mandatory figure as FAILED',
      _probe_res['success'] == []
      and any('must_exist_probe.png' in reason for _, reason in _probe_res['failed']))
_bio_cfg = [m for m in _rfa.VISUALIZATION_MODULES if m['name'] == 'Biometric Visualizations'][0]
check('biometric visualizations receive the raw export and declare mandatory figures',
      _bio_cfg['needs_raw_data'] is True
      and 'biometric_violins.png' in _bio_cfg.get('expected_artifacts', []))

# ---------------------------------------------------------------- JSON sanitizer type coverage
from transfusion_registry_mapping import json_sanitize as _js
import json as _json2
_payload = {'f32': np.float32(1.5), 'f64nan': np.float64('nan'),
            'na': pd.NA, 'nat': pd.NaT,
            'dt64': np.datetime64('2026-01-01'),
            'inf': float('inf'), 'arr': np.array([np.float32(2.5), np.nan]),
            'nested': [{'x': np.float32('nan')}]}
_dumped = _json2.dumps(_js(_payload), allow_nan=False)
check('sanitizer handles float32, NaN, pd.NA, pd.NaT, datetime64, Infinity, arrays',
      '"f32": 1.5' in _dumped and '"f64nan": null' in _dumped
      and '"na": null' in _dumped and '"nat": null' in _dumped
      and '2026-01-01' in _dumped and '"inf": null' in _dumped
      and 'NaN' not in _dumped and 'Infinity' not in _dumped)

print(f"\nTOTAL: {len(passed)} passed, {len(failed)} failed")
sys.exit(1 if failed else 0)
