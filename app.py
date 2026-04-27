import json
import os
import pickle
import random
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from flask import Flask, jsonify, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash

from risk_engine import (
    LOAN_TYPE_BASE_RATES,
    calculate_emi,
    engineer_features,
    normalize_employment_status,
    normalize_loan_type,
    normalize_loan_tenure_months,
    normalize_previous_loan,
    tenure_years,
)


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "loan.db"
MODEL_PATH = BASE_DIR / "model.pkl"
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
APP_SECRET = os.getenv("APP_SECRET", "smartloan-dev-secret")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@loanai.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin@123")
DEMO_CUSTOMER_EMAIL = os.getenv("DEMO_CUSTOMER_EMAIL", "customer@gmail.com")
DEMO_CUSTOMER_PASSWORD = os.getenv("DEMO_CUSTOMER_PASSWORD", "Customer@123")

app = Flask(__name__, static_folder=None)
app.secret_key = APP_SECRET


def load_model_bundle():
    if not MODEL_PATH.exists():
        raise FileNotFoundError("model.pkl not found. Run: python3 train_model.py")
    with MODEL_PATH.open("rb") as file:
        bundle = pickle.load(file)
    required_keys = {
        "artifact_version",
        "model",
        "scaler",
        "raw_features",
        "model_features",
        "categorical_features",
        "numeric_features",
        "class_labels",
        "label_mapping",
    }
    if not isinstance(bundle, dict) or not required_keys.issubset(bundle):
        raise ValueError("model.pkl is outdated or incomplete. Run: python3 train_model.py")
    return bundle

