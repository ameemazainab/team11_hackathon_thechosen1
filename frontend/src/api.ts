// Typed client for the Chosen One API. All calls use the signed-in session cookie.

export interface Person { code: string; name: string }
export interface Capabilities {
  can_create: boolean; can_assign_owner: boolean; can_snapshot: boolean; can_close_months: boolean;
  can_admin: boolean; can_sync: boolean; can_edit_any: boolean; read_only: boolean;
}
export interface Me {
  user: { code: string; name: string; email: string; roles: string[] };
  capabilities: Capabilities; auth_mode: "demo" | "google"; ai_enabled: boolean;
}
export interface SyncBanner { last_synced: string | null; stale: boolean; since: string | null; message: string | null; source: string }
export interface Reason { code: string; label: string; use_when: string | null }
export interface Meta {
  months: string[]; month_labels: Record<string, string>; closed_through: string; closed_label: string; as_of: string;
  window: string[]; forecast_months: string[]; review_due: string;
  options: { tech: string[]; region: string[]; industry: string[]; category: string[]; customer: string[]; status: string[]; billing_type: string[] };
  owners: { code: string; name: string; roles: string[] }[]; reasons: Reason[]; sync: SyncBanner;
}
export type MonthMap = Record<string, number>;
export interface Project {
  id: string; customer: string; project: string; client_partner: Person | null; ae: Person | null; commercial_owner: Person | null;
  owner_label: string; tech: string | null; region: string | null; industry: string | null; category: string | null;
  country: string | null; billing_type: string; currency: string; status: string; deal_id: string | null;
  last_updated: string; last_updated_by_name: string; revenue: MonthMap; can_edit: boolean; edit_reason: string | null;
  open_findings: number; draft: { closed_at: string; amount: number } | null;
}
export interface PipelineLine {
  deal_id: string; name: string; company: string; stage: string; amount: number; probability: number; weighted: number; owner: string;
  owner_code: string | null; tech: string | null; region: string | null; close_date: string; expected_start: string | null;
  duration_months: number | null; status: "ok" | "below" | "linked" | "unphased"; note: string; months: MonthMap; linked_row: string | null;
  has_override: boolean; flags?: string[]; can_phase?: boolean;
}
export interface Totals { committed: MonthMap; weighted: MonthMap; total: MonthMap }
export interface ForecastResp { rows: Project[]; totals: Totals; pipeline: PipelineLine[]; unphased_total: number; closed_through: string; count: number }
export interface HistoryEntry {
  id: string; ts: string; user: string; user_name: string; row_id: string; customer: string | null; project: string | null; field: string;
  field_label: string; old: number | string | null; new: number | string | null; reason: string | null; reason_label: string | null;
  note: string | null; after_snapshot: boolean;
}
export interface ProjectDetail extends Project {
  history: HistoryEntry[]; findings: { id: string; title: string; severity: string; status: string }[];
  deal: { deal_id: string; name: string; stage: string; amount: number } | null; attested: { by: string; at: string } | null;
}
export interface Finding {
  id: string; rule: string; severity: "high" | "medium" | "low"; title: string; owner: string; owner_name: string; evidence: string[]; fix: string;
  impact: number; status: "open" | "accepted" | "dismissed"; resolution: { reason: string; by_name: string; at: string } | null;
  deal: string | null; explained?: boolean; rows: { id: string; customer: string; project: string }[]; can_resolve: boolean; mine: boolean;
}
export interface ChecksResp {
  findings: Finding[]; last_run: string | null;
  summary: { open: number; by_severity: Record<string, number>; by_rule: Record<string, number>; accepted: number; dismissed: number };
}
export interface AskResp {
  title: string; facts: string[]; answer: string[]; used_ai: boolean; notice: string | null;
  cites: { row_id: string; label: string; entry_id: string | null; entry: string | null }[];
}
export interface ReviewResp {
  cycle: string; window: string[]; due: string;
  status: { owner: string; owner_name: string; rows: string[]; attested: number; total: number; amount: number; oldest: string; stale: boolean }[];
  mine: { id: string; customer: string; project: string; last_updated: string; window: MonthMap; window_total: number; owner_label: string; attested: boolean; attested_by: string | null; attested_at: string | null }[];
  overall: { rows: number; attested: number; pct: number };
}
export interface PipelineResp {
  lines: PipelineLine[]; closed: { deal_id: string; name: string; company: string; stage: string; amount: number; close_date: string; linked_row: string | null }[];
  events: { ts: string; kind: string; deal_id: string | null; message: string }[]; sync: SyncBanner;
  stages: { stage: string; probability: number; in_forecast: string; note: string | null }[]; unphased_total: number;
  weighted_by_month: MonthMap; months: string[]; rows_for_linking: { id: string; label: string; deal_id: string | null }[]; can_sync: boolean;
}
export interface Snapshot {
  id: string; date: string; label: string; taken_by: string; created: string | null; auto: boolean; rows: number; months: string[];
  committed: MonthMap; weighted: MonthMap | null;
  table?: { id: string; customer: string; project: string; client_partner: string; values: MonthMap }[];
}
export interface Mover {
  row_id: string; customer: string; project: string; owner: string; was: number; now: number; delta: number; is_new: boolean;
  reason: string | null; note: string | null; entry: string | null; changed_by: string; changed_at: string; after_snapshot_edits: number;
}
export interface MovementResp {
  snapshot: { id: string; date: string; label: string }; months: string[]; series: { month: string; label: string; snapshot: number; current: number }[];
  total_was: number; total_now: number; movers: Mover[]; unexplained: number;
}
export interface ByResp {
  dim: string; label: string; months: string[];
  rows: { key: string; committed: MonthMap; weighted: MonthMap | null; committed_total: number; weighted_total: number | null }[];
}
export interface FyGapResp {
  available: boolean; fy_end?: string; fy_end_label?: string; baseline?: number;
  series?: { month: string; label: string; committed: number; weighted: number; total: number; gap: number; coverage_pct: number | null; committed_coverage_pct: number | null }[];
  stopping?: { id: string; customer: string; project: string; owner: string; monthly: number }[]; stopping_total?: number; cover_deals?: PipelineLine[];
}
export interface LookaheadItem {
  k: number; snapshot_id: string | null; snapshot_date: string | null; committed?: number; weighted?: number | null; total?: number; has_weighted?: boolean;
  committed_variance?: number; committed_variance_pct?: number | null; committed_flag?: boolean;
  total_variance?: number; total_variance_pct?: number | null; total_flag?: boolean;
}
export interface AccuracyResp { tolerance_pct: number; note: string; months: { month: string; actual: number; lookaheads: LookaheadItem[] }[] }
export interface Overview {
  as_of: string; closed_through: string; series: { month: string; label: string; committed: number; weighted: number; total: number }[];
  kpis: { window: string[]; committed: number; weighted: number; total: number; unphased: number; next12_committed: number };
  checks: { open: number; high: number; mine: number; top: Finding[]; last_run: string | null; last_nightly: string | null };
  review: { rows: number; attested: number; pct: number; due: string; my_rows: number; my_todo: number };
  drafts: { id: string; customer: string; project: string; amount: number; closed_at: string | null }[];
  snapshot: { id: string; date: string; label: string } | null;
  movers: { row_id: string; customer: string; project: string; delta: number; is_new: boolean; reason: string | null }[]; sync: SyncBanner;
}
export interface AdminUser { code: string; name: string; email: string; roles: string[]; location: string | null; notes: string | null; active: boolean }
export interface Stage { stage: string; probability: number; in_forecast: string; note: string | null }
export interface Thresholds {
  runRateAbs: number; runRatePct: number; staleDays: number; mismatchPct: number; dupSimilarity: number; reviewDue: string; amountMismatchCheck: boolean;
}
export interface CalendarDay { id: number; country: string; date: string; name: string; type: string; factor: number; note: string | null }
export interface DuplicateHit { id: string; customer: string; project: string; owner_label: string; similarity: number; status: string }
export interface ImportReport {
  committed: boolean; rows_found: number; rows_accepted: number; rows_rejected: number;
  rejects: { sheet_row: number; customer: string | null; project: string | null; problems: string[] }[]; totals_by_month: MonthMap;
}

