"""
Cohort filters for registry export CSVs.

Two ways to restrict an export to a fixed cohort while retaining follow-up
questionnaires completed later:

A) Enrollment cutoff (date-inferred cohort)
   A patient is retained if their earliest "Episode date" (the episode-level
   date assigned by the registry, present on every row, format DD/MM/YYYY)
   is on or before the cutoff (<=). ALL records of retained patients are
   kept. Patients with no parseable "Episode date" on any row cannot be
   assigned to the cohort; they are EXCLUDED and reported explicitly.

   Note: this infers cohort membership from episode dates. It cannot
   represent consent-only registrants without episode records, and it counts
   post-cutoff episodes of retained patients. When the cohort must match an
   earlier export exactly, use B.

B) Cohort from an earlier export (PID whitelist) + optional clinical cap
   The cohort is exactly the set of PIDs present in a reference export
   (e.g. the export a submitted analysis was computed from) — including
   consent-only registrants. From the newer export, rows of cohort patients
   are kept as follows (when a cap date is given):
     - follow-up rows (any form-435 field filled): ALWAYS kept, regardless
       of date — this is the point of the exercise;
     - administration rows (any form-433 record-7 field filled): kept only
       if the ADMINISTRATION date (X_433_7_11) is <= the cap. Episodes that
       start before the cap but continue afterwards therefore contribute
       only their administrations up to the cap. Administration rows
       WITHOUT a parseable administration date are kept only if a
       corresponding administration exists in the reference export
       ("documented by the reference date" is the ground truth, and the
       reference export is exactly that set). Correspondence is checked
       per row, first by the registry record identifier ("Unique ID"
       column, where filled in both exports), then by content
       (PID + product + dose value + dose unit); each reference row can
       justify at most one row of the newer export, and a corrected row
       matches by identifier and carries its corrected values. Unmatched
       undated administrations are dropped and reported with PIDs;
     - other clinical rows (episode/record-0 data): kept only if
       "Episode date" <= the cap; rows without a parseable episode date
       are kept and reported for review.
   Cohort patients first treated after the cap therefore remain untreated in
   the filtered data (their late follow-ups are retained and will appear in
   the follow-up module's "follow-up without treatment" review category).

C) Reference-clinical splice (exact reviewed dataset + current follow-up)
   For analyses that must reproduce a reviewed data cut exactly while
   counting later follow-up: the output contains, for the patients of the
   reference export, ALL non-form-435 rows taken VERBATIM from the
   reference export (clinical data = the reviewed snapshot, deliberately
   forfeiting later corrections to clinical fields) and ALL form-435
   follow-up rows taken from the current export (follow-up = current
   state). Rows carrying any form-435 content count as follow-up rows.
   Schemas are aligned by column name (element IDs are stable): the
   reference column set must be a subset of the current one; the output
   uses the current schema, with current-only columns empty on reference-
   sourced rows and listed in the run summary. Renamed or removed columns
   abort the splice. Patients can be excluded entirely (--exclude-pids, e.g.
   consent erasure) or from follow-up only (--exclude-followup-pids,
   partial withdrawal: reviewed clinical rows stay, follow-up is removed);
   exclusions are recorded in the output file name and run summary.

The filtered file preserves the export structure: the first 8 lines
(7 metadata rows + header row) are copied verbatim (from the reference
export in splice mode); data rows of retained patients are written
unchanged in their original order.

Usage (standalone):
    python3 enrollment_filter.py <input_csv> <cutoff YYYY-MM-DD> [output_csv]
    python3 enrollment_filter.py <input_csv> --cohort-from <reference_csv> \
        [--episode-cutoff YYYY-MM-DD] [output_csv]
    python3 enrollment_filter.py <input_csv> --clinical-from <reference_csv> \
        [--exclude-pids P1,P2] [--exclude-followup-pids P1,P2] [output_csv]

    python3 enrollment_filter.py "../synthetic test data/test_data_150patients.csv" 2025-06-30
    python3 enrollment_filter.py ../new_export.csv \
        --cohort-from ../reference_export.csv --episode-cutoff 2026-01-15
    python3 enrollment_filter.py ../new_export.csv \
        --clinical-from ../reference_export.csv

Usually invoked via the master script instead:
    python3 run_full_analysis.py <input_csv> --enrollment-cutoff YYYY-MM-DD
    python3 run_full_analysis.py <input_csv> --cohort-from <reference_csv> \
        --episode-cutoff YYYY-MM-DD
    python3 run_full_analysis.py <input_csv> --clinical-from <reference_csv>
"""

