import pickle

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


RNG = np.random.default_rng(42)
EMPLOYMENT = np.array(["salaried", "self-employed", "business", "student", "unemployed"])


def build_dummy_dataset(rows=1200):
    employment = RNG.choice(EMPLOYMENT, rows, p=[0.45, 0.22, 0.2, 0.07, 0.06])
    income = RNG.normal(65000, 28000, rows).clip(12000, 220000).round(0)
    credit_score = RNG.normal(700, 85, rows).clip(300, 900).round(0).astype(int)
    loan_amount = RNG.normal(360000, 180000, rows).clip(50000, 1500000).round(0)
    existing_loans = RNG.normal(85000, 85000, rows).clip(0, 650000).round(0)

    employment_bonus = {
        "salaried": 0.45,
        "business": 0.25,
        "self-employed": 0.15,
        "student": -0.75,
        "unemployed": -1.2,
    }
    dti = (existing_loans + loan_amount * 0.025) / np.maximum(income, 1)
    raw_score = (
        (credit_score - 650) / 80
        + (income - 45000) / 45000
        - dti * 1.35
        - (loan_amount / np.maximum(income, 1)) * 0.09
        + np.vectorize(employment_bonus.get)(employment)
        + RNG.normal(0, 0.45, rows)
    )
    approved = (raw_score > 0.1).astype(int)

    return pd.DataFrame(
        {
            "income": income,
            "credit_score": credit_score,
            "employment_status": employment,
            "loan_amount": loan_amount,
            "existing_loans": existing_loans,
            "approved": approved,
        }
    )


def main():
    df = build_dummy_dataset()
    df.to_csv("loan_data.csv", index=False)

    features = ["income", "credit_score", "employment_status", "loan_amount", "existing_loans"]
    X = df[features]
    y = df["approved"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    preprocess = ColumnTransformer(
        transformers=[
            ("employment", OneHotEncoder(handle_unknown="ignore"), ["employment_status"]),
        ],
        remainder="passthrough",
    )
    model = Pipeline(
        steps=[
            ("preprocess", preprocess),
            ("classifier", RandomForestClassifier(n_estimators=220, max_depth=8, random_state=42, class_weight="balanced")),
        ]
    )
    model.fit(X_train, y_train)
    preds = model.predict(X_test)
    print(f"Model accuracy: {accuracy_score(y_test, preds):.3f}")

    with open("model.pkl", "wb") as file:
        pickle.dump(model, file)
    print("Saved model.pkl and refreshed loan_data.csv")


if __name__ == "__main__":
    main()
