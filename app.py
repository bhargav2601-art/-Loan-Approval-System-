import json
import os
import pickle
import random
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from flask import Flask, jsonify, request, send_from_directory, session, url_for
from werkzeug.exceptions import HTTPException
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
MODELS_DIR = BASE_DIR / "models"
LATEST_MODEL_PATH = MODELS_DIR / "model_latest.pkl"
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
    model_candidate = LATEST_MODEL_PATH if LATEST_MODEL_PATH.exists() else MODEL_PATH
    if not model_candidate.exists():
        raise FileNotFoundError("No trained model found. Run: python3 train_model.py")
    with model_candidate.open("rb") as file:
        bundle = pickle.load(file)
    if not isinstance(bundle, dict):
        raise ValueError(f"{model_candidate.name} is invalid. Expected a bundle dictionary.")
    if "model" not in bundle or bundle["model"] is None:
        raise KeyError(f"{model_candidate.name} is missing the trained model object.")
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
        "decision_threshold",
    }
    if not required_keys.issubset(bundle):
        raise ValueError(f"{model_candidate.name} is outdated or incomplete. Run: python3 train_model.py")
    return bundle

MODEL_LOAD_ERROR = None
MODEL_BUNDLE = {}
MODEL = None
SCALER = None
MODEL_FEATURES = []
NUMERIC_FEATURES = []
CLASS_LABELS = []
LABEL_MAPPING = {}
APPROVED_CLASS = None
APPROVED_CLASS_INDEX = 0
DECISION_THRESHOLD = 0.7

try:
    MODEL_BUNDLE = load_model_bundle()
    MODEL = MODEL_BUNDLE["model"]
    SCALER = MODEL_BUNDLE["scaler"]
    MODEL_FEATURES = MODEL_BUNDLE["model_features"]
    NUMERIC_FEATURES = MODEL_BUNDLE["numeric_features"]
    CLASS_LABELS = [int(value) for value in MODEL_BUNDLE["class_labels"]]
    LABEL_MAPPING = MODEL_BUNDLE["label_mapping"]
    APPROVED_CLASS = int(LABEL_MAPPING["Approved"])
    APPROVED_CLASS_INDEX = CLASS_LABELS.index(APPROVED_CLASS)
    DECISION_THRESHOLD = float(MODEL_BUNDLE.get("decision_threshold", 0.7))
except Exception as exc:
    MODEL_LOAD_ERROR = str(exc)
    app.logger.exception("Model initialization failed: %s", exc)


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


def wants_json_error():
    return request.path.startswith("/api/") or request.path in {
        "/predict",
        "/login",
        "/register",
        "/send_otp",
        "/verify_otp",
    }


@app.errorhandler(HTTPException)
def handle_http_exception(error):
    if not wants_json_error():
        return error
    app.logger.exception("HTTP error on %s: %s", request.path, error)
    return jsonify({"error": error.description or "Request failed"}), error.code


@app.errorhandler(Exception)
def handle_unexpected_exception(error):
    app.logger.exception("Unhandled server error on %s", request.path)
    if wants_json_error():
        return jsonify({"error": "Internal server error"}), 500
    return ("Internal server error", 500)


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
    if dti_ratio <= 0.4:
        return "Approved"
    if dti_ratio <= 0.6:
        return "Risky"
    return "Rejected"


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