import os
import sys

import pandas as pd

HEADER_LINES = 8  # 7 metadata rows + 1 header row, copied verbatim


def filter_by_enrollment_cutoff(input_csv, cutoff_date, output_csv=None):
    """Write a copy of input_csv containing only patients enrolled on or
    before cutoff_date. Returns (output_path, stats_dict).

    cutoff_date: 'YYYY-MM-DD' string or datetime-like.
    """
    cutoff = pd.to_datetime(cutoff_date)

    with open(input_csv, encoding='utf-8') as f:
        header_lines = [f.readline() for _ in range(HEADER_LINES)]
    if any(line == '' for line in header_lines):
        raise ValueError(f"{input_csv}: fewer than {HEADER_LINES} header lines")

    # dtype=str + keep_default_na=False so every value round-trips unchanged
    df = pd.read_csv(input_csv, sep=';', skiprows=HEADER_LINES - 1,
                     dtype=str, keep_default_na=False, encoding='utf-8')
    if 'PID' not in df.columns or 'Episode date' not in df.columns:
        raise ValueError(f"{input_csv}: expected 'PID' and 'Episode date' columns")

    episode_dates = pd.to_datetime(df['Episode date'], format='%d/%m/%Y',
                                   errors='coerce')
    enrollment = episode_dates.groupby(df['PID']).min()

    retained_pids = set(enrollment[enrollment <= cutoff].index)
    undatable_pids = sorted(enrollment[enrollment.isna()].index)
    after_cutoff_pids = set(enrollment[enrollment > cutoff].index)

    mask = df['PID'].isin(retained_pids)
    filtered = df[mask]

    if output_csv is None:
        stem, ext = os.path.splitext(input_csv)
        output_csv = f"{stem}_cohort{cutoff.strftime('%Y%m%d')}{ext}"

    with open(output_csv, 'w', encoding='utf-8', newline='') as f:
        f.writelines(header_lines)
        filtered.to_csv(f, sep=';', header=False, index=False)

    stats = {
        'cutoff': cutoff.strftime('%Y-%m-%d'),
        'patients_input': int(df['PID'].nunique()),
        'patients_retained': len(retained_pids),
        'patients_excluded_after_cutoff': len(after_cutoff_pids),
        'patients_excluded_no_enrollment_date': len(undatable_pids),
        'undatable_pids': [str(p) for p in undatable_pids],
        'rows_input': int(len(df)),
        'rows_retained': int(len(filtered)),
        'output_csv': output_csv,
    }
    return output_csv, stats


def _dedupe_labels(cols):
    """Deterministically disambiguate duplicate column labels by occurrence
    index ('label', 'label__dup1', 'label__dup2', ...).

    The registry export header repeats some labels (e.g. one
    "Unique ID (Form_Record_DataElement):" column per form). pandas 2.x
    mangles such duplicates at parse time into unique names ('X', 'X.1'),
    but newer parsers may preserve them, and duplicated labels break any
    label-based alignment. Occurrence-suffixing keeps both parser behaviors
    aligned across two exports, because a reference export's columns appear
    in the current export in the same relative order (the schema only gains
    elements). Suffixes are internal only - output files are written with
    the original header line and values, never with these names."""
    seen = {}
    out = []
    for c in cols:
        k = seen.get(c, 0)
        seen[c] = k + 1
        out.append(c if k == 0 else f"{c}__dup{k}")
    return out


def _duplicated_label_counts(cols):
    counts = {}
    for c in cols:
        counts[c] = counts.get(c, 0) + 1
    return {c: n for c, n in counts.items() if n > 1}


def _is_padding(name, series):
    """An all-empty column whose (base) label is empty or parser-generated."""
    base = name.split('__dup')[0]
    return (base == '' or base.startswith('Unnamed:')) and (series == '').all()


def _followup_mask(frame):
    """Rows carrying any form-435 (follow-up questionnaire) content."""
    cols = [c for c in frame.columns if c.startswith('X_435_')]
    if not cols:
        return pd.Series(False, index=frame.index)
    return (frame[cols] != '').any(axis=1)


def splice_reference_clinical(current_csv, reference_csv, exclude_pids=None,
                              exclude_followup_pids=None,
                              reference_followup_pids=None, output_csv=None):
    """Build an analysis file whose clinical rows are the reference export
    verbatim and whose follow-up rows come from the current export.
    reference_followup_pids: patients whose follow-up rows are taken from
    the REFERENCE export instead (e.g. patients who withdrew consent after
    the reference date and are absent from the current export - their
    pre-withdrawal responses exist only in the reference snapshot).
    Returns (output_path, stats_dict)."""
    exclude_pids = {str(p) for p in (exclude_pids or [])}
    exclude_fu = {str(p) for p in (exclude_followup_pids or [])}
    ref_fu_pids = {str(p) for p in (reference_followup_pids or [])}

    with open(reference_csv, encoding='utf-8') as f:
        ref_header = [f.readline() for _ in range(HEADER_LINES)]
    with open(current_csv, encoding='utf-8') as f:
        cur_header = [f.readline() for _ in range(HEADER_LINES)]
    if any(line == '' for line in ref_header + cur_header):
        raise ValueError("one of the exports has fewer than "
                         f"{HEADER_LINES} header lines")

    ref = pd.read_csv(reference_csv, sep=';', skiprows=HEADER_LINES - 1,
                      dtype=str, keep_default_na=False, encoding='utf-8')
    cur = pd.read_csv(current_csv, sep=';', skiprows=HEADER_LINES - 1,
                      dtype=str, keep_default_na=False, encoding='utf-8')

    # The export header repeats some labels (one "Unique ID ..." column per
    # form). Depending on the pandas version these arrive mangled ('X.1')
    # or preserved as true duplicates; disambiguate deterministically by
    # occurrence so label-based alignment is safe under both behaviors.
    dup_ref = _duplicated_label_counts(ref.columns)
    dup_cur = _duplicated_label_counts(cur.columns)
    ref.columns = _dedupe_labels(ref.columns)
    cur.columns = _dedupe_labels(cur.columns)
    for name, frame in (('reference', ref), ('current', cur)):
        if 'PID__dup1' in frame.columns:
            raise ValueError(f"the {name} export has more than one 'PID' "
                             "column - cannot align")
    if 'PID' not in ref.columns or 'PID' not in cur.columns:
        raise ValueError("expected a 'PID' column in both exports")

    # Name-keyed schema alignment. The eCRF may gain data elements between
    # exports: the reference column set must be a SUBSET of the current one
    # (element IDs are stable identifiers; duplicated labels are matched by
    # occurrence order); the spliced file is emitted in the CURRENT schema,
    # with current-only columns empty on reference-sourced rows. Renamed or
    # removed reference columns are genuine incompatibility and abort the
    # splice. Empty padding columns (from trailing/empty separators;
    # unnamed after parsing) are ignored for the comparison.
    ref_real = [c for c in ref.columns if not _is_padding(c, ref[c])]
    cur_real = {c for c in cur.columns if not _is_padding(c, cur[c])}
    missing_in_current = [c for c in ref_real if c not in cur_real]
    if missing_in_current:
        raise ValueError(
            "reference export columns absent from the current export "
            f"(renamed or removed element IDs - genuine schema "
            f"incompatibility): {missing_in_current}")
    current_only_cols = [c for c in cur.columns
                         if c in cur_real and c not in set(ref_real)]
    # column-by-column build against the current schema (never NA-fills,
    # safe regardless of how the parser treated duplicate labels)
    ref_cols = set(ref.columns)
    ref = pd.DataFrame({c: (ref[c] if c in ref_cols else
                            pd.Series('', index=ref.index))
                        for c in cur.columns})
    header_diagnostics = {
        'reference_columns': len(ref_cols),
        'current_columns': len(cur.columns),
        'duplicated_labels_reference': dup_ref,
        'duplicated_labels_current': dup_cur,
    }

    cohort = set(ref['PID']) - exclude_pids

    ref_fu = _followup_mask(ref)
    cur_fu = _followup_mask(cur)
    clinical = ref[~ref_fu & ref['PID'].isin(cohort)]
    followup = cur[cur_fu &
                   cur['PID'].isin(cohort - exclude_fu - ref_fu_pids)]
    followup_ref = ref[ref_fu &
                       ref['PID'].isin((cohort & ref_fu_pids) - exclude_fu)]
    spliced = pd.concat([clinical, followup, followup_ref],
                        ignore_index=True)

    if output_csv is None:
        stem, ext = os.path.splitext(current_csv)
        ref_stem = os.path.splitext(os.path.basename(reference_csv))[0]
        suffix = f"_clinicalfrom{ref_stem}"
        if exclude_pids:
            suffix += f"_excl{len(exclude_pids)}"
        if exclude_fu:
            suffix += f"_exclfu{len(exclude_fu)}"
        if ref_fu_pids:
            suffix += f"_reffu{len(ref_fu_pids)}"
        output_csv = f"{stem}{suffix}{ext}"

    with open(output_csv, 'w', encoding='utf-8', newline='') as f:
        f.writelines(cur_header)  # the output uses the current export's schema
        spliced.to_csv(f, sep=';', header=False, index=False)

    fu_pids_wo_clinical = sorted(
        (set(followup['PID']) | set(followup_ref['PID'])) -
        set(clinical['PID']))
    stats = {
        'mode': 'reference_clinical_splice',
        'reference_csv': reference_csv,
        'current_csv': current_csv,
        'cohort_size': len(cohort),
        'excluded_pids': sorted(exclude_pids),
        'excluded_followup_pids': sorted(exclude_fu),
        'reference_followup_pids': sorted(ref_fu_pids),
        'current_only_columns': current_only_cols,
        'header_diagnostics': header_diagnostics,
        'clinical_rows_from_reference': int(len(clinical)),
        'followup_rows_from_current': int(len(followup)),
        'followup_rows_from_reference': int(len(followup_ref)),
        'followup_pids_without_clinical_rows':
            [str(p) for p in fu_pids_wo_clinical],
        'current_only_patients_dropped':
            int(cur.loc[~cur['PID'].isin(cohort), 'PID'].nunique()),
        'rows_output': int(len(spliced)),
        'output_csv': output_csv,
    }
    return output_csv, stats


