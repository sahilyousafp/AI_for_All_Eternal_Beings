"""
train_rf.py — One-time training script for the Random Forest soil classifier.

Run from the repo root:
    python -m backend.ml_models.train_rf

Outputs (saved to backend/ml_models/models/):
    rf_soil_classifier.joblib   — trained RandomForestClassifier
    rf_scaler.joblib            — fitted StandardScaler

USDA Soil Texture Classes (Soil_Texture raster values 1–12):
    1  Clay
    2  Silty Clay
    3  Sandy Clay
    4  Clay Loam
    5  Silty Clay Loam
    6  Sandy Clay Loam
    7  Loam
    8  Silt Loam
    9  Silt
    10 Sandy Loam
    11 Loamy Sand
    12 Sand
"""

import os
import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, accuracy_score

from backend.ml_models.data_loader import load_feature_and_label_matrix

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_HERE       = os.path.dirname(os.path.abspath(__file__))
_MODELS_DIR = os.path.join(_HERE, "models")
MODEL_PATH  = os.path.join(_MODELS_DIR, "rf_soil_classifier.joblib")
SCALER_PATH = os.path.join(_MODELS_DIR, "rf_scaler.joblib")

TEXTURE_CLASS_NAMES = {
    1: "Clay",
    2: "Silty Clay",
    3: "Sandy Clay",
    4: "Clay Loam",
    5: "Silty Clay Loam",
    6: "Sandy Clay Loam",
    7: "Loam",
    8: "Silt Loam",
    9: "Silt",
    10: "Sandy Loam",
    11: "Loamy Sand",
    12: "Sand",
}


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train(depth_suffix: str = "b0", n_estimators: int = 100,
          test_size: float = 0.2, random_state: int = 42) -> None:
    print("=" * 60)
    print("Random Forest — Soil Texture Classifier")
    print("=" * 60)

    # 1. Load data
    print(f"\nLoading feature matrix (depth={depth_suffix})...")
    X, y, feature_names = load_feature_and_label_matrix(depth_suffix)
    print(f"  Samples : {X.shape[0]:,}")
    print(f"  Features: {feature_names}")
    unique, counts = np.unique(y, return_counts=True)
    print("  Class distribution:")
    for cls, cnt in zip(unique, counts):
        name = TEXTURE_CLASS_NAMES.get(int(cls), f"Class {cls}")
        print(f"    {int(cls):2d} {name:<20s} — {cnt:,} pixels ({cnt/len(y)*100:.1f}%)")

    # 2. Train / test split (stratified)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )
    print(f"\nTrain: {len(X_train):,}  |  Test: {len(X_test):,}")

    # 3. Scale features
    scaler = StandardScaler()
    X_train_sc = scaler.fit_transform(X_train)
    X_test_sc  = scaler.transform(X_test)

    # 4. Train RF
    print(f"\nTraining RandomForestClassifier (n_estimators={n_estimators})...")
    clf = RandomForestClassifier(
        n_estimators=n_estimators,
        max_depth=15,
        min_samples_split=5,
        n_jobs=-1,
        random_state=random_state,
    )
    clf.fit(X_train_sc, y_train)

    # 5. Evaluate
    train_acc = accuracy_score(y_train, clf.predict(X_train_sc))
    test_acc  = accuracy_score(y_test,  clf.predict(X_test_sc))
    print(f"\nTrain accuracy : {train_acc:.4f}")
    print(f"Test  accuracy : {test_acc:.4f}")

    target_names = [
        TEXTURE_CLASS_NAMES.get(int(c), f"Class {c}") for c in clf.classes_
    ]
    print("\nClassification Report:")
    print(classification_report(y_test, clf.predict(X_test_sc),
                                 labels=clf.classes_,
                                 target_names=target_names,
                                 zero_division=0))

    # 6. Feature importance
    print("Feature Importance:")
    for name, imp in sorted(zip(feature_names, clf.feature_importances_),
                             key=lambda x: x[1], reverse=True):
        bar = "#" * int(imp * 40)
        print(f"  {name:<12s} {imp:.4f}  {bar}")

    # 7. Save
    os.makedirs(_MODELS_DIR, exist_ok=True)
    joblib.dump(clf,    MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)
    print(f"\nModel saved  -> {MODEL_PATH}")
    print(f"Scaler saved -> {SCALER_PATH}")
    print("\nDone.")


if __name__ == "__main__":
    train()
