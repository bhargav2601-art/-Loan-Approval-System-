from __future__ import annotations

from typing import Any


AGE_MIN = 20
AGE_MAX = 55
AGE_ERROR = "Eligible age must be between 20 and 55 years."
CONSISTENCY_WARNING = "⚠ Additional verification required due to inconsistent financial information."
STUDENT_INCOME_SOURCES = {"Internship", "Freelancing", "Part-time"}
BUSINESS_OWNERSHIP_TYPES = {
    "Startup",
    "Partnership",
    "LLP",
    "Private Limited",
    "Proprietorship",
    "Inherited",
}

SALARY_BANDS = [
    # Age 20-22: Expected ₹8k-35k | Warning ₹35k-40k | Manual Review ₹40k-60k | Reject above ₹60k
    {"min_age": 20, "max_age": 22, "normal_min": 8000, "normal_max": 35000, "warning_above": 35000, "review_above": 40000, "reject_above": 60000},
    # Age 23-25: Expected ₹15k-60k | Warning ₹60k-70k | Manual Review ₹70k-90k | Reject above ₹90k
    {"min_age": 23, "max_age": 25, "normal_min": 15000, "normal_max": 60000, "warning_above": 60000, "review_above": 70000, "reject_above": 90000},
    # Age 26-30: Expected ₹20k-120k | Warning ₹120k-140k | Manual Review ₹140k-180k | Reject above ₹180k
    {"min_age": 26, "max_age": 30, "normal_min": 20000, "normal_max": 120000, "warning_above": 120000, "review_above": 140000, "reject_above": 180000},
    # Age 31-40: Expected ₹25k-250k | Warning ₹250k-280k | Manual Review ₹280k-350k | Reject above ₹350k
    {"min_age": 31, "max_age": 40, "normal_min": 25000, "normal_max": 250000, "warning_above": 250000, "review_above": 280000, "reject_above": 350000},
    # Age 41-55: Expected ₹25k-400k | Warning ₹400k-450k | Manual Review ₹450k-550k | Reject above ₹550k
    {"min_age": 41, "max_age": 55, "normal_min": 25000, "normal_max": 400000, "warning_above": 400000, "review_above": 450000, "reject_above": 550000},
]


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def clean_yes_no(value: Any) -> str:
    return "Yes" if clean_text(value).lower() == "yes" else "No"


def clean_float(value: Any) -> float:
    text = clean_text(value)
    if not text:
        return 0.0
    return float(text)


def clean_int(value: Any) -> int:
    return int(float(clean_text(value)))


def normalize_employment_status(value: Any) -> str:
    status = clean_text(value).lower()
    if status in {"salaried", "business", "student", "unemployed"}:
        return status
    return "salaried"


def salary_band_for_age(age: int) -> dict[str, float]:
    for band in SALARY_BANDS:
        if band["min_age"] <= age <= band["max_age"]:
            return band
    raise ValueError(AGE_ERROR)


def validate_age(age: int) -> None:
    if not AGE_MIN <= age <= AGE_MAX:
        raise ValueError(AGE_ERROR)