export class ApiError extends Error {
  status: number;
  detail: Record<string, unknown>;
  constructor(status: number, message: string, detail: Record<string, unknown> = {}) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

type Q = Record<string, string | number | boolean | undefined | null>;
const qs = (q?: Q) => {
  const p = new URLSearchParams();
  Object.entries(q ?? {}).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== "" && v !== false) p.set(k, String(v)); });
  const s = p.toString();
  return s ? "?" + s : "";
};

async function request<T>(method: string, path: string, body?: unknown, q?: Q): Promise<T> {
  const res = await fetch("/api" + path + qs(q), {
    method,
    credentials: "same-origin",
    headers: body instanceof FormData || body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : body instanceof FormData ? body : JSON.stringify(body),
  });
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  let data: unknown = null;
  try { data = text ? JSON.parse(text) : null; } catch { /* not JSON */ }
  if (!res.ok) {
    if (res.status === 401) window.dispatchEvent(new Event("chosen-one:unauthorized"));
    const d = ((data as { detail?: unknown })?.detail ?? {}) as Record<string, unknown> | string;
    const detail = typeof d === "string" ? { message: d } : d;
    throw new ApiError(res.status, String(detail.message ?? res.statusText ?? "Something went wrong"), detail);
  }
  return data as T;
}

export const api = {
  get: <T,>(path: string, q?: Q) => request<T>("GET", path, undefined, q),
  post: <T,>(path: string, body?: unknown, q?: Q) => request<T>("POST", path, body ?? {}, q),
  put: <T,>(path: string, body: unknown) => request<T>("PUT", path, body),
  patch: <T,>(path: string, body: unknown) => request<T>("PATCH", path, body),
  del: <T,>(path: string) => request<T>("DELETE", path),
  upload: <T,>(path: string, file: File, q?: Q) => { const f = new FormData(); f.append("file", file); return request<T>("POST", path, f, q); },
  url: (path: string, q?: Q) => "/api" + path + qs(q),
};

export type Filters = { q: string; tech: string; region: string; industry: string; category: string; owner: string; customer: string; status: string };
export const emptyFilters = (): Filters => ({ q: "", tech: "", region: "", industry: "", category: "", owner: "", customer: "", status: "" });
