import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from risk_engine import engineer_features, normalize_loan_tenure_months, safe_divide, tenure_years


RNG = np.random.default_rng(42)
BASE_DIR = Path(__file__).resolve().parent
DATASET_PATH = BASE_DIR / "loan_data.csv"
MODEL_PATH = BASE_DIR / "model.pkl"
ARTIFACT_VERSION = 3
LABEL_MAPPING = {"Rejected": 0, "Approved": 1}

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
        {"income": 128000, "credit_score": 690, "employment_status": "business", "loan_amount": 1400000, "existing_loans": 520000, "loan_type": "Home Loan", "previous_loan": "Yes", "previous_loan_amount": 420000, "loan_tenure": 180},
        {"income": 59000, "credit_score": 771, "employment_status": "salaried", "loan_amount": 280000, "existing_loans": 25000, "loan_type": "Personal Loan", "previous_loan": "No", "previous_loan_amount": 0, "loan_tenure": 24},
        {"income": 67000, "credit_score": 722, "employment_status": "business", "loan_amount": 510000, "existing_loans": 160000, "loan_type": "Vehicle Loan", "previous_loan": "Yes", "previous_loan_amount": 190000, "loan_tenure": 60},
        {"income": 83000, "credit_score": 748, "employment_status": "salaried", "loan_amount": 620000, "existing_loans": 45000, "loan_type": "Education Loan", "previous_loan": "No", "previous_loan_amount": 0, "loan_tenure": 120},
    ]
    return pd.DataFrame(rows)


def build_synthetic_dataset(rows=3200):
    employment = RNG.choice(EMPLOYMENT, rows, p=[0.46, 0.2, 0.17, 0.08, 0.09])
    income = RNG.lognormal(mean=11.0, sigma=0.48, size=rows).clip(18000, 260000).round(0)
    credit_score = RNG.normal(695, 78, rows).clip(300, 900).round(0).astype(int)
    loan_type = RNG.choice(LOAN_TYPES, rows, p=[0.34, 0.28, 0.16, 0.22])
    loan_amount = RNG.lognormal(mean=13.0, sigma=0.58, size=rows).clip(80000, 4500000).round(0)
    existing_loans = (income * RNG.uniform(0.0, 4.8, rows) + RNG.normal(0, 22000, rows)).clip(0, 1200000).round(0)
    previous_loan = np.where(RNG.random(rows) < 0.42, "Yes", "No")
    previous_loan_amount = np.where(
        previous_loan == "Yes",
        (income * RNG.uniform(0.2, 4.8, rows)).clip(15000, 900000).round(0),
        0,
    )
    loan_tenure = RNG.choice([12, 24, 36, 60, 84, 120, 180, 240, 300, 360], rows, p=[0.08, 0.16, 0.14, 0.13, 0.07, 0.14, 0.11, 0.08, 0.05, 0.04])

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


def expand_reference_profiles(reference_df, copies=16):
    rows = []
    for _, row in reference_df.iterrows():
        for _ in range(copies):
            income = max(18000, row["income"] * RNG.uniform(0.82, 1.2))
            loan_amount = max(50000, row["loan_amount"] * RNG.uniform(0.75, 1.25))
            existing_loans = max(0, row["existing_loans"] * RNG.uniform(0.65, 1.35))
            previous_loan_amount = max(0, row["previous_loan_amount"] * RNG.uniform(0.6, 1.3))
            credit_score = int(np.clip(round(row["credit_score"] + RNG.normal(0, 26)), 300, 900))
            loan_tenure = normalize_loan_tenure_months(row["loan_tenure"] * RNG.choice([0.8, 1.0, 1.2]))
            rows.append(
                {
                    "income": round(income, 0),
                    "credit_score": credit_score,
                    "employment_status": row["employment_status"],
                    "loan_amount": round(loan_amount, 0),
                    "existing_loans": round(existing_loans, 0),
                    "loan_type": row["loan_type"],
                    "previous_loan": row["previous_loan"],
                    "previous_loan_amount": round(previous_loan_amount, 0),
                    "loan_tenure": loan_tenure,
                }
            )
    return pd.DataFrame(rows)


def build_tenure_scenarios(df, tenures=(24, 36, 60, 84, 120, 180, 240, 300, 360), sample_size=240):
    sample = df.sample(n=min(sample_size, len(df)), random_state=42)
    rows = []
    for _, row in sample.iterrows():
        for tenure in tenures:
            scenario = row.to_dict()
            scenario["loan_tenure"] = normalize_loan_tenure_months(tenure)
            rows.append(scenario)
    return pd.DataFrame(rows)


