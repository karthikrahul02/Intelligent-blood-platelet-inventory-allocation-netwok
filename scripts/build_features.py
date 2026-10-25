"""
HemoNet: Reusable historical demand feature generation.

Creates lag and rolling-demand features for CatBoost.

Input requirements:
    date
    hospital_id
    blood_group
    daily_demand

Output:
    Original columns plus the historical demand features.
"""

from pathlib import Path

import numpy as np
import pandas as pd


# ---------------------------------------------------------
# 1. REQUIRED INPUT COLUMNS
# ---------------------------------------------------------

REQUIRED_COLUMNS = [
    "date",
    "hospital_id",
    "blood_group",
    "daily_demand",
]


# ---------------------------------------------------------
# 2. VALIDATE INPUT DATA
# ---------------------------------------------------------

def validate_demand_data(df: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalize historical demand records."""

    missing = [
        column
        for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing required columns: {missing}"
        )

    df = df.copy()

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce",
    )

    if df["date"].isna().any():
        raise ValueError(
            "Invalid or missing dates were found."
        )

    if df[["hospital_id", "blood_group"]].isna().any().any():
        raise ValueError(
            "hospital_id and blood_group cannot be missing."
        )

    df["daily_demand"] = pd.to_numeric(
        df["daily_demand"],
        errors="coerce",
    )

    if df["daily_demand"].isna().any():
        raise ValueError(
            "daily_demand contains missing or nonnumeric values."
        )

    if not np.isfinite(df["daily_demand"]).all():
        raise ValueError(
            "daily_demand contains infinite values."
        )

    if (df["daily_demand"] < 0).any():
        raise ValueError(
            "daily_demand cannot be negative."
        )

    # One observation per date, hospital, and blood group.
    duplicate_mask = df.duplicated(
        subset=[
            "date",
            "hospital_id",
            "blood_group",
        ],
        keep=False,
    )

    if duplicate_mask.any():
        raise ValueError(
            "Duplicate date/hospital_id/blood_group records "
            "were found. Aggregate or resolve them before "
            "feature generation."
        )

    return df.sort_values(
        [
            "hospital_id",
            "blood_group",
            "date",
        ]
    ).reset_index(drop=True)


# ---------------------------------------------------------
# 3. GENERATE HISTORICAL FEATURES
# ---------------------------------------------------------

def build_demand_features(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Generate lag and rolling features.

    Rolling features are shifted by one observation to ensure
    the current target is not used to predict itself.
    """

    df = validate_demand_data(df)

    group_columns = [
        "hospital_id",
        "blood_group",
    ]

    grouped = df.groupby(
        group_columns,
        sort=False,
    )["daily_demand"]

    # Previous observed demand.
    df["lag_1"] = grouped.shift(1)
    df["lag_7"] = grouped.shift(7)
    df["lag_14"] = grouped.shift(14)

    # Historical rolling statistics.
    # Shift first so today's demand is not included.
    df["rolling_mean_7"] = (
        df.groupby(group_columns)["daily_demand"]
        .transform(
            lambda series: series.shift(1)
            .rolling(window=7, min_periods=7)
            .mean()
        )
    )

    df["rolling_mean_14"] = (
        df.groupby(group_columns)["daily_demand"]
        .transform(
            lambda series: series.shift(1)
            .rolling(window=14, min_periods=14)
            .mean()
        )
    )

    df["rolling_std_7"] = (
        df.groupby(group_columns)["daily_demand"]
        .transform(
            lambda series: series.shift(1)
            .rolling(window=7, min_periods=7)
            .std()
        )
    )

    df["rolling_max_7"] = (
        df.groupby(group_columns)["daily_demand"]
        .transform(
            lambda series: series.shift(1)
            .rolling(window=7, min_periods=7)
            .max()
        )
    )

    df["rolling_min_7"] = (
        df.groupby(group_columns)["daily_demand"]
        .transform(
            lambda series: series.shift(1)
            .rolling(window=7, min_periods=7)
            .min()
        )
    )

    df["demand_change_7"] = (
        df["lag_1"] - df["lag_7"]
    )

    return df


# ---------------------------------------------------------
# 4. COMMAND-LINE ENTRY POINT
# ---------------------------------------------------------

def main():
    project_root = Path(__file__).resolve().parent.parent

    input_path = (
        project_root
        / "data"
        / "processed"
        / "historical_demand.csv"
    )

    output_path = (
        project_root
        / "data"
        / "processed"
        / "historical_demand_features.csv"
    )

    if not input_path.exists():
        raise FileNotFoundError(
            f"Input file not found: {input_path}\n"
            "Create historical_demand.csv with columns: "
            "date, hospital_id, blood_group, daily_demand."
        )

    historical_df = pd.read_csv(input_path)

    features_df = build_demand_features(historical_df)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    features_df.to_csv(
        output_path,
        index=False,
    )

    print("Feature generation completed.")
    print("Input rows:", len(historical_df))
    print("Output rows:", len(features_df))
    print("Output:", output_path)


if __name__ == "__main__":
    main()