GENERAL_CHAT_KNOWLEDGE = {
    "emi": "EMI means Equated Monthly Instalment. It is the fixed monthly amount you pay toward your loan principal and interest. Lower EMI usually comes from a smaller loan amount, lower rate, or longer tenure.",
    "dti": "DTI means debt-to-income ratio. It compares your total monthly debt obligations with your monthly income. Lower DTI is healthier because it shows you have enough repayment capacity after current obligations.",
    "credit score": "A credit score summarizes repayment behavior and borrowing discipline. Higher scores usually improve approval odds, lower interest rates, and access to larger loan amounts.",
    "interest rate": "Interest rate is the cost of borrowing. It depends on loan type, credit score, debt burden, repayment profile, and sometimes employment stability or collateral quality.",
    "home loan": "Home loans usually carry lower rates than unsecured loans because the property acts as collateral. Lenders focus on credit score, income stability, down payment strength, and repayment capacity.",
    "personal loan": "Personal loans are unsecured, so lenders usually apply stricter risk checks and higher interest rates than secured products like home or vehicle loans.",
    "education loan": "Education loan approval usually considers co-applicant strength, institution quality, expected earning potential, credit behavior, and repayment support.",
    "vehicle loan": "Vehicle loans are secured by the vehicle, so rates are often lower than personal loans. Approval still depends on income, credit profile, and total monthly debt load.",
    "secured": "A secured loan is backed by collateral such as a house, vehicle, or deposit. Because lender risk is lower, secured loans often get better pricing and easier approval than unsecured loans.",
    "unsecured": "An unsecured loan has no collateral. Because lender risk is higher, approval standards and rates are usually stricter than for secured loans.",
    "banking": "In retail banking, loan decisions typically balance credit score, affordability, income stability, existing obligations, product risk, tenure, and policy cutoffs like DTI or EMI-to-income limits.",
}

CHAT_QUICK_GUIDE = (
    "Ask me about EMI, DTI, credit score, interest rates, home loans, personal loans, "
    "education loans, vehicle loans, secured vs unsecured loans, approval chances, or ways to improve eligibility."
)


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
    if monthly_emi > income * 0.55:
        reasons.append("Projected EMI is above 55% of monthly income")
        suggestions.append("Choose a longer tenure or lower loan amount to bring EMI below 55% of income.")
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

    if features["dti_ratio"] > 0.55:
        reasons.append("Debt-to-income ratio exceeds the bank policy limit")
        suggestions.append("Lower your combined EMIs and debts so total obligations stay below 55% of income.")
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
    if features["emi_to_income_ratio"] > 0.55:
        reasons.append("Projected EMI exceeds the bank policy limit")
        suggestions.append("Lower the loan amount or extend the tenure so EMI falls below 55% of income.")
    if features["emi_to_income_ratio"] > 0.4:
        reasons.append("Projected EMI is above the bank's comfortable income share")
        suggestions.append("Increase tenure moderately or reduce the loan amount so EMI stays below 40% of income.")
    if features["credit_score"] < 650:
        reasons.append("Credit score is below the bank's clean approval threshold")
        suggestions.append("Improve credit behavior and repayment history to move the score above 650.")
    if features["emi_to_income_ratio"] > 0.35:
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
    if approval_probability >= DECISION_THRESHOLD:
        return None
    if features["credit_score"] < 700:
        return None
    if features["dti_ratio"] > 0.4 or features["emi_to_income_ratio"] > 0.4:
        return None
    if features["loan_type"] == "Personal Loan" and features["loan_to_income_ratio"] > 10:
        return None
    override_probability = max(DECISION_THRESHOLD, affordability_probability(features))
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


def model_insights_payload():
    metrics = MODEL_BUNDLE.get("model_insights") or MODEL_BUNDLE.get("metrics") or {}
    confusion = MODEL_BUNDLE.get("confusion_matrix")
    threshold_metrics = MODEL_BUNDLE.get("threshold_metrics") or metrics.get("threshold_metrics") or []
    validation_metrics = MODEL_BUNDLE.get("validation_metrics") or {}
    static_image = BASE_DIR / "static" / "confusion_matrix.png"
    image_url = ""
    if static_image.exists():
        cache_bust = int(static_image.stat().st_mtime)
        image_url = f"{url_for('serve_static_file', filename='confusion_matrix.png')}?v={cache_bust}"
    elif metrics.get("image_url"):
        image_url = metrics["image_url"]
    return {
        "accuracy": metrics.get("accuracy"),
        "precision": metrics.get("precision"),
        "recall": metrics.get("recall"),
        "f1_score": metrics.get("f1_score"),
        "roc_auc": metrics.get("roc_auc"),
        "decision_threshold": MODEL_BUNDLE.get("decision_threshold", DECISION_THRESHOLD),
        "validation_metrics": validation_metrics,
        "threshold_metrics": threshold_metrics,
        "confusion_matrix": confusion if isinstance(confusion, list) else [],
        "image_url": image_url,
        "available": bool(metrics) or bool(confusion),
    }


