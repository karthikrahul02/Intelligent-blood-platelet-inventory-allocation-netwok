"""
Conservative preprocessing for the KL clinical dataset.
Before running, edit RAW_FILE and TIMESTAMP_COLUMN to match the inspection report.
This script does not reinterpret clinical values or drop outliers automatically.
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

# EDIT THESE TWO VALUES after running scripts/inspect_datasets.py.
RAW_FILE = ROOT / "data" / "raw" / "KL_dataset" / "KL_dataset.xlsx"
TIMESTAMP_COLUMN = "timestamp"  # replace with the exact timestamp column name
OUTPUT_FILE = ROOT / "data" / "processed" / "kl_dataset_cleaned.csv"
REPORT_FILE = ROOT / "outputs" / "kl_preprocessing_report.txt"

def main():
    if not RAW_FILE.exists():
        raise FileNotFoundError(
            f"Raw file not found: {RAW_FILE}\n"
            "Edit RAW_FILE in scripts/preprocess_kl.py to match your actual file location."
        )

    if RAW_FILE.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(RAW_FILE)
    elif RAW_FILE.suffix.lower() == ".csv":
        df = pd.read_csv(RAW_FILE, low_memory=False)
    else:
        raise ValueError("Supported inputs are .xlsx, .xls and .csv")

    original_rows, original_cols = df.shape
    df.columns = [str(c).strip() for c in df.columns]

    if TIMESTAMP_COLUMN not in df.columns:
        raise KeyError(
            f"Timestamp column {TIMESTAMP_COLUMN!r} was not found. "
            f"Available columns: {list(df.columns)}. Edit TIMESTAMP_COLUMN to the exact name."
        )

    parsed = pd.to_datetime(df[TIMESTAMP_COLUMN], errors="coerce")
    invalid_timestamps = int(parsed.isna().sum())
    df[TIMESTAMP_COLUMN] = parsed

    # Remove only exact duplicate rows; retain unusual clinical values for review.
    exact_duplicates = int(df.duplicated().sum())
    df = df.drop_duplicates()
    df = df.dropna(subset=[TIMESTAMP_COLUMN]).sort_values(TIMESTAMP_COLUMN).reset_index(drop=True)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_FILE, index=False)

    report = [
        "KL DATASET PREPROCESSING REPORT",
        f"Input file: {RAW_FILE}",
        f"Original rows: {original_rows}",
        f"Original columns: {original_cols}",
        f"Exact duplicate rows removed: {exact_duplicates}",
        f"Invalid/missing timestamps removed: {invalid_timestamps}",
        f"Output rows: {len(df)}",
        f"Output columns: {len(df.columns)}",
        f"Remaining missing cells: {int(df.isna().sum().sum())}",
        f"Earliest timestamp: {df[TIMESTAMP_COLUMN].min()}",
        f"Latest timestamp: {df[TIMESTAMP_COLUMN].max()}",
        f"Output file: {OUTPUT_FILE}",
        "",
        "Note: No clinical outliers were automatically deleted or imputed.",
        "Inspect laboratory ranges and field meanings with appropriate domain context."
    ]
    REPORT_FILE.write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report))

if __name__ == "__main__":
    main()
