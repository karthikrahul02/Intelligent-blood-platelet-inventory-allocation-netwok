"""Generate next-day predictions for each hospital/blood-group using saved model."""
from pathlib import Path
import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "synthetic" / "platelet_inventory_demand.csv"
MODEL = ROOT / "models" / "demand_forecaster.joblib"
OUT = ROOT / "outputs" / "next_day_forecasts.csv"

def main():
    if not MODEL.exists():
        raise FileNotFoundError("Trained model missing. Run scripts/train_demand_model.py first.")
    bundle = joblib.load(MODEL)
    df = pd.read_csv(DATA, parse_dates=["date"]).sort_values(["hospital_id", "blood_group", "date"])
    latest_date = df["date"].max()
    last_rows = df.groupby(["hospital_id", "blood_group"], as_index=False).tail(7).copy()
    last_rows["hospital_code"] = last_rows["hospital_id"].astype("category").cat.set_categories(bundle["hospital_categories"]).cat.codes
    last_rows["blood_group_code"] = last_rows["blood_group"].astype("category").cat.set_categories(bundle["blood_group_categories"]).cat.codes
    last_rows["day_of_week"] = (latest_date + pd.Timedelta(days=1)).dayofweek
    last_rows["month"] = (latest_date + pd.Timedelta(days=1)).month
    last_rows = last_rows.sort_values(["hospital_id", "blood_group", "date"])
    latest_features = last_rows.groupby(["hospital_id", "blood_group"], as_index=False).tail(1).copy()
    means = last_rows.groupby(["hospital_id", "blood_group"])["daily_demand"].mean().rename("rolling_mean_7")
    lags = last_rows.groupby(["hospital_id", "blood_group"])["daily_demand"].agg(
        lag_1="last", lag_7=lambda x: x.iloc[0] if len(x) == 7 else x.iloc[-1]
    )
    latest_features = latest_features.drop(columns=["rolling_mean_7", "lag_1", "lag_7"], errors="ignore")
    latest_features = latest_features.merge(means, on=["hospital_id", "blood_group"], how="left")
    latest_features = latest_features.merge(lags, on=["hospital_id", "blood_group"], how="left")
    latest_features["emergency_event"] = 0  # no emergency is assumed unless a scenario supplies one
    features = bundle["features"]
    latest_features["predicted_demand"] = np.maximum(0, bundle["model"].predict(latest_features[features]))
    latest_features["forecast_date"] = (latest_date + pd.Timedelta(days=1)).date().isoformat()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    cols = ["hospital_id", "blood_group", "forecast_date", "predicted_demand"]
    latest_features[cols].to_csv(OUT, index=False)
    print(f"Saved {len(latest_features)} forecasts to {OUT}")
    print(latest_features[cols].head(10).to_string(index=False))

if __name__ == "__main__":
    main()