MODEL_BUNDLE = load_model_bundle()
MODEL = MODEL_BUNDLE["model"]
SCALER = MODEL_BUNDLE["scaler"]
MODEL_FEATURES = MODEL_BUNDLE["model_features"]
NUMERIC_FEATURES = MODEL_BUNDLE["numeric_features"]
CLASS_LABELS = [int(value) for value in MODEL_BUNDLE["class_labels"]]
LABEL_MAPPING = MODEL_BUNDLE["label_mapping"]
APPROVED_CLASS = int(LABEL_MAPPING["Approved"])
APPROVED_CLASS_INDEX = CLASS_LABELS.index(APPROVED_CLASS)


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                name TEXT,
                role TEXT DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS otp_logs(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT NOT NULL,
                otp TEXT NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                verified INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS loans(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                income REAL NOT NULL,
                credit_score INTEGER NOT NULL,
                employment_status TEXT NOT NULL,
                loan_amount REAL NOT NULL,
                existing_loans REAL NOT NULL,
                result TEXT NOT NULL,
                approval_probability REAL NOT NULL,
                risk_score REAL NOT NULL,
                risk_category TEXT NOT NULL,
                reasons TEXT NOT NULL,
                suggestions TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )

        columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "phone" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN phone TEXT")
        if "email" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
        if "password_hash" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
        if "role" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")

        loan_columns = {row["name"] for row in conn.execute("PRAGMA table_info(loans)").fetchall()}
        loan_migrations = {
            "employment_status": "ALTER TABLE loans ADD COLUMN employment_status TEXT DEFAULT 'salaried'",
            "loan_amount": "ALTER TABLE loans ADD COLUMN loan_amount REAL DEFAULT 0",
            "existing_loans": "ALTER TABLE loans ADD COLUMN existing_loans REAL DEFAULT 0",
            "approval_probability": "ALTER TABLE loans ADD COLUMN approval_probability REAL DEFAULT 0",
            "confidence_score": "ALTER TABLE loans ADD COLUMN confidence_score REAL DEFAULT 0",
            "risk_category": "ALTER TABLE loans ADD COLUMN risk_category TEXT DEFAULT 'Moderate'",
            "reasons": "ALTER TABLE loans ADD COLUMN reasons TEXT DEFAULT '[]'",
            "suggestions": "ALTER TABLE loans ADD COLUMN suggestions TEXT DEFAULT '[]'",
            "fraud_flags": "ALTER TABLE loans ADD COLUMN fraud_flags TEXT DEFAULT '[]'",
            "loan_type": "ALTER TABLE loans ADD COLUMN loan_type TEXT DEFAULT 'Personal Loan'",
            "previous_loan": "ALTER TABLE loans ADD COLUMN previous_loan TEXT DEFAULT 'No'",
            "previous_loan_amount": "ALTER TABLE loans ADD COLUMN previous_loan_amount REAL DEFAULT 0",
            "monthly_emi": "ALTER TABLE loans ADD COLUMN monthly_emi REAL DEFAULT 0",
            "loan_tenure": "ALTER TABLE loans ADD COLUMN loan_tenure INTEGER DEFAULT 24",
            "interest_rate": "ALTER TABLE loans ADD COLUMN interest_rate REAL DEFAULT 0",
            "dti_ratio": "ALTER TABLE loans ADD COLUMN dti_ratio REAL DEFAULT 0",
            "emi_to_income_ratio": "ALTER TABLE loans ADD COLUMN emi_to_income_ratio REAL DEFAULT 0",
            "credit_utilization": "ALTER TABLE loans ADD COLUMN credit_utilization REAL DEFAULT 0",
            "top_factors": "ALTER TABLE loans ADD COLUMN top_factors TEXT DEFAULT '[]'",
        }
        for column, statement in loan_migrations.items():
            if column not in loan_columns:
                conn.execute(statement)

        existing_admin = conn.execute("SELECT id FROM users WHERE lower(email)=lower(?)", (ADMIN_EMAIL,)).fetchone()
        if existing_admin:
            conn.execute(
                "UPDATE users SET role='admin', password_hash=? WHERE id=?",
                (generate_password_hash(ADMIN_PASSWORD), existing_admin["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO users(email, password_hash, name, role) VALUES(?,?,?,?)",
                (ADMIN_EMAIL, generate_password_hash(ADMIN_PASSWORD), "Bank Officer", "admin"),
            )

        existing_customer = conn.execute("SELECT id FROM users WHERE lower(email)=lower(?)", (DEMO_CUSTOMER_EMAIL,)).fetchone()
        if not existing_customer:
            conn.execute(
                "INSERT INTO users(email, password_hash, name, role, phone) VALUES(?,?,?,?,?)",
                (DEMO_CUSTOMER_EMAIL, generate_password_hash(DEMO_CUSTOMER_PASSWORD), "Demo Customer", "user", "9876543210"),
            )


@app.after_request
def cors(response):
    response.headers["Access-Control-Allow-Origin"] = request.headers.get("Origin", "*")
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response


@app.route("/api/<path:_>", methods=["OPTIONS"])
def options(_):
    return ("", 204)


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    with db() as conn:
        return conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()


def require_user():
    user = current_user()
    if not user:
        return None, (jsonify({"error": "Authentication required"}), 401)
    return user, None


def require_role(role):
    user, error = require_user()
    if error:
        return None, error
    if user["role"] != role:
        return None, (jsonify({"error": "Access Denied – Unauthorized Role"}), 403)
    return user, None


def user_to_dict(user):
    email = user["email"] or ""
    return {
        "id": user["id"],
        "name": user["name"] or (email.split("@")[0] if email else "Customer"),
        "email": email,
        "phone": user["phone"] if "phone" in user.keys() else "",
        "role": user["role"] or "user",
    }


def normalize_email(email):
    return str(email or "").strip().lower()


def valid_email(email):
    return "@" in email and "." in email.rsplit("@", 1)[-1]


def normalize_phone(phone):
    return "".join(ch for ch in str(phone or "") if ch.isdigit())


def parse_input_loan_tenure(value):
    text = str(value or "").strip().lower()
    if not text:
        raise ValueError("Missing fields: loan_tenure")

    if "year" in text:
        years = int(float(text.split()[0]))
        return years * 12
    if "month" in text:
        return int(float(text.split()[0]))

    numeric_value = float(value)
    if isinstance(value, str):
        numeric_text = text.replace(".0", "")
        if numeric_text.isdigit():
            raw_int = int(numeric_text)
            if raw_int >= 12 and raw_int % 12 == 0:
                return raw_int
            if 1 <= raw_int <= 30:
                return raw_int * 12
            return raw_int

    raw_int = int(round(numeric_value))
    if 1 <= raw_int <= 30:
        return raw_int * 12
    return raw_int


def risk_category(score):
    if score < 35:
        return "Low"
    if score < 68:
        return "Moderate"
    return "High"


def underwriting_decision_tier(features):
    dti_ratio = float(features["dti_ratio"])
    emi_ratio = float(features["emi_to_income_ratio"])
    credit_score = int(features["credit_score"])

    if dti_ratio > 0.6 or emi_ratio > 0.5:
        return "Rejected"
    if emi_ratio > 0.4:
        return "Risky"
    if dti_ratio > 0.4:
        return "Approved" if credit_score >= 750 else "Risky"
    if credit_score < 650:
        return "Risky"
    return "Approved"


FACTOR_COPY = {
    "credit_score": {
        "negative": (
            "Credit score is below the preferred lending range",
            "Improve repayment discipline and keep credit card utilization low to move closer to 700+.",
        ),
        "positive": (
            "Credit score supports stronger pricing and approval odds",
            "Keep current repayment behavior steady to preserve this advantage.",
        ),
    },
    "dti_ratio": {
        "negative": (
            "Debt-to-income ratio is stretching affordability",
            "Reduce existing obligations or choose a smaller EMI before reapplying.",
        ),
        "positive": (
            "Debt-to-income ratio is within a healthier underwriting band",
            "Maintaining low recurring debt will keep affordability strong.",
        ),
    },
    "emi_to_income_ratio": {
        "negative": (
            "Projected EMI takes too much of monthly income",
            "A longer tenure or lower loan amount can improve monthly affordability.",
        ),
        "positive": (
            "Projected EMI is manageable for the declared income",
            "This affordability signal supports faster credit review.",
        ),
    },
    "credit_utilization": {
        "negative": (
            "Current credit utilization is elevated",
            "Pay down revolving balances and reduce leverage before the next application.",
        ),
        "positive": (
            "Credit utilization looks controlled",
            "Continue keeping total borrowing well below income capacity.",
        ),
    },
    "income_stability_factor": {
        "negative": (
            "Income profile appears less stable for this loan request",
            "Add verified income continuity or a co-applicant to strengthen stability.",
        ),
        "positive": (
            "Income stability supports repayment confidence",
            "Stable documented income remains one of the strongest approval signals.",
        ),
    },
    "loan_type_risk_weight": {
        "negative": (
            "The selected loan type is assessed with a higher risk weight",
            "Secured borrowing usually receives better pricing and approval treatment than unsecured loans.",
        ),
        "positive": (
            "The selected loan type sits in a lower risk bucket",
            "Secured or policy-favored products often benefit from more generous affordability treatment.",
        ),
    },
    "previous_loan_impact": {
        "negative": (
            "Previous loan exposure is heavy relative to income",
            "Reduce older balances or show strong repayment closure before taking fresh credit.",
        ),
        "positive": (
            "Previous borrowing history is helping rather than hurting this case",
            "Keeping prior loans well-managed builds trust in future repayment behavior.",
        ),
    },
    "loan_to_income_ratio": {
        "negative": (
            "Requested loan amount is high relative to income",
            "Reduce the ticket size or stretch tenure carefully to improve fit.",
        ),
        "positive": (
            "Requested loan amount is proportionate to income",
            "This improves the overall affordability profile for approval review.",
        ),
    },
    "interest_rate": {
        "negative": (
            "The priced interest rate is higher because the profile carries more risk",
            "Improving credit quality and lowering leverage can unlock better pricing.",
        ),
        "positive": (
            "The quoted rate reflects a relatively healthier risk profile",
            "Stronger credit and lower leverage are helping the pricing outcome.",
        ),
    },
}


def validate_prediction_input(data):
    required = ["income", "credit_score", "employment_status", "loan_amount", "loan_type", "previous_loan", "loan_tenure"]
    missing = [field for field in required if data.get(field) in (None, "")]
    if missing:
        raise ValueError(f"Missing fields: {', '.join(missing)}")

    income = float(data["income"])
    credit_score = int(data["credit_score"])
    loan_amount = float(data["loan_amount"])
    existing_loans = float(data.get("existing_loans") or 0)
    loan_tenure = normalize_loan_tenure_months(parse_input_loan_tenure(data["loan_tenure"]))
    previous_loan = normalize_previous_loan(data.get("previous_loan"))
    previous_loan_amount = float(data.get("previous_loan_amount") or 0)
    employment_status = normalize_employment_status(data.get("employment_status"))
    loan_type = normalize_loan_type(data.get("loan_type"))

    if income <= 0 or loan_amount <= 0:
        raise ValueError("Income and loan amount must be greater than zero.")
    if not 300 <= credit_score <= 900:
        raise ValueError("Credit score must be between 300 and 900.")
    if existing_loans < 0 or previous_loan_amount < 0:
        raise ValueError("Debt values cannot be negative.")
    if income > 1000000:
        raise ValueError("Monthly income entered is unrealistically high for instant approval.")
    if loan_amount > 100000000:
        raise ValueError("Loan amount entered is unrealistically high.")
    if not 12 <= loan_tenure <= 360:
        raise ValueError("Loan tenure must be between 12 and 360 months.")
    if previous_loan == "Yes" and previous_loan_amount <= 0:
        raise ValueError("Please enter your previous loan amount.")

    return {
        "income": income,
        "credit_score": credit_score,
        "employment_status": employment_status,
        "loan_amount": loan_amount,
        "existing_loans": existing_loans,
        "loan_type": loan_type,
        "previous_loan": previous_loan,
        "previous_loan_amount": previous_loan_amount,
        "loan_tenure": loan_tenure,
    }


def pre_model_policy_validation(features):
    reasons = []
    suggestions = []
    income = float(features["income"])
    monthly_emi = float(features["monthly_emi"])
    existing_loans = float(features["existing_loans"])
    loan_amount = float(features["loan_amount"])
    loan_tenure = int(features["loan_tenure"])

    if existing_loans > income:
        reasons.append("Existing EMI obligations are higher than monthly income")
        suggestions.append("Reduce current EMI burden before applying for additional credit.")
    if monthly_emi > income * 0.5:
        reasons.append("Projected EMI is above 50% of monthly income")
        suggestions.append("Choose a longer tenure or lower loan amount to bring EMI below half of income.")
    if loan_amount >= 1500000 and loan_tenure <= 24:
        reasons.append("Loan tenure is too short for the requested large loan amount")
        suggestions.append("Use a longer tenure for large-ticket borrowing so affordability stays realistic.")
    if loan_amount >= 800000 and loan_tenure <= 12:
        reasons.append("One-year tenure is too short for this loan size")
        suggestions.append("Select a more realistic repayment term for this borrowing amount.")

    return list(dict.fromkeys(reasons)), list(dict.fromkeys(suggestions))


def post_model_policy_override(features):
    reasons = []
    suggestions = []

    if features["dti_ratio"] > 0.6:
        reasons.append("Debt-to-income ratio exceeds the bank policy limit")
        suggestions.append("Lower your combined EMIs and debts so total obligations stay below 60% of income.")
    if features["monthly_emi"] > features["income"]:
        reasons.append("Projected EMI is higher than monthly income")
        suggestions.append("This application needs a lower amount or much longer tenure before it can be reconsidered.")
    if features["existing_loans"] > features["income"] * 3:
        reasons.append("Existing loan obligations are too high for new unsecured exposure")
        suggestions.append("Reduce outstanding obligations substantially before applying again.")

    return list(dict.fromkeys(reasons)), list(dict.fromkeys(suggestions))


def risky_case_guidance(features):
    reasons = []
    suggestions = []

    if features["dti_ratio"] > 0.4:
        reasons.append("Debt-to-income ratio is above the preferred approval band")
        suggestions.append("Reduce existing EMIs or lower the requested amount to bring DTI below 40%.")
    if features["emi_to_income_ratio"] > 0.4:
        reasons.append("Projected EMI is above the bank's comfortable income share")
        suggestions.append("Increase tenure moderately or reduce the loan amount so EMI stays below 40% of income.")
    if features["credit_score"] < 650:
        reasons.append("Credit score is below the bank's clean approval threshold")
        suggestions.append("Improve credit behavior and repayment history to move the score above 650.")
    if features["emi_to_income_ratio"] > 0.3:
        reasons.append("Projected EMI is high relative to monthly income")
        suggestions.append("Choose a slightly longer tenure or smaller loan amount to improve affordability.")
    if features["credit_utilization"] > 0.35:
        reasons.append("Existing credit utilization leaves limited repayment buffer")
        suggestions.append("Pay down current balances before final underwriting review.")

    if not reasons:
        reasons.append("Application falls into a conditional approval band and needs additional review")
    if not suggestions:
        suggestions.append("Strengthen affordability or add supporting income documents before final approval.")

    return list(dict.fromkeys(reasons))[:4], list(dict.fromkeys(suggestions))[:4]


def low_risk_affordability_override(features, approval_probability):
    if approval_probability >= 0.5:
        return None
    if features["credit_score"] < 700:
        return None
    if features["dti_ratio"] > 0.35 or features["emi_to_income_ratio"] > 0.2:
        return None
    if features["monthly_emi"] > features["income"] * 0.25:
        return None
    if features["loan_type"] == "Personal Loan" and features["loan_to_income_ratio"] > 10:
        return None
    override_probability = max(0.52, affordability_probability(features))
    if features["loan_type"] == "Home Loan" and features["loan_tenure"] >= 180:
        return round(override_probability, 6)
    if features["loan_to_income_ratio"] <= 8:
        return round(override_probability, 6)
    return None


def conceptual_risk_signals(features):
    return {
        "credit_score": max(0.0, min(1.0, (700 - features["credit_score"]) / 300)),
        "dti_ratio": max(0.0, min(1.0, features["dti_ratio"] / 0.75)),
        "emi_to_income_ratio": max(0.0, min(1.0, features["emi_to_income_ratio"] / 0.55)),
        "credit_utilization": max(0.0, min(1.0, features["credit_utilization"] / 0.9)),
        "income_stability_factor": max(0.0, min(1.0, (0.9 - features["income_stability_factor"]) / 0.7)),
        "loan_type_risk_weight": max(0.0, min(1.0, (features["loan_type_risk_weight"] - 0.85) / 0.4)),
        "previous_loan_impact": max(0.0, min(1.0, (0.35 - features["previous_loan_impact"]) / 0.75)),
        "loan_to_income_ratio": max(0.0, min(1.0, features["loan_to_income_ratio"] / 12)),
        "interest_rate": max(0.0, min(1.0, (features["interest_rate"] - 8.0) / 8.0)),
    }


def feature_factor_summary(features):
    signals = conceptual_risk_signals(features)
    importance = MODEL_BUNDLE.get("feature_importance") or {}
    ranked = []
    for key, signal in signals.items():
        weight = float(importance.get(key, 0.04))
        severity = signal * max(weight, 0.04)
        direction = "negative" if signal >= 0.52 else "positive"
        title, suggestion = FACTOR_COPY[key][direction]
        ranked.append(
            {
                "feature": key,
                "signal": round(signal, 3),
                "weight": round(weight, 4),
                "impact": round(severity if direction == "negative" else -severity, 4),
                "direction": direction,
                "title": title,
                "suggestion": suggestion,
            }
        )
    ranked.sort(key=lambda item: abs(item["impact"]), reverse=True)
    return ranked


def explain_decision(features, approval_probability):
    factor_summary = feature_factor_summary(features)
    reasons = []
    suggestions = []

    for factor in factor_summary:
        if factor["direction"] == "negative" and len(reasons) < 4:
            reasons.append(factor["title"])
            suggestions.append(factor["suggestion"])

    if approval_probability >= 0.62:
        positives = [item["title"] for item in factor_summary if item["direction"] == "positive"][:3]
        if positives:
            reasons = positives + reasons
        if not suggestions:
            suggestions.append("Profile looks healthy. Keep leverage and repayment behavior stable to preserve pricing.")
    elif not reasons:
        reasons.append("Portfolio review is balanced, but the case still needs stronger affordability signals.")
        suggestions.append("Improve either leverage, credit quality, or requested amount to build a clearer approval margin.")

    unique_reasons = list(dict.fromkeys(reasons))[:4]
    unique_suggestions = list(dict.fromkeys(suggestions))[:4]
    top_factors = factor_summary[:5]
    return unique_reasons, unique_suggestions, top_factors


def model_confidence(row, approval_probability):
    preprocessed = MODEL.named_steps["preprocess"].transform(row)
    tree_probabilities = [estimator.predict_proba(preprocessed)[0][APPROVED_CLASS_INDEX] for estimator in MODEL.named_steps["classifier"].estimators_]
    spread = pd.Series(tree_probabilities).std() if tree_probabilities else 0
    margin = abs(approval_probability - 0.5) * 2
    agreement = max(0.0, min(1.0, 1 - (float(spread) / 0.5)))
    confidence = (margin * 0.58) + (agreement * 0.42)
    return round(confidence * 100, 1)


def build_prediction_row(features):
    missing = [column for column in MODEL_FEATURES if column not in features]
    if missing:
        raise ValueError(f"Prediction features missing from engineered payload: {', '.join(missing)}")
    ordered_payload = {column: features[column] for column in MODEL_FEATURES}
    row = pd.DataFrame([ordered_payload], columns=MODEL_FEATURES)
    return ordered_payload, row


def log_prediction_inputs(ordered_payload, row):
    scaled_numeric = SCALER.transform(row[NUMERIC_FEATURES])[0].tolist()
    transformed = MODEL.named_steps["preprocess"].transform(row)
    if hasattr(transformed, "toarray"):
        transformed = transformed.toarray()
    transformed_array = transformed[0].tolist()
    app.logger.info("Prediction feature order: %s", MODEL_FEATURES)
    app.logger.info("Prediction ordered input: %s", [ordered_payload[column] for column in MODEL_FEATURES])
    app.logger.info("Prediction scaled numeric input: %s", dict(zip(NUMERIC_FEATURES, [round(float(value), 6) for value in scaled_numeric])))
    app.logger.info("Prediction final model array: %s", [round(float(value), 6) for value in transformed_array])


def affordability_probability(features):
    years = tenure_years(features["loan_tenure"])
    short_tenure_penalty = max(0.0, (5.0 - years) / 4.0)
    optimal_tenure_bonus = max(0.0, 1.0 - abs(years - 13.0) / 7.5)
    long_tenure_penalty = max(0.0, (years - 25.0) / 8.0)
    score = (
        2.45
        + ((features["credit_score"] - 700) / 115)
        + ((features["income_stability_factor"] - 0.7) * 1.1)
        + (features["previous_loan_impact"] * 0.45)
        - (features["emi_to_income_ratio"] * 6.8)
        - (features["dti_ratio"] * 3.6)
        - (features["credit_utilization"] * 1.15)
        - (max(0.0, features["loan_to_income_ratio"] - 18) * 0.035)
        - ((features["loan_type_risk_weight"] - 1.0) * 0.9)
        - (short_tenure_penalty * 0.42)
        + (optimal_tenure_bonus * 0.18)
        - (long_tenure_penalty * 0.22)
    )
    probability = 1 / (1 + np.exp(-score))
    return max(0.01, min(0.99, float(probability)))


def stabilized_probability(features, model_probability):
    affordability = affordability_probability(features)
    gap = abs(model_probability - affordability)
    affordability_weight = 0.65 if gap <= 0.12 else 0.82
    blended = (model_probability * (1 - affordability_weight)) + (affordability * affordability_weight)
    return round(float(blended), 6), round(affordability, 6)


def prediction_payload(data):
    validated = validate_prediction_input(data)
    features = engineer_features(validated)
    validation_reasons, validation_suggestions = pre_model_policy_validation(features)

    if validation_reasons:
        fraud_messages = fraud_flags(features)
        reasons = validation_reasons + fraud_messages[:1]
        suggestions = validation_suggestions or ["Correct the affordability issues before retrying this application."]
        return {
            "status": "Rejected",
            "approval_probability": 0.0,
            "risk_score": 99.0,
            "confidence_score": 100.0,
            "risk_category": risk_category(99.0),
            "reasons": list(dict.fromkeys(reasons))[:4],
            "suggestions": list(dict.fromkeys(suggestions))[:4],
            "top_factors": [],
            "fraud_flags": fraud_messages,
            "fraud_flag": bool(fraud_messages),
            "warning_message": fraud_messages[0] if fraud_messages else "Application failed affordability validation before model scoring.",
            "inputs": features,
            "calculated_emi": features["monthly_emi"],
            "interest_rate": features["interest_rate"],
            "metrics": {
                "dti_ratio": round(features["dti_ratio"] * 100, 1),
                "emi_to_income_ratio": round(features["emi_to_income_ratio"] * 100, 1),
                "credit_utilization": round(features["credit_utilization"] * 100, 1),
                "income_stability_factor": round(features["income_stability_factor"] * 100, 1),
                "loan_to_income_ratio": round(features["loan_to_income_ratio"], 2),
            },
            "model_metrics": MODEL_BUNDLE.get("metrics", {}),
        }

    ordered_payload, row = build_prediction_row(features)
    log_prediction_inputs(ordered_payload, row)
    model_probability = float(MODEL.predict_proba(row)[0][APPROVED_CLASS_INDEX])
    predicted_class = int(MODEL.predict(row)[0])
    probability, affordability_prob = stabilized_probability(features, model_probability)
    status = underwriting_decision_tier(features)
    confidence_score = model_confidence(row, model_probability)
    risk_score = round((1 - probability) * 100, 1)
    reasons, suggestions, top_factors = explain_decision(features, probability)
    override_reasons, override_suggestions = post_model_policy_override(features)
    fraud_messages = fraud_flags(features)
    affordability_override_probability = low_risk_affordability_override(features, probability)
    app.logger.info(
        "Prediction probabilities: model=%s affordability=%s stabilized=%s classifier_label=%s",
        round(model_probability, 6),
        affordability_prob,
        probability,
        predicted_class,
    )

    if override_reasons:
        status = "Rejected"
        probability = min(probability, 0.49)
        risk_score = max(risk_score, 85.0)
        reasons = override_reasons + reasons
        suggestions = override_suggestions + suggestions
    elif affordability_override_probability is not None:
        status = "Approved"
        probability = max(probability, affordability_override_probability)
        risk_score = round((1 - probability) * 100, 1)
        approval_reason = "Affordability policy override approved this low-DTI application"
        approval_suggestion = "Maintain the same low debt burden and repayment discipline through disbursal."
        reasons = [approval_reason] + reasons
        suggestions = [approval_suggestion] + suggestions

    if status == "Risky":
        probability = min(max(probability, 0.5), 0.69)
        risk_score = max(45.0, min(round((1 - probability) * 100, 1), 69.0))
        risky_reasons, risky_suggestions = risky_case_guidance(features)
        reasons = risky_reasons + reasons
        suggestions = risky_suggestions + suggestions

    return {
        "status": status,
        "approval_probability": round(probability * 100, 1),
        "risk_score": risk_score,
        "confidence_score": confidence_score,
        "risk_category": risk_category(risk_score),
        "reasons": list(dict.fromkeys(reasons))[:4],
        "suggestions": list(dict.fromkeys(suggestions))[:4],
        "top_factors": top_factors,
        "fraud_flags": fraud_messages,
        "fraud_flag": bool(fraud_messages),
        "warning_message": fraud_messages[0] if fraud_messages else "",
        "inputs": features,
        "calculated_emi": features["monthly_emi"],
        "interest_rate": features["interest_rate"],
        "metrics": {
            "dti_ratio": round(features["dti_ratio"] * 100, 1),
            "emi_to_income_ratio": round(features["emi_to_income_ratio"] * 100, 1),
            "credit_utilization": round(features["credit_utilization"] * 100, 1),
            "income_stability_factor": round(features["income_stability_factor"] * 100, 1),
            "loan_to_income_ratio": round(features["loan_to_income_ratio"], 2),
        },
        "model_metrics": MODEL_BUNDLE.get("metrics", {}),
    }


def fraud_flags(features):
    flags = []
    income = float(features["income"])
    loan_amount = float(features["loan_amount"])
    credit_score = int(features["credit_score"])
    existing_loans = float(features["existing_loans"])
    monthly_emi = float(features["monthly_emi"])
    previous_loan = str(features.get("previous_loan", "No"))
    previous_loan_amount = float(features.get("previous_loan_amount", 0))

    if income > 500000:
        flags.append("Unrealistic income entered for instant verification")
    if loan_amount > income * 24:
        flags.append("Loan amount is unusually high compared with income")
    if existing_loans > income:
        flags.append("Existing EMI obligations already exceed monthly income")
    if existing_loans > income * 8:
        flags.append("Existing loan exposure is unusually high")
    if credit_score < 350 and income > 200000:
        flags.append("High income with extremely low score needs manual review")
    if monthly_emi > income * 0.8:
        flags.append("Projected EMI is extremely high compared with monthly income")
    if monthly_emi > income:
        flags.append("Projected EMI is higher than declared monthly income")
    if loan_amount >= 1500000 and features["loan_tenure"] <= 12:
        flags.append("Large loan with ultra-short tenure looks unrealistic")
    if previous_loan == "Yes" and previous_loan_amount > income * 5:
        flags.append("Previous loan amount is very high compared to income")
    return flags


@app.post("/api/register")
@app.post("/register")
def register():
    payload = request.get_json(force=True)
    name = str(payload.get("name") or "").strip()
    email = normalize_email(payload.get("email"))
    password = str(payload.get("password") or "")

    if not name:
        return jsonify({"error": "Enter your full name."}), 400
    if not valid_email(email):
        return jsonify({"error": "Enter a valid email address."}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400

    with db() as conn:
        existing = conn.execute("SELECT id FROM users WHERE lower(email)=lower(?)", (email,)).fetchone()
        if existing:
            return jsonify({"error": "An account already exists for this email."}), 409
        conn.execute(
            "INSERT INTO users(email, password_hash, name, role) VALUES(?,?,?,?)",
            (email, generate_password_hash(password), name, "user"),
        )
        user = conn.execute("SELECT * FROM users WHERE lower(email)=lower(?)", (email,)).fetchone()

    session["user_id"] = user["id"]
    return jsonify({"user": user_to_dict(user)})


@app.post("/api/login")
@app.post("/login")
def login():
    payload = request.get_json(force=True)
    email = normalize_email(payload.get("email"))
    password = str(payload.get("password") or "")
    role = str(payload.get("role") or "user").lower()
    if role not in {"user", "admin"}:
        return jsonify({"error": "Invalid login role."}), 400

    with db() as conn:
        user = conn.execute("SELECT * FROM users WHERE lower(email)=lower(?)", (email,)).fetchone()

    if not user or not user["password_hash"] or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid email or password."}), 401
    if user["role"] != role:
        return jsonify({"error": f"This account is not registered as {role}."}), 403
    session["user_id"] = user["id"]
    return jsonify({"user": user_to_dict(user)})


@app.post("/api/send_otp")
@app.post("/send_otp")
def send_otp():
    payload = request.get_json(force=True)
    phone = normalize_phone(payload.get("phone"))
    if len(phone) < 10:
        return jsonify({"error": "Enter a valid phone number."}), 400

    otp = f"{random.randint(100000, 999999)}"
    expires_at = (datetime.utcnow() + timedelta(minutes=5)).isoformat(timespec="seconds")

    with db() as conn:
        conn.execute(
            "INSERT INTO otp_logs(phone, otp, expires_at) VALUES(?,?,?)",
            (phone, otp, expires_at),
        )

    # Twilio can be connected here with env vars in production. For local demos,
    # returning the OTP keeps the workflow runnable without paid SMS credentials.
    return jsonify({
        "message": "OTP sent successfully.",
        "dev_otp": otp,
        "expires_in_seconds": 300,
    })


@app.post("/api/verify_otp")
@app.post("/verify_otp")
def verify_otp():
    payload = request.get_json(force=True)
    phone = normalize_phone(payload.get("phone"))
    otp = str(payload.get("otp") or "").strip()
    if len(phone) < 10 or len(otp) != 6:
        return jsonify({"error": "Invalid phone number or OTP."}), 400

    now = datetime.utcnow().isoformat(timespec="seconds")
    with db() as conn:
        otp_row = conn.execute(
            """
            SELECT * FROM otp_logs
            WHERE phone=? AND otp=? AND verified=0 AND expires_at >= ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (phone, otp, now),
        ).fetchone()
        if not otp_row:
            return jsonify({"error": "Invalid OTP or OTP expired."}), 401

        conn.execute("UPDATE otp_logs SET verified=1 WHERE id=?", (otp_row["id"],))
        user = conn.execute("SELECT * FROM users WHERE phone=? AND role='user' ORDER BY id DESC LIMIT 1", (phone,)).fetchone()
        if not user:
            email = f"{phone}@otp.smartloan.local"
            conn.execute(
                "INSERT INTO users(email, password_hash, name, role, phone) VALUES(?,?,?,?,?)",
                (email, "", f"Customer {phone[-4:]}", "user", phone),
            )
            user = conn.execute("SELECT * FROM users WHERE phone=? AND role='user' ORDER BY id DESC LIMIT 1", (phone,)).fetchone()

    session["user_id"] = user["id"]
    return jsonify({"user": user_to_dict(user)})


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify({"message": "Logged out"})


@app.get("/api/me")
def me():
    user = current_user()
    if not user:
        return jsonify({"user": None})
    return jsonify({"user": user_to_dict(user)})


@app.post("/api/predict")
@app.post("/predict")
def predict():
    user, error = require_role("user")
    if error:
        return error
    try:
        result = prediction_payload(request.get_json(force=True))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    with db() as conn:
        conn.execute(
            """
            INSERT INTO loans(
                user_id, income, credit_score, employment_status, loan_amount, existing_loans,
                loan_type, previous_loan, previous_loan_amount, monthly_emi, loan_tenure, interest_rate,
                dti_ratio, emi_to_income_ratio, credit_utilization,
                result, approval_probability, confidence_score, risk_score, risk_category,
                reasons, suggestions, fraud_flags, top_factors
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                user["id"],
                result["inputs"]["income"],
                result["inputs"]["credit_score"],
                result["inputs"]["employment_status"],
                result["inputs"]["loan_amount"],
                result["inputs"]["existing_loans"],
                result["inputs"]["loan_type"],
                result["inputs"]["previous_loan"],
                result["inputs"]["previous_loan_amount"],
                result["inputs"]["monthly_emi"],
                result["inputs"]["loan_tenure"],
                result["inputs"]["interest_rate"],
                result["inputs"]["dti_ratio"],
                result["inputs"]["emi_to_income_ratio"],
                result["inputs"]["credit_utilization"],
                result["status"],
                result["approval_probability"],
                result["confidence_score"],
                result["risk_score"],
                result["risk_category"],
                json.dumps(result["reasons"]),
                json.dumps(result["suggestions"]),
                json.dumps(result["fraud_flags"]),
                json.dumps(result["top_factors"]),
            ),
        )

    return jsonify(result)


@app.post("/api/simulate")
def simulate():
    user, error = require_role("user")
    if error:
        return error
    try:
        result = prediction_payload(request.get_json(force=True))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result)


def loan_to_dict(row):
    return {
        "id": row["id"],
        "income": row["income"],
        "credit_score": row["credit_score"],
        "employment_status": row["employment_status"],
        "loan_amount": row["loan_amount"],
        "existing_loans": row["existing_loans"],
        "loan_type": row["loan_type"],
        "previous_loan": row["previous_loan"],
        "previous_loan_amount": row["previous_loan_amount"],
        "monthly_emi": row["monthly_emi"],
        "loan_tenure": row["loan_tenure"],
        "interest_rate": row["interest_rate"] if "interest_rate" in row.keys() else LOAN_TYPE_BASE_RATES.get(row["loan_type"], 12.0),
        "status": row["result"],
        "approval_probability": row["approval_probability"],
        "confidence_score": row["confidence_score"] if "confidence_score" in row.keys() else 0,
        "risk_score": row["risk_score"],
        "risk_category": row["risk_category"],
        "metrics": {
            "dti_ratio": round((row["dti_ratio"] if "dti_ratio" in row.keys() else 0) * 100, 1),
            "emi_to_income_ratio": round((row["emi_to_income_ratio"] if "emi_to_income_ratio" in row.keys() else 0) * 100, 1),
            "credit_utilization": round((row["credit_utilization"] if "credit_utilization" in row.keys() else 0) * 100, 1),
        },
        "reasons": json.loads(row["reasons"]),
        "suggestions": json.loads(row["suggestions"]),
        "fraud_flags": json.loads(row["fraud_flags"] or "[]"),
        "top_factors": json.loads(row["top_factors"] or "[]") if "top_factors" in row.keys() else [],
        "created_at": row["created_at"],
    }


@app.get("/api/history")
@app.get("/history")
@app.get("/api/user-loans")
@app.get("/user-loans")
def history():
    user, error = require_role("user")
    if error:
        return error
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM loans WHERE user_id=? ORDER BY created_at DESC",
            (user["id"],),
        ).fetchall()
    loans = [loan_to_dict(row) for row in rows]
    approved = sum(1 for item in loans if item["status"] == "Approved")
    risky = sum(1 for item in loans if item["status"] == "Risky")
    rejected = sum(1 for item in loans if item["status"] == "Rejected")
    avg_confidence = round(sum(item["confidence_score"] for item in loans) / len(loans), 1) if loans else 0
    avg_risk = round(sum(item["risk_score"] for item in loans) / len(loans), 1) if loans else 0
    return jsonify({"loans": loans, "stats": {"total": len(loans), "approved": approved, "risky": risky, "rejected": rejected, "avg_confidence": avg_confidence, "avg_risk": avg_risk}})


@app.post("/api/chat")
@app.post("/chat")
def chat():
    user, error = require_role("user")
    if error:
        return error

    message = request.get_json(force=True).get("message", "").lower()
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM loans WHERE user_id=? ORDER BY created_at DESC LIMIT 1",
            (user["id"],),
        ).fetchone()

    if not row:
        reply = "I do not see an application yet. Start with income, credit score, employment status, loan amount, existing loans, loan type, property ownership, previous loan tenure, and loan tenure so I can assess eligibility."
        return jsonify({"reply": reply, "response": reply})

    latest = loan_to_dict(row)
    reasons = ", ".join(latest["reasons"])
    suggestions = " ".join(latest["suggestions"])
    factor_titles = ", ".join(item["title"] for item in latest.get("top_factors", [])[:3])

    if "why" in message or "rejected" in message or "reason" in message:
        response = f"Your latest application was {latest['status']} with {latest['approval_probability']}% approval probability and {latest['confidence_score']}% model confidence. Main drivers: {factor_titles or reasons}. {suggestions}"
    elif "improve" in message or "chance" in message or "suggest" in message:
        response = suggestions
    elif "risk" in message or "score" in message:
        response = f"Your current risk score is {latest['risk_score']}/100, categorized as {latest['risk_category']} risk. DTI is {latest['metrics']['dti_ratio']}% and EMI to income is {latest['metrics']['emi_to_income_ratio']}%."
    elif "confidence" in message or "probability" in message:
        response = f"The model sees {latest['approval_probability']}% approval probability with {latest['confidence_score']}% confidence based on the consistency of the random forest ensemble."
    else:
        response = "Ask me about rejection reasons, approval probability, confidence score, risk score, or how to improve approval chances."

    return jsonify({"reply": response, "response": response})


@app.get("/api/admin/stats")
@app.get("/api/admin-data")
@app.get("/admin-data")
def admin_stats():
    user, error = require_role("admin")
    if error:
        return error

    with db() as conn:
        total_users = conn.execute("SELECT COUNT(*) AS count FROM users WHERE role='user'").fetchone()["count"]
        rows = conn.execute(
            """
            SELECT l.*, u.email, u.name
            FROM loans l
            LEFT JOIN users u ON u.id = l.user_id
            ORDER BY l.created_at DESC
            """
        ).fetchall()
        duplicate_rows = conn.execute(
            """
            SELECT lower(email) AS email, COUNT(*) AS count
            FROM users
            WHERE email IS NOT NULL AND email != ''
            GROUP BY lower(email)
            HAVING COUNT(*) > 1
            """
        ).fetchall()

    loans = [loan_to_dict(row) for row in rows]
    for loan, row in zip(loans, rows):
        loan["user_id"] = row["user_id"]
        loan["user_email"] = row["email"] or "legacy-user"
        loan["user_name"] = row["name"] or "Customer"

    approved = sum(1 for item in loans if item["status"] == "Approved")
    risky = sum(1 for item in loans if item["status"] == "Risky")
    rejected = sum(1 for item in loans if item["status"] == "Rejected")
    high_risk = [item for item in loans if item["risk_score"] >= 68 or item["fraud_flags"]]
    income_groups = [
        {"group": "Below 30k", "rejected": sum(1 for item in loans if item["income"] < 30000 and item["status"] == "Rejected")},
        {"group": "30k-75k", "rejected": sum(1 for item in loans if 30000 <= item["income"] < 75000 and item["status"] == "Rejected")},
        {"group": "75k+", "rejected": sum(1 for item in loans if item["income"] >= 75000 and item["status"] == "Rejected")},
    ]
    factor_impact = [
        {"factor": "Low credit score", "count": sum(1 for item in loans if item["credit_score"] < 660)},
        {"factor": "High existing loans", "count": sum(1 for item in loans if item["existing_loans"] > item["income"] * 2)},
        {"factor": "High loan amount", "count": sum(1 for item in loans if item["loan_amount"] > item["income"] * 8)},
        {"factor": "Unstable employment", "count": sum(1 for item in loans if item["employment_status"] in {"student", "unemployed"})},
    ]

    return jsonify({
        "total_users": total_users,
        "total_applications": len(loans),
        "approved": approved,
        "risky": risky,
        "rejected": rejected,
        "applications": loans,
        "high_risk": high_risk[:8],
        "duplicate_users": [{"email": row["email"], "count": row["count"]} for row in duplicate_rows],
        "income_groups": income_groups,
        "factor_impact": factor_impact,
    })


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_react(path):
    if FRONTEND_DIST.exists():
        file_path = FRONTEND_DIST / path
        if path and file_path.exists():
            return send_from_directory(FRONTEND_DIST, path)
        return send_from_directory(FRONTEND_DIST, "index.html")
    return jsonify({
        "message": "SmartLoan AI API is running.",
        "frontend": "Run the React app from ./frontend with npm install && npm run dev",
    })


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
