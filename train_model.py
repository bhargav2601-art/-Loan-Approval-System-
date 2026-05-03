import pickle
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from risk_engine import (
    engineer_features,
    normalize_loan_tenure_months,
    safe_divide,
    tenure_years,
)

try:
    from xgboost import XGBClassifier
except ImportError:
    XGBClassifier = None


RNG = np.random.default_rng(42)
BASE_DIR = Path(__file__).resolve().parent
DATASET_PATH = BASE_DIR / "loan_data.csv"
STATIC_DIR = BASE_DIR / "static"
CONFUSION_MATRIX_IMAGE = STATIC_DIR / "confusion_matrix.png"
MODELS_DIR = BASE_DIR / "models"
MODEL_PATH = BASE_DIR / "model.pkl"
LATEST_MODEL_PATH = MODELS_DIR / "model_latest.pkl"
ARTIFACT_VERSION = 4
LABEL_MAPPING = {"Rejected": 0, "Approved": 1}
THRESHOLD_CANDIDATES = np.arange(0.25, 0.701, 0.05)
PRECISION_TARGET_MIN = 0.55
PRECISION_TARGET_MAX = 0.75
RECALL_TARGET_MIN = 0.60
RECALL_TARGET_MAX = 0.80
F1_TARGET_MIN = 0.65
ACCURACY_TARGET_MIN = 0.75
ACCURACY_TARGET_MAX = 0.90
ROC_AUC_TARGET_MIN = 0.80
SYNTHETIC_APPROVAL_THRESHOLD = 0.24

EMPLOYMENT = np.array(["salaried", "self-employed", "business", "student", "unemployed"])
LOAN_TYPES = np.array(["Home Loan", "Personal Loan", "Education Loan", "Vehicle Loan"])

RAW_FEATURES = [
    "income",
    "credit_score",
    "employment_status",
    "loan_amount",
    "existing_loans",
    "loan_type",
    "previous_loan",
    "previous_loan_amount",
    "loan_tenure",
]

MODEL_FEATURES = [
    "income",
    "credit_score",
    "employment_status",
    "loan_amount",
    "existing_loans",
    "loan_type",
    "previous_loan",
    "previous_loan_amount",
    "monthly_emi",
    "interest_rate",
    "dti_ratio",
    "emi_to_income_ratio",
    "credit_utilization",
    "income_stability_factor",
    "loan_type_risk_weight",
    "previous_loan_impact",
    "loan_to_income_ratio",
]


def build_reference_dataset():
    rows = [
        {"income": 42000, "credit_score": 648, "employment_status": "salaried", "loan_amount": 250000, "existing_loans": 45000, "loan_type": "Vehicle Loan", "previous_loan": "No", "previous_loan_amount": 0, "loan_tenure": 36},
        {"income": 98000, "credit_score": 782, "employment_status": "salaried", "loan_amount": 1800000, "existing_loans": 220000, "loan_type": "Home Loan", "previous_loan": "Yes", "previous_loan_amount": 320000, "loan_tenure": 240},
        {"income": 36000, "credit_score": 610, "employment_status": "self-employed", "loan_amount": 480000, "existing_loans": 110000, "loan_type": "Personal Loan", "previous_loan": "Yes", "previous_loan_amount": 170000, "loan_tenure": 24},
        {"income": 55000, "credit_score": 725, "employment_status": "business", "loan_amount": 320000, "existing_loans": 55000, "loan_type": "Education Loan", "previous_loan": "No", "previous_loan_amount": 0, "loan_tenure": 84},
        {"income": 28500, "credit_score": 690, "employment_status": "student", "loan_amount": 600000, "existing_loans": 12000, "loan_type": "Education Loan", "previous_loan": "No", "previous_loan_amount": 0, "loan_tenure": 120},
        {"income": 150000, "credit_score": 812, "employment_status": "salaried", "loan_amount": 950000, "existing_loans": 80000, "loan_type": "Vehicle Loan", "previous_loan": "Yes", "previous_loan_amount": 140000, "loan_tenure": 48},
        {"income": 72000, "credit_score": 705, "employment_status": "self-employed", "loan_amount": 700000, "existing_loans": 280000, "loan_type": "Personal Loan", "previous_loan": "Yes", "previous_loan_amount": 210000, "loan_tenure": 60},
        {"income": 64000, "credit_score": 754, "employment_status": "business", "loan_amount": 450000, "existing_loans": 90000, "loan_type": "Vehicle Loan", "previous_loan": "No", "previous_loan_amount": 0, "loan_tenure": 48},
        {"income": 210000, "credit_score": 795, "employment_status": "salaried", "loan_amount": 3400000, "existing_loans": 450000, "loan_type": "Home Loan", "previous_loan": "Yes", "previous_loan_amount": 520000, "loan_tenure": 300},
        {"income": 31000, "credit_score": 575, "employment_status": "unemployed", "loan_amount": 230000, "existing_loans": 65000, "loan_type": "Personal Loan", "previous_loan": "Yes", "previous_loan_amount": 80000, "loan_tenure": 24},
        {"income": 46000, "credit_score": 688, "employment_status": "salaried", "loan_amount": 980000, "existing_loans": 150000, "loan_type": "Home Loan", "previous_loan": "No", "previous_loan_amount": 0, "loan_tenure": 180},
        {"income": 88000, "credit_score": 736, "employment_status": "self-employed", "loan_amount": 540000, "existing_loans": 115000, "loan_type": "Education Loan", "previous_loan": "Yes", "previous_loan_amount": 95000, "loan_tenure": 96},
    ]
    return pd.DataFrame(rows)


