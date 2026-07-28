from __future__ import annotations

from typing import Any


STUDENT_INCOME_SOURCES = {"Internship", "Freelancing", "Part-time"}
INCONSISTENCY_WARNING = "⚠ Additional verification required due to inconsistent financial information."


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _clean_yes_no(value: Any) -> str:
    return "Yes" if _clean_text(value).lower() == "yes" else "No"


def _clean_float(value: Any) -> float:
    text = _clean_text(value)
    if not text:
        return 0.0
    return float(text)


def validate_employment_profile(data: dict[str, Any], employment_status: str) -> dict[str, Any]:
    profile = {
        "student_earning": "",
        "income_source": "",
        "parent_guardian_income": 0.0,
        "sponsor_available": "",
        "source_of_income": "",
        "savings_amount": 0.0,
        "co_applicant_available": "",
        "company_name": "",
        "work_experience": 0.0,
        "business_type": "",
        "years_in_business": 0.0,
    }

    if employment_status == "student":
        student_earning = _clean_yes_no(data.get("student_earning"))
        if not _clean_text(data.get("student_earning")):
            raise ValueError("Please specify whether the student applicant is earning.")
        profile["student_earning"] = student_earning

        if student_earning == "Yes":
            income_source = _clean_text(data.get("income_source"))
            if income_source not in STUDENT_INCOME_SOURCES:
                raise ValueError("Please choose a valid student income source.")
            profile["income_source"] = income_source
            return profile

        parent_guardian_income = _clean_float(data.get("parent_guardian_income"))
        if parent_guardian_income <= 0:
            raise ValueError("Please enter parent or guardian income for a non-earning student.")
        if not _clean_text(data.get("sponsor_available")):
            raise ValueError("Please specify whether a sponsor is available.")
        profile["parent_guardian_income"] = parent_guardian_income
        profile["sponsor_available"] = _clean_yes_no(data.get("sponsor_available"))
        return profile

    if employment_status == "unemployed":
        source_of_income = _clean_text(data.get("source_of_income"))
        if not source_of_income:
            raise ValueError("Please enter the source of income for an unemployed applicant.")
        if not _clean_text(data.get("co_applicant_available")):
            raise ValueError("Please specify whether a co-applicant is available.")
        savings_amount = _clean_float(data.get("savings_amount"))
        if savings_amount < 0:
            raise ValueError("Savings amount cannot be negative.")
        profile["source_of_income"] = source_of_income
        profile["savings_amount"] = savings_amount
        profile["co_applicant_available"] = _clean_yes_no(data.get("co_applicant_available"))
        return profile

    if employment_status == "salaried":
        company_name = _clean_text(data.get("company_name"))
        work_experience = _clean_float(data.get("work_experience"))
        if not company_name:
            raise ValueError("Please enter the company name for salaried applicants.")
        if work_experience < 0:
            raise ValueError("Work experience cannot be negative.")
        profile["company_name"] = company_name
        profile["work_experience"] = work_experience
        return profile

    if employment_status in {"business", "self-employed"}:
        business_type = _clean_text(data.get("business_type"))
        years_in_business = _clean_float(data.get("years_in_business"))
        if not business_type:
            raise ValueError("Please enter the business type for self-employed applicants.")
        if years_in_business < 0:
            raise ValueError("Years in business cannot be negative.")
        profile["business_type"] = business_type
        profile["years_in_business"] = years_in_business

    return profile


