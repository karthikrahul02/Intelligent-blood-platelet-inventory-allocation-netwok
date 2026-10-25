from pathlib import Path
import math
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "synthetic" / "platelet_inventory_demand.csv"
RNG = np.random.default_rng(20261019)

HOSPITALS = [
    (f"H{i:03d}", ["Small", "Medium", "Large"][(i - 1) % 3])
    for i in range(1, 11)
]
GROUPS = ["O+", "A+", "B+", "AB+", "O-", "A-", "B-", "AB-"]
GROUP_SCALE = {"O+": 1.25, "A+": 1.0, "B+": 0.9, "AB+": 0.55,
               "O-": 0.25, "A-": 0.20, "B-": 0.18, "AB-": 0.10}
HOSPITAL_SCALE = {"Small": 0.65, "Medium": 1.0, "Large": 1.45}
START = pd.Timestamp("2026-01-01")
DAYS = 180

def main():
    rows = []
    for idx, size in HOSPITALS:
        scale = HOSPITAL_SCALE[size]
        for group in GROUPS:
            gscale = GROUP_SCALE[group]
            opening = max(5, int(round(20 * scale * gscale + 5)))
            for day in range(DAYS):
                date = START + pd.Timedelta(days=day)
                weekend_factor = 0.85 if date.dayofweek >= 5 else 1.0
                seasonal_factor = 1.0 + 0.08 * math.sin(2 * math.pi * date.dayofyear / 365.25)
                emergency = int(RNG.random() < 0.025)
                mean_demand = max(1.0, 6.5 * scale * gscale * weekend_factor * seasonal_factor)
                demand = max(0, int(RNG.poisson(mean_demand) + (RNG.integers(2, 7) if emergency else 0)))

                # Replenishment policy: modest regular delivery plus extra replenishment when stock is low.
                routine_incoming = int(RNG.poisson(max(0.8, 3.2 * scale * gscale)))
                reorder_point = max(4, int(round(9 * scale * gscale)))
                emergency_replenishment = max(0, reorder_point + int(RNG.integers(3, 9)) - (opening + routine_incoming)) if opening + routine_incoming < reorder_point else 0
                incoming = routine_incoming + emergency_replenishment

                available = opening + incoming
                used = min(demand, available)
                unmet = max(0, demand - used)
                # Aggregate synthetic expiry events; batch expiry is not represented here.
                expired = min(max(0, available - used), int(RNG.random() < 0.02))
                closing = available - used - expired

                rows.append({
                    "hospital_id": idx,
                    "date": date.date().isoformat(),
                    "blood_component": "Platelets",
                    "blood_group": group,
                    "opening_inventory": opening,
                    "incoming_units": incoming,
                    "daily_demand": demand,
                    "units_used": used,
                    "units_expired": expired,
                    "closing_inventory": closing,
                    "unmet_demand": unmet,
                    "emergency_event": emergency,
                    "is_synthetic": True
                })
                opening = closing

    result = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT, index=False)
    print(f"Saved {len(result):,} rows to {OUT}")
    print("All rows are synthetic. Do not describe them as real hospital records.")
    print(f"Inventory balance violations: {int((result['closing_inventory'] != result['opening_inventory'] + result['incoming_units'] - result['units_used'] - result['units_expired']).sum())}")

if __name__ == "__main__":
    main()