@app.get("/static/<path:filename>")
def serve_static_file(filename):
    return send_from_directory(BASE_DIR / "static", filename)


def normalize_chat_message(message):
    return " ".join(str(message or "").strip().lower().split())


def general_loan_chat_response(message):
    if not message:
        return f"Ask me any loan or banking question. {CHAT_QUICK_GUIDE}"

    if any(term in message for term in ("hello", "hi", "hey", "good morning", "good evening")):
        return f"Hi, I am your SmartLoan assistant. I can answer loan and banking questions and also explain your latest application. {CHAT_QUICK_GUIDE}"

    if any(term in message for term in ("emi", "monthly installment", "monthly instalment")):
        return GENERAL_CHAT_KNOWLEDGE["emi"]
    if any(term in message for term in ("dti", "debt to income", "debt-to-income")):
        return GENERAL_CHAT_KNOWLEDGE["dti"]
    if any(term in message for term in ("credit score", "cibil", "score improve", "improve score")):
        return GENERAL_CHAT_KNOWLEDGE["credit score"] + " To improve it, pay dues on time, avoid overusing credit lines, and keep borrowing stable."
    if any(term in message for term in ("interest rate", "rate of interest", "loan rate")):
        return GENERAL_CHAT_KNOWLEDGE["interest rate"]
    if "home loan" in message or "mortgage" in message:
        return GENERAL_CHAT_KNOWLEDGE["home loan"]
    if "personal loan" in message:
        return GENERAL_CHAT_KNOWLEDGE["personal loan"]
    if "education loan" in message or "student loan" in message:
        return GENERAL_CHAT_KNOWLEDGE["education loan"]
    if "vehicle loan" in message or "car loan" in message or "auto loan" in message:
        return GENERAL_CHAT_KNOWLEDGE["vehicle loan"]
    if "secured" in message and "unsecured" in message:
        return f"{GENERAL_CHAT_KNOWLEDGE['secured']} {GENERAL_CHAT_KNOWLEDGE['unsecured']}"
    if "secured" in message:
        return GENERAL_CHAT_KNOWLEDGE["secured"]
    if "unsecured" in message:
        return GENERAL_CHAT_KNOWLEDGE["unsecured"]
    if any(term in message for term in ("loan eligibility", "eligible", "eligibility", "can i get a loan", "approval chance")):
        return (
            "Loan eligibility usually depends on income, credit score, current EMIs, loan amount, tenure, employment stability, "
            "and loan type. Strong eligibility usually means lower DTI, manageable EMI, stable income, and healthier credit history."
        )
    if any(term in message for term in ("bank", "banking", "loan process", "underwriting")):
        return GENERAL_CHAT_KNOWLEDGE["banking"]
    if any(term in message for term in ("documents", "paperwork", "what documents")):
        return (
            "Common loan documents include identity proof, address proof, income proof, bank statements, employment or business proof, "
            "and product-specific documents like property or vehicle papers."
        )
    if any(term in message for term in ("tenure", "loan duration", "repayment period")):
        return (
            "Longer tenure usually reduces EMI but increases total interest paid. Shorter tenure raises EMI but reduces overall interest cost."
        )
    if any(term in message for term in ("down payment", "margin money")):
        return (
            "A stronger down payment reduces the financed amount, improves affordability, and can strengthen approval odds for secured loans."
        )
    if any(term in message for term in ("how to improve", "improve approval", "improve eligibility")):
        return (
            "To improve approval chances, reduce existing EMIs, request a smaller amount, increase tenure carefully, improve your credit score, "
            "and maintain stable documented income."
        )

    return f"I can help with loan and banking topics, but I did not fully understand that one. {CHAT_QUICK_GUIDE}"


def ensure_model_ready():
    if MODEL_LOAD_ERROR:
        raise RuntimeError(f"Model unavailable: {MODEL_LOAD_ERROR}")
    if MODEL is None:
        raise RuntimeError("Model unavailable: trained model is not loaded.")
    if SCALER is None:
        raise RuntimeError("Model unavailable: scaler is not loaded.")
    if not MODEL_FEATURES or not NUMERIC_FEATURES:
        raise RuntimeError("Model unavailable: feature metadata is missing.")
    if APPROVED_CLASS is None or not CLASS_LABELS:
        raise RuntimeError("Model unavailable: class metadata is missing.")


