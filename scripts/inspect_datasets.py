from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)

SUPPORTED = {".csv", ".xlsx", ".xls", ".json", ".parquet"}

def load_preview(path):
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, nrows=5000, low_memory=False)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path, nrows=5000)
    if suffix == ".json":
        return pd.read_json(path)
    if suffix == ".parquet":
        return pd.read_parquet(path)
    return None

records = []
for path in sorted(RAW.rglob("*")):
    if not path.is_file() or path.suffix.lower() not in SUPPORTED:
        continue
    try:
        frame = load_preview(path)
        if frame is None:
            continue
        date_like = [str(c) for c in frame.columns if any(k in str(c).lower() for k in ("date", "time", "timestamp"))]
        records.append({
            "file": str(path.relative_to(ROOT)),
            "rows_loaded_for_profile": int(len(frame)),
            "columns": int(len(frame.columns)),
            "column_names": [str(c) for c in frame.columns],
            "missing_cells_in_preview": int(frame.isna().sum().sum()),
            "date_like_columns": date_like,
            "preview_note": "CSV/Excel inspection is capped at 5,000 rows for speed; row count here may not be total rows."
        })
        print(f"\nFILE: {path.relative_to(ROOT)}")
        print(f"Preview shape: {frame.shape}")
        print("Columns:", list(frame.columns))
        print("Dtypes:\n", frame.dtypes.astype(str).to_string())
        print("Missing values (preview):\n", frame.isna().sum().sort_values(ascending=False).head(15).to_string())
        print("Date-like columns:", date_like)
    except Exception as exc:
        records.append({"file": str(path.relative_to(ROOT)), "error": str(exc)})
        print(f"\nFAILED: {path.relative_to(ROOT)} — {exc}")

out_path = OUT / "dataset_inventory.json"
out_path.write_text(json.dumps(records, indent=2, default=str), encoding="utf-8")
print(f"\nWrote report: {out_path}")