def validate_employment_profile(data: dict[str, Any], employment_status: str) -> dict[str, Any]:
    status = normalize_employment_status(employment_status)
    profile = {
        # student
        "student_earning": "",
        "income_source": "",
        "parent_guardian_income": 0.0,
        "sponsor_available": "",
        "education": "",
        "graduation_year": 0,
        "scholarship": "",
        "education_loan": "",
        "financial_support": "",
        "monthly_stipend": 0.0,
        # unemployed
        "source_of_income": "",
        "savings_amount": 0.0,
        "investments_amount": 0.0,
        "rental_income": 0.0,
        "emergency_fund": 0.0,
        "co_applicant_available": "",
        # salaried
        "company_name": "",
        "work_experience": 0.0,
        # business
        "business_type": "",
        "business_age_years": 0.0,
        "ownership_type": "",
    }

    if status == "student":
        student_earning = clean_yes_no(data.get("student_earning"))
        if not clean_text(data.get("student_earning")):
            raise ValueError("Please specify whether the student applicant is earning.")
        profile["student_earning"] = student_earning

        # Common student fields collected regardless of earning status
        profile["education"] = clean_text(data.get("education"))
        profile["graduation_year"] = clean_int(data.get("graduation_year") or 0)
        profile["scholarship"] = clean_yes_no(data.get("scholarship"))
        profile["education_loan"] = clean_yes_no(data.get("education_loan"))
        profile["financial_support"] = clean_text(data.get("financial_support"))

        if student_earning == "Yes":
            income_source = clean_text(data.get("income_source"))
            if income_source not in STUDENT_INCOME_SOURCES:
                raise ValueError("Please choose a valid student income source.")
            profile["income_source"] = income_source
            profile["monthly_stipend"] = clean_float(data.get("monthly_stipend") or 0)
            return profile

        parent_guardian_income = clean_float(data.get("parent_guardian_income"))
        if parent_guardian_income <= 0:
            raise ValueError("Please enter parent or guardian income for a non-earning student.")
        if not clean_text(data.get("sponsor_available")):
            raise ValueError("Please specify whether a sponsor is available.")
        profile["parent_guardian_income"] = parent_guardian_income
        profile["sponsor_available"] = clean_yes_no(data.get("sponsor_available"))
        return profile

    if status == "unemployed":
        source_of_income = clean_text(data.get("source_of_income"))
        if not source_of_income:
            raise ValueError("Please enter the source of income for an unemployed applicant.")
        savings_amount = clean_float(data.get("savings_amount"))
        investments_amount = clean_float(data.get("investments_amount"))
        rental_income = clean_float(data.get("rental_income") or 0)
        emergency_fund = clean_float(data.get("emergency_fund") or 0)
        if savings_amount < 0 or investments_amount < 0 or rental_income < 0 or emergency_fund < 0:
            raise ValueError("Financial amounts cannot be negative.")
        if not clean_text(data.get("sponsor_available")):
            raise ValueError("Please specify whether a sponsor is available.")
        if not clean_text(data.get("co_applicant_available")):
            raise ValueError("Please specify whether a co-applicant is available.")
        profile["source_of_income"] = source_of_income
        profile["savings_amount"] = savings_amount
        profile["investments_amount"] = investments_amount
        profile["rental_income"] = rental_income
        profile["emergency_fund"] = emergency_fund
        profile["sponsor_available"] = clean_yes_no(data.get("sponsor_available"))
        profile["co_applicant_available"] = clean_yes_no(data.get("co_applicant_available"))
        return profile

    if status == "salaried":
        company_name = clean_text(data.get("company_name"))
        work_experience = clean_float(data.get("work_experience"))
        if not company_name:
            raise ValueError("Please enter the company name for salaried applicants.")
        if work_experience < 0:
            raise ValueError("Work experience cannot be negative.")
        profile["company_name"] = company_name
        profile["work_experience"] = work_experience
        return profile

    if status == "business":
        business_type = clean_text(data.get("business_type"))
        business_age_years = clean_float(data.get("business_age_years", data.get("years_in_business")))
        ownership_type = clean_text(data.get("ownership_type"))
        if not business_type:
            raise ValueError("Please enter the business type.")
        if business_age_years < 0:
            raise ValueError("Business age cannot be negative.")
        if ownership_type not in BUSINESS_OWNERSHIP_TYPES:
            raise ValueError("Please choose a valid ownership type.")
        profile["business_type"] = business_type
        profile["business_age_years"] = business_age_years
        profile["ownership_type"] = ownership_type

    return profile


def salary_assessment(age: int, income: float) -> dict[str, Any]:
    band = salary_band_for_age(age)
    if income > band["reject_above"]:
        level = "reject"
        message = "Income is not realistic for this age band."
        points = 38
    elif income > band["review_above"]:
        level = "manual_review"
        message = "Income is unusually high for this age and needs verification."
        points = 24
    elif income > band["warning_above"]:
        level = "warning"
        message = "Salary unusually high for this age."
        points = 10
    elif band["normal_min"] <= income <= band["normal_max"]:
        level = "normal"
        message = "Salary within expected range."
        points = 0
    elif income < band["normal_min"]:
        level = "warning"
        message = "Income is below the typical range for this age band."
        points = 8
    else:
        level = "normal"
        message = "Salary within acceptable range."
        points = 0

    return {
        "level": level,
        "message": message,
        "points": points,
        "expected_min": band["normal_min"],
        "expected_max": band["normal_max"],
    }