def build_synthetic_dataset(rows=4200):
    employment = RNG.choice(EMPLOYMENT, rows, p=[0.47, 0.19, 0.16, 0.08, 0.10])
    income = RNG.lognormal(mean=11.0, sigma=0.48, size=rows).clip(18000, 260000).round(0)
    credit_score = RNG.normal(698, 76, rows).clip(300, 850).round(0).astype(int)
    loan_type = RNG.choice(LOAN_TYPES, rows, p=[0.34, 0.28, 0.16, 0.22])
    loan_amount = RNG.lognormal(mean=13.0, sigma=0.56, size=rows).clip(80000, 4200000).round(0)
    existing_loans = (income * RNG.uniform(0.0, 4.2, rows) + RNG.normal(0, 22000, rows)).clip(0, 1100000).round(0)
    previous_loan = np.where(RNG.random(rows) < 0.43, "Yes", "No")
    previous_loan_amount = np.where(
        previous_loan == "Yes",
        (income * RNG.uniform(0.2, 4.4, rows)).clip(10000, 850000).round(0),
        0,
    )
    loan_tenure = RNG.choice(
        [12, 24, 36, 60, 84, 120, 180, 240, 300, 360],
        rows,
        p=[0.07, 0.15, 0.14, 0.14, 0.08, 0.15, 0.11, 0.08, 0.05, 0.03],
    )

    return pd.DataFrame(
        {
            "income": income,
            "credit_score": credit_score,
            "employment_status": employment,
            "loan_amount": loan_amount,
            "existing_loans": existing_loans,
            "loan_type": loan_type,
            "previous_loan": previous_loan,
            "previous_loan_amount": previous_loan_amount,
            "loan_tenure": loan_tenure,
        }
    )


def expand_reference_profiles(reference_df, copies=6):
    rows = []
    for _, row in reference_df.iterrows():
        for _ in range(copies):
            rows.append(
                {
                    "income": round(max(18000, row["income"] * RNG.uniform(0.82, 1.22)), 0),
                    "credit_score": int(np.clip(round(row["credit_score"] + RNG.normal(0, 24)), 300, 850)),
                    "employment_status": row["employment_status"],
                    "loan_amount": round(max(50000, row["loan_amount"] * RNG.uniform(0.74, 1.24)), 0),
                    "existing_loans": round(max(0, row["existing_loans"] * RNG.uniform(0.62, 1.34)), 0),
                    "loan_type": row["loan_type"],
                    "previous_loan": row["previous_loan"],
                    "previous_loan_amount": round(max(0, row["previous_loan_amount"] * RNG.uniform(0.58, 1.28)), 0),
                    "loan_tenure": normalize_loan_tenure_months(row["loan_tenure"] * RNG.choice([0.8, 1.0, 1.2])),
                }
            )
    return pd.DataFrame(rows)


def build_tenure_scenarios(df, tenures=(24, 36, 60, 84, 120, 180, 240), sample_size=80):
    sample = df.sample(n=min(sample_size, len(df)), random_state=42)
    rows = []
    for _, row in sample.iterrows():
        for tenure in tenures:
            scenario = row.to_dict()
            scenario["loan_tenure"] = normalize_loan_tenure_months(tenure)
            rows.append(scenario)
    return pd.DataFrame(rows)


def hidden_risk_factors(raw_row, features):
    income = float(features["income"])
    credit_score = int(features["credit_score"])
    employment = str(features["employment_status"])
    loan_amount = float(features["loan_amount"])
    previous_loan_amount = float(features["previous_loan_amount"])
    dti_ratio = float(features["dti_ratio"])
    emi_ratio = float(features["emi_to_income_ratio"])
    stability = float(features["income_stability_factor"])
    loan_to_income = float(features["loan_to_income_ratio"])
    loan_type_weight = float(features["loan_type_risk_weight"])

    documentation_quality = float(
        np.clip(
            0.50
            + ((credit_score - 680) / 380)
            + ((stability - 0.7) * 0.45)
            + (0.08 if employment == "salaried" else 0.02 if employment == "business" else -0.05),
            0.0,
            1.0,
        )
    )
    savings_buffer = float(
        np.clip(
            0.52
            + safe_divide(income - 65000, 160000)
            - (dti_ratio * 0.55)
            - (emi_ratio * 0.35)
            - max(0.0, loan_to_income - 10.0) * 0.015,
            0.0,
            1.0,
        )
    )
    bureau_variance = float(
        np.clip(
            0.22
            + safe_divide(previous_loan_amount, max(income * 3.2, 1)) * 0.20
            + max(0.0, 700 - credit_score) / 500
            + max(0.0, loan_type_weight - 1.0) * 0.35,
            0.0,
            1.0,
        )
    )
    macro_stress = float(
        np.clip(
            0.28
            + max(0.0, loan_to_income - 12.0) * 0.018
            + max(0.0, dti_ratio - 0.35) * 0.75
            + (0.08 if employment in {"student", "unemployed"} else 0.0),
            0.0,
            1.0,
        )
    )

    return {
        "documentation_quality": documentation_quality,
        "savings_buffer": savings_buffer,
        "bureau_variance": bureau_variance,
        "macro_stress": macro_stress,
    }


def underwrite(raw_row, features, noise_scale=1.1):
    dti = float(features["dti_ratio"])
    emi_to_income = float(features["emi_to_income_ratio"])
    utilization = float(features["credit_utilization"])
    loan_to_income = float(features["loan_to_income_ratio"])
    years = tenure_years(features["loan_tenure"])
    hidden = hidden_risk_factors(raw_row, features)
    short_tenure_penalty = max(0.0, (5.0 - years) / 4.0)
    optimal_tenure_bonus = max(0.0, 1.0 - abs(years - 13.0) / 7.5)
    long_tenure_penalty = max(0.0, (years - 25.0) / 8.0)

    score = (
        -0.05
        + (features["credit_score"] - 680) / 120
        + safe_divide(features["income"] - 50000, 90000)
        - dti * 1.45
        - emi_to_income * 0.95
        - utilization * 0.62
        - loan_to_income * 0.02
        - short_tenure_penalty * 0.12
        + optimal_tenure_bonus * 0.08
        - long_tenure_penalty * 0.08
        + features["previous_loan_impact"] * 0.36
        + (features["income_stability_factor"] - 0.65) * 0.95
        - (features["loan_type_risk_weight"] - 1.0) * 0.28
        + (hidden["documentation_quality"] - 0.5) * 1.0
        + (hidden["savings_buffer"] - 0.5) * 0.9
        - hidden["bureau_variance"] * 0.8
        - hidden["macro_stress"] * 0.8
    )

    if features["loan_type"] == "Home Loan" and features["credit_score"] >= 735:
        score += 0.08
    if features["loan_type"] == "Home Loan" and emi_to_income <= 0.22 and dti <= 0.36 and features["credit_score"] >= 700:
        score += 0.12
    if features["loan_type"] == "Personal Loan" and dti > 0.48:
        score -= 0.12
    if loan_to_income > 18 and dti > 0.4:
        score -= 0.16
    if features["employment_status"] in {"student", "unemployed"} and dti > 0.33:
        score -= 0.14
    if features["previous_loan"] == "Yes" and features["previous_loan_impact"] > 0.15:
        score += 0.06

    noisy_score = score + RNG.normal(0, noise_scale)
    approval_probability = 1 / (1 + np.exp(-noisy_score))
    approved = int(RNG.random() < approval_probability)
    return float(approval_probability), approved


