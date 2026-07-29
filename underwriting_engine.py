"""
underwriting_engine.py
======================
SmartLoan AI — Underwriting Engine v3

Three integrated sub-engines:

  1. Consistency Engine  — detects impossible / suspicious combinations
  2. Financial Engine    — computes 7 financial ratios + affordability score
  3. Risk Scoring Engine — combines ML prediction + all rule signals into
                           one of: Low Risk | Medium Risk | High Risk |
                           Manual Review | Reject
"""
from __future__ import annotations

from typing import Any

# ── Constants ─────────────────────────────────────────────────────────────────
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

# Minimum working age assumed for experience calculation
MIN_WORKING_AGE = 18
# Maximum realistic work-experience start age (some professional degrees)
MIN_PROFESSIONAL_START_AGE = 22

SALARY_BANDS = [
    # Age 20-22: Expected ₹8k-35k | Warning ₹35k-40k | Manual Review ₹40k-60k | Reject above ₹60k
    {"min_age": 20, "max_age": 22, "normal_min": 8000,  "normal_max": 35000,
     "warning_above": 35000,  "review_above": 40000,  "reject_above": 60000},
    # Age 23-25: Expected ₹15k-60k | Warning ₹60k-70k | Manual Review ₹70k-90k | Reject above ₹90k
    {"min_age": 23, "max_age": 25, "normal_min": 15000, "normal_max": 60000,
     "warning_above": 60000,  "review_above": 70000,  "reject_above": 90000},
    # Age 26-30: Expected ₹20k-120k | Warning ₹120k-140k | Manual Review ₹140k-180k | Reject above ₹180k
    {"min_age": 26, "max_age": 30, "normal_min": 20000, "normal_max": 120000,
     "warning_above": 120000, "review_above": 140000, "reject_above": 180000},
    # Age 31-40: Expected ₹25k-250k | Warning ₹250k-280k | Manual Review ₹280k-350k | Reject above ₹350k
    {"min_age": 31, "max_age": 40, "normal_min": 25000, "normal_max": 250000,
     "warning_above": 250000, "review_above": 280000, "reject_above": 350000},
    # Age 41-55: Expected ₹25k-400k | Warning ₹400k-450k | Manual Review ₹450k-550k | Reject above ₹550k
    {"min_age": 41, "max_age": 55, "normal_min": 25000, "normal_max": 400000,
     "warning_above": 400000, "review_above": 450000, "reject_above": 550000},
]


# ── Helpers ───────────────────────────────────────────────────────────────────
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


def add(items: list[str], message: str) -> None:
    if message and message not in items:
        items.append(message)


