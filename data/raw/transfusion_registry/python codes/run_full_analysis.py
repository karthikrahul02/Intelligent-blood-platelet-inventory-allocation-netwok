#!/usr/bin/env python3
"""
Master Analysis Script for Transfusion Registry Data

This script runs all analysis modules in the correct order:
1. Descriptive Statistics (biometrics, treatments, indications, follow-up, temporal volumes, SNOMED codes, LOS)
2. Data Quality Checks (completeness, dosage, follow-up duplicates, validity, lab values)
3. Visualizations (all figures for each analysis module)

Usage:
    python3 run_full_analysis.py <input_csv_path>
    python3 run_full_analysis.py <input_csv_path> --interactive
    python3 run_full_analysis.py <input_csv_path> --skip-quality
    python3 run_full_analysis.py <input_csv_path> --stats-only
    python3 run_full_analysis.py <input_csv_path> --viz-only
    python3 run_full_analysis.py <input_csv_path> --enrollment-cutoff YYYY-MM-DD
    python3 run_full_analysis.py <input_csv_path> --data-end-date YYYY-MM-DD
    python3 run_full_analysis.py <input_csv_path> --allow-derived-end-date   (test runs only)
    python3 run_full_analysis.py <input_csv_path> --cohort-from <reference_csv> [--episode-cutoff YYYY-MM-DD]
    python3 run_full_analysis.py <input_csv_path> --clinical-from <reference_csv> [--exclude-pids P1,P2] [--exclude-followup-pids P1,P2]

Examples:
    python3 run_full_analysis.py "../synthetic test data/test_data_150patients.csv"
    python3 run_full_analysis.py "../synthetic test data/test_data_150patients.csv" --interactive
    python3 run_full_analysis.py "../synthetic test data/test_data_150patients.csv" --enrollment-cutoff 2025-06-30
    python3 run_full_analysis.py ../new_export.csv --cohort-from ../reference_export.csv --episode-cutoff 2026-01-15

Options:
    --enrollment-cutoff YYYY-MM-DD
        Restrict the analysis to the cohort of patients whose first episode
        date is on or before the given date, while keeping ALL records of
        those patients (including follow-ups completed after the cutoff).
        A filtered copy of the export (<stem>_cohortYYYYMMDD.csv) is written
        next to the input file and all modules run on it, so the output
        directory name records the cohort definition. See enrollment_filter.py.

    --cohort-from <reference_csv> [--episode-cutoff YYYY-MM-DD]
        Restrict the analysis to exactly the patients present in the
        reference export (PID whitelist — including consent-only
        registrants without episode records). With --episode-cutoff,
        clinical rows are kept only up to that episode date while follow-up
        rows are always kept, so treatment data matches the reference
        window but later follow-up questionnaires are analyzed. Mutually
        exclusive with --enrollment-cutoff. The filtered copy is named
        <stem>_cohortfrom<reference>_capYYYYMMDD.csv and the output
        directory follows it, recording the full cohort definition.

    --clinical-from <reference_csv> [--exclude-pids P1,P2] [--exclude-followup-pids P1,P2]
        Reference-clinical splice: the analysis file contains, for the
        patients of the reference export, all non-follow-up rows VERBATIM
        from the reference export (clinical data = the exact reviewed data
        cut) and all follow-up (form 435) rows from the current export.
        Schemas are aligned by column name: the reference columns must be
        a subset of the current export's (new eCRF elements are allowed
        and stay empty on reference-sourced rows; renamed or removed
        columns abort the run).
        --exclude-pids removes patients entirely (e.g. consent erasure);
        --exclude-followup-pids keeps their reviewed clinical rows but
        removes their follow-up (partial withdrawal). Exclusions are
        recorded in the output file name and run summary. Mutually
        exclusive with the other cohort options.

Output:
    Creates a directory named after the CSV file (e.g., test_data_150patients/) containing:
    - All statistics files (JSON, TXT, CSV)
    - Data quality reports
    - figures/ subdirectory with all visualizations

Author: Elina Nuerenberg-Goloub with Claude Opus 4.5 by Anthropic
Date: 2026-01-25
"""