def evaluate_underwriting_rules(
    application: dict[str, Any],
    features: dict[str, Any],
    ml_probability: float,
) -> dict[str, Any]:
    employment_status = str(application.get("employment_status", ""))
    profile = application.get("employment_profile", {})
    reported_income = float(application.get("reported_income") or 0)
    income_was_derived = bool(application.get("income_was_derived"))
    income = float(features["income"])
    loan_amount = float(features["loan_amount"])
    existing_loans = float(features["existing_loans"])
    monthly_emi = float(features["monthly_emi"])
    dti_ratio = float(features["dti_ratio"])
    emi_to_income_ratio = float(features["emi_to_income_ratio"])
    credit_score = int(features["credit_score"])

    penalties = []
    positive_reasons = []
    review_reasons = []
    reject_reasons = []
    suggestions = []
    warnings = []
    inconsistencies = []
    manual_review = False
    hard_reject = False

    if credit_score >= 730:
        positive_reasons.append("Strong credit score")
    if dti_ratio <= 0.35:
        positive_reasons.append("Healthy debt-to-income ratio")
    if emi_to_income_ratio <= 0.3:
        positive_reasons.append("Projected EMI is manageable compared with income")
    if existing_loans <= income * 0.2:
        positive_reasons.append("Existing liabilities are well controlled")

    if emi_to_income_ratio > 0.5:
        hard_reject = True
        reject_reasons.append("EMI to income ratio is above 50%")
        suggestions.append("Reduce the loan amount or increase tenure until EMI falls below 50% of income.")

    if monthly_emi + existing_loans > income * 0.85:
        hard_reject = True
        reject_reasons.append("Income is insufficient for the requested loan after existing obligations")
        suggestions.append("Reduce existing liabilities or request a smaller loan amount.")

    if existing_loans > income * 0.65:
        penalties.append(("Existing liabilities are already high", 12))
        suggestions.append("Lower ongoing EMIs before taking on a new loan.")

    if dti_ratio > 0.45:
        penalties.append(("Debt-to-income ratio is above the preferred underwriting band", 10))
        suggestions.append("Bring total monthly obligations below 45% of income for a cleaner approval profile.")

    if employment_status == "student":
        if profile.get("student_earning") == "No":
            penalties.append(("Student applicant depends on external financial support", 8))
            if profile.get("sponsor_available") == "No":
                penalties.append(("Student applicant does not have a sponsor", 18))
                review_reasons.append("Student profile without sponsor support needs manual assessment")
                suggestions.append("Add a sponsor or co-borrower with stable income.")
                manual_review = True
            else:
                parent_income = float(profile.get("parent_guardian_income") or 0)
                if parent_income < income * 1.5:
                    penalties.append(("Declared sponsor income provides limited repayment buffer", 6))
                    suggestions.append("Provide stronger sponsor income proof or reduce the requested amount.")
        elif profile.get("income_source") in STUDENT_INCOME_SOURCES:
            positive_reasons.append(f"Student income source is declared as {profile['income_source']}")

        if profile.get("student_earning") == "No" and reported_income > 0 and not income_was_derived:
            inconsistencies.append("Student marked as not earning but applicant income is declared.")

    if employment_status == "unemployed":
        if income >= 80000:
            inconsistencies.append("Unemployed applicant declared unusually high monthly income.")
            review_reasons.append("Unemployed profile with very high income requires manual review")
            manual_review = True

        if profile.get("co_applicant_available") == "No":
            penalties.append(("No co-applicant support is available for the unemployed profile", 15))
            suggestions.append("Add a co-applicant or wait until stable income is established.")

        savings_amount = float(profile.get("savings_amount") or 0)
        if savings_amount < loan_amount * 0.1:
            penalties.append(("Savings buffer is low relative to the requested loan", 8))
            suggestions.append("Build a stronger savings reserve before reapplying.")

        if monthly_emi > max(savings_amount / 24, 1):
            penalties.append(("Savings alone do not comfortably cover the projected EMI", 6))

    if employment_status == "salaried":
        if float(profile.get("work_experience") or 0) < 1:
            penalties.append(("Work experience is below one year", 7))
            suggestions.append("A longer track record at the current employer can strengthen approval odds.")

        if profile.get("company_name"):
            positive_reasons.append("Employer information is available for verification")

    if employment_status in {"business", "self-employed"}:
        if float(profile.get("years_in_business") or 0) < 2:
            penalties.append(("Business operating history is below two years", 8))
            suggestions.append("More business seasoning and income proof can improve lender confidence.")

        if profile.get("business_type"):
            positive_reasons.append("Business profile details are available for underwriting")

    if inconsistencies:
        warnings.append(INCONSISTENCY_WARNING)
        manual_review = True
        penalties.append(("Application contains inconsistent employment or income information", 14))

    total_penalty = sum(points for _, points in penalties)
    probability_adjustment = total_penalty / 100
    adjusted_probability = max(0.01, min(0.99, ml_probability - probability_adjustment))

    if hard_reject:
        final_status = "Rejected"
    elif manual_review:
        final_status = "Risky"
    elif adjusted_probability >= 0.7 and dti_ratio <= 0.45:
        final_status = "Approved"
    elif adjusted_probability >= 0.45:
        final_status = "Risky"
    else:
        final_status = "Rejected"

    if final_status == "Approved" and not positive_reasons:
        positive_reasons.append("Profile satisfies the affordability and policy checks")
    if final_status != "Approved" and not reject_reasons and review_reasons:
        reject_reasons.extend(review_reasons)
    if final_status != "Approved" and not reject_reasons:
        reject_reasons.extend([reason for reason, _ in penalties[:3]])

    return {
        "adjusted_probability": adjusted_probability,
        "penalty_points": total_penalty,
        "risk_penalty_points": min(30, round(total_penalty * 0.9)),
        "positive_reasons": list(dict.fromkeys(positive_reasons))[:4],
        "negative_reasons": list(dict.fromkeys(reject_reasons))[:4],
        "review_reasons": list(dict.fromkeys(review_reasons))[:4],
        "suggestions": list(dict.fromkeys(suggestions))[:4],
        "warnings": list(dict.fromkeys(warnings)),
        "inconsistencies": list(dict.fromkeys(inconsistencies)),
        "manual_review": manual_review,
        "hard_reject": hard_reject,
        "final_status": final_status,
    }
