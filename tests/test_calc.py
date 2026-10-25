import pytest

import calc


def test_readme_flat_rate_example_is_about_47_percent():
    # ₹1 lakh, 24 months, 1.5% a month flat, 2% fee, ₹5,000 deducted insurance.
    loan = calc.loan_cost(
        principal=100_000,
        tenure_months=24,
        quoted_rate_percent=1.5,
        rate_period="month",
        rate_type="flat",
        processing_fee_percent=2,
        insurance_premium=5_000,
    )
    assert loan["cash_in_hand"] == 93_000
    assert loan["emi"] == 5_667
    assert loan["quoted_annual_percent"] == 18
    assert loan["real_annual_percent"] == pytest.approx(47.5, abs=0.5)


def test_reducing_rate_without_fees_matches_quoted_rate():
    loan = calc.loan_cost(
        principal=100_000,
        tenure_months=12,
        quoted_rate_percent=12,
        rate_period="year",
        rate_type="reducing",
    )
    # 12% a year compounded monthly is an effective 12.68% a year.
    assert loan["real_annual_percent"] == pytest.approx(12.7, abs=0.1)
    assert loan["cash_in_hand"] == loan["loan_amount"] == 100_000


def test_quoted_emi_wins_when_rate_does_not_match():
    loan = calc.loan_cost(
        principal=100_000,
        tenure_months=12,
        quoted_rate_percent=10,
        rate_period="year",
        rate_type="reducing",
        emi_quoted=9_500,
    )
    assert loan["method"] == "quoted_emi"
    assert loan["emi"] == 9_500


def test_financed_insurance_raises_the_loan_not_the_cash_cut():
    loan = calc.loan_cost(
        principal=100_000,
        tenure_months=12,
        quoted_rate_percent=12,
        rate_period="year",
        rate_type="reducing",
        insurance_premium=5_000,
        insurance_financed=True,
    )
    assert loan["loan_amount"] == 105_000
    assert loan["cash_in_hand"] == 100_000


@pytest.mark.parametrize(
    "kwargs",
    [
        {"principal": None, "tenure_months": 12},
        {"principal": 100_000, "tenure_months": None},
        {"principal": 100_000, "tenure_months": 12},  # no rate and no EMI
    ],
)
def test_loan_cost_returns_none_without_enough_terms(kwargs):
    assert calc.loan_cost(**kwargs) is None


def test_insurance_return_is_below_fd_for_typical_endowment_pitch():
    # ₹50,000 a year for 10 years, ₹6 lakh at maturity.
    ins = calc.insurance_return(
        annual_premium=50_000,
        premium_paying_years=10,
        maturity_amount=600_000,
        policy_years=15,
    )
    assert ins["total_premiums"] == 500_000
    assert 0 < ins["real_annual_percent"] < ins["fd_benchmark_percent"]


def test_insurance_return_needs_all_core_terms():
    assert calc.insurance_return(None, 10, 600_000) is None
    assert calc.insurance_return(50_000, None, 600_000) is None
    assert calc.insurance_return(50_000, 10, None) is None
