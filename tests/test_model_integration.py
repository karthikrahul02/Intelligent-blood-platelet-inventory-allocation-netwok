from pathlib import Path
import json

import pandas as pd
from catboost import CatBoostRegressor

PROJECT_ROOT = Path(__file__).resolve().parent.parent

MODEL_PATH = (
    PROJECT_ROOT
    / "models"
    / "catboost_platelet_demand.cbm"
)

METADATA_PATH = (
    PROJECT_ROOT
    / "models"
    / "model_metadata.json"
)


def test_model_and_metadata_feature_count():
    model = CatBoostRegressor()
    model.load_model(str(MODEL_PATH))

    with open(
        METADATA_PATH,
        "r",
        encoding="utf-8",
    ) as file:
        metadata = json.load(file)

    metadata_features = metadata["all_features"]

    assert (
        model.n_features_in_ == len(metadata_features)
    ), (
        f"Model expects {model.n_features_in_} features, "
        f"but metadata lists {len(metadata_features)}."
    )


if __name__ == "__main__":
    test_model_and_metadata_feature_count()
    print("Model/metadata feature-count test passed.")