def print_splice_stats(stats):
    hd = stats.get('header_diagnostics', {})
    if hd:
        print(f"Header diagnostics:    reference {hd['reference_columns']} "
              f"columns, current {hd['current_columns']} columns")
        for side in ('reference', 'current'):
            dups = hd.get(f'duplicated_labels_{side}', {})
            if dups:
                print(f"  duplicated labels in {side} export (aligned by "
                      f"occurrence): "
                      + ", ".join(f"'{c}' x{n}" for c, n in dups.items()))
    print(f"Clinical rows:         {stats['clinical_rows_from_reference']} "
          f"(VERBATIM from {stats['reference_csv']})")
    if stats['current_only_columns']:
        print(f"Schema evolution:      {len(stats['current_only_columns'])} "
              f"column(s) exist only in the current export and are empty on "
              f"reference-sourced rows: "
              f"{', '.join(stats['current_only_columns'])}")
    print(f"Follow-up rows:        {stats['followup_rows_from_current']} "
          f"(from {stats['current_csv']})")
    if stats['reference_followup_pids']:
        print(f"Follow-up from the REFERENCE export instead: "
              f"{stats['followup_rows_from_reference']} row(s) for "
              f"{len(stats['reference_followup_pids'])} patient(s) "
              f"(PIDs: {', '.join(stats['reference_followup_pids'])}) - "
              f"e.g. withdrawn after the reference date; their responses "
              f"exist only in the reference snapshot")
    print(f"Cohort:                {stats['cohort_size']} patients "
          f"(all patients of the reference export"
          + (f", {len(stats['excluded_pids'])} excluded entirely: "
             f"{', '.join(stats['excluded_pids'])}" if stats['excluded_pids']
             else "")
          + (f", {len(stats['excluded_followup_pids'])} excluded from "
             f"follow-up only: {', '.join(stats['excluded_followup_pids'])}"
             if stats['excluded_followup_pids'] else "") + ")")
    print(f"Patients only in the current export (dropped): "
          f"{stats['current_only_patients_dropped']}")
    if stats['followup_pids_without_clinical_rows']:
        print(f"NOTE - patients with follow-up rows but no clinical rows in "
              f"the reference snapshot: "
              f"{len(stats['followup_pids_without_clinical_rows'])} "
              f"(PIDs: {', '.join(stats['followup_pids_without_clinical_rows'])})")
        print("         Expected for registrants first treated after the "
              "reference date - their questionnaires appear under "
              "'follow-up without treatment' for review.")
    print(f"Rows written:          {stats['rows_output']}")
    print(f"Spliced file:          {stats['output_csv']}")