import sys
import os
import time
from datetime import datetime
from typing import List, Tuple, Optional, Callable

# =============================================================================
# CONFIGURATION: Define all analysis modules
# =============================================================================

# Statistics modules: (name, function_import, description, output_files)
STATISTICS_MODULES = [
    {
        'name': 'Biometric Statistics',
        'module': 'descriptive_biometrics',
        'function': 'run_biometric_analysis',
        'description': 'Patient demographics, physical characteristics, comorbidities',
        'outputs': ['biometric_descriptives.csv', 'biometric_descriptives.txt', 'biometric_descriptives_detailed.json'],
        'required_for_viz': 'biometrics',
    },
    {
        'name': 'Treatment Statistics',
        'module': 'descriptive_treatments',
        'function': 'run_treatment_analysis',
        'description': 'Blood product administration, dosages, lab values',
        'outputs': ['treatment_statistics_detailed.json', 'treatment_statistics_combined.txt'],
        'required_for_viz': 'treatments',
    },
    {
        'name': 'Indication Statistics',
        'module': 'descriptive_indications',
        'function': 'run_indication_intervention_analysis',
        'description': 'Indications, interventions, hemorrhage risk',
        'outputs': ['indication_intervention_statistics_detailed.json', 'indication_intervention_statistics_combined.txt'],
        'required_for_viz': 'indications',
    },
    {
        'name': 'Follow-up Statistics',
        'module': 'descriptive_followup',
        'function': 'run_followup_analysis',
        'description': 'Patient outcomes at 3-month and 1-year follow-up',
        'outputs': ['followup_statistics_detailed.json', 'followup_statistics.txt'],
        'required_for_viz': 'followup',
    },
    {
        'name': 'Temporal Volume Analysis',
        'module': 'descriptive_temporal_volumes',
        'function': 'run_temporal_volume_analysis',
        'description': 'Monthly and quarterly blood product volumes',
        'outputs': ['temporal_volumes_detailed.json', 'temporal_volumes_combined.txt'],
        'required_for_viz': 'temporal',
    },
    {
        'name': 'SNOMED Code Analysis',
        'module': 'descriptive_snomed',
        'function': 'run_snomed_analysis',
        'description': 'Diagnoses and procedures (SNOMED CT codes)',
        'outputs': ['SNOMED/snomed_statistics.json', 'SNOMED/snomed_statistics.txt', 'SNOMED/snomed_codes_for_lookup.csv'],
        'required_for_viz': None,
    },
    {
        'name': 'Post-Intervention Time to Discharge',
        'module': 'descriptive_los',
        'function': 'run_los_analysis',
        'description': 'Days from interventional care to hospital discharge (no admission date in the export)',
        'outputs': ['LOS/los_analysis.json', 'LOS/los_analysis.txt', 'LOS/los_patient_data.csv'],
        'required_for_viz': None,
    },
]

# Data quality modules
DATA_QUALITY_MODULES = [
    {
        'name': 'Completeness Analysis',
        'module': 'data_quality_module1_completeness',
        'function': 'run_completeness_analysis',
        'description': 'Data completeness across all sections',
        'outputs': ['data_quality_completeness.json', 'data_quality_completeness.txt'],
    },
    {
        'name': 'Dosage Quality',
        'module': 'data_quality_module2_dosage',
        'function': 'run_dosage_analysis',
        'description': 'Dosage plausibility and unit validation',
        'outputs': ['data_quality_dosage.json', 'data_quality_dosage.txt'],
    },
    {
        'name': 'Follow-up Duplicates',
        'module': 'data_quality_module3_followup_duplicates',
        'function': 'run_followup_duplicates_analysis',
        'description': 'Detection and resolution of duplicate follow-up records',
        'outputs': ['data_quality_followup_duplicates.json', 'data_quality_followup_duplicates.txt'],
    },
    {
        'name': 'Data Validity',
        'module': 'data_quality_module4_validity',
        'function': 'run_validity_analysis',
        'description': 'Value range and logical consistency checks',
        'outputs': ['data_quality_validity.json', 'data_quality_validity.txt'],
    },
    {
        'name': 'Lab Value Quality',
        'module': 'lab_value_quality',
        'function': 'run_lab_value_quality_check',
        'description': 'Lab value unit detection and outlier flagging',
        'outputs': ['lab_value_quality_report.txt', 'lab_value_unit_issues.csv'],
    },
]

