import { $, esc, inr } from "./ui.js";

const LABELS = {
  principal: "Loan amount",
  tenure_months: "Tenure (months)",
  quoted_rate_percent: "Quoted rate %",
  rate_period: "Rate period",
  rate_type: "Rate type",
  emi_quoted: "EMI quoted",
  processing_fee: "Processing fee",
  processing_fee_percent: "Processing fee %",
  insurance_premium: "Insurance premium",
  insurance_financed: "Insurance added to loan",
  other_fees: "Other fees",
  annual_premium: "Annual premium",
  premium_paying_years: "Premium paying years",
  policy_years: "Policy years",
  maturity_amount: "Maturity amount",
  sum_assured: "Sum assured",
  claimed_return_percent: "Claimed return %",
};

const stat = (value, label) =>
  `<div class="stat"><b>${esc(value)}</b><span>${esc(label)}</span></div>`;

const bigNumber = (percent, bad) =>
  `<div class="big ${bad ? "bad" : "good"}">${esc(percent)}% <small>per year</small></div>`;

export function renderCost({ loan, insurance }) {
  const el = $("costCard");

  if (loan && loan.real_annual_percent != null) {
    const quoted = loan.quoted_annual_percent;
    const bad = quoted && loan.real_annual_percent >= 1.3 * quoted;
    el.innerHTML = `
      <h2 class="card-title">Real cost of this loan</h2>
      ${bigNumber(loan.real_annual_percent, bad)}
      <p class="sub">${quoted ? `Agent said: ${esc(quoted)}% per year equivalent` : "Based on the EMI quoted"}</p>
      <div class="stats">
        ${stat(inr(loan.emi), "EMI per month")}
        ${stat(inr(loan.cash_in_hand), "Cash you actually get")}
        ${stat(inr(loan.total_paid), "Total you pay")}
        ${stat(inr(loan.total_extra), "Extra paid over what you got")}
      </div>`;
  } else if (insurance && insurance.real_annual_percent != null) {
    const bad = insurance.real_annual_percent < insurance.fd_benchmark_percent;
    const claimed =
      insurance.claimed_return_percent != null
        ? `Agent claimed: ${esc(insurance.claimed_return_percent)}% · `
        : "";
    el.innerHTML = `
      <h2 class="card-title">Real return of this policy</h2>
      ${bigNumber(insurance.real_annual_percent, bad)}
      <p class="sub">${claimed}Bank FD benchmark: ~${esc(insurance.fd_benchmark_percent)}%</p>
      <div class="stats">
        ${stat(inr(insurance.total_premiums), "Total premiums you pay")}
        ${stat(inr(insurance.maturity_amount), "You get at maturity")}
      </div>`;
  } else {
    el.innerHTML = `
      <h2 class="card-title">Real cost</h2>
      <p class="empty">Waiting for loan or insurance numbers…</p>`;
  }
}

export function renderFlags(flags) {
  const el = $("flags");
  el.className = flags.length ? "" : "empty";
  el.innerHTML = flags.length
    ? flags
        .map((f) => {
          const sev = ["high", "medium"].includes(f.severity)
            ? f.severity
            : "low";
          return `<div class="flag ${sev}">
            <div class="flag-title"><span class="chip">${sev}</span>${esc(f.title_en)}</div>
            ${f.explain ? `<div class="flag-explain">${esc(f.explain)}</div>` : ""}
          </div>`;
        })
        .join("")
    : "No red flags detected so far.";
}

export function renderQuestions(questions) {
  const el = $("questions");
  el.className = questions.length ? "" : "empty";
  el.innerHTML = questions.length
    ? `<ul class="questions">${questions.map((q) => `<li>${esc(q)}</li>`).join("")}</ul>`
    : "None yet.";
}

export function renderTerms(extracted) {
  const group =
    extracted.product_type === "insurance"
      ? extracted.insurance
      : extracted.loan;
  const rows = Object.entries(group || {}).filter(
    ([, v]) => v !== null && v !== undefined && v !== "",
  );
  const el = $("terms");
  el.className = rows.length ? "" : "empty";
  el.innerHTML = rows.length
    ? `<table class="terms">${rows
        .map(
          ([k, v]) =>
            `<tr><td>${esc(LABELS[k] || k)}</td><td>${esc(v)}</td></tr>`,
        )
        .join("")}</table>`
    : "Nothing extracted yet.";
}