def filter_by_cohort_whitelist(data_csv, cohort_csv, episode_cutoff=None,
                               output_csv=None):
    """Restrict data_csv to the patients present in cohort_csv (PID
    whitelist). Optionally cap clinical rows at episode_cutoff while always
    keeping follow-up rows. Returns (output_path, stats_dict)."""
    ref = pd.read_csv(cohort_csv, sep=';', skiprows=HEADER_LINES - 1,
                      dtype=str, keep_default_na=False, encoding='utf-8')
    if 'PID' not in ref.columns:
        raise ValueError(f"{cohort_csv}: expected a 'PID' column")
    whitelist = set(ref['PID'])

    with open(data_csv, encoding='utf-8') as f:
        header_lines = [f.readline() for _ in range(HEADER_LINES)]
    if any(line == '' for line in header_lines):
        raise ValueError(f"{data_csv}: fewer than {HEADER_LINES} header lines")

    df = pd.read_csv(data_csv, sep=';', skiprows=HEADER_LINES - 1,
                     dtype=str, keep_default_na=False, encoding='utf-8')
    if 'PID' not in df.columns or 'Episode date' not in df.columns:
        raise ValueError(f"{data_csv}: expected 'PID' and 'Episode date' columns")

    in_cohort = df['PID'].isin(whitelist)
    cols_435 = [c for c in df.columns if c.startswith('X_435_')]
    is_followup = (df[cols_435] != '').any(axis=1) if cols_435 else \
        pd.Series(False, index=df.index)
    cols_admin = [c for c in df.columns if c.startswith('X_433_7_')]
    is_admin = ~is_followup & ((df[cols_admin] != '').any(axis=1)
                               if cols_admin else False)

    n_undatable_clinical = 0
    undatable_clinical_pids = []
    n_undated_kept_recordid = 0
    n_undated_kept_content = 0
    n_undated_dropped = 0
    undated_unmatched_pids = []
    n_admin_dropped = 0
    if episode_cutoff is not None:
        from collections import Counter
        cap = pd.to_datetime(episode_cutoff)
        ep = pd.to_datetime(df['Episode date'], format='%d/%m/%Y',
                            errors='coerce')
        episode_ok = (ep <= cap) | ep.isna()

        # administration rows are capped by the ADMINISTRATION date, so
        # episodes straddling the cap contribute only their administrations
        # up to the cap
        admin_date = pd.to_datetime(
            df['X_433_7_11'], errors='coerce') if 'X_433_7_11' in df.columns \
            else pd.Series(pd.NaT, index=df.index)
        admin_ok = (admin_date <= cap)

        # UNDATED administration rows are kept only if a corresponding
        # administration exists in the reference export ("documented by the
        # reference date"). Matching: record identifier first, then content;
        # each reference row justifies at most one row here.
        def _col(frame, name):
            return frame[name] if name in frame.columns else \
                pd.Series('', index=frame.index)

        def _uid_col(frame):
            name = next((c for c in frame.columns
                         if c.startswith('Unique ID')), None)
            return _col(frame, name) if name else \
                pd.Series('', index=frame.index)

        def _normcode(s):
            return s.astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

        def _admin_mask(frame):
            cols7 = [c for c in frame.columns if c.startswith('X_433_7_')]
            cols435 = [c for c in frame.columns if c.startswith('X_435_')]
            fu = (frame[cols435] != '').any(axis=1) if cols435 else \
                pd.Series(False, index=frame.index)
            return (~fu & ((frame[cols7] != '').any(axis=1)
                           if cols7 else False))

        ref_admin = ref[_admin_mask(ref)]
        ref_uid = _uid_col(ref_admin)
        uid_counter = Counter(
            zip(ref_admin.loc[ref_uid != '', 'PID'], ref_uid[ref_uid != '']))
        content_counter = Counter(zip(
            ref_admin['PID'],
            _normcode(_col(ref_admin, 'X_433_7_746')),
            _normcode(_col(ref_admin, 'X_433_7_22')),
            _normcode(_col(ref_admin, 'X_433_7_734'))))

        df_uid = _uid_col(df)
        df_prod = _normcode(_col(df, 'X_433_7_746'))
        df_dose = _normcode(_col(df, 'X_433_7_22'))
        df_unit = _normcode(_col(df, 'X_433_7_734'))
        undated_idx = df.index[in_cohort & is_admin & admin_date.isna()]
        unmatched_pid_set = set()
        for i in undated_idx:
            pid = df.at[i, 'PID']
            uid = df_uid.at[i]
            if uid and uid_counter[(pid, uid)] > 0:
                uid_counter[(pid, uid)] -= 1
                admin_ok.at[i] = True
                n_undated_kept_recordid += 1
                continue
            ckey = (pid, df_prod.at[i], df_dose.at[i], df_unit.at[i])
            if content_counter[ckey] > 0:
                content_counter[ckey] -= 1
                admin_ok.at[i] = True
                n_undated_kept_content += 1
            else:
                n_undated_dropped += 1
                unmatched_pid_set.add(pid)
        undated_unmatched_pids = sorted(unmatched_pid_set)

        undatable_clinical = in_cohort & ~is_followup & ~is_admin & ep.isna()
        n_undatable_clinical = int(undatable_clinical.sum())
        undatable_clinical_pids = sorted(df.loc[undatable_clinical, 'PID'].unique())

        keep = in_cohort & (is_followup |
                            (is_admin & admin_ok) |
                            (~is_admin & ~is_followup & episode_ok))
        n_admin_dropped = int((in_cohort & is_admin & ~admin_ok).sum())
    else:
        cap = None
        keep = in_cohort

    filtered = df[keep]

    if output_csv is None:
        stem, ext = os.path.splitext(data_csv)
        ref_stem = os.path.splitext(os.path.basename(cohort_csv))[0]
        suffix = f"_cohortfrom{ref_stem}"
        if cap is not None:
            suffix += f"_cap{cap.strftime('%Y%m%d')}"
        output_csv = f"{stem}{suffix}{ext}"

    with open(output_csv, 'w', encoding='utf-8', newline='') as f:
        f.writelines(header_lines)
        filtered.to_csv(f, sep=';', header=False, index=False)

    data_pids = set(df['PID'])
    missing_from_data = sorted(whitelist - data_pids)
    # cohort patients present in the data whose every row was dropped by the
    # episode cap - they would silently leave the cohort denominator
    vanished_after_cap = sorted((data_pids & whitelist) -
                                set(filtered['PID']))
    fu_kept = filtered[(filtered[cols_435] != '').any(axis=1)] if cols_435 \
        else filtered.iloc[0:0]
    stats = {
        'mode': 'cohort_whitelist',
        'cohort_source': cohort_csv,
        'episode_cutoff': cap.strftime('%Y-%m-%d') if cap is not None else None,
        'cohort_size': len(whitelist),
        'cohort_pids_missing_from_data': [str(p) for p in missing_from_data],
        'cohort_pids_no_rows_after_cap': [str(p) for p in vanished_after_cap],
        'patients_input': int(df['PID'].nunique()),
        'patients_retained': int(filtered['PID'].nunique()),
        'patients_dropped_not_in_cohort': int(df.loc[~in_cohort, 'PID'].nunique()),
        'rows_input': int(len(df)),
        'rows_retained': int(len(filtered)),
        'admin_rows_dropped_after_cap': n_admin_dropped,
        'clinical_rows_dropped_after_cap': int((in_cohort & ~keep).sum())
                                          - n_admin_dropped,
        'admin_rows_retained': int((keep & is_admin).sum()),
        'followup_rows_retained': int(len(fu_kept)),
        'admin_undated_kept_by_recordid': n_undated_kept_recordid,
        'admin_undated_kept_by_content': n_undated_kept_content,
        'admin_undated_dropped_unmatched': n_undated_dropped,
        'undated_unmatched_pids': [str(p) for p in undated_unmatched_pids],
        'clinical_rows_undatable_kept': n_undatable_clinical,
        'undatable_clinical_pids': [str(p) for p in undatable_clinical_pids],
        'output_csv': output_csv,
    }
    return output_csv, stats


