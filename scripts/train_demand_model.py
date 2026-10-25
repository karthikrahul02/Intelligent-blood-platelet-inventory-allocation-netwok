from pathlib import Path
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "synthetic" / "platelet_inventory_demand.csv"
MODEL_OUT = ROOT / "models" / "demand_forecaster.joblib"
METRICS_OUT = ROOT / "outputs" / "forecast_metrics.json"
PRED_OUT = ROOT / "outputs" / "forecast_test_predictions.csv"
FEATURES = ["hospital_code", "blood_group_code", "day_of_week", "month",
            "lag_1", "lag_7", "rolling_mean_7", "emergency_event"]

def build_features(df):
    df = df.sort_values(["hospital_id", "blood_group", "date"]).copy()
    df["date"] = pd.to_datetime(df["date"])
    df["hospital_code"] = df["hospital_id"].astype("category").cat.codes
    df["blood_group_code"] = df["blood_group"].astype("category").cat.codes
    df["day_of_week"] = df["date"].dt.dayofweek
    df["month"] = df["date"].dt.month
    grouped = df.groupby(["hospital_id", "blood_group"], sort=False)["daily_demand"]
    df["lag_1"] = grouped.shift(1)
    df["lag_7"] = grouped.shift(7)
    df["rolling_mean_7"] = grouped.transform(lambda s: s.shift(1).rolling(7, min_periods=7).mean())
    return df.dropna(subset=["lag_1", "lag_7", "rolling_mean_7"]).copy()

def main():
    if not DATA.exists():
        raise FileNotFoundError(f"Missing {DATA}. Run scripts/generate_synthetic_operational_data.py first.")
    raw = pd.read_csv(DATA)
    if not raw["is_synthetic"].astype(bool).all():
        raise ValueError("Expected all records to be labelled synthetic.")
    df = build_features(raw)
    unique_dates = sorted(df["date"].unique())
    split_date = unique_dates[int(len(unique_dates) * 0.8)]
    train = df[df["date"] < split_date]
    test = df[df["date"] >= split_date]
    model = RandomForestRegressor(n_estimators=150, min_samples_leaf=2, random_state=42, n_jobs=-1)
    model.fit(train[FEATURES], train["daily_demand"])
    predictions = np.maximum(0, model.predict(test[FEATURES]))
    baseline = np.maximum(0, test["rolling_mean_7"].to_numpy())
    mae = float(mean_absolute_error(test["daily_demand"], predictions))
    rmse = float(np.sqrt(mean_squared_error(test["daily_demand"], predictions)))
    baseline_mae = float(mean_absolute_error(test["daily_demand"], baseline))
    wape_denominator = float(test["daily_demand"].abs().sum())
    wape = float((np.abs(test["daily_demand"].to_numpy() - predictions).sum() / wape_denominator) * 100) if wape_denominator else None

    MODEL_OUT.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({
        "model": model,
        "features": FEATURES,
        "hospital_categories": sorted(raw["hospital_id"].unique().tolist()),
        "blood_group_categories": sorted(raw["blood_group"].unique().tolist()),
        "target": "daily_demand",
        "source": "synthetic",
        "forecast_horizon_days": 1
    }, MODEL_OUT)
    METRICS_OUT.parent.mkdir(parents=True, exist_ok=True)
    metrics = {
        "data_source": "synthetic",
        "forecast_horizon_days": 1,
        "test_start": str(pd.Timestamp(test["date"].min()).date()),
        "test_end": str(pd.Timestamp(test["date"].max()).date()),
        "training_rows": int(len(train)),
        "test_rows": int(len(test)),
        "random_forest_mae": mae,
        "random_forest_rmse": rmse,
        "random_forest_wape_percent": wape,
        "seven_day_baseline_mae": baseline_mae,
        "interpretation": "These metrics evaluate performance only on the generated synthetic distribution; they do not establish real-world hospital forecasting accuracy."
    }
    METRICS_OUT.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    pd.DataFrame({
        "date": test["date"].dt.date.astype(str),
        "hospital_id": test["hospital_id"].to_numpy(),
        "blood_group": test["blood_group"].to_numpy(),
        "actual_demand": test["daily_demand"].to_numpy(),
        "random_forest_prediction": predictions,
        "seven_day_baseline": baseline
    }).to_csv(PRED_OUT, index=False)
    print(json.dumps(metrics, indent=2))
    print(f"Saved model: {MODEL_OUT}")
    print(f"Saved test predictions: {PRED_OUT}")

if __name__ == "__main__":
    main()
