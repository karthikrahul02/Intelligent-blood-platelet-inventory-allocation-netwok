from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "synthetic" / "platelet_inventory_demand.csv"

def test_operational_data_shape_and_labels():
    df = pd.read_csv(DATA)
    assert len(df) == 10 * 8 * 180
    assert df["is_synthetic"].astype(bool).all()
    assert df[["hospital_id", "date", "blood_group"]].duplicated().sum() == 0

def test_inventory_balance():
    df = pd.read_csv(DATA)
    calculated = df["opening_inventory"] + df["incoming_units"] - df["units_used"] - df["units_expired"]
    assert (calculated == df["closing_inventory"]).all()

def test_demand_usage_relationship():
    df = pd.read_csv(DATA)
    assert (df["units_used"] <= df["daily_demand"]).all()
    assert (df["unmet_demand"] == df["daily_demand"] - df["units_used"]).all()