def approval_by_threshold(probability, features):
    if float(features["dti_ratio"]) > 0.55:
        return False
    return float(probability) > DECISION_THRESHOLD


def get_preprocess_step():
    preprocess = getattr(MODEL, "named_steps", {}).get("preprocess")
    if preprocess is None:
        raise RuntimeError("Model pipeline is missing the 'preprocess' step.")
    return preprocess


def get_classifier_step():
    named_steps = getattr(MODEL, "named_steps", {})
    classifier = named_steps.get("classifier") or named_steps.get("clf")
    if classifier is None:
        raise RuntimeError("Model pipeline is missing the classifier step.")
    return classifier


def explain_decision(features, approval_probability, status):
    factor_summary = feature_factor_summary(features)
    reasons = []
    suggestions = []
    primary_reason = ""
    primary_suggestion = ""

    if status == "Approved":
        primary_reason = "Debt-to-income ratio is within safe limits"
        primary_suggestion = "Current total debt obligations are within a healthy affordability range."
    elif status == "Risky":
        primary_reason = "Debt-to-income ratio is above the preferred approval band"
        primary_suggestion = "Reduce total monthly debt obligations to bring DTI back within safer limits."
    else:
        primary_reason = "Debt-to-income ratio exceeds the bank policy limit"
        primary_suggestion = "Lower total monthly debt obligations before reapplying."

    reasons.append(primary_reason)
    suggestions.append(primary_suggestion)

    for factor in factor_summary:
        if factor["feature"] == "previous_loan_impact":
            continue
        if factor["direction"] == "negative" and len(reasons) < 4 and status != "Approved":
            reasons.append(factor["title"])
            suggestions.append(factor["suggestion"])

    if status == "Approved":
        positives = [item["title"] for item in factor_summary if item["direction"] == "positive"][:3]
        if positives:
            reasons.extend([title for title in positives if title != primary_reason])
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
    preprocess = get_preprocess_step()
    classifier = get_classifier_step()
    preprocessed = preprocess.transform(row)
    margin = abs(approval_probability - 0.5) * 2

    if hasattr(classifier, "estimators_"):
        estimator_probabilities = [estimator.predict_proba(preprocessed)[0][APPROVED_CLASS_INDEX] for estimator in classifier.estimators_]
        spread = pd.Series(estimator_probabilities).std() if estimator_probabilities else 0
        agreement = max(0.0, min(1.0, 1 - (float(spread) / 0.5)))
        confidence = (margin * 0.58) + (agreement * 0.42)
    else:
        confidence = 0.62 + (margin * 0.38)

    return round(confidence * 100, 1)


def build_prediction_row(features):
    missing = [column for column in MODEL_FEATURES if column not in features]
    if missing:
        raise ValueError(f"Prediction features missing from engineered payload: {', '.join(missing)}")
    ordered_payload = {column: features[column] for column in MODEL_FEATURES}
    row = pd.DataFrame([ordered_payload], columns=MODEL_FEATURES)
    return ordered_payload, row


def log_prediction_inputs(ordered_payload, row):
    preprocess = get_preprocess_step()
    scaled_numeric = SCALER.transform(row[NUMERIC_FEATURES])[0].tolist()
    transformed = preprocess.transform(row)
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
        - (features["emi_to_income_ratio"] * 4.6)
        - (features["dti_ratio"] * 4.1)
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
    ensure_model_ready()
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
    probability, affordability_prob = stabilized_probability(features, model_probability)
    status = underwriting_decision_tier(features)
    confidence_score = model_confidence(row, model_probability)
    raw_risk_score = round((1 - probability) * 100, 1)
    if status == "Approved":
        risk_score = min(raw_risk_score, 39.0)
    elif status == "Risky":
        risk_score = min(max(raw_risk_score, 40.0), 69.0)
    else:
        risk_score = max(raw_risk_score, 70.0)
    reasons, suggestions, top_factors = explain_decision(features, probability, status)
    fraud_messages = fraud_flags(features)
    app.logger.info(
        "Prediction probabilities: model=%s affordability=%s stabilized=%s final_status=%s",
        round(model_probability, 6),
        affordability_prob,
        probability,
        status,
    )

    if status == "Risky":
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
        "model_metrics": {
            **MODEL_BUNDLE.get("metrics", {}),
            "decision_threshold": DECISION_THRESHOLD,
        },
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
        app.logger.exception("Prediction validation failed")
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        app.logger.exception("Prediction failed")
        return jsonify({"error": str(exc)}), 500

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
        app.logger.exception("Simulation validation failed")
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        app.logger.exception("Simulation failed")
        return jsonify({"error": str(exc)}), 500
    return jsonify(result)