def underwrite(features, noise_scale=0.36):
    dti = features["dti_ratio"]
    emi_to_income = features["emi_to_income_ratio"]
    utilization = features["credit_utilization"]
    loan_to_income = features["loan_to_income_ratio"]
    years = tenure_years(features["loan_tenure"])
    short_tenure_penalty = max(0.0, (5.0 - years) / 4.0)
    optimal_tenure_bonus = max(0.0, 1.0 - abs(years - 13.0) / 7.5)
    long_tenure_penalty = max(0.0, (years - 25.0) / 8.0)

    score = (
        (features["credit_score"] - 680) / 95
        + safe_divide(features["income"] - 50000, 62000)
        - dti * 2.0
        - emi_to_income * 1.3
        - utilization * 1.15
        - loan_to_income * 0.035
        - short_tenure_penalty * 0.38
        + optimal_tenure_bonus * 0.16
        - long_tenure_penalty * 0.18
        + features["previous_loan_impact"] * 0.9
        + (features["income_stability_factor"] - 0.65) * 2.1
        - (features["loan_type_risk_weight"] - 1.0) * 0.9
    )

    if features["loan_type"] == "Home Loan" and features["credit_score"] >= 740:
        score += 0.22
    if features["loan_type"] == "Home Loan" and emi_to_income <= 0.2 and dti <= 0.35 and features["credit_score"] >= 700:
        score += 0.42
    if features["loan_type"] == "Personal Loan" and dti > 0.48:
        score -= 0.35
    if loan_to_income > 18 and dti > 0.4:
        score -= 0.4
    if features["previous_loan"] == "Yes" and features["previous_loan_impact"] > 0.15:
        score += 0.18

    noisy_score = score + RNG.normal(0, noise_scale)
    approval_probability = 1 / (1 + np.exp(-noisy_score))
    approved = int(approval_probability >= 0.52)
    return approval_probability, approved


def attach_engineered_fields(df, noise_scale=0.36):
    engineered_rows = []
    approvals = []
    approval_probabilities = []

    for row in df.to_dict(orient="records"):
        features = engineer_features(row)
        probability, approved = underwrite(features, noise_scale=noise_scale)
        engineered_rows.append(features)
        approval_probabilities.append(round(probability, 4))
        approvals.append(approved)

    engineered_df = pd.DataFrame(engineered_rows)
    engineered_df["approval_probability_seed"] = approval_probabilities
    engineered_df["approved"] = approvals
    return engineered_df


def build_hybrid_dataset():
    reference_df = build_reference_dataset()
    synthetic_df = build_synthetic_dataset()
    expanded_reference_df = expand_reference_profiles(reference_df)
    tenure_scenarios_df = build_tenure_scenarios(pd.concat([reference_df, expanded_reference_df], ignore_index=True))
    stochastic_df = pd.concat([reference_df, expanded_reference_df, synthetic_df], ignore_index=True)
    stochastic_df = attach_engineered_fields(stochastic_df, noise_scale=0.36)
    tenure_scenarios_df = attach_engineered_fields(tenure_scenarios_df, noise_scale=0.0)
    hybrid_df = pd.concat([stochastic_df, tenure_scenarios_df], ignore_index=True)
    return hybrid_df.sample(frac=1, random_state=42).reset_index(drop=True)


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


def build_model_bundle(df):
    X = df[MODEL_FEATURES]
    y = df["approved"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    categorical = ["employment_status", "loan_type", "previous_loan"]
    numeric = [column for column in MODEL_FEATURES if column not in categorical]
    numeric_transformer = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
        ]
    )
    preprocess = ColumnTransformer(
        transformers=[
            ("categorical", OneHotEncoder(handle_unknown="ignore"), categorical),
            ("numeric", numeric_transformer, numeric),
        ]
    )

    pipeline = Pipeline(
        steps=[
            ("preprocess", preprocess),
            (
                "classifier",
                RandomForestClassifier(
                    n_estimators=360,
                    max_depth=11,
                    min_samples_leaf=4,
                    random_state=42,
                    class_weight="balanced_subsample",
                ),
            ),
        ]
    )
    pipeline.fit(X_train, y_train)

    predictions = pipeline.predict(X_test)
    probabilities = pipeline.predict_proba(X_test)[:, 1]
    accuracy = accuracy_score(y_test, predictions)
    auc = roc_auc_score(y_test, probabilities)

    feature_names = pipeline.named_steps["preprocess"].get_feature_names_out()
    importances = pipeline.named_steps["classifier"].feature_importances_
    aggregated_importances = aggregate_importances(feature_names, importances)
    medians = {column: float(df[column].median()) for column in MODEL_FEATURES if column not in categorical}
    scaler = pipeline.named_steps["preprocess"].named_transformers_["numeric"].named_steps["scaler"]
    classes = [int(value) for value in pipeline.named_steps["classifier"].classes_]

    return {
        "artifact_version": ARTIFACT_VERSION,
        "model": pipeline,
        "scaler": scaler,
        "raw_features": RAW_FEATURES,
        "model_features": MODEL_FEATURES,
        "categorical_features": categorical,
        "numeric_features": numeric,
        "class_labels": classes,
        "label_mapping": LABEL_MAPPING,
        "tenure_approval_summary": (
            df.groupby("loan_tenure")["approved"].agg(["count", "mean"]).reset_index().to_dict(orient="records")
        ),
        "metrics": {"accuracy": round(float(accuracy), 4), "roc_auc": round(float(auc), 4)},
        "feature_importance": aggregated_importances,
        "benchmarks": medians,
        "training_rows": int(len(df)),
    }


def main():
    dataset = build_hybrid_dataset()
    dataset.to_csv(DATASET_PATH, index=False)

    bundle = build_model_bundle(dataset)
    with MODEL_PATH.open("wb") as file:
        pickle.dump(bundle, file)

    print(f"Training rows: {bundle['training_rows']}")
    print(f"Model accuracy: {bundle['metrics']['accuracy']:.3f}")
    print(f"Model ROC-AUC: {bundle['metrics']['roc_auc']:.3f}")
    print("Saved model.pkl and refreshed loan_data.csv")


if __name__ == "__main__":
    main()