def business_assessment(age: int, income: float, profile: dict[str, Any]) -> dict[str, Any]:
    business_age = float(profile.get("business_age_years") or 0)
    if business_age < 1:
        maturity = "High Risk"
        expected_max = 80000
        review_above = 150000
        points = 24
    elif business_age < 3:
        maturity = "Moderate Risk"
        expected_max = 180000
        review_above = 300000
        points = 14
    elif business_age < 5:
        maturity = "Good"
        expected_max = 280000
        review_above = 450000
        points = 6
    elif business_age < 10:
        maturity = "Strong"
        expected_max = 500000
        review_above = 750000
        points = 0
    else:
        maturity = "Excellent"
        expected_max = 800000
        review_above = 1200000
        points = 0

    level = "normal"
    message = f"Business maturity is {maturity.lower()}."
    if income > review_above:
        level = "manual_review"
        message = "Business income is unusually high for declared business age."
        points += 24
    elif income > expected_max:
        level = "warning"
        message = "Business income is above the expected range for this business age."
        points += 10

    inconsistent = age - business_age < 16
    if inconsistent:
        level = "manual_review"
        message = "Business age is inconsistent with applicant age."
        points += 28

    return {
        "level": level,
        "message": message,
        "points": points,
        "maturity": maturity,
        "expected_max": expected_max,
        "review_above": review_above,
        "inconsistent": inconsistent,
    }


def calculate_financial_ratios(features: dict[str, Any], profile: dict[str, Any]) -> dict[str, float]:
    income = max(float(features["income"]), 1)
    loan_amount = float(features["loan_amount"])
    existing_loans = float(features["existing_loans"])
    monthly_emi = float(features["monthly_emi"])
    savings = float(profile.get("savings_amount") or 0)
    investments = float(profile.get("investments_amount") or 0)
    liquid_assets = savings + investments
    disposable_income = income - existing_loans - monthly_emi

    return {
        "debt_to_income": round((existing_loans + monthly_emi) / income, 4),
        "loan_to_income": round(loan_amount / income, 4),
        "disposable_income": round(disposable_income, 2),
        "emi_ratio": round(monthly_emi / income, 4),
        "savings_ratio": round(liquid_assets / max(loan_amount, 1), 4),
        "existing_loan_ratio": round(existing_loans / income, 4),
    }


def add(items: list[str], message: str) -> None:
    if message and message not in items:
        items.append(message)