@app.post("/api/suggestions")
def get_suggestions():
    """Generate smart suggestions by varying loan parameters"""
    user, error = require_role("user")
    if error:
        return error
    
    try:
        data = request.get_json(force=True)
        current_result = prediction_payload(data)
    except ValueError as exc:
        app.logger.exception("Suggestions validation failed")
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        app.logger.exception("Suggestions generation failed")
        return jsonify({"error": str(exc)}), 500
    
    current_approval = current_result["approval_probability"]
    income = float(data.get("income", 0))
    loan_amount = float(data.get("loan_amount", 0))
    loan_tenure = int(parse_input_loan_tenure(data.get("loan_tenure", 0)))
    existing_loans = float(data.get("existing_loans", 0))
    
    suggestions = []
    
    # Suggestion 1: Increase tenure
    if loan_tenure < 360:
        new_tenure = min(360, loan_tenure + 60)  # Add 5 years
        try:
            test_data = dict(data)
            test_data["loan_tenure"] = new_tenure
            test_result = prediction_payload(test_data)
            improvement = test_result["approval_probability"] - current_approval
            new_emi = test_result["calculated_emi"]
            suggestions.append({
                "type": "increase_tenure",
                "title": "Increase Loan Tenure",
                "description": "Extend repayment period to lower monthly EMI",
                "suggested_value": new_tenure,
                "current_value": loan_tenure,
                "unit": "months",
                "current_approval_prob": current_approval,
                "new_approval_prob": test_result["approval_probability"],
                "improvement_percent": round(improvement, 1),
                "new_emi": round(new_emi, 2),
                "current_emi": round(current_result["calculated_emi"], 2),
                "emi_reduction": round(current_result["calculated_emi"] - new_emi, 2),
            })
        except:
            pass
    
    # Suggestion 2: Reduce loan amount
    if loan_amount > income * 2:
        new_amount = max(income * 2, loan_amount * 0.85)  # Reduce by 15%
        try:
            test_data = dict(data)
            test_data["loan_amount"] = new_amount
            test_result = prediction_payload(test_data)
            improvement = test_result["approval_probability"] - current_approval
            suggestions.append({
                "type": "reduce_loan_amount",
                "title": "Reduce Loan Amount",
                "description": "Request a smaller loan amount to improve approval odds",
                "suggested_value": round(new_amount, 2),
                "current_value": round(loan_amount, 2),
                "unit": "₹",
                "current_approval_prob": current_approval,
                "new_approval_prob": test_result["approval_probability"],
                "improvement_percent": round(improvement, 1),
                "new_emi": round(test_result["calculated_emi"], 2),
                "current_emi": round(current_result["calculated_emi"], 2),
                "emi_reduction": round(current_result["calculated_emi"] - test_result["calculated_emi"], 2),
            })
        except:
            pass
    
    # Suggestion 3: Reduce existing loans (if applicable)
    if existing_loans > 0 and existing_loans > income * 0.5:
        new_existing = max(0, existing_loans * 0.8)  # Reduce by 20%
        try:
            test_data = dict(data)
            test_data["existing_loans"] = new_existing
            test_result = prediction_payload(test_data)
            improvement = test_result["approval_probability"] - current_approval
            suggestions.append({
                "type": "reduce_existing_loans",
                "title": "Reduce Existing Debt",
                "description": "Pay down current EMIs to improve debt-to-income ratio",
                "suggested_value": round(new_existing, 2),
                "current_value": round(existing_loans, 2),
                "unit": "₹",
                "current_approval_prob": current_approval,
                "new_approval_prob": test_result["approval_probability"],
                "improvement_percent": round(improvement, 1),
                "new_emi": round(test_result["calculated_emi"], 2),
                "current_emi": round(current_result["calculated_emi"], 2),
            })
        except:
            pass
    
    # If no custom suggestions, generate tenure-based trend
    if not suggestions:
        tenures = [12, 24, 36, 60, 84, 120]
        try:
            test_data = dict(data)
            for tenure in tenures:
                test_data["loan_tenure"] = tenure
                test_result = prediction_payload(test_data)
                improvement = test_result["approval_probability"] - current_approval
                if improvement > 5:
                    suggestions.append({
                        "type": "tenure_option",
                        "suggested_value": tenure,
                        "current_approval_prob": current_approval,
                        "new_approval_prob": test_result["approval_probability"],
                        "improvement_percent": round(improvement, 1),
                    })
                    break
        except:
            pass
    
    # Sort by improvement and take top 3
    suggestions.sort(key=lambda x: x.get("improvement_percent", 0), reverse=True)
    
    return jsonify({
        "current_approval_probability": current_approval,
        "suggestions": suggestions[:3],
        "best_suggestion": suggestions[0] if suggestions else None,
    })


