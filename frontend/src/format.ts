export const money = (v: number | null | undefined): string => {
  if (v === null || v === undefined || Number.isNaN(v)) return "";
  return (v < 0 ? "-" : "") + "$" + Math.round(Math.abs(v)).toLocaleString("en-US");
};
export const moneyK = (v: number): string => {
  const a = Math.abs(v);
  const s = a >= 1e6 ? (a / 1e6).toFixed(2) + "M" : a >= 1e3 ? Math.round(a / 1e3) + "K" : String(Math.round(a));
  return (v < 0 ? "-" : "") + "$" + s;
};
export const num = (v: number | null | undefined): string => (v === null || v === undefined ? "" : Math.round(v).toLocaleString("en-US"));
const MN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export const monthLabel = (m: string): string => MN[Number(m.slice(5, 7)) - 1] + " " + m.slice(2, 4);
export const monthLong = (m: string): string => ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"][Number(m.slice(5, 7)) - 1] + " " + m.slice(0, 4);
/** Fiscal year runs April to March; FY27 = Apr 2026 to Mar 2027. */
export const fiscalYear = (m: string): string => {
  const y = Number(m.slice(0, 4)), mo = Number(m.slice(5, 7));
  return "FY" + String((mo >= 4 ? y + 1 : y) % 100).padStart(2, "0");
};
export const day = (ts: string | null | undefined): string => (ts ? ts.slice(0, 10) : "");
export const stamp = (ts: string | null | undefined): string => (ts ? ts.replace("T", " ").slice(0, 16) : "");
export const pct = (v: number | null | undefined): string => (v === null || v === undefined ? "" : (v > 0 ? "+" : "") + v.toFixed(1) + "%");

/** Same rules as the server (FR-05): numbers only, never negative, no formulas. The server checks again. */
export type Parsed = { ok: true; value: number | null } | { ok: false; error: string };
export function parseValue(raw: unknown): Parsed {
  const s = String(raw ?? "").trim();
  if (s === "") return { ok: true, value: null };
  if (s[0] === "=") return { ok: false, error: "Formulas are not accepted. Type the final number instead." };
  const t = s.replace(/[$,\s]/g, "");
  if (!/^-?[0-9]+(\.[0-9]+)?$/.test(t)) return { ok: false, error: "Please enter a number, for example 42000." };
  const v = Number(t);
  if (v < 0) return { ok: false, error: "Revenue cannot be negative." };
  if (v > 1e12) return { ok: false, error: "That number is too large." };
  return { ok: true, value: Math.round(v * 100) / 100 };
}
