"""Deterministic money math. The LLM extracts numbers; it never computes them."""


def _irr(cash_in: float, payment: float, periods: int) -> float | None:
    """Per-period rate i such that cash_in == payment * annuity(i, periods)."""
    if cash_in <= 0 or payment <= 0 or periods <= 0:
        return None
    if payment * periods <= cash_in:
        return 0.0

    def pv(i: float) -> float:
        return payment * (1 - (1 + i) ** -periods) / i

    lo, hi = 1e-9, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if pv(mid) > cash_in:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _annual_from_monthly(i: float) -> float:
    return ((1 + i) ** 12 - 1) * 100


def loan_cost(
    principal: float | None,
    tenure_months: float | None,
    quoted_rate_percent: float | None = None,
    rate_period: str | None = None,
    rate_type: str | None = None,
    emi_quoted: float | None = None,
    processing_fee: float | None = None,
    processing_fee_percent: float | None = None,
    insurance_premium: float | None = None,
    insurance_financed: bool | None = None,
    other_fees: float | None = None,
    **_,
) -> dict | None:
    if not principal or not tenure_months:
        return None
    n = round(tenure_months)
    P = float(principal)

    fee = float(processing_fee or 0)
    if not fee and processing_fee_percent:
        fee = P * processing_fee_percent / 100
    ins = float(insurance_premium or 0)
    other = float(other_fees or 0)

    # Financed add-ons raise the loan amount; upfront ones cut the cash you get.
    loan_amount = P + (ins if insurance_financed else 0)
    cash_in_hand = P - fee - other - (0 if insurance_financed else ins)

    emi, method = None, None
    if quoted_rate_percent:
        monthly = quoted_rate_percent / 100 / (1 if rate_period == "month" else 12)
        if rate_type == "flat":
            emi = (loan_amount + loan_amount * monthly * n) / n
            method = "flat"
        else:
            emi = (
                loan_amount / n
                if monthly == 0
                else loan_amount * monthly / (1 - (1 + monthly) ** -n)
            )
            method = "reducing"
    if emi_quoted and (emi is None or abs(emi_quoted - emi) / emi > 0.02):
        # Trust the quoted EMI over a rate that doesn't match it.
        emi, method = float(emi_quoted), "quoted_emi"
    if emi is None:
        return None

    i = _irr(cash_in_hand, emi, n)
    total_paid = emi * n
    quoted_annual = None
    if quoted_rate_percent:
        quoted_annual = quoted_rate_percent * (12 if rate_period == "month" else 1)

    return {
        "loan_amount": round(loan_amount),
        "cash_in_hand": round(cash_in_hand),
        "tenure_months": n,
        "emi": round(emi),
        "total_paid": round(total_paid),
        "total_extra": round(total_paid - cash_in_hand),
        "quoted_annual_percent": round(quoted_annual, 2) if quoted_annual else None,
        "real_annual_percent": round(_annual_from_monthly(i), 1)
        if i is not None
        else None,
        "method": method,
    }


def insurance_return(
    annual_premium: float | None,
    premium_paying_years: float | None,
    maturity_amount: float | None,
    policy_years: float | None = None,
    claimed_return_percent: float | None = None,
    **_,
) -> dict | None:
    """Real yearly return of a pay-N-years, get-lump-sum-at-maturity savings policy."""
    if not annual_premium or not premium_paying_years or not maturity_amount:
        return None
    ppt = round(premium_paying_years)
    term = round(policy_years or premium_paying_years)
    term = max(term, ppt)

    def npv(r: float) -> float:
        paid = sum(annual_premium * (1 + r) ** (term - t) for t in range(ppt))
        return maturity_amount - paid

    lo, hi = -0.99, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if npv(mid) > 0:
            lo = mid
        else:
            hi = mid
    total_paid = annual_premium * ppt
    return {
        "total_premiums": round(total_paid),
        "maturity_amount": round(maturity_amount),
        "real_annual_percent": round((lo + hi) / 2 * 100, 1),
        "claimed_return_percent": claimed_return_percent,
        "fd_benchmark_percent": 7.0,
    }