@app.get("/api/model-insights")
def get_model_insights():
    user, error = require_role("admin")
    if error:
        return error

    try:
        payload = model_insights_payload()
        if not payload["available"]:
            return jsonify(
                {
                    "accuracy": None,
                    "precision": None,
                    "recall": None,
                    "f1_score": None,
                    "roc_auc": None,
                    "confusion_matrix": [],
                    "image_url": "",
                    "error": "Model insights are not available yet. Retrain the model to generate evaluation artifacts.",
                }
            ), 404
        return jsonify(payload)
    except Exception as exc:
        app.logger.exception("Failed to load model insights")
        return jsonify(
            {
                "accuracy": None,
                "precision": None,
                "recall": None,
                "f1_score": None,
                "roc_auc": None,
                "confusion_matrix": [],
                "image_url": "",
                "error": str(exc),
            }
        ), 500


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

    message = normalize_chat_message(request.get_json(force=True).get("message", ""))
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM loans WHERE user_id=? ORDER BY created_at DESC LIMIT 1",
            (user["id"],),
        ).fetchone()

    if not row:
        reply = general_loan_chat_response(message)
        return jsonify({"reply": reply, "response": reply})

    latest = loan_to_dict(row)
    reasons = ", ".join(latest["reasons"])
    suggestions = " ".join(latest["suggestions"])
    factor_titles = ", ".join(item["title"] for item in latest.get("top_factors", [])[:3])

    if any(term in message for term in ("latest application", "my application", "my loan", "decision")):
        response = (
            f"Your latest application is {latest['status']} with {latest['approval_probability']}% approval probability, "
            f"{latest['confidence_score']}% model confidence, and risk score {latest['risk_score']}/100."
        )
    elif "why" in message or "rejected" in message or "reason" in message:
        response = f"Your latest application was {latest['status']} with {latest['approval_probability']}% approval probability and {latest['confidence_score']}% model confidence. Main drivers: {factor_titles or reasons}. {suggestions}"
    elif "improve" in message or "chance" in message or "suggest" in message:
        response = suggestions
    elif "risk" in message or "score" in message:
        response = f"Your current risk score is {latest['risk_score']}/100, categorized as {latest['risk_category']} risk. DTI is {latest['metrics']['dti_ratio']}% and EMI to income is {latest['metrics']['emi_to_income_ratio']}%."
    elif "confidence" in message or "probability" in message:
        response = f"The model sees {latest['approval_probability']}% approval probability with {latest['confidence_score']}% confidence based on the consistency of the random forest ensemble."
    elif any(term in message for term in ("emi", "dti", "credit score", "cibil", "interest rate", "home loan", "personal loan", "education loan", "vehicle loan", "secured", "unsecured", "banking", "documents", "tenure", "eligibility")):
        response = general_loan_chat_response(message)
    else:
        response = (
            f"{general_loan_chat_response(message)} "
            f"If you want case-specific help, ask about your rejection reasons, approval probability, risk score, EMI, or how to improve your latest application."
        )

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
        "frontend": "Build the React app from ./frontend with npm run build, then serve it from Flask on port 5000.",
    })


if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5001)
