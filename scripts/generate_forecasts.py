"""
HemoNet — Platelet Demand Forecasting

Loads a trained CatBoost model, generates demand predictions
from prepared historical features, and exports the forecasts.

This script does not train the model.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor


# ---------------------------------------------------------
# 1. PROJECT PATHS
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

MODEL_DIR = PROJECT_ROOT / "models"
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "outputs"

MODEL_PATH = MODEL_DIR / "catboost_platelet_demand.cbm"
METADATA_PATH = MODEL_DIR / "model_metadata.json"

DEFAULT_INPUT_PATH = (
    DATA_DIR / "processed" / "forecast_input.csv"
)

DEFAULT_OUTPUT_PATH = (
    OUTPUT_DIR / "demand_forecasts.csv"
)


# ---------------------------------------------------------
# 2. LOAD MODEL METADATA
# ---------------------------------------------------------

def load_metadata():
    """Load feature definitions and model metadata."""

    if not METADATA_PATH.exists():
        raise FileNotFoundError(
            f"Model metadata not found: {METADATA_PATH}"
        )

    with open(
        METADATA_PATH,
        "r",
        encoding="utf-8",
    ) as file:
        metadata = json.load(file)

    return metadata


# ---------------------------------------------------------
# 3. LOAD TRAINED MODEL
# ---------------------------------------------------------

def load_model():
    """Load the previously trained CatBoost model."""

    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Trained model not found: {MODEL_PATH}"
        )

    model = CatBoostRegressor()
    model.load_model(str(MODEL_PATH))

    print("Trained model loaded successfully.")

    return model


# ---------------------------------------------------------
# 4. VALIDATE INPUT DATA
# ---------------------------------------------------------

def validate_input(df, metadata):
    """Validate input columns and missing feature values."""

    required_columns = (
        metadata["all_features"]
        + ["forecast_date", "hospital_id", "blood_group"]
    )

    # Preserve the order while removing duplicate column names.
    required_columns = list(dict.fromkeys(required_columns))

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            "Input data is missing required columns: "
            + ", ".join(missing_columns)
        )

    if df.empty:
        raise ValueError(
            "The input dataset contains no records."
        )

    df = df.copy()

    df["forecast_date"] = pd.to_datetime(
        df["forecast_date"],
        errors="coerce",
    )

    if df["forecast_date"].isna().any():
        raise ValueError(
            "Invalid or missing forecast_date values found."
        )

    if df[["hospital_id", "blood_group"]].isna().any().any():
        raise ValueError(
            "hospital_id and blood_group cannot be missing."
        )

    duplicate_keys = df.duplicated(
        subset=[
            "forecast_date",
            "hospital_id",
            "blood_group",
        ]
    )

    if duplicate_keys.any():
        raise ValueError(
            "Duplicate forecast_date/hospital_id/blood_group "
            "records found."
        )

    numeric_features = metadata["numeric_features"]

    for column in numeric_features:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    missing_feature_values = df[
        metadata["all_features"]
    ].isna().sum()

    invalid_features = missing_feature_values[
        missing_feature_values > 0
    ]

    if not invalid_features.empty:
        raise ValueError(
            "Missing or invalid model feature values found:\n"
            + invalid_features.to_string()
        )

    return df


# ---------------------------------------------------------
# 5. PREPARE MODEL INPUT
# ---------------------------------------------------------

def prepare_features(df, metadata):
    """Prepare categorical and numeric features."""

    features = metadata["all_features"]

    X = df[features].copy()

    categorical_features = metadata["categorical_features"]

    for column in categorical_features:
        X[column] = X[column].astype(str)

    return X


# ---------------------------------------------------------
# 6. GENERATE FORECASTS
# ---------------------------------------------------------

def generate_forecasts(input_path, output_path):
    """Generate forecasts and export them to CSV."""

    input_path = Path(input_path)
    output_path = Path(output_path)

    if not input_path.is_absolute():
        input_path = PROJECT_ROOT / input_path

    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path

    if not input_path.exists():
        raise FileNotFoundError(
            f"Forecast input file not found: {input_path}"
        )

    metadata = load_metadata()
    model = load_model()

    df = pd.read_csv(input_path)

    print("Input records:", len(df))

    df = validate_input(df, metadata)

    X = prepare_features(df, metadata)

    predictions = model.predict(X)

    predictions = np.maximum(
        predictions,
        0,
    )

    results = pd.DataFrame({
        "forecast_date": df["forecast_date"],
        "hospital_id": df["hospital_id"],
        "blood_group": df["blood_group"],
        "predicted_demand": predictions,
        "model_version": metadata["model_name"],
    })

    # Forecast demand is expressed in units.
    # Retain decimal values for evaluation and aggregation.
    results["predicted_demand"] = (
        results["predicted_demand"].round(3)
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    results.to_csv(
        output_path,
        index=False,
    )

    print("\nForecasting completed.")
    print("Forecast records:", len(results))
    print("Output file:", output_path)

    print("\nForecast preview:")
    print(results.head(10).to_string(index=False))

    return results


# ---------------------------------------------------------
# 7. COMMAND-LINE ENTRY POINT
# ---------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate HemoNet platelet demand forecasts."
    )

    parser.add_argument(
        "--input",
        default=str(DEFAULT_INPUT_PATH),
        help="CSV containing prepared forecasting features.",
    )

    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help="Path for the forecast output CSV.",
    )

    args = parser.parse_args()

    generate_forecasts(
        input_path=args.input,
        output_path=args.output,
    )


if __name__ == "__main__":
    main()