# Visualization modules
VISUALIZATION_MODULES = [
    {
        'name': 'Biometric Visualizations',
        'module': 'visualize_biometrics',
        'function': 'run_biometric_visualization',
        'description': 'Age pyramid, BMI distribution, comorbidities',
        'requires': 'biometric_descriptives_detailed.json',
        'needs_raw_data': True,  # violin/raw-data plots need the export CSV
        'expected_artifacts': ['biometric_gender_distribution.png',
                               'biometric_violins.png'],
    },
    {
        'name': 'Treatment Visualizations',
        'module': 'visualize_treatments',
        'function': 'run_treatment_visualization',
        'description': 'Product distribution, temporal trends, lab value violin plots',
        'requires': 'treatment_statistics_detailed.json',
        'needs_raw_data': True,
    },
    {
        'name': 'Dosage Visualizations',
        'module': 'visualize_dosages',
        'function': 'run_dosage_visualization',
        'description': 'Dosage histograms by product',
        'requires': 'treatment_statistics_detailed.json',
        'needs_raw_data': True,
    },
    {
        'name': 'Indication Visualizations',
        'module': 'visualize_indications',
        'function': 'run_indication_visualization',
        'description': 'Indication and intervention charts',
        'requires': 'indication_intervention_statistics_detailed.json',
        'needs_raw_data': False,
    },
    {
        'name': 'Follow-up Visualizations',
        'module': 'visualize_followup',
        'function': 'run_followup_visualization',
        'description': 'Outcome distributions and comparisons',
        'requires': 'followup_statistics_detailed.json',
        'needs_raw_data': False,
    },
    {
        'name': 'Temporal Volume Visualizations',
        'module': 'visualize_temporal_volumes',
        'function': 'run_temporal_volume_visualization',
        'description': 'Monthly and quarterly volume charts',
        'requires': 'temporal_volumes_detailed.json',
        'needs_raw_data': False,
    },
]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def print_header(text: str, char: str = '='):
    """Print a formatted header."""
    width = 70
    print()
    print(char * width)
    print(f"  {text}")
    print(char * width)


def print_step(step_num: int, total: int, name: str):
    """Print a step indicator."""
    print(f"\n[{step_num}/{total}] {name}")
    print("-" * 50)


def print_success(message: str):
    """Print a success message."""
    print(f"  [OK] {message}")


def print_error(message: str):
    """Print an error message."""
    print(f"  [ERROR] {message}")


def print_skip(message: str):
    """Print a skip message."""
    print(f"  [SKIP] {message}")


def format_duration(seconds: float) -> str:
    """Format duration in human-readable form."""
    if seconds < 60:
        return f"{seconds:.1f} seconds"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def get_output_dir_name(csv_path: str) -> str:
    """Extract output directory name from CSV filename."""
    basename = os.path.basename(csv_path)
    name = os.path.splitext(basename)[0]
    return name


def check_file_exists(filepath: str) -> bool:
    """Check if a file exists."""
    return os.path.exists(filepath)


DATA_END_DATE = None  # optional explicit export/censoring date (--data-end-date)


def import_and_run(module_name: str, function_name: str, *args, **kwargs):
    """Dynamically import a module and run a function."""
    try:
        module = __import__(module_name)
        func = getattr(module, function_name)
        return func(*args, **kwargs)
    except ImportError as e:
        raise ImportError(f"Could not import {module_name}: {e}")
    except AttributeError as e:
        raise AttributeError(f"Function {function_name} not found in {module_name}: {e}")