def print_whitelist_stats(stats):
    print(f"Cohort source:         {stats['cohort_source']} "
          f"({stats['cohort_size']} patients)")
    if stats['episode_cutoff']:
        print(f"Clinical cap:          administrations kept only if the "
              f"administration date is on or before {stats['episode_cutoff']}; "
              f"other clinical rows by episode date; follow-up rows always kept")
    print(f"Patients in input:     {stats['patients_input']}")
    print(f"Patients retained:     {stats['patients_retained']}")
    print(f"Dropped (not in cohort): {stats['patients_dropped_not_in_cohort']}")
    if stats['cohort_pids_missing_from_data']:
        print(f"WARNING - cohort patients absent from this export: "
              f"{len(stats['cohort_pids_missing_from_data'])} "
              f"(PIDs: {', '.join(stats['cohort_pids_missing_from_data'])})")
        print("         These existed in the reference export but have no rows "
              "here - review in the registry.")
    if stats['cohort_pids_no_rows_after_cap']:
        print(f"WARNING - cohort patients with NO rows on or before the episode "
              f"cap: {len(stats['cohort_pids_no_rows_after_cap'])} "
              f"(PIDs: {', '.join(stats['cohort_pids_no_rows_after_cap'])})")
        print("         They are absent from the filtered file, shrinking the "
              "cohort denominator - review their episode dates in the registry.")
    print(f"Rows: {stats['rows_input']} -> {stats['rows_retained']} "
          f"(administrations: {stats['admin_rows_retained']} kept, "
          f"{stats['admin_rows_dropped_after_cap']} beyond the cap dropped; "
          f"other clinical rows beyond the cap dropped: "
          f"{stats['clinical_rows_dropped_after_cap']}; follow-up rows "
          f"retained: {stats['followup_rows_retained']})")
    n_undated = (stats['admin_undated_kept_by_recordid'] +
                 stats['admin_undated_kept_by_content'] +
                 stats['admin_undated_dropped_unmatched'])
    if n_undated:
        print(f"Undated administrations: {n_undated} total - "
              f"{stats['admin_undated_kept_by_recordid']} kept (matched in the "
              f"reference export by record ID), "
              f"{stats['admin_undated_kept_by_content']} kept (matched by "
              f"content), {stats['admin_undated_dropped_unmatched']} dropped "
              f"(no counterpart in the reference export)")
    if stats['admin_undated_dropped_unmatched']:
        print(f"NOTE - dropped undated administrations belong to PIDs: "
              f"{', '.join(stats['undated_unmatched_pids'])} - these were not "
              f"documented in the reference export and are treated as "
              f"post-reference documentation.")
    if stats['clinical_rows_undatable_kept']:
        print(f"WARNING - clinical rows without parseable episode date kept: "
              f"{stats['clinical_rows_undatable_kept']} "
              f"(PIDs: {', '.join(stats['undatable_clinical_pids'])}) - review "
              f"in the registry.")
    print(f"Filtered file:         {stats['output_csv']}")