# ── Employment Profile Validator ──────────────────────────────────────────────
def validate_employment_profile(data: dict[str, Any], employment_status: str) -> dict[str, Any]:
    status = normalize_employment_status(employment_status)
    profile: dict[str, Any] = {
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


# ── Salary Assessment ─────────────────────────────────────────────────────────
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


# ── Business Assessment ───────────────────────────────────────────────────────
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


# ═══════════════════════════════════════════════════════════════════════════════
# PART 1 — CONSISTENCY ENGINE
# Detects impossible or highly suspicious combinations across age, employment,
# income, experience, business age, loan amount and declared fields.
# Returns a list of ConsistencyFlag dicts: {level, message, points}
# ═══════════════════════════════════════════════════════════════════════════════
def _consistency_engine(
    age: int,
    income: float,
    loan_amount: float,
    monthly_emi: float,
    employment_status: str,
    profile: dict[str, Any],
    credit_score: int,
    existing_loans: float,
) -> list[dict[str, Any]]:
    """
    Returns a list of flags.
    Each flag: {"level": "impossible"|"review"|"warning", "message": str, "points": int}
    """
    flags: list[dict[str, Any]] = []

    def flag(level: str, message: str, points: int) -> None:
        flags.append({"level": level, "message": message, "points": points})

    # ── 1. Salaried consistency ───────────────────────────────────────────────
    if employment_status == "salaried":
        work_exp = float(profile.get("work_experience") or 0)
        max_possible_exp = max(age - MIN_WORKING_AGE, 0)

        # Completely impossible: more experience than possible working years
        if work_exp > max_possible_exp:
            flag("impossible",
                 f"Work experience ({int(work_exp)}y) is impossible for age {age}. "
                 f"Maximum possible is {int(max_possible_exp)}y.",
                 35)

        # Suspicious: started working before age 16
        elif work_exp > 0 and (age - work_exp) < 16:
            flag("review",
                 f"Work experience implies employment started at age {int(age - work_exp)}, "
                 "which is unusually early.",
                 18)

        # Very fresh graduate with very high salary
        elif work_exp < 1 and income > 80000:
            flag("review",
                 "High income declared with less than 1 year of work experience.",
                 12)

    # ── 2. Business consistency ───────────────────────────────────────────────
    elif employment_status == "business":
        biz_age = float(profile.get("business_age_years") or 0)
        biz_start_age = age - biz_age

        # Business started before owner was 16
        if biz_age > 0 and biz_start_age < 16:
            flag("impossible",
                 f"Business age ({biz_age:.1f}y) implies it was started at age {biz_start_age:.0f}, "
                 "which is impossible.",
                 35)

        # Brand-new startup claiming very high income
        elif biz_age < 0.5 and income > 200000:
            flag("review",
                 f"Business is less than 6 months old but declares ₹{int(income):,}/mo income. "
                 "Requires verification.",
                 20)

        # Young business with high income relative to maturity
        elif biz_age < 1 and income > 100000:
            flag("review",
                 f"Business age under 1 year with ₹{int(income):,}/mo income. "
                 "Income requires supporting documents.",
                 14)

        # Business older than owner's working life
        elif biz_age > 0 and biz_start_age < 18:
            flag("review",
                 f"Business reportedly started at age {biz_start_age:.0f}. "
                 "Ownership history requires verification.",
                 14)

    # ── 3. Student consistency ────────────────────────────────────────────────
    elif employment_status == "student":
        student_earning = profile.get("student_earning")

        if student_earning == "Yes":
            income_source = profile.get("income_source", "")

            # Internship > ₹60k/mo is very unusual
            if income_source == "Internship" and income > 60000:
                flag("review",
                     f"Internship income of ₹{int(income):,}/mo is unusually high. Verification needed.",
                     20)

            # Freelancing student with very high income
            elif income_source == "Freelancing" and income > 80000:
                flag("review",
                     f"Student freelancing income of ₹{int(income):,}/mo requires proof.",
                     16)

            # Part-time student income limit
            elif income_source == "Part-time" and income > 30000:
                flag("review",
                     f"Part-time student income of ₹{int(income):,}/mo is above typical range.",
                     12)

            # Any student income above ₹2L/mo — hard review
            if income > 200000:
                flag("review",
                     f"Student income of ₹{int(income):,}/mo is extremely high regardless of source.",
                     28)

        # Student applying for a home loan
        if profile.get("education_loan") == "Yes" and loan_amount > 5000000:
            flag("review",
                 "Student with existing education loan requesting high loan amount. "
                 "Debt burden review required.",
                 18)

    # ── 4. Unemployed consistency ─────────────────────────────────────────────
    elif employment_status == "unemployed":
        source = clean_text(profile.get("source_of_income"))
        savings = float(profile.get("savings_amount") or 0)
        investments = float(profile.get("investments_amount") or 0)
        rental = float(profile.get("rental_income") or 0)
        liquid = savings + investments

        # High income with vague or no declared source
        if income >= 80000 and not source:
            flag("review",
                 f"Unemployed applicant declared ₹{int(income):,}/mo income with no source. "
                 "Source must be verified.",
                 25)

        elif income >= 50000 and source.lower() in {"", "none", "nil"}:
            flag("review",
                 "Significant income declared with insufficient source explanation.",
                 18)

        # Declared very high income with no matching assets
        if income >= 100000 and liquid < 50000 and rental < monthly_emi:
            flag("review",
                 "High income declared but no supporting savings, investments, or rental income.",
                 22)

        # Virtually no financial base applying for a large loan
        if liquid == 0 and rental == 0 and income < monthly_emi:
            flag("impossible",
                 "No savings, no investments, no rental income, and income below projected EMI. "
                 "Loan is unaffordable.",
                 40)

        # Income far exceeds what unemployed status should permit
        if income >= 300000:
            flag("review",
                 f"Declared income of ₹{int(income):,}/mo for an unemployed applicant "
                 "requires full documentation.",
                 30)

    # ── 5. Cross-category consistency checks (all statuses) ───────────────────

    # Age vs credit score — very young with very high credit score
    if age <= 22 and credit_score >= 780:
        flag("review",
             f"Credit score {credit_score} at age {age} is unusually high. "
             "Credit history will require verification.",
             12)

    # Existing loan obligations exceeding income entirely
    if existing_loans >= income and income > 0:
        flag("impossible",
             f"Existing loan EMIs (₹{int(existing_loans):,}) equal or exceed monthly income "
             f"(₹{int(income):,}). No repayment capacity remains.",
             35)

    # Requested loan > 40× monthly income (extreme)
    if income > 0 and loan_amount > income * 40:
        flag("impossible",
             f"Loan amount (₹{int(loan_amount):,}) is over 40× monthly income "
             f"(₹{int(income):,}). Affordability is clearly impossible.",
             40)

    # Loan > 20× income — high but not impossible
    elif income > 0 and loan_amount > income * 20:
        flag("review",
             f"Loan amount (₹{int(loan_amount):,}) is more than 20× monthly income. "
             "Detailed affordability assessment required.",
             20)

    # EMI already covers more than full income
    if income > 0 and monthly_emi >= income:
        flag("impossible",
             f"Projected EMI (₹{int(monthly_emi):,}) equals or exceeds monthly income "
             f"(₹{int(income):,}). Loan cannot be serviced.",
             40)

    # EMI more than 60% of income — unsustainable
    elif income > 0 and monthly_emi > income * 0.6:
        flag("review",
             f"Projected EMI (₹{int(monthly_emi):,}) is {int(monthly_emi / income * 100)}% "
             "of income. Sustainable repayment is at serious risk.",
             22)

    # Student applying for an amount that dwarfs any reasonable income projection
    if employment_status == "student" and loan_amount > 10000000:
        flag("review",
             "Student applicant requesting loan above ₹1 Crore. "
             "Exceptional review required.",
             25)

    # Credit score too low to be plausible
    if credit_score < 300:
        flag("review",
             f"Credit score {credit_score} is abnormally low. Data accuracy check required.",
             18)

    # Perfect credit score with very high risk indicators
    if credit_score >= 850 and income == 0:
        flag("review",
             "Excellent credit score but zero income declared. Inconsistency requires review.",
             15)

    return flags


# ═══════════════════════════════════════════════════════════════════════════════
# PART 2 — FINANCIAL ENGINE
# Computes 7 financial ratios + affordability score.
# ═══════════════════════════════════════════════════════════════════════════════
def calculate_financial_ratios(
    features: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, float]:
    """
    Returns:
        debt_to_income       — (existing_loans + emi) / income
        loan_to_income       — loan_amount / income
        disposable_income    — income - existing_loans - emi  (₹/mo)
        emi_ratio            — emi / income
        savings_ratio        — liquid_assets / loan_amount
        existing_loan_ratio  — existing_loans / income
        affordability_score  — 0–100, higher = more affordable
    """
    income = max(float(features.get("income") or 0), 1)
    loan_amount = float(features.get("loan_amount") or 0)
    existing_loans = float(features.get("existing_loans") or 0)
    monthly_emi = float(features.get("monthly_emi") or 0)

    savings = float(profile.get("savings_amount") or 0)
    investments = float(profile.get("investments_amount") or 0)
    rental_income = float(profile.get("rental_income") or 0)
    emergency_fund = float(profile.get("emergency_fund") or 0)
    liquid_assets = savings + investments + emergency_fund

    # Effective income for unemployed / rental scenarios
    effective_income = max(income + rental_income, 1)

    disposable_income = effective_income - existing_loans - monthly_emi

    debt_to_income = round((existing_loans + monthly_emi) / effective_income, 4)
    loan_to_income = round(loan_amount / effective_income, 4)
    emi_ratio = round(monthly_emi / effective_income, 4)
    savings_ratio = round(liquid_assets / max(loan_amount, 1), 4)
    existing_loan_ratio = round(existing_loans / effective_income, 4)

    # ── Affordability Score (0–100) ───────────────────────────────────────────
    # Combines DTI, EMI ratio, disposable income adequacy, savings coverage.
    # Higher = more affordable (100 = perfectly affordable).
    score = 100.0

    # Penalise DTI
    if debt_to_income > 0.65:
        score -= 40
    elif debt_to_income > 0.50:
        score -= 25
    elif debt_to_income > 0.35:
        score -= 10

    # Penalise EMI ratio
    if emi_ratio > 0.50:
        score -= 35
    elif emi_ratio > 0.40:
        score -= 20
    elif emi_ratio > 0.30:
        score -= 8

    # Negative disposable income
    if disposable_income < 0:
        score -= 30
    elif disposable_income < monthly_emi:
        score -= 10

    # Savings coverage
    if savings_ratio >= 0.50:
        score += 10  # bonus: strong asset backing
    elif savings_ratio < 0.05:
        score -= 10

    # Loan-to-income
    if loan_to_income > 24:
        score -= 25
    elif loan_to_income > 12:
        score -= 10

    affordability_score = round(max(0.0, min(100.0, score)), 1)

    return {
        "debt_to_income": debt_to_income,
        "loan_to_income": loan_to_income,
        "disposable_income": round(disposable_income, 2),
        "emi_ratio": emi_ratio,
        "savings_ratio": savings_ratio,
        "existing_loan_ratio": existing_loan_ratio,
        "affordability_score": affordability_score,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# PART 3 — MAIN EVALUATE FUNCTION
# Combines ML + Business Rules + Financial Ratios + Consistency + Stability
# ═══════════════════════════════════════════════════════════════════════════════
def evaluate(application: dict[str, Any]) -> dict[str, Any]:
    features = application["features"]
    ml_probability = float(application.get("ml_probability", 0))
    age = int(application["age"])
    validate_age(age)

    employment_status = normalize_employment_status(application["employment_status"])
    profile = application.get("employment_profile", {})

    income = float(features.get("income") or 0)
    loan_amount = float(features.get("loan_amount") or 0)
    existing_loans = float(features.get("existing_loans") or 0)
    monthly_emi = float(features.get("monthly_emi") or 0)
    credit_score = int(features.get("credit_score") or 0)

    ratios = calculate_financial_ratios(features, profile)

    # Accumulator lists
    positive_reasons: list[str] = []
    risk_factors: list[str] = []
    reject_reasons: list[str] = []
    review_reasons: list[str] = []
    warnings: list[str] = []
    inconsistencies: list[str] = []
    suggestions: list[str] = []
    field_feedback: dict[str, dict[str, str]] = {}

    rule_points = 0          # from business rules
    consistency_points = 0   # from consistency engine
    stability_points = 0     # from employment stability
    financial_points = 0     # from financial engine ratios
    hard_reject = False
    manual_review = False

    # ─────────────────────────────────────────────────────────────────────────
    # CONSISTENCY ENGINE — run first so flags can influence later logic
    # ─────────────────────────────────────────────────────────────────────────
    c_flags = _consistency_engine(
        age=age,
        income=income,
        loan_amount=loan_amount,
        monthly_emi=monthly_emi,
        employment_status=employment_status,
        profile=profile,
        credit_score=credit_score,
        existing_loans=existing_loans,
    )

    for flag_item in c_flags:
        add(inconsistencies, flag_item["message"])
        consistency_points += flag_item["points"]
        if flag_item["level"] == "impossible":
            hard_reject = True
            add(reject_reasons, flag_item["message"])
        else:
            manual_review = True
            add(review_reasons, f"Consistency flag: {flag_item['message']}")

    if inconsistencies:
        add(warnings, CONSISTENCY_WARNING)

    # ─────────────────────────────────────────────────────────────────────────
    # FINANCIAL ENGINE — evaluate all financial ratios
    # ─────────────────────────────────────────────────────────────────────────
    dti = ratios["debt_to_income"]
    emi_ratio = ratios["emi_ratio"]
    disp_income = ratios["disposable_income"]
    lti = ratios["loan_to_income"]
    savings_ratio = ratios["savings_ratio"]
    affordability = ratios["affordability_score"]

    # Debt-to-income
    if dti <= 0.35:
        add(positive_reasons, f"Healthy debt-to-income ratio ({dti:.0%})")
    elif dti > 0.65:
        add(reject_reasons, "Existing liabilities too high relative to income")
        financial_points += 28
    elif dti > 0.50:
        add(risk_factors, "Debt-to-income ratio above recommended 50%")
        financial_points += 18
    elif dti > 0.45:
        add(risk_factors, "Debt-to-income ratio is above preferred limits")
        financial_points += 12

    # EMI ratio
    if emi_ratio > 0.50:
        hard_reject = True
        add(reject_reasons, "EMI exceeds 50% of income — not affordable")
        add(suggestions, "Reduce the loan amount or increase tenure until EMI is below 50% of income.")
        financial_points += 35
    elif emi_ratio > 0.40:
        add(risk_factors, "EMI consumes over 40% of income")
        add(suggestions, "Consider a longer tenure to reduce monthly EMI burden.")
        financial_points += 16
    elif emi_ratio <= 0.30:
        add(positive_reasons, "EMI is comfortably within 30% of income")
    else:
        add(risk_factors, "Projected EMI reduces repayment buffer")
        financial_points += 8

    # Disposable income
    if disp_income < 0:
        hard_reject = True
        add(reject_reasons, "Income insufficient after existing obligations")
        financial_points += 30
    elif disp_income < monthly_emi * 0.5:
        add(risk_factors, "Very little disposable income left after EMI")
        add(suggestions, "Reduce existing loan obligations before applying.")
        financial_points += 14
    elif disp_income >= income * 0.5:
        add(positive_reasons, "Good disposable income after loan obligations")

    # Loan-to-income
    if lti > 24:
        hard_reject = True
        add(reject_reasons, "Loan amount is unrealistic relative to income")
        financial_points += 30
    elif lti > 12:
        add(risk_factors, "High loan-to-income ratio")
        financial_points += 14
    elif lti <= 6:
        add(positive_reasons, "Loan amount is well within income capacity")

    # Savings ratio
    if savings_ratio >= 0.50:
        add(positive_reasons, "Strong asset base relative to loan amount")
    elif savings_ratio >= 0.20:
        add(positive_reasons, "Adequate savings coverage")
    elif savings_ratio < 0.05 and employment_status in {"unemployed", "student"}:
        add(risk_factors, "Minimal savings relative to loan request")
        add(suggestions, "Build savings before applying for this loan size.")
        financial_points += 10

    # Affordability score feedback
    field_feedback["affordability"] = {
        "level": (
            "normal" if affordability >= 70
            else "warning" if affordability >= 45
            else "manual_review"
        ),
        "message": f"Affordability score: {affordability}/100",
    }

    # Existing loan ratio
    existing_loan_ratio = ratios["existing_loan_ratio"]
    if existing_loan_ratio > 0.40:
        add(risk_factors, "High existing loan burden relative to income")
        financial_points += 10
    elif existing_loan_ratio == 0:
        add(positive_reasons, "No existing loan obligations")

    # Credit score
    if credit_score >= 750:
        add(positive_reasons, "Excellent credit score")
    elif credit_score >= 700:
        add(positive_reasons, "Good credit history")
    elif credit_score < 620:
        add(risk_factors, "Poor credit score")
        financial_points += 18
    elif credit_score < 650:
        add(risk_factors, "Below-average credit score")
        financial_points += 10

    # ─────────────────────────────────────────────────────────────────────────
    # EMPLOYMENT STABILITY + BUSINESS RULES per employment type
    # ─────────────────────────────────────────────────────────────────────────
    if employment_status == "salaried":
        salary = salary_assessment(age, income)
        field_feedback["income"] = {"level": salary["level"], "message": salary["message"]}
        rule_points += salary["points"]
        if salary["level"] == "reject":
            hard_reject = True
            add(reject_reasons, "Income not realistic for age")
        elif salary["level"] == "manual_review":
            manual_review = True
            add(review_reasons, "Income inconsistent with age band")
        elif salary["level"] == "warning":
            add(warnings, salary["message"])
            add(risk_factors, "Age-income mismatch detected")
        else:
            add(positive_reasons, "Income is appropriate for age")

        work_experience = float(profile.get("work_experience") or 0)
        # Stability scoring
        if work_experience >= 5:
            add(positive_reasons, "Stable long-term employment")
            stability_points -= 5   # reduces overall risk
        elif work_experience >= 2:
            add(positive_reasons, "Adequate work experience")
        elif work_experience >= 1:
            add(risk_factors, "Limited work experience")
            stability_points += 6
        else:
            add(risk_factors, "Very short employment duration")
            stability_points += 12

    elif employment_status == "business":
        business = business_assessment(age, income, profile)
        field_feedback["income"] = {"level": business["level"], "message": business["message"]}
        field_feedback["business_age_years"] = {
            "level": "normal" if not business["inconsistent"] else "manual_review",
            "message": f"Business maturity: {business['maturity']}.",
        }
        rule_points += business["points"]

        if business["level"] == "manual_review":
            manual_review = True
            add(review_reasons, "Business income unusually high for declared business age")
        elif business["level"] == "warning":
            add(warnings, business["message"])
            add(risk_factors, "Business income needs supporting documents")
        else:
            add(positive_reasons, "Business income aligned with business maturity")

        if business["inconsistent"]:
            # Consistency engine already flagged this — avoid double-counting
            pass

        # Ownership type stability
        ownership = clean_text(profile.get("ownership_type"))
        if ownership in {"Private Limited", "LLP"}:
            add(positive_reasons, f"Formal business structure ({ownership})")
            stability_points -= 4
        elif ownership == "Startup":
            add(risk_factors, "Startup ownership carries higher income volatility")
            stability_points += 8
        elif ownership == "Inherited":
            add(positive_reasons, "Inherited business provides established revenue base")
            stability_points -= 3

        # Business age stability tier
        biz_age = float(profile.get("business_age_years") or 0)
        if biz_age >= 10:
            add(positive_reasons, "Excellent business tenure (10+ years)")
            stability_points -= 6
        elif biz_age >= 5:
            add(positive_reasons, "Strong business tenure (5–10 years)")
            stability_points -= 3
        elif biz_age < 1:
            add(risk_factors, "Business is less than 1 year old — high income volatility")
            stability_points += 14
        elif biz_age < 3:
            add(risk_factors, "Young business — moderate income stability")
            stability_points += 8

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
                add(review_reasons, "Student income requires verification")
            if monthly_stipend > 0:
                add(positive_reasons, f"Student receives a monthly stipend of ₹{int(monthly_stipend):,}")
            field_feedback["income"] = {
                "level": "manual_review" if manual_review else salary["level"],
                "message": "Student income source requires verification." if manual_review else salary["message"],
            }
        else:
            add(risk_factors, "Student depends on external financial support")
            stability_points += 10
            if profile.get("sponsor_available") == "No":
                manual_review = True
                add(review_reasons, "Student profile without sponsor support")
                stability_points += 18
            elif financial_support:
                add(positive_reasons, f"Financial support: {financial_support}")

        if has_scholarship:
            add(positive_reasons, "Scholarship reduces financial dependency")
            rule_points = max(0, rule_points - 6)
        if has_education_loan:
            add(risk_factors, "Existing education loan increases debt burden")
            rule_points += 8

        if loan_amount >= 4000000 and income <= 10000:
            hard_reject = True
            add(reject_reasons, "Student loan amount is not affordable for declared income")
            rule_points += 35

        stability_points += 8   # students are inherently lower stability

    elif employment_status == "unemployed":
        savings = float(profile.get("savings_amount") or 0)
        investments = float(profile.get("investments_amount") or 0)
        rental_income = float(profile.get("rental_income") or 0)
        emergency_fund = float(profile.get("emergency_fund") or 0)
        liquid_assets = savings + investments
        has_co_applicant = profile.get("co_applicant_available") == "Yes"
        has_sponsor = profile.get("sponsor_available") == "Yes"
        support_available = has_co_applicant or has_sponsor

        # Rental income — strong positive
        if rental_income >= monthly_emi:
            add(positive_reasons, f"Rental income (₹{int(rental_income):,}/mo) covers projected EMI")
            stability_points -= 8
        elif rental_income > 0:
            add(positive_reasons, f"Rental income (₹{int(rental_income):,}/mo) provides partial support")
            stability_points -= 4

        # Emergency fund
        if emergency_fund >= monthly_emi * 6:
            add(positive_reasons, "Emergency fund covers 6+ months of EMI")
            stability_points -= 5
        elif emergency_fund > 0:
            add(positive_reasons, "Emergency fund provides a buffer")

        # Liquid assets vs loan
        if liquid_assets < max(loan_amount * 0.10, monthly_emi * 6):
            add(risk_factors, "Savings are insufficient for the requested loan exposure")
            add(suggestions, "Build savings or add a co-applicant with income.")
            stability_points += 16
        elif liquid_assets >= loan_amount * 0.40:
            add(positive_reasons, "Strong savings and investments relative to loan amount")

        # Support network
        if has_co_applicant:
            add(positive_reasons, "Co-applicant strengthens repayment capacity")
            stability_points -= 5
        elif has_sponsor:
            add(positive_reasons, "Sponsor support improves creditworthiness")
            stability_points -= 3
        else:
            add(risk_factors, "No co-applicant or sponsor support")
            stability_points += 14

        stability_points += 10  # baseline: unemployed = lower stability

    # ─────────────────────────────────────────────────────────────────────────
    # FINAL RISK SCORE CALCULATION
    # Combines: ML probability + business rules + financial + consistency +
    #           employment stability.
    #
    # Formula:
    #   base_risk  = (1 - ml_probability) × 40      [0-40]
    #   rule_risk  = rule_points                     [0-N]
    #   fin_risk   = financial_points                [0-N]
    #   cons_risk  = consistency_points              [0-N]
    #   stab_risk  = max(0, stability_points)        [0-N]
    #   raw_score  = base + rule + fin + cons + stab
    #   risk_score = clamp(raw_score, 0, 100)
    #
    # Adjusted probability is ML prediction tempered by rule violations.
    # ─────────────────────────────────────────────────────────────────────────
    stability_points = max(0, stability_points)  # floor at 0 (bonuses only reduce below)
    total_penalty = rule_points + financial_points + consistency_points + stability_points
    base_risk = (1 - ml_probability) * 40
    raw_score = base_risk + total_penalty
    risk_score = int(min(100, max(0, round(raw_score))))

    # Temper the ML probability by the total penalty load
    adjusted_probability = max(0.01, min(0.99, ml_probability - (total_penalty / 130)))

    # ─────────────────────────────────────────────────────────────────────────
    # DECISION TREE
    # Priority: hard_reject > manual_review > score-based
    # ─────────────────────────────────────────────────────────────────────────
    if hard_reject:
        final_status = "Reject"
        risk_category = "High Risk"

    elif manual_review or consistency_points >= 30:
        final_status = "Manual Review"
        risk_category = "Manual Review"
        manual_review = True

    elif risk_score < 30 and adjusted_probability >= 0.70:
        final_status = "Low Risk"
        risk_category = "Low Risk"

    elif risk_score < 55 and adjusted_probability >= 0.48:
        final_status = "Medium Risk"
        risk_category = "Medium Risk"

    elif risk_score >= 80:
        # Very high combined score — escalate to manual review before outright reject
        final_status = "Manual Review"
        risk_category = "Manual Review"
        manual_review = True
        add(review_reasons, "Combined risk score requires underwriter validation")

    else:
        final_status = "High Risk"
        risk_category = "High Risk"

    # Fallback messaging
    if not positive_reasons and final_status in {"Low Risk", "Medium Risk"}:
        add(positive_reasons, "Profile satisfies core affordability checks")
    if final_status == "Reject" and not reject_reasons:
        add(reject_reasons, "High default probability based on combined scoring")
    if final_status == "Manual Review" and not review_reasons:
        add(review_reasons, "Verification required before final decision")

    return {
        "final_status": final_status,
        "risk_category": risk_category,
        "adjusted_probability": adjusted_probability,
        "risk_score": risk_score,
        # Breakdown for transparency
        "rule_points": rule_points,
        "financial_points": financial_points,
        "consistency_points": consistency_points,
        "stability_points": stability_points,
        "financial_ratios": ratios,
        # Narrative outputs
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