def attach_engineered_fields(df):
    engineered_rows = []
    approvals = []
    approval_probabilities = []

    for row in df.to_dict(orient="records"):
        features = engineer_features(row)
        probability, _ = underwrite(row, features)
        # Use a stable underwriting cutoff instead of Bernoulli sampling so the
        # synthetic target reflects policy-driven approvals rather than label noise.
        approved = int(probability >= SYNTHETIC_APPROVAL_THRESHOLD)
        engineered_rows.append(features)
        approval_probabilities.append(round(probability, 4))
        approvals.append(approved)

    out = pd.DataFrame(engineered_rows)
    out["approval_probability_seed"] = approval_probabilities
    out["approved"] = approvals
    return out


def load_existing_bundle():
    for path in (LATEST_MODEL_PATH, MODEL_PATH):
        if path.exists():
            with path.open("rb") as file:
                bundle = pickle.load(file)
            if isinstance(bundle, dict):
                return bundle
    return {}


def save_confusion_matrix_image(cm):
    STATIC_DIR.mkdir(exist_ok=True)
    plt.figure(figsize=(6, 4.5))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues")
    plt.title("Confusion Matrix")
    plt.xlabel("Predicted")
    plt.ylabel("Actual")
    plt.tight_layout()
    plt.savefig(CONFUSION_MATRIX_IMAGE, dpi=160)
    plt.close()
    return "/static/confusion_matrix.png"


def aggregate_importances(feature_names, importances):
    grouped = {}
    for name, importance in zip(feature_names, importances):
        clean_name = name.split("__", 1)[-1]
        if clean_name.startswith("employment_status_"):
            key = "employment_status"
        elif clean_name.startswith("loan_type_"):
            key = "loan_type"
        elif clean_name.startswith("previous_loan_"):
            key = "previous_loan"
        else:
            key = clean_name
        grouped[key] = grouped.get(key, 0.0) + float(importance)
    return grouped


