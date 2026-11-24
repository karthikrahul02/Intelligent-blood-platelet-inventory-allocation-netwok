# Synthetic Test Data Generator

**Author:** Elina Nuerenberg-Goloub — **Last revised:** 2026-08-18

## Purpose

`generate_test_data.py` produces the two fully synthetic validation
datasets and their answer keys. All patients are computer-generated; no
real data enters the generation in any form.

## Input and outputs

| | File | Location |
|---|---|---|
| Input | `header_template.csv` | `validation datasets/` (or the parent folder in a flat layout) |
| Output | `test_data_100patients.csv`, `test_data_150patients.csv` | `synthetic test data/` (or the parent folder) |
| Output | `seeded_errors_100.json`, `seeded_errors_150.json` | written together with the datasets |

The input template contains only the export structure (7 metadata rows and
the header row, 189 columns) — no data. One run writes all four output
files.

## Usage

```bash
cd "python codes"
python3 generate_test_data.py
```

## What is generated

Fictional patients in the exact registry export format, with all forms of
the electronic case report: basic data (year of birth), clinical episodes
with product administrations (product, administration date, dosage value
and unit, blood groups, indications, laboratory values before/after) and
follow-up questionnaires (completion date, physical capacity, Clinical
Frailty Scale, outcome items). All column assignments and value codes
follow the official data dictionary
(`20250227_Datenelemente-Transfusionsregister.csv`,
`20250227_permitted-values-Transfusionsregister.csv`).

## Planted errors and answer keys

While generating, deliberate data-quality errors are planted in disjoint
patient groups — wrong units, implausible values, contradictory duplicate
questionnaires, blood-group incompatibilities, negative lengths of stay,
and negative controls that must not be flagged. The generator records
which patient received which error as it plants them, producing the
machine-readable answer keys (`seeded_errors_*.json`). The complete
class-by-class table with counts is in `Validation.pdf`, section 4; the pipeline's
exact recovery of the planted errors is part of the validation described
there.

## Reproducibility

The generator uses fixed random seeds (seed 42). Every run reproduces all
four output files byte-identically, so the deposited datasets can be
regenerated and compared at any time. Conformance of the generated data to
the data dictionary and the exact placement of every planted error are
checked by `verify_test_data.py` (66 comparisons; see `validation datasets/Validation_Datasets.pdf`).

## Generating different data

The fixed seed is deliberate — the deposited datasets, the answer keys, and
the documented verification results all describe this one data state. To
generate a *different* synthetic cohort, change the two seed calls near the
top of `generate_test_data.py` (`np.random.seed(42)` / `random.seed(42)`)
to another value and rerun. Three things to know:

- The datasets and their answer keys are written together, so they stay
  consistent under any seed, and `verify_test_data.py` still checks the new
  data against the new keys.
- The documented results in `Validation.pdf` (the exact patients carrying
  each planted error, the documented boundary case, and the "nothing else
  flagged" outcome of the full run) apply to seed 42 only. Another seed
  plants the same error classes at different patients — and can additionally
  produce naturally extreme values that the screening then legitimately
  flags on top of the planted set.
- Rerunning with the default seed 42 restores the deposited files exactly,
  byte for byte.

For a hand-constructed sample with values of your own choosing, the
recommended route is `header_template.csv` (see "Constructing your own test
sample" in `validation datasets/Validation_Datasets.pdf`).

