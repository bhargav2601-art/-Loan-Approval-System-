import json
import os
import pickle
import random
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
from flask import Flask, jsonify, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "loan.db"
MODEL_PATH = BASE_DIR / "model.pkl"
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
APP_SECRET = os.getenv("APP_SECRET", "smartloan-dev-secret")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@smartloan.ai")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin@123")
DEMO_CUSTOMER_EMAIL = os.getenv("DEMO_CUSTOMER_EMAIL", "customer@gmail.com")
DEMO_CUSTOMER_PASSWORD = os.getenv("DEMO_CUSTOMER_PASSWORD", "Customer@123")

app = Flask(__name__, static_folder=None)
app.secret_key = APP_SECRET


def load_model():
    if not MODEL_PATH.exists():
        raise FileNotFoundError("model.pkl not found. Run: python3 train_model.py")
    with MODEL_PATH.open("rb") as file:
        return pickle.load(file)


model = load_model()


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
            "risk_category": "ALTER TABLE loans ADD COLUMN risk_category TEXT DEFAULT 'Moderate'",
            "reasons": "ALTER TABLE loans ADD COLUMN reasons TEXT DEFAULT '[]'",
            "suggestions": "ALTER TABLE loans ADD COLUMN suggestions TEXT DEFAULT '[]'",
            "fraud_flags": "ALTER TABLE loans ADD COLUMN fraud_flags TEXT DEFAULT '[]'",
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


def risk_category(score):
    if score < 35:
        return "Low"
    if score < 68:
        return "Moderate"
    return "High"


def explain(features, approval_probability):
    income = float(features["income"])
    credit_score = int(features["credit_score"])
    loan_amount = float(features["loan_amount"])
    existing_loans = float(features["existing_loans"])
    employment_status = features["employment_status"]
    dti = (existing_loans + loan_amount * 0.025) / max(income, 1)

    reasons = []
    suggestions = []

    checks = [
        (credit_score < 660, "Credit score is below preferred lending range", "Bring your credit score above 700 with on-time payments and lower card utilization."),
        (income < 30000, "Income is low for the requested exposure", "Add a co-applicant or apply after strengthening monthly income."),
        (dti > 0.55, "Debt burden is high compared with monthly income", "Close or consolidate existing loans before reapplying."),
        (loan_amount > income * 8, "Requested loan amount is aggressive for this income", "Try a lower amount or longer tenure to improve affordability."),
        (employment_status.lower() in {"unemployed", "student"}, "Employment profile is considered unstable", "Show stable employment, business cash flow, or verified alternate income."),
    ]

    for failed, reason, suggestion in checks:
        if failed:
            reasons.append(reason)
            suggestions.append(suggestion)

    if approval_probability >= 0.5 and not reasons:
        reasons = ["Strong repayment profile", "Healthy credit behavior", "Loan amount fits the income band"]
        suggestions = ["Maintain low credit utilization and keep income documents ready for faster disbursal."]
    elif approval_probability >= 0.5:
        suggestions.append("Approval looks possible, but improving the flagged areas can help secure better pricing.")
    elif not reasons:
        reasons = ["Model sees elevated combined portfolio risk"]
        suggestions = ["Reduce the requested amount and provide additional verified financial documents."]

    return reasons[:4], suggestions[:4]


def prediction_payload(data):
    required = ["income", "credit_score", "employment_status", "loan_amount", "existing_loans"]
    missing = [field for field in required if data.get(field) in (None, "")]
    if missing:
        raise ValueError(f"Missing fields: {', '.join(missing)}")

    features = {
        "income": float(data["income"]),
        "credit_score": int(data["credit_score"]),
        "employment_status": str(data["employment_status"]).strip().lower(),
        "loan_amount": float(data["loan_amount"]),
        "existing_loans": float(data["existing_loans"]),
    }

    if features["income"] <= 0 or features["loan_amount"] <= 0:
        raise ValueError("Income and loan amount must be greater than zero.")
    if not 300 <= features["credit_score"] <= 900:
        raise ValueError("Credit score must be between 300 and 900.")
    if features["existing_loans"] < 0:
        raise ValueError("Existing loans cannot be negative.")

    row = pd.DataFrame([features])
    probability = float(model.predict_proba(row)[0][1])
    status = "Approved" if probability >= 0.5 else "Rejected"
    risk_score = round((1 - probability) * 100, 1)
    reasons, suggestions = explain(features, probability)

    return {
        "status": status,
        "approval_probability": round(probability, 3),
        "risk_score": risk_score,
        "risk_category": risk_category(risk_score),
        "reasons": reasons,
        "suggestions": suggestions,
        "fraud_flags": fraud_flags(features),
        "inputs": features,
    }


def fraud_flags(features):
    flags = []
    income = float(features["income"])
    loan_amount = float(features["loan_amount"])
    credit_score = int(features["credit_score"])
    existing_loans = float(features["existing_loans"])

    if income > 500000:
        flags.append("Unrealistic income entered for instant verification")
    if loan_amount > income * 12:
        flags.append("Loan amount is unusually high compared with income")
    if existing_loans > income * 8:
        flags.append("Existing loan exposure is unusually high")
    if credit_score < 350 and income > 200000:
        flags.append("High income with extremely low score needs manual review")
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
                result, approval_probability, risk_score, risk_category, reasons, suggestions
                , fraud_flags
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                user["id"],
                result["inputs"]["income"],
                result["inputs"]["credit_score"],
                result["inputs"]["employment_status"],
                result["inputs"]["loan_amount"],
                result["inputs"]["existing_loans"],
                result["status"],
                result["approval_probability"],
                result["risk_score"],
                result["risk_category"],
                json.dumps(result["reasons"]),
                json.dumps(result["suggestions"]),
                json.dumps(result["fraud_flags"]),
            ),
        )

    return jsonify(result)


def loan_to_dict(row):
    return {
        "id": row["id"],
        "income": row["income"],
        "credit_score": row["credit_score"],
        "employment_status": row["employment_status"],
        "loan_amount": row["loan_amount"],
        "existing_loans": row["existing_loans"],
        "status": row["result"],
        "approval_probability": row["approval_probability"],
        "risk_score": row["risk_score"],
        "risk_category": row["risk_category"],
        "reasons": json.loads(row["reasons"]),
        "suggestions": json.loads(row["suggestions"]),
        "fraud_flags": json.loads(row["fraud_flags"] or "[]"),
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
    rejected = sum(1 for item in loans if item["status"] == "Rejected")
    return jsonify({"loans": loans, "stats": {"total": len(loans), "approved": approved, "rejected": rejected}})


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
        reply = "I do not see an application yet. Start with income, credit score, employment status, loan amount, and existing loans so I can assess eligibility."
        return jsonify({"reply": reply, "response": reply})

    latest = loan_to_dict(row)
    reasons = ", ".join(latest["reasons"])
    suggestions = " ".join(latest["suggestions"])

    if "why" in message or "rejected" in message or "reason" in message:
        response = f"Your latest application was {latest['status']}. Main signals: {reasons}. {suggestions}"
    elif "improve" in message or "chance" in message or "suggest" in message:
        response = suggestions
    elif "risk" in message or "score" in message:
        response = f"Your current risk score is {latest['risk_score']}/100, categorized as {latest['risk_category']} risk."
    else:
        response = "Ask me about rejection reasons, risk score, or how to improve your approval chances."

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