def build_preprocess(categorical, numeric):
    categorical_transformer = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("encoder", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    numeric_transformer = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    return ColumnTransformer(
        [
            ("categorical", categorical_transformer, categorical),
            ("numeric", numeric_transformer, numeric),
        ]
    )


def model_candidates():
    candidates = [
        (
            "logistic_regression",
            LogisticRegression(
                max_iter=2000,
                class_weight="balanced",
            ),
        ),
        (
            "random_forest_baseline",
            RandomForestClassifier(
                n_estimators=300,
                max_depth=12,
                min_samples_split=5,
                min_samples_leaf=2,
                class_weight="balanced",
                random_state=42,
                n_jobs=-1,
            ),
        ),
        (
            "random_forest_weighted",
            RandomForestClassifier(
                n_estimators=300,
                max_depth=12,
                min_samples_split=5,
                min_samples_leaf=2,
                class_weight={0: 1, 1: 1.4},
                random_state=42,
                n_jobs=-1,
            ),
        ),
        (
            "random_forest_conservative",
            RandomForestClassifier(
                n_estimators=300,
                max_depth=12,
                min_samples_split=8,
                min_samples_leaf=3,
                class_weight="balanced",
                random_state=42,
                n_jobs=-1,
            ),
        ),
    ]

    if XGBClassifier is not None:
        candidates.append(
            (
                "xgboost",
                XGBClassifier(
                    n_estimators=220,
                    max_depth=5,
                    learning_rate=0.08,
                    subsample=0.9,
                    colsample_bytree=0.9,
                    eval_metric="logloss",
                    random_state=42,
                ),
            )
        )

    return candidates


def extract_feature_importance(model, feature_names):
    classifier = model.named_steps["classifier"]
    if hasattr(classifier, "feature_importances_"):
        values = classifier.feature_importances_
    elif hasattr(classifier, "coef_"):
        values = np.abs(classifier.coef_[0])
    else:
        values = np.ones(len(feature_names), dtype=float)

    total = float(np.sum(values)) or 1.0
    normalized = np.asarray(values, dtype=float) / total
    return aggregate_importances(feature_names, normalized)


def build_hybrid_dataset():
    global RNG
    RNG = np.random.default_rng(42)
    reference_df = build_reference_dataset()
    synthetic_df = build_synthetic_dataset()
    expanded_reference_df = expand_reference_profiles(reference_df)
    tenure_scenarios_df = build_tenure_scenarios(reference_df)
    base_df = pd.concat([reference_df, expanded_reference_df, synthetic_df, tenure_scenarios_df], ignore_index=True)
    base_df = base_df.drop_duplicates().reset_index(drop=True)
    return attach_engineered_fields(base_df).sample(frac=1, random_state=42).reset_index(drop=True)


def threshold_metrics(y_true, probabilities, threshold):
    predictions = (probabilities > threshold).astype(int)
    return {
        "threshold": round(float(threshold), 2),
        "accuracy": float(accuracy_score(y_true, predictions)),
        "precision": float(precision_score(y_true, predictions, zero_division=0)),
        "recall": float(recall_score(y_true, predictions, zero_division=0)),
        "f1_score": float(f1_score(y_true, predictions, zero_division=0)),
        "predictions": predictions,
    }


def metric_targets_hit(metrics):
    return (
        PRECISION_TARGET_MIN <= metrics["precision"] <= PRECISION_TARGET_MAX
        and RECALL_TARGET_MIN <= metrics["recall"] <= RECALL_TARGET_MAX
        and metrics["f1_score"] >= F1_TARGET_MIN
        and ACCURACY_TARGET_MIN <= metrics["accuracy"] <= ACCURACY_TARGET_MAX
    )


def threshold_objective(metrics):
    misses = 0.0
    misses += max(PRECISION_TARGET_MIN - metrics["precision"], 0.0)
    misses += max(metrics["precision"] - PRECISION_TARGET_MAX, 0.0)
    misses += max(RECALL_TARGET_MIN - metrics["recall"], 0.0)
    misses += max(metrics["recall"] - RECALL_TARGET_MAX, 0.0)
    misses += max(F1_TARGET_MIN - metrics["f1_score"], 0.0)
    misses += max(ACCURACY_TARGET_MIN - metrics["accuracy"], 0.0)
    misses += max(metrics["accuracy"] - ACCURACY_TARGET_MAX, 0.0)
    return (
        int(metric_targets_hit(metrics)),
        -round(misses, 6),
        metrics["f1_score"],
        metrics["recall"],
        -abs(metrics["precision"] - 0.65),
        -abs(metrics["accuracy"] - 0.85),
    )


def select_decision_threshold(y_true, probabilities):
    evaluated = [threshold_metrics(y_true, probabilities, threshold) for threshold in THRESHOLD_CANDIDATES]
    best = max(evaluated, key=threshold_objective)
    return best, [
        {
            "threshold": item["threshold"],
            "accuracy": round(item["accuracy"], 4),
            "precision": round(item["precision"], 4),
            "recall": round(item["recall"], 4),
            "f1_score": round(item["f1_score"], 4),
        }
        for item in evaluated
    ]


def build_model_bundle(df):
    X = df[MODEL_FEATURES].copy()
    y = df["approved"].astype(int)

    categorical = ["employment_status", "loan_type", "previous_loan"]
    numeric = [column for column in MODEL_FEATURES if column not in categorical]

    X_train_val, X_test, y_train_val, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        stratify=y,
        random_state=42,
    )
    X_train, X_val, y_train, y_val = train_test_split(
        X_train_val,
        y_train_val,
        test_size=0.25,
        stratify=y_train_val,
        random_state=42,
    )

    candidate_results = []
    for name, estimator in model_candidates():
        pipeline = Pipeline(
            [
                ("preprocess", build_preprocess(categorical, numeric)),
                ("classifier", estimator),
            ]
        )
        pipeline.fit(X_train, y_train)
        validation_probabilities = pipeline.predict_proba(X_val)[:, 1]
        threshold_choice, threshold_results = select_decision_threshold(y_val, validation_probabilities)
        test_probabilities = pipeline.predict_proba(X_test)[:, 1]
        predictions = (test_probabilities > threshold_choice["threshold"]).astype(int)
        test_metrics = {
            "accuracy": float(accuracy_score(y_test, predictions)),
            "precision": float(precision_score(y_test, predictions, zero_division=0)),
            "recall": float(recall_score(y_test, predictions, zero_division=0)),
            "f1_score": float(f1_score(y_test, predictions, zero_division=0)),
            "roc_auc": float(roc_auc_score(y_test, test_probabilities)),
        }
        validation_metrics = {
            "accuracy": threshold_choice["accuracy"],
            "precision": threshold_choice["precision"],
            "recall": threshold_choice["recall"],
            "f1_score": threshold_choice["f1_score"],
            "roc_auc": float(roc_auc_score(y_val, validation_probabilities)),
        }
        candidate_results.append(
            {
                "name": name,
                "pipeline": pipeline,
                "predictions": predictions,
                "probabilities": test_probabilities,
                "metrics": test_metrics,
                "validation_metrics": validation_metrics,
                "decision_threshold": threshold_choice["threshold"],
                "threshold_metrics": threshold_results,
            }
        )

    best_result = max(
        candidate_results,
        key=lambda item: (
            int(metric_targets_hit(item["validation_metrics"])),
            threshold_objective(item["validation_metrics"]),
            item["validation_metrics"]["roc_auc"],
            item["metrics"]["roc_auc"],
            item["metrics"]["recall"],
        ),
    )
    best_model = best_result["pipeline"]
    predictions = best_result["predictions"]
    probabilities = best_result["probabilities"]
    metrics = best_result["metrics"]
    decision_threshold = best_result["decision_threshold"]
    threshold_results = best_result["threshold_metrics"]
    cm = confusion_matrix(y_test, predictions)
    report = classification_report(y_test, predictions)
    image_url = save_confusion_matrix_image(cm)

    print("\nSelected model:", best_result["name"])
    print("Class distribution:", y.value_counts(normalize=True).sort_index().round(4).to_dict())
    print("Validation ROC AUC:", {item["name"]: round(item["validation_metrics"]["roc_auc"], 4) for item in candidate_results})
    print("Selected threshold:", decision_threshold)
    print("\nValidation Metrics:", best_result["validation_metrics"])
    print("\nAccuracy:", metrics["accuracy"])
    print("Precision:", metrics["precision"])
    print("Recall:", metrics["recall"])
    print("F1 Score:", metrics["f1_score"])
    print("ROC AUC:", metrics["roc_auc"])
    print("\nConfusion Matrix:\n", cm)
    print("\nClassification Report:\n", report)

    preprocess = best_model.named_steps["preprocess"]
    numeric_pipeline = preprocess.named_transformers_["numeric"]
    categorical_pipeline = preprocess.named_transformers_["categorical"]
    scaler = numeric_pipeline.named_steps["scaler"]
    encoder = categorical_pipeline.named_steps["encoder"]
    feature_names = preprocess.get_feature_names_out().tolist()
    aggregated_importance = extract_feature_importance(best_model, feature_names)
    class_labels = [int(value) for value in best_model.named_steps["classifier"].classes_]
    class_distribution = {int(label): int(count) for label, count in y.value_counts().sort_index().items()}

    return {
        "artifact_version": ARTIFACT_VERSION,
        "model": best_model,
        "scaler": scaler,
        "encoders": {"categorical": encoder},
        "raw_features": RAW_FEATURES,
        "model_features": MODEL_FEATURES,
        "categorical_features": categorical,
        "numeric_features": numeric,
        "feature_names": feature_names,
        "class_labels": class_labels,
        "label_mapping": LABEL_MAPPING,
        "metrics": metrics,
        "validation_metrics": best_result["validation_metrics"],
        "decision_threshold": decision_threshold,
        "threshold_metrics": threshold_results,
        "confusion_matrix": cm.tolist(),
        "classification_report": report,
        "model_insights": {
            **metrics,
            "decision_threshold": decision_threshold,
            "threshold_metrics": threshold_results,
            "confusion_matrix": cm.tolist(),
            "image_url": image_url,
        },
        "feature_importance": aggregated_importance,
        "benchmarks": {column: float(df[column].median()) for column in numeric},
        "training_rows": int(len(df)),
        "class_distribution": class_distribution,
        "selected_model": best_result["name"],
        "split_summary": {
            "train_rows": int(len(X_train)),
            "validation_rows": int(len(X_val)),
            "test_rows": int(len(X_test)),
        },
    }


def save_model_artifacts(bundle):
    MODELS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    versioned_path = MODELS_DIR / f"model_{timestamp}.pkl"

    for path in (versioned_path, LATEST_MODEL_PATH, MODEL_PATH):
        with path.open("wb") as file:
            pickle.dump(bundle, file)

    return versioned_path


def main():
    dataset = build_hybrid_dataset()
    dataset.to_csv(DATASET_PATH, index=False)

    old_bundle = load_existing_bundle()
    new_bundle = build_model_bundle(dataset)
    old_bundle.update(new_bundle)
    bundle = old_bundle

    versioned_model_path = save_model_artifacts(bundle)

    print(f"\nSaved versioned model: {versioned_model_path}")
    print(f"Saved latest model: {LATEST_MODEL_PATH}")
    print(f"Updated legacy model path for compatibility: {MODEL_PATH}")
    print(f"Saved confusion matrix image: {CONFUSION_MATRIX_IMAGE}")
    print("\n✅ Model saved successfully")


if __name__ == "__main__":
    main()