# =============================================================================
# INTERACTIVE MODE
# =============================================================================

def interactive_menu(modules: List[dict], category: str) -> List[dict]:
    """Display interactive menu and return selected modules."""
    print(f"\n{category} Modules:")
    print("-" * 40)

    for i, mod in enumerate(modules, 1):
        print(f"  {i}. {mod['name']}")
        print(f"     {mod['description']}")

    print(f"\n  A. Run ALL {category.lower()} modules")
    print(f"  S. SKIP all {category.lower()} modules")
    print()

    while True:
        choice = input(f"Select modules (e.g., 1,3,4 or A for all, S to skip): ").strip().upper()

        if choice == 'A':
            return modules
        elif choice == 'S':
            return []
        else:
            try:
                indices = [int(x.strip()) for x in choice.split(',')]
                selected = [modules[i-1] for i in indices if 1 <= i <= len(modules)]
                if selected:
                    return selected
                print("  Invalid selection. Please try again.")
            except (ValueError, IndexError):
                print("  Invalid input. Please enter numbers separated by commas, A, or S.")


def run_interactive_mode(csv_path: str, output_dir: str) -> Tuple[List[dict], List[dict], List[dict]]:
    """Run interactive mode to select modules."""
    print_header("INTERACTIVE MODE")
    print(f"\nInput file: {csv_path}")
    print(f"Output directory: {output_dir}/")
    print("\nSelect which modules to run:")

    stats = interactive_menu(STATISTICS_MODULES, "Statistics")
    quality = interactive_menu(DATA_QUALITY_MODULES, "Data Quality")
    viz = interactive_menu(VISUALIZATION_MODULES, "Visualization")

    return stats, quality, viz


# =============================================================================
# MAIN EXECUTION FUNCTIONS
# =============================================================================

def run_statistics_modules(csv_path: str, output_dir: str, modules: List[dict]) -> dict:
    """Run selected statistics modules."""
    results = {'success': [], 'failed': [], 'skipped': []}

    if not modules:
        print_skip("No statistics modules selected")
        return results

    print_header("RUNNING STATISTICS ANALYSIS")

    for i, mod in enumerate(modules, 1):
        print_step(i, len(modules), mod['name'])
        print(f"  {mod['description']}")

        try:
            start_time = time.time()
            kwargs = {}
            if DATA_END_DATE and mod['function'] in ('run_followup_analysis',
                                                     'run_followup_duplicates_analysis'):
                kwargs['data_end_date'] = DATA_END_DATE
            import_and_run(mod['module'], mod['function'], csv_path, output_dir, **kwargs)
            duration = time.time() - start_time
            print_success(f"Completed in {format_duration(duration)}")
            results['success'].append(mod['name'])
        except Exception as e:
            print_error(f"Failed: {str(e)}")
            results['failed'].append((mod['name'], str(e)))

    return results


def run_data_quality_modules(csv_path: str, output_dir: str, modules: List[dict]) -> dict:
    """Run selected data quality modules."""
    results = {'success': [], 'failed': [], 'skipped': []}

    if not modules:
        print_skip("No data quality modules selected")
        return results

    print_header("RUNNING DATA QUALITY CHECKS")

    for i, mod in enumerate(modules, 1):
        print_step(i, len(modules), mod['name'])
        print(f"  {mod['description']}")

        try:
            start_time = time.time()
            kwargs = {}
            if DATA_END_DATE and mod['function'] in ('run_followup_analysis',
                                                     'run_followup_duplicates_analysis'):
                kwargs['data_end_date'] = DATA_END_DATE
            import_and_run(mod['module'], mod['function'], csv_path, output_dir, **kwargs)
            duration = time.time() - start_time
            print_success(f"Completed in {format_duration(duration)}")
            results['success'].append(mod['name'])
        except Exception as e:
            print_error(f"Failed: {str(e)}")
            results['failed'].append((mod['name'], str(e)))

    return results


