"""LLM extraction + deterministic cost math + red-flag merge."""

import calc
import sarvam

LANG_NAMES = {
    "hi-IN": "Hindi", "bn-IN": "Bengali", "ta-IN": "Tamil", "te-IN": "Telugu",
    "kn-IN": "Kannada", "ml-IN": "Malayalam", "mr-IN": "Marathi", "gu-IN": "Gujarati",
    "pa-IN": "Punjabi", "od-IN": "Odia", "en-IN": "English",
}

SCRIPTS = {
    "hi-IN": "Devanagari (हिन्दी)", "mr-IN": "Devanagari (मराठी)", "bn-IN": "Bengali script (বাংলা)",
    "ta-IN": "Tamil script (தமிழ்)", "te-IN": "Telugu script (తెలుగు)", "kn-IN": "Kannada script (ಕನ್ನಡ)",
    "ml-IN": "Malayalam script (മലയാളം)", "gu-IN": "Gujarati script (ગુજરાતી)",
    "pa-IN": "Gurmukhi (ਪੰਜਾਬੀ)", "od-IN": "Odia script (ଓଡ଼ିଆ)", "en-IN": "English",
}

SYSTEM_PROMPT = """You are Teesra Kaan, a voice advocate who works for the CUSTOMER (borrower or policyholder), not the agent. You read a transcript of a conversation between a customer and a loan or insurance agent and warn the customer about anything unfair.

Rules:
- Extract ONLY numbers that were actually said. Use null when unknown. NEVER compute rates, totals or EMIs yourself; a calculator does that.
- Convert Indian amounts to plain rupees: "1 lakh" = 100000, "50 hazaar" = 50000. Convert tenure to months: "do saal" = 24.
- rate_type is "flat" if the rate is called flat, or charged per month on the original amount (e.g. "har mahine 1.5%" on the full principal). "reducing" if called reducing/diminishing balance. Otherwise "unknown".
- rate_period is "month" or "year" (how the quoted rate is expressed).
- Flag these tricks when present: flat rate quoted as a monthly rate, fees deducted from the disbursed amount, bundled or "compulsory" insurance, "guaranteed" or "bonus" returns, pressure to sign today, foreclosure or prepayment penalties, vague answers about total cost, "0% interest" with hidden fees, blank signatures or documents.
- Write "explain", "questions_to_ask", "top_warning" and "real_cost_sentence" in {lang_name}, written in its native script (for example Devanagari for Hindi), NEVER in Roman/Latin letters, in simple spoken language. "title_en" and "summary_en" are in English.
- Style example for Hindi (copy the SCRIPT, not the words): "एजेंट आप पर आज ही साइन करने का दबाव डाल रहा है। पूरा खर्च पूछे बिना दस्तखत न करें।" It must NOT look like "Agent aap par dabaav daal raha hai".
- "top_warning" is 1-2 short sentences and must contain NO computed numbers.
- "real_cost_sentence" is one sentence in {lang_name} that contains the literal token {{REAL_RATE}} exactly once where the real yearly percentage belongs.
- "questions_to_ask" has 3-5 short questions the customer can say out loud to the agent.
- If nothing is wrong or there is too little information, return an empty red_flags list.

Respond with ONLY a JSON object of exactly this shape:
{{
  "product_type": "loan" | "insurance" | "unknown",
  "loan": {{"principal": null, "tenure_months": null, "quoted_rate_percent": null, "rate_period": null, "rate_type": null, "emi_quoted": null, "processing_fee": null, "processing_fee_percent": null, "insurance_premium": null, "other_fees": null}},
  "insurance": {{"annual_premium": null, "premium_paying_years": null, "policy_years": null, "maturity_amount": null, "sum_assured": null, "claimed_return_percent": null}},
  "red_flags": [{{"severity": "high" | "medium" | "low", "title_en": "", "explain": ""}}],
  "questions_to_ask": [],
  "top_warning": "",
  "real_cost_sentence": "",
  "summary_en": ""
}}"""

_NUMERIC_STR = {"rate_period", "rate_type"}


def _clean(d: dict | None) -> dict:
    """Coerce numeric strings to floats; leave string enums and booleans alone."""
    out = {}
    for k, v in (d or {}).items():
        if k in _NUMERIC_STR or isinstance(v, bool) or v is None:
            out[k] = v
            continue
        try:
            out[k] = float(str(v).replace(",", "").replace("₹", "").strip())
        except ValueError:
            out[k] = None
    return out


def _safe(fn, d: dict):
    try:
        return fn(**_clean(d))
    except Exception:
        return None


def _fmt(n) -> str:
    return f"{n:g}"


def _inr(n) -> str:
    return f"{int(n):,}"


async def analyze(transcript: str, language_code: str) -> dict:
    lang = LANG_NAMES.get(language_code, "Hindi")
    x = await sarvam.chat_json(
        SYSTEM_PROMPT.format(lang_name=lang),
        f"Conversation transcript so far:\n{transcript}\n\n"
        f"REMINDER: the transcript may be in Roman letters, but write explain, questions_to_ask, top_warning and "
        f"real_cost_sentence in {lang} using {SCRIPTS.get(language_code, 'its native script')} only, not Roman letters.",
    )

    loan = _safe(calc.loan_cost, x.get("loan"))
    ins = _safe(calc.insurance_return, x.get("insurance"))

    flags = []
    if loan:
        real, quoted = loan.get("real_annual_percent"), loan.get("quoted_annual_percent")
        if real is not None and quoted and real >= 1.3 * quoted:
            flags.append({"severity": "high", "title_en": f"Real cost {_fmt(real)}%/yr vs quoted {_fmt(quoted)}%", "explain": ""})
        if loan["cash_in_hand"] < loan["loan_amount"]:
            flags.append({"severity": "medium", "title_en": f"You receive ₹{_inr(loan['cash_in_hand'])} but repay on ₹{_inr(loan['loan_amount'])}", "explain": ""})
    if ins and ins.get("real_annual_percent") is not None and ins["real_annual_percent"] < 6:
        flags.append({"severity": "high", "title_en": f"Real return {_fmt(ins['real_annual_percent'])}%/yr — below a bank FD (~7%)", "explain": ""})

    x["red_flags"] = flags + list(x.get("red_flags") or [])

    real_rate = (loan or ins or {}).get("real_annual_percent")
    explained = sorted((f for f in x["red_flags"] if f.get("explain")), key=lambda f: f.get("severity") != "high")
    parts = [x.get("top_warning") or (explained[0]["explain"] if explained else "")]
    sentence = x.get("real_cost_sentence") or ""
    if real_rate is not None and "{REAL_RATE}" in sentence:
        parts.append(sentence.replace("{REAL_RATE}", _fmt(real_rate)))
    parts.extend((x.get("questions_to_ask") or [])[:2])

    return {**x, "calc": {"loan": loan, "insurance": ins}, "whisper_text": " ".join(p for p in parts if p)}
