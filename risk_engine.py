from __future__ import annotations

from typing import Dict


LOAN_TYPE_BASE_RATES = {
    "Home Loan": 8.6,
    "Vehicle Loan": 9.4,
    "Education Loan": 8.9,
    "Personal Loan": 13.75,
}

EMPLOYMENT_STABILITY = {
    "salaried": 0.92,
    "business": 0.8,
    "self-employed": 0.74,
    "student": 0.42,
    "unemployed": 0.22,
}

LOAN_TYPE_RISK_WEIGHTS = {
    "Home Loan": 0.88,
    "Vehicle Loan": 1.0,
    "Education Loan": 0.95,
    "Personal Loan": 1.18,
}


def normalize_employment_status(value: str) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in EMPLOYMENT_STABILITY else "salaried"


def normalize_loan_type(value: str) -> str:
    text = str(value or "").strip()
    return text if text in LOAN_TYPE_BASE_RATES else "Personal Loan"


def normalize_previous_loan(value: str) -> str:
    return "Yes" if str(value or "").strip().lower() == "yes" else "No"


def safe_divide(numerator: float, denominator: float) -> float:
    return float(numerator) / float(denominator) if denominator else 0.0


def tenure_years(tenure_months: float | int) -> float:
    return float(tenure_months) / 12.0


def normalize_loan_tenure_months(value: float | int) -> int:
    tenure = int(round(float(value)))
    return max(12, min(360, tenure))


def calculate_emi(principal: float, annual_rate: float, tenure_months: int) -> float:
    if tenure_months <= 0 or principal <= 0:
        return 0.0
    monthly_rate = annual_rate / 12 / 100
    if monthly_rate == 0:
        return round(principal / tenure_months, 2)
    emi = (principal * monthly_rate * (1 + monthly_rate) ** tenure_months) / ((1 + monthly_rate) ** tenure_months - 1)
    return round(emi, 2)


def previous_loan_impact(previous_loan: str, previous_loan_amount: float, income: float) -> float:
    if normalize_previous_loan(previous_loan) != "Yes":
        return 0.3
    ratio = safe_divide(previous_loan_amount, max(income, 1))
    if ratio <= 1:
        return 0.35
    if ratio <= 2.5:
        return 0.05
    if ratio <= 4:
        return -0.18
    return -0.4


def interest_rate_for_profile(
    loan_type: str,
    credit_score: int,
    debt_to_income_ratio: float,
    previous_loan: str,
    income_stability_factor: float,
) -> float:
    loan_type = normalize_loan_type(loan_type)
    credit_score = int(credit_score)
    rate = LOAN_TYPE_BASE_RATES[loan_type]

    if credit_score >= 780:
        rate -= 0.7
    elif credit_score >= 720:
        rate -= 0.35
    elif credit_score < 620:
        rate += 1.35
    elif credit_score < 680:
        rate += 0.65

    if debt_to_income_ratio > 0.6:
        rate += 1.1
    elif debt_to_income_ratio > 0.45:
        rate += 0.45

    if normalize_previous_loan(previous_loan) == "Yes":
        rate += 0.15

    if income_stability_factor < 0.5:
        rate += 0.85
    elif income_stability_factor < 0.7:
        rate += 0.35

    return round(max(rate, 7.5), 2)


def engineer_features(raw: Dict[str, float | int | str]) -> Dict[str, float | int | str]:
    income = float(raw["income"])
    credit_score = int(raw["credit_score"])
    employment_status = normalize_employment_status(raw["employment_status"])
    loan_amount = float(raw["loan_amount"])
    existing_loans = float(raw.get("existing_loans") or 0)
    loan_type = normalize_loan_type(raw["loan_type"])
    previous_loan = normalize_previous_loan(raw.get("previous_loan", "No"))
    previous_loan_amount = float(raw.get("previous_loan_amount") or 0)
    loan_tenure = normalize_loan_tenure_months(raw["loan_tenure"])

    stability = EMPLOYMENT_STABILITY[employment_status]
    provisional_rate = interest_rate_for_profile(loan_type, credit_score, safe_divide(existing_loans, max(income, 1)), previous_loan, stability)
    monthly_emi = calculate_emi(loan_amount, provisional_rate, loan_tenure)
    dti_ratio = safe_divide(existing_loans + monthly_emi, max(income, 1))
    final_rate = interest_rate_for_profile(loan_type, credit_score, dti_ratio, previous_loan, stability)
    if final_rate != provisional_rate:
        monthly_emi = calculate_emi(loan_amount, final_rate, loan_tenure)
        dti_ratio = safe_divide(existing_loans + monthly_emi, max(income, 1))

    emi_to_income_ratio = safe_divide(monthly_emi, max(income, 1))
    credit_utilization = safe_divide(existing_loans + (previous_loan_amount * 0.55), max((income * 12) + (loan_amount * 0.25), 1))
    loan_to_income_ratio = safe_divide(loan_amount, max(income, 1))

    features = {
        "income": income,
        "credit_score": credit_score,
        "employment_status": employment_status,
        "loan_amount": loan_amount,
        "existing_loans": existing_loans,
        "loan_type": loan_type,
        "previous_loan": previous_loan,
        "previous_loan_amount": previous_loan_amount,
        "loan_tenure": loan_tenure,
        "interest_rate": final_rate,
        "monthly_emi": monthly_emi,
        "dti_ratio": round(dti_ratio, 4),
        "emi_to_income_ratio": round(emi_to_income_ratio, 4),
        "credit_utilization": round(credit_utilization, 4),
        "income_stability_factor": round(stability, 4),
        "loan_type_risk_weight": LOAN_TYPE_RISK_WEIGHTS[loan_type],
        "previous_loan_impact": round(previous_loan_impact(previous_loan, previous_loan_amount, income), 4),
        "loan_to_income_ratio": round(loan_to_income_ratio, 4),
    }
    return features