def run_visualization_modules(output_dir: str, raw_csv_path: str, modules: List[dict]) -> dict:
    """Run selected visualization modules."""
    results = {'success': [], 'failed': [], 'skipped': []}

    if not modules:
        print_skip("No visualization modules selected")
        return results

    print_header("GENERATING VISUALIZATIONS")

    # Create figures subdirectory
    figures_dir = os.path.join(output_dir, 'figures')
    os.makedirs(figures_dir, exist_ok=True)

    for i, mod in enumerate(modules, 1):
        print_step(i, len(modules), mod['name'])
        print(f"  {mod['description']}")

        # Check if required input file exists
        required_file = os.path.join(output_dir, mod['requires'])
        if not check_file_exists(required_file):
            print_skip(f"Required file not found: {mod['requires']}")
            results['skipped'].append((mod['name'], f"Missing {mod['requires']}"))
            continue

        try:
            start_time = time.time()

            # Some visualization modules need raw data path
            if mod['needs_raw_data']:
                import_and_run(mod['module'], mod['function'], output_dir, figures_dir, raw_csv_path)
            else:
                import_and_run(mod['module'], mod['function'], output_dir, figures_dir)

            duration = time.time() - start_time

            # A visualization module only counts as successful if its
            # mandatory figures actually exist - a run that silently skips
            # plots must not be reported as success.
            missing = [a for a in mod.get('expected_artifacts', [])
                       if not os.path.exists(os.path.join(figures_dir, a))]
            if missing:
                print_error(f"Completed but mandatory figure(s) missing: {', '.join(missing)}")
                results['failed'].append(
                    (mod['name'], f"missing artifacts: {', '.join(missing)}"))
            else:
                print_success(f"Completed in {format_duration(duration)}")
                results['success'].append(mod['name'])
        except Exception as e:
            print_error(f"Failed: {str(e)}")
            results['failed'].append((mod['name'], str(e)))

    return results