def evaluate(application: dict[str, Any]) -> dict[str, Any]:
    features = application["features"]
    ml_probability = float(application.get("ml_probability", 0))
    age = int(application["age"])
    validate_age(age)

    employment_status = normalize_employment_status(application["employment_status"])
    profile = application.get("employment_profile", {})
    income = float(features["income"])
    loan_amount = float(features["loan_amount"])
    existing_loans = float(features["existing_loans"])
    monthly_emi = float(features["monthly_emi"])
    credit_score = int(features["credit_score"])
    ratios = calculate_financial_ratios(features, profile)

    positive_reasons: list[str] = []
    risk_factors: list[str] = []
    reject_reasons: list[str] = []
    review_reasons: list[str] = []
    warnings: list[str] = []
    inconsistencies: list[str] = []
    suggestions: list[str] = []
    field_feedback: dict[str, dict[str, str]] = {}
    rule_points = 0
    consistency_points = 0
    hard_reject = False
    manual_review = False

    if credit_score >= 740:
        add(positive_reasons, "Good credit history")
    elif credit_score < 620:
        add(risk_factors, "Poor credit score")
        rule_points += 18

    if ratios["debt_to_income"] <= 0.35:
        add(positive_reasons, "Healthy DTI")
    elif ratios["debt_to_income"] > 0.65:
        add(reject_reasons, "Existing liabilities high")
        rule_points += 28
    elif ratios["debt_to_income"] > 0.45:
        add(risk_factors, "Debt-to-income ratio is above preferred limits")
        rule_points += 14

    if ratios["emi_ratio"] > 0.5:
        hard_reject = True
        add(reject_reasons, "EMI exceeds affordability")
        add(suggestions, "Reduce the loan amount or increase tenure until EMI is below 50% of income.")
        rule_points += 35
    elif ratios["emi_ratio"] <= 0.3:
        add(positive_reasons, "Loan affordable")
    else:
        add(risk_factors, "Projected EMI reduces repayment buffer")
        rule_points += 8

    if ratios["disposable_income"] < 0:
        hard_reject = True
        add(reject_reasons, "Income insufficient after current obligations")
        rule_points += 30

    if ratios["loan_to_income"] > 24:
        hard_reject = True
        add(reject_reasons, "Requested loan amount is unrealistic for income")
        rule_points += 30
    elif ratios["loan_to_income"] > 12:
        add(risk_factors, "High loan-to-income ratio")
        rule_points += 14

    if employment_status == "salaried":
        salary = salary_assessment(age, income)
        field_feedback["income"] = {"level": salary["level"], "message": salary["message"]}
        rule_points += salary["points"]
        if salary["level"] == "reject":
            hard_reject = True
            add(reject_reasons, "Income not realistic for age")
        elif salary["level"] == "manual_review":
            manual_review = True
            add(review_reasons, "Income inconsistent with age")
        elif salary["level"] == "warning":
            add(warnings, salary["message"])
            add(risk_factors, "Age-income mismatch")
        else:
            add(positive_reasons, "Good income")

        work_experience = float(profile.get("work_experience") or 0)
        if work_experience > max(age - 18, 0):
            manual_review = True
            consistency_points += 30
            add(inconsistencies, "Work experience is impossible for applicant age.")
            add(review_reasons, "Employment details require validation")
        elif work_experience < 1:
            add(risk_factors, "Short employment duration")
            rule_points += 7
        else:
            add(positive_reasons, "Stable employment")

    elif employment_status == "business":
        business = business_assessment(age, income, profile)
        field_feedback["income"] = {"level": business["level"], "message": business["message"]}
        field_feedback["business_age_years"] = {"level": "normal" if not business["inconsistent"] else "manual_review", "message": f"Business maturity: {business['maturity']}."}
        rule_points += business["points"]
        if business["level"] == "manual_review":
            manual_review = True
            add(review_reasons, "Business income unusually high")
        elif business["level"] == "warning":
            add(warnings, business["message"])
            add(risk_factors, "Business income needs supporting documents")
        else:
            add(positive_reasons, "Business income is aligned with business maturity")
        if business["inconsistent"]:
            consistency_points += 30
            add(inconsistencies, "Business age is inconsistent with applicant age.")

    elif employment_status == "student":
        student_earning = profile.get("student_earning")
        has_scholarship = profile.get("scholarship") == "Yes"
        has_education_loan = profile.get("education_loan") == "Yes"
        financial_support = clean_text(profile.get("financial_support"))

        if student_earning == "Yes":
            salary = salary_assessment(age, income)
            monthly_stipend = float(profile.get("monthly_stipend") or 0)
            if income > 120000 or (profile.get("income_source") == "Internship" and income > 60000):
                manual_review = True
                consistency_points += 24
                add(review_reasons, "Student income requires verification")
                add(inconsistencies, "Student income is unusually high for declared source.")
            if monthly_stipend > 0:
                add(positive_reasons, f"Student receives a monthly stipend of \u20B9{int(monthly_stipend):,}")
            field_feedback["income"] = {"level": "manual_review" if manual_review else salary["level"], "message": "Student income source requires verification." if manual_review else salary["message"]}
        else:
            add(risk_factors, "Student applicant depends on external financial support")
            rule_points += 10
            if profile.get("sponsor_available") == "No":
                manual_review = True
                add(review_reasons, "Student profile without sponsor support needs manual assessment")
                rule_points += 18
            elif financial_support:
                add(positive_reasons, f"Financial support declared: {financial_support}")

        # Scholarship reduces risk — lowers repayment burden
        if has_scholarship:
            add(positive_reasons, "Scholarship reduces financial dependency")
            rule_points = max(0, rule_points - 6)
        # Education loan as co-funding is acceptable but raises DTI
        if has_education_loan:
            add(risk_factors, "Existing education loan increases debt burden")
            rule_points += 8

        if loan_amount >= 4000000 and income <= 10000:
            hard_reject = True
            add(reject_reasons, "Student loan amount is not affordable for declared income")
            rule_points += 35

    elif employment_status == "unemployed":
        savings = float(profile.get("savings_amount") or 0)
        investments = float(profile.get("investments_amount") or 0)
        rental_income = float(profile.get("rental_income") or 0)
        emergency_fund = float(profile.get("emergency_fund") or 0)
        liquid_assets = savings + investments
        total_financial_buffer = liquid_assets + emergency_fund
        # Rental income boosts effective monthly income for repayment capacity
        effective_income = income + rental_income
        support_available = profile.get("sponsor_available") == "Yes" or profile.get("co_applicant_available") == "Yes"
        has_sponsor = profile.get("sponsor_available") == "Yes"
        has_co_applicant = profile.get("co_applicant_available") == "Yes"

        if income >= 80000:
            manual_review = True
            consistency_points += 18
            add(review_reasons, "Unemployed income requires verification")
            add(inconsistencies, "Unemployed applicant declared unusually high monthly income.")
        if income >= 300000:
            manual_review = True
            consistency_points += 30
            add(review_reasons, "Income source must be verified before decision")

        # Rental income is a strong positive signal for unemployed applicants
        if rental_income >= monthly_emi:
            add(positive_reasons, f"Rental income (\u20B9{int(rental_income):,}/mo) covers projected EMI")
            rule_points = max(0, rule_points - 8)
        elif rental_income > 0:
            add(positive_reasons, f"Rental income (\u20B9{int(rental_income):,}/mo) provides partial repayment support")
            rule_points = max(0, rule_points - 4)

        # Emergency fund check
        if emergency_fund >= monthly_emi * 6:
            add(positive_reasons, "Emergency fund covers 6+ months of EMI")
            rule_points = max(0, rule_points - 5)
        elif emergency_fund > 0:
            add(positive_reasons, "Emergency fund provides a repayment buffer")

        if liquid_assets < max(loan_amount * 0.1, monthly_emi * 6):
            add(risk_factors, "Savings are weak for requested loan exposure")
            add(suggestions, "Build a stronger savings reserve or add a verified co-applicant.")
            rule_points += 16
        elif liquid_assets >= loan_amount * 0.4:
            add(positive_reasons, "Savings and investments provide strong repayment buffer")

        if has_co_applicant:
            add(positive_reasons, "Co-applicant strengthens repayment capacity")
            rule_points = max(0, rule_points - 5)
        elif has_sponsor:
            add(positive_reasons, "Sponsor support improves creditworthiness")
            rule_points = max(0, rule_points - 3)
        elif not support_available:
            add(risk_factors, "No sponsor or co-applicant support")
            rule_points += 14

    if inconsistencies:
        add(warnings, CONSISTENCY_WARNING)
        manual_review = True

    risk_points = min(100, round(((1 - ml_probability) * 45) + rule_points + consistency_points))
    adjusted_probability = max(0.01, min(0.99, ml_probability - ((rule_points + consistency_points) / 120)))

    if hard_reject:
        final_status = "Reject"
        risk_category = "High Risk"
    elif manual_review:
        final_status = "Manual Review"
        risk_category = "Manual Review"
    elif risk_points < 35 and adjusted_probability >= 0.68:
        final_status = "Low Risk"
        risk_category = "Low Risk"
    elif risk_points < 65 and adjusted_probability >= 0.45:
        final_status = "Medium Risk"
        risk_category = "Medium Risk"
    else:
        final_status = "High Risk"
        risk_category = "High Risk"

    if final_status == "High Risk" and risk_points >= 82:
        final_status = "Manual Review"
        risk_category = "Manual Review"
        manual_review = True
        add(review_reasons, "Combined risk score requires underwriter validation")

    if not positive_reasons and final_status in {"Low Risk", "Medium Risk"}:
        add(positive_reasons, "Profile satisfies core affordability checks")
    if final_status == "Reject" and not reject_reasons:
        add(reject_reasons, "High default probability")
    if final_status == "Manual Review" and not review_reasons:
        add(review_reasons, "Verification required")

    return {
        "final_status": final_status,
        "risk_category": risk_category,
        "adjusted_probability": adjusted_probability,
        "risk_score": risk_points,
        "rule_points": rule_points,
        "consistency_points": consistency_points,
        "financial_ratios": ratios,
        "positive_reasons": positive_reasons[:5],
        "risk_factors": risk_factors[:5],
        "negative_reasons": reject_reasons[:5],
        "review_reasons": review_reasons[:5],
        "suggestions": suggestions[:5],
        "warnings": warnings[:5],
        "inconsistencies": inconsistencies[:5],
        "field_feedback": field_feedback,
        "manual_review": manual_review,
        "hard_reject": hard_reject,
    }
