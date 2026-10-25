export const $ = (id) => document.getElementById(id);

const ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" };

export const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ESCAPES[c]);

export const inr = (n) => "₹" + Number(n).toLocaleString("en-IN");

let toastTimer;

export function toast(msg) {
  const el = $("toast");
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.hidden = true), 8000);
}

$("toast").onclick = () => ($("toast").hidden = true);

export function store(key, value) {
  try {
    if (value === undefined) return localStorage.getItem(key);
    localStorage.setItem(key, value);
  } catch {
    return null;
  }
}
