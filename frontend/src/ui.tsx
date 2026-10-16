import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { ApiError } from "./api";

/* ---------- data loading ---------- */
export function useApi<T>(load: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const seq = useRef(0);
  const run = useCallback(() => {
    const id = ++seq.current;
    setLoading(true);
    load().then(
      (d) => { if (id === seq.current) { setData(d); setError(null); setLoading(false); } },
      (e: unknown) => { if (id === seq.current) { setError(errText(e)); setLoading(false); } },
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(() => { run(); }, [run]);
  return { data, error, loading, reload: run, setData };
}

export const errText = (e: unknown): string => (e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Something went wrong.");

/* ---------- toasts ---------- */
type Toast = { id: number; kind: "success" | "danger" | "info"; text: string };
const ToastCtx = createContext<(kind: Toast["kind"], text: string) => void>(() => undefined);
export const useToast = () => useContext(ToastCtx);
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback((kind: Toast["kind"], text: string) => {
    const id = Date.now() + Math.random();
    setItems((x) => [...x, { id, kind, text }]);
    setTimeout(() => setItems((x) => x.filter((t) => t.id !== id)), kind === "danger" ? 9000 : 4500);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toast-stack" role="status" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className={`alert alert-${t.kind} shadow-sm py-2 px-3 mb-2`}>{t.text}</div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

/* ---------- small pieces ---------- */
export function Spinner({ label = "Loading..." }: { label?: string }) {
  return <div className="text-muted py-4 text-center" role="status"><span className="spinner-border spinner-border-sm me-2" aria-hidden="true" />{label}</div>;
}
export function ErrorBox({ error, onRetry }: { error: string; onRetry?: () => void }) {
  return (
    <div className="alert alert-danger d-flex justify-content-between align-items-center" role="alert">
      <span>{error}</span>{onRetry && <button className="btn btn-sm btn-outline-danger" onClick={onRetry}>Try again</button>}
    </div>
  );
}
export function Page({ title, subtitle, actions, children }: { title: string; subtitle?: ReactNode; actions?: ReactNode; children: ReactNode }) {
  return (
    <div>
      <div className="d-flex flex-wrap justify-content-between align-items-start gap-2 mb-3">
        <div>
          <h1 className="h3 mb-1">{title}</h1>
          {subtitle && <p className="text-muted mb-0">{subtitle}</p>}
        </div>
        {actions && <div className="d-flex flex-wrap gap-2">{actions}</div>}
      </div>
      {children}
    </div>
  );
}
export function Card({ title, actions, children, className = "" }: { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`card shadow-sm mb-3 ${className}`}>
      {(title || actions) && (
        <div className="card-header bg-white d-flex justify-content-between align-items-center gap-2">
          <h2 className="h6 mb-0">{title}</h2>{actions}
        </div>
      )}
      <div className="card-body">{children}</div>
    </section>
  );
}
export function Stat({ label, value, hint, tone }: { label: string; value: ReactNode; hint?: ReactNode; tone?: "danger" | "warning" | "success" }) {
  return (
    <div className="stat h-100">
      <div className="stat-label">{label}</div>
      <div className={`stat-value ${tone ? "text-" + tone : ""}`}>{value}</div>
      {hint && <div className="stat-hint">{hint}</div>}
    </div>
  );
}
const SEV: Record<string, string> = { high: "danger", medium: "warning", low: "secondary" };
export const SeverityBadge = ({ s }: { s: string }) => (
  <span className={`badge text-bg-${SEV[s] ?? "secondary"} text-capitalize`}>{s === "high" ? "High" : s === "medium" ? "Medium" : "Low"} priority</span>
);
export const Badge = ({ tone = "secondary", children }: { tone?: string; children: ReactNode }) => <span className={`badge text-bg-${tone}`}>{children}</span>;

export function Modal({ title, onClose, children, footer, size = "" }: { title: string; onClose: () => void; children: ReactNode; footer?: ReactNode; size?: "lg" | "xl" | "" }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null;
    ref.current?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("keydown", onKey); prev?.focus?.(); };
  }, [onClose]);
  return (
    <>
      <div className="modal-backdrop fade show" />
      <div className="modal fade show d-block" role="dialog" aria-modal="true" aria-label={title} onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
        <div className={`modal-dialog modal-dialog-scrollable ${size ? "modal-" + size : ""}`}>
          <div className="modal-content" ref={ref} tabIndex={-1}>
            <div className="modal-header"><h2 className="modal-title h5">{title}</h2><button className="btn-close" aria-label="Close" onClick={onClose} /></div>
            <div className="modal-body">{children}</div>
            {footer && <div className="modal-footer">{footer}</div>}
          </div>
        </div>
      </div>
    </>
  );
}

export function Field({ label, children, hint, id }: { label: string; children: ReactNode; hint?: string; id: string }) {
  return (
    <div className="mb-3">
      <label className="form-label fw-semibold" htmlFor={id}>{label}</label>
      {children}
      {hint && <div className="form-text">{hint}</div>}
    </div>
  );
}

export function Select({ id, value, onChange, options, blank, label }: { id?: string; value: string; onChange: (v: string) => void; options: (string | { value: string; label: string })[]; blank?: string; label: string }) {
  return (
    <select id={id} aria-label={label} className="form-select form-select-sm" value={value} onChange={(e) => onChange(e.target.value)}>
      {blank !== undefined && <option value="">{blank}</option>}
      {options.map((o) => typeof o === "string" ? <option key={o} value={o}>{o}</option> : <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
}

export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: { id: T; label: string }[]; value: T; onChange: (t: T) => void }) {
  return (
    <ul className="nav nav-tabs mb-3" role="tablist">
      {tabs.map((t) => (
        <li className="nav-item" key={t.id} role="presentation">
          <button role="tab" aria-selected={value === t.id} className={`nav-link ${value === t.id ? "active" : ""}`} onClick={() => onChange(t.id)}>{t.label}</button>
        </li>
      ))}
    </ul>
  );
}

export function download(url: string) {
  const a = document.createElement("a");
  a.href = url;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
}