def print_stats(stats):
    print(f"Enrollment cutoff:     {stats['cutoff']} (patients whose first "
          f"episode is on or before this date are retained)")
    print(f"Patients in input:     {stats['patients_input']}")
    print(f"Patients retained:     {stats['patients_retained']}")
    print(f"Excluded (enrolled after cutoff): "
          f"{stats['patients_excluded_after_cutoff']}")
    if stats['patients_excluded_no_enrollment_date']:
        print(f"WARNING - excluded, no parseable Episode date on any row: "
              f"{stats['patients_excluded_no_enrollment_date']} "
              f"(PIDs: {', '.join(stats['undatable_pids'])})")
        print("         These patients cannot be assigned to the cohort and "
              "should be reviewed in the registry.")
    print(f"Rows: {stats['rows_input']} -> {stats['rows_retained']}")
    print(f"Filtered file:         {stats['output_csv']}")


def _parse_date_arg(value, name):
    try:
        pd.to_datetime(value, format='%Y-%m-%d')
    except (ValueError, TypeError):
        print(f"Error: {name} must be YYYY-MM-DD, got: {value}")
        sys.exit(1)
    return value


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    input_csv = args[0]
    if not os.path.exists(input_csv):
        print(f"Error: input file not found: {input_csv}")
        sys.exit(1)

    if '--clinical-from' in args:
        idx = args.index('--clinical-from')
        if idx + 1 >= len(args):
            print("Error: --clinical-from requires a reference CSV path")
            sys.exit(1)
        reference_csv = args[idx + 1]
        if not os.path.exists(reference_csv):
            print(f"Error: reference export not found: {reference_csv}")
            sys.exit(1)

        def _pid_list(flag):
            if flag not in args:
                return []
            fidx = args.index(flag)
            if fidx + 1 >= len(args):
                print(f"Error: {flag} requires a comma-separated PID list")
                sys.exit(1)
            return [p.strip() for p in args[fidx + 1].split(',') if p.strip()]

        consumed = {'--clinical-from', '--exclude-pids',
                    '--exclude-followup-pids', '--reference-followup-pids'}
        positional = [a for i, a in enumerate(args[1:], start=1)
                      if not a.startswith('--') and args[i - 1] not in consumed]
        _, stats = splice_reference_clinical(
            input_csv, reference_csv,
            exclude_pids=_pid_list('--exclude-pids'),
            exclude_followup_pids=_pid_list('--exclude-followup-pids'),
            reference_followup_pids=_pid_list('--reference-followup-pids'),
            output_csv=positional[0] if positional else None)
        print_splice_stats(stats)
        return

    if '--cohort-from' in args:
        idx = args.index('--cohort-from')
        if idx + 1 >= len(args):
            print("Error: --cohort-from requires a reference CSV path")
            sys.exit(1)
        cohort_csv = args[idx + 1]
        if not os.path.exists(cohort_csv):
            print(f"Error: reference export not found: {cohort_csv}")
            sys.exit(1)
        episode_cutoff = None
        if '--episode-cutoff' in args:
            cidx = args.index('--episode-cutoff')
            if cidx + 1 >= len(args):
                print("Error: --episode-cutoff requires a date (YYYY-MM-DD)")
                sys.exit(1)
            episode_cutoff = _parse_date_arg(args[cidx + 1], '--episode-cutoff')
        positional = [a for i, a in enumerate(args[1:], start=1)
                      if not a.startswith('--')
                      and args[i - 1] not in ('--cohort-from', '--episode-cutoff')]
        output_csv = positional[0] if positional else None
        _, stats = filter_by_cohort_whitelist(input_csv, cohort_csv,
                                              episode_cutoff, output_csv)
        print_whitelist_stats(stats)
        return

    if len(args) < 2:
        print(__doc__)
        sys.exit(1)
    cutoff = _parse_date_arg(args[1], 'cutoff')
    output_csv = args[2] if len(args) > 2 else None
    _, stats = filter_by_enrollment_cutoff(input_csv, cutoff, output_csv)
    print_stats(stats)


if __name__ == '__main__':
    main()