def print_summary(stats_results: dict, quality_results: dict, viz_results: dict, total_time: float):
    """Print final summary of all results."""
    print_header("ANALYSIS COMPLETE", '=')

    all_success = (stats_results['success'] + quality_results['success'] + viz_results['success'])
    all_failed = (stats_results['failed'] + quality_results['failed'] + viz_results['failed'])
    all_skipped = (stats_results['skipped'] + quality_results['skipped'] + viz_results['skipped'])

    print(f"\nTotal time: {format_duration(total_time)}")
    print(f"\nResults:")
    print(f"  Successful: {len(all_success)}")
    print(f"  Failed:     {len(all_failed)}")
    print(f"  Skipped:    {len(all_skipped)}")

    if all_success:
        print(f"\nSuccessful modules:")
        for name in all_success:
            print(f"  [OK] {name}")

    if all_failed:
        print(f"\nFailed modules:")
        for name, error in all_failed:
            print(f"  [ERROR] {name}: {error}")

    if all_skipped:
        print(f"\nSkipped modules:")
        for name, reason in all_skipped:
            print(f"  [SKIP] {name}: {reason}")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """Main entry point."""
    # Parse arguments
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    csv_path = sys.argv[1]

    # Check if input file exists
    if not os.path.exists(csv_path):
        print(f"Error: Input file not found: {csv_path}")
        sys.exit(1)

    # Parse options
    interactive = '--interactive' in sys.argv or '-i' in sys.argv
    skip_quality = '--skip-quality' in sys.argv
    stats_only = '--stats-only' in sys.argv
    viz_only = '--viz-only' in sys.argv

    # Optional reference-clinical splice: clinical rows verbatim from a
    # reference export (the exact reviewed data cut), follow-up rows from
    # the current export
    if '--clinical-from' in sys.argv:
        if '--cohort-from' in sys.argv or '--enrollment-cutoff' in sys.argv:
            print("Error: --clinical-from cannot be combined with "
                  "--cohort-from or --enrollment-cutoff")
            sys.exit(1)
        idx = sys.argv.index('--clinical-from')
        if idx + 1 >= len(sys.argv) or sys.argv[idx + 1].startswith('-'):
            print("Error: --clinical-from requires a reference CSV path")
            sys.exit(1)
        reference_csv = sys.argv[idx + 1]
        if not os.path.exists(reference_csv):
            print(f"Error: reference export not found: {reference_csv}")
            sys.exit(1)

        def _pid_list(flag):
            if flag not in sys.argv:
                return []
            fidx = sys.argv.index(flag)
            if fidx + 1 >= len(sys.argv) or sys.argv[fidx + 1].startswith('-'):
                print(f"Error: {flag} requires a comma-separated PID list")
                sys.exit(1)
            return [p.strip() for p in sys.argv[fidx + 1].split(',')
                    if p.strip()]

        from enrollment_filter import (splice_reference_clinical,
                                       print_splice_stats)
        print_header("REFERENCE-CLINICAL SPLICE")
        csv_path, splice_stats = splice_reference_clinical(
            csv_path, reference_csv,
            exclude_pids=_pid_list('--exclude-pids'),
            exclude_followup_pids=_pid_list('--exclude-followup-pids'),
            reference_followup_pids=_pid_list('--reference-followup-pids'))
        print_splice_stats(splice_stats)

    # Optional explicit export/censoring date for follow-up eligibility
    global DATA_END_DATE
    if '--data-end-date' in sys.argv:
        idx = sys.argv.index('--data-end-date')
        if idx + 1 >= len(sys.argv) or sys.argv[idx + 1].startswith('-'):
            print("Error: --data-end-date requires a date (YYYY-MM-DD)")
            sys.exit(1)
        try:
            datetime.strptime(sys.argv[idx + 1], '%Y-%m-%d')
        except ValueError:
            print(f"Error: --data-end-date must be YYYY-MM-DD, got: {sys.argv[idx + 1]}")
            sys.exit(1)
        DATA_END_DATE = sys.argv[idx + 1]

    # Reportable follow-up denominators are censored at the data end date.
    # Without an explicit date the modules would derive it from the latest
    # observed event, which makes eligibility depend on the very data being
    # analyzed - refuse to run instead of silently deriving.
    if DATA_END_DATE is None and not viz_only:
        if '--allow-derived-end-date' in sys.argv:
            print("NOTE: running WITHOUT an explicit data end date "
                  "(--allow-derived-end-date): follow-up eligibility will be "
                  "derived from the latest observed event. Not for reportable "
                  "results.")
        else:
            print("Error: --data-end-date YYYY-MM-DD is required.")
            print("  Follow-up eligibility and completion rates are censored at")
            print("  this date - use the export date of the analyzed file.")
            print("  For non-reportable test runs only, --allow-derived-end-date")
            print("  derives the date from the latest observed event instead.")
            sys.exit(1)

    # Optional cohort-from filter: restrict to the patients present in a
    # reference export (PID whitelist, e.g. the export a submitted analysis
    # was computed from), optionally capping clinical rows at an episode
    # date while always keeping follow-up rows
    if '--cohort-from' in sys.argv:
        if '--enrollment-cutoff' in sys.argv:
            print("Error: --cohort-from and --enrollment-cutoff are mutually "
                  "exclusive (the cohort is defined by the reference export)")
            sys.exit(1)
        idx = sys.argv.index('--cohort-from')
        if idx + 1 >= len(sys.argv) or sys.argv[idx + 1].startswith('-'):
            print("Error: --cohort-from requires a reference CSV path")
            sys.exit(1)
        cohort_csv = sys.argv[idx + 1]
        if not os.path.exists(cohort_csv):
            print(f"Error: reference export not found: {cohort_csv}")
            sys.exit(1)
        episode_cutoff = None
        if '--episode-cutoff' in sys.argv:
            cidx = sys.argv.index('--episode-cutoff')
            if cidx + 1 >= len(sys.argv) or sys.argv[cidx + 1].startswith('-'):
                print("Error: --episode-cutoff requires a date (YYYY-MM-DD)")
                sys.exit(1)
            episode_cutoff = sys.argv[cidx + 1]
            try:
                datetime.strptime(episode_cutoff, '%Y-%m-%d')
            except ValueError:
                print(f"Error: --episode-cutoff must be YYYY-MM-DD, "
                      f"got: {episode_cutoff}")
                sys.exit(1)
        from enrollment_filter import (filter_by_cohort_whitelist,
                                       print_whitelist_stats)
        print_header("COHORT FILTER (reference export)")
        csv_path, filter_stats = filter_by_cohort_whitelist(
            csv_path, cohort_csv, episode_cutoff)
        print_whitelist_stats(filter_stats)

    # Optional enrollment cutoff: restrict to the cohort enrolled on or
    # before the given date (all records of retained patients are kept,
    # including follow-ups completed after the cutoff)
    if '--enrollment-cutoff' in sys.argv:
        idx = sys.argv.index('--enrollment-cutoff')
        if idx + 1 >= len(sys.argv) or sys.argv[idx + 1].startswith('-'):
            print("Error: --enrollment-cutoff requires a date (YYYY-MM-DD)")
            sys.exit(1)
        cutoff = sys.argv[idx + 1]
        try:
            datetime.strptime(cutoff, '%Y-%m-%d')
        except ValueError:
            print(f"Error: --enrollment-cutoff must be YYYY-MM-DD, got: {cutoff}")
            sys.exit(1)
        from enrollment_filter import filter_by_enrollment_cutoff, print_stats
        print_header("ENROLLMENT CUTOFF FILTER")
        csv_path, filter_stats = filter_by_enrollment_cutoff(csv_path, cutoff)
        print_stats(filter_stats)

    # Determine output directory
    output_dir = get_output_dir_name(csv_path)

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Print header
    print_header("TRANSFUSION REGISTRY ANALYSIS SUITE")
    print(f"\nInput file:       {csv_path}")
    print(f"Output directory: {output_dir}/")
    print(f"Started at:       {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Determine which modules to run
    if interactive:
        stats_modules, quality_modules, viz_modules = run_interactive_mode(csv_path, output_dir)
    elif stats_only:
        stats_modules = STATISTICS_MODULES
        quality_modules = []
        viz_modules = []
    elif viz_only:
        stats_modules = []
        quality_modules = []
        viz_modules = VISUALIZATION_MODULES
    else:
        stats_modules = STATISTICS_MODULES
        quality_modules = [] if skip_quality else DATA_QUALITY_MODULES
        viz_modules = VISUALIZATION_MODULES

    # Track total time
    total_start = time.time()

    # Run statistics modules
    # Persist the loader's own QC findings (unparseable dates, conflicting
    # patient attributes) as a run artifact before the modules start
    if not viz_only:
        try:
            from transfusion_data_loader import TransfusionDataLoader as _QCLoader
            _qc_loader = _QCLoader()
            _qc_loader.load_data(csv_path, validate=False)
            _qc_loader.export_qc_findings(os.path.join(output_dir, 'data quality reporting'))
        except Exception as _qc_err:
            print(f"  WARNING: loader QC findings export failed: {_qc_err}")

    stats_results = run_statistics_modules(csv_path, output_dir, stats_modules)

    # Run data quality modules
    quality_results = run_data_quality_modules(csv_path, output_dir, quality_modules)

    # Run visualization modules
    viz_results = run_visualization_modules(output_dir, csv_path, viz_modules)

    # Calculate total time
    total_time = time.time() - total_start

    # Print summary
    print_summary(stats_results, quality_results, viz_results, total_time)

    print(f"\nOutput saved to: {output_dir}/")
    print(f"Figures saved to: {output_dir}/figures/")

    # Signal failure via exit code so scripted callers (CI, validation
    # harnesses) can detect a broken run — previously this always exited 0.
    n_failed = (len(stats_results.get('failed', []))
                + len(quality_results.get('failed', []))
                + len(viz_results.get('failed', [])))
    if n_failed > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
