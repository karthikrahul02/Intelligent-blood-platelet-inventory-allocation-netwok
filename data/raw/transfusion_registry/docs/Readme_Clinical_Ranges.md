# Clinical Value Ranges — Specification and Decisions

**Author:** Elina Nuerenberg-Goloub — **Last revised:** 2026-08-21

## The authoritative specification

All permissible value ranges used anywhere in the pipeline come from one
versioned specification: **`physician_value_ranges.csv`** (package root),
version 2026-08-21, **approved by the study lead**. It consolidates the
study's physician range documentation into canonical analysis units and is
the binding source — the code registry (`CLINICAL_RANGE_REGISTRY` in
`python codes/transfusion_registry_mapping.py`) mirrors it, and the test
battery compares registry and specification **value by value** (suite 2),
so any drift between code and the approved specification fails the
battery. No parameter bound is defined anywhere else.

## Decisions recorded

1. **Canonical albumin unit (binding: g/dl).** The specification states
   serum albumin in g/dl (0–7.0). This supersedes the mg/dl labels in
   older working documents and in the official registry data dictionary;
   the dictionary's registry-side correction is initiated. Documented
   albumin entries ≥ 100 are legacy wrong-scale (mg/dl) values — they are
   converted once (÷1000) and counted in the audit; the observed clinical
   values are on the g/dl scale.
2. **Zero floors on laboratory parameters** (study-lead decision
   2026-08-21): a floor of 0 on a laboratory parameter is the entry floor
   of the field, not a plausible measured value. Documented laboratory
   values ≤ 0 are excluded as impossible on every path and reported as
   data-quality findings — itemized with patient identifier and value,
   counted separately (`n_excluded_nonpositive`) and **never conflated
   with missing values**. Machine-autotransfusion volumes keep their
   inclusive 0 floors (a recovered volume of 0 ml is a real quantity).
3. **Dosage unit conventions** (confirmed clinically 2026-08-21): iron
   i.v. in mg, EPO in IU, oral iron in mg — completing the checked unit
   conventions for product codes 1–10; machine autotransfusion (11) is
   documented as not applicable.
4. **Weight is recorded as integer kilograms** (registry input
   constraint; permissible range 1–250 kg). Should the registry later
   permit decimal weights, the loader accepts them unchanged, analyzes the
   column as float, and reports the decimal entries as QC findings —
   INTEGER-declared fields are generally cast to integer only when every
   documented value is integral; decimal values are never truncated or
   dropped.
5. **Follow-up anchor in the review exports**: follow-up questionnaires
   are assigned relative to the patient's FIRST product administration —
   the same anchor the follow-up statistics use. A questionnaire completed
   before the first administration is never reported as a follow-up.

## Bounds

See `physician_value_ranges.csv` for the authoritative machine-readable
list (inclusive bounds, canonical units, per-parameter notes).
