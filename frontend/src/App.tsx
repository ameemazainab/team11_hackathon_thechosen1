import { useCallback, useEffect, useMemo, useState } from "react";
import { NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { api, type Me, type Meta, type Overview } from "./api";
import { monthLong, stamp } from "./format";
import { SessionCtx, useSession } from "./session";
import { Spinner, ErrorBox, errText, useToast } from "./ui";
import Login from "./Login";
import OverviewPage from "./pages/Overview";
import ForecastGrid from "./pages/ForecastGrid";
import MonthlyReview from "./pages/MonthlyReview";
import PipelinePage from "./pages/Pipeline";
import QualityChecks from "./pages/QualityChecks";
import Insights from "./pages/Insights";
import Snapshots from "./pages/Snapshots";
import HistoryPage from "./pages/History";
import Admin from "./pages/Admin";

const ICONS: Record<string, string> = {
  overview: "M3 3h8v8H3zM13 3h8v5h-8zM13 10h8v11h-8zM3 13h8v8H3z",
  grid: "M3 4h18v16H3zM3 10h18M3 15h18M9 4v16M15 4v16",
  review: "M4 12l5 5L20 6",
  pipeline: "M3 5h18l-7 8v6l-4 2v-8z",
  checks: "M12 3l9 16H3zM12 10v4M12 17h.01",
  insights: "M4 20V10M10 20V4M16 20v-8M22 20H2",
  snapshots: "M4 7h16v13H4zM8 7V4h8v3M12 11v6M9 14h6",
  history: "M12 7v5l3 2M3 12a9 9 0 1 0 3-6.7M3 4v5h5",
  admin: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M5 19l2-2M17 7l2-2",
};
const Icon = ({ k }: { k: string }) => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={ICONS[k]} /></svg>
);
const NAV = [
  { to: "/", label: "Overview", icon: "overview", end: true },
  { to: "/forecast", label: "Forecast grid", icon: "grid" },
  { to: "/review", label: "Monthly review", icon: "review" },
  { to: "/pipeline", label: "HubSpot pipeline", icon: "pipeline" },
  { to: "/checks", label: "Quality checks", icon: "checks" },
  { to: "/insights", label: "Insights", icon: "insights" },
  { to: "/snapshots", label: "Snapshots & export", icon: "snapshots" },
  { to: "/history", label: "History", icon: "history" },
  { to: "/admin", label: "Admin", icon: "admin", admin: true },
];

export default function App() {
  const [me, setMe] = useState<Me | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [state, setState] = useState<"loading" | "anon" | "ready" | "error">("loading");
  const [error, setError] = useState("");

  const boot = useCallback(async () => {
    try {
      const m = await api.get<Me>("/auth/me");
      const meta = await api.get<Meta>("/meta");
      setMe(m); setMeta(meta); setState("ready");
    } catch (e) {
      const status = (e as { status?: number }).status;
      if (status === 401) setState("anon"); else { setError(errText(e)); setState("error"); }
    }
  }, []);
  useEffect(() => { boot(); }, [boot]);
  useEffect(() => {
    const h = () => setState("anon");
    window.addEventListener("chosen-one:unauthorized", h);
    return () => window.removeEventListener("chosen-one:unauthorized", h);
  }, []);

  const session = useMemo(() => me && meta ? {
    me, meta,
    reloadMeta: () => { api.get<Meta>("/meta").then(setMeta).catch(() => undefined); },
    switchUser: async (code: string) => { await api.post("/auth/demo-login", { code }); setState("loading"); await boot(); },
    logout: async () => { await api.post("/auth/logout"); setMe(null); setMeta(null); setState("anon"); },
  } : null, [me, meta, boot]);

  if (state === "loading") return <Spinner label="Starting The Chosen One..." />;
  if (state === "error") return <div className="p-4"><ErrorBox error={error} onRetry={boot} /></div>;
  if (state === "anon" || !session) return <Login onDone={boot} />;
  return <SessionCtx.Provider value={session}><Shell /></SessionCtx.Provider>;
}


function Shell() {
  const { me, meta, switchUser, logout } = useSession();
  const [open, setOpen] = useState(false);
  const [badge, setBadge] = useState<number | null>(null);
  const loc = useLocation();
  const toast = useToast();
  const [users, setUsers] = useState<{ code: string; name: string; roles: string[] }[]>([]);

  useEffect(() => { setOpen(false); }, [loc.pathname]);
  useEffect(() => { api.get<Overview>("/overview").then((o) => setBadge(o.checks.open)).catch(() => undefined); }, [loc.pathname]);
  useEffect(() => {
    if (me.auth_mode === "demo") api.get<{ code: string; name: string; roles: string[] }[]>("/auth/demo-users").then(setUsers).catch(() => undefined);
  }, [me.auth_mode]);

  return (
    <div className="shell">
      <a className="skip-link" href="#main">Skip to content</a>
      <aside className={`sidebar ${open ? "open" : ""}`} aria-label="Main navigation">
        <div className="brand"><span className="logo" aria-hidden="true">1</span> The Chosen One</div>
        <nav>
          {NAV.filter((n) => !n.admin || me.capabilities.can_admin).map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end} className={({ isActive }) => (isActive ? "active" : "")}>
              <Icon k={n.icon} />{n.label}
              {n.to === "/checks" && badge ? <span className="count badge text-bg-warning" aria-label={`${badge} open`}>{badge}</span> : null}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto p-3 small text-white-50">Fiscal year April to March.<br />As of {meta.as_of}. Closed through {monthLong(meta.closed_through)}.</div>
      </aside>
      <div className="main">
        <header className="topbar">
          <button className="btn btn-outline-secondary btn-sm menu-toggle" aria-label="Open menu" aria-expanded={open} onClick={() => setOpen(!open)}>☰ Menu</button>
          <div className="ms-auto dropdown-center d-flex align-items-center gap-2">
            <span className="text-muted d-none d-md-inline small">Signed in as</span>
            <UserMenu name={me.user.name} roles={me.user.roles} users={users} demo={me.auth_mode === "demo"} onSwitch={(c) => switchUser(c).then(() => toast("info", "Switched user"))} onLogout={logout} />
          </div>
        </header>
        <SyncBanner />
        <main id="main" className="content" tabIndex={-1}>
          <Routes>
            <Route path="/" element={<OverviewPage />} />
            <Route path="/forecast" element={<ForecastGrid />} />
            <Route path="/review" element={<MonthlyReview />} />
            <Route path="/pipeline" element={<PipelinePage />} />
            <Route path="/checks" element={<QualityChecks />} />
            <Route path="/insights" element={<Insights />} />
            <Route path="/snapshots" element={<Snapshots />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/admin" element={me.capabilities.can_admin ? <Admin /> : <Navigate to="/" />} />
            <Route path="*" element={<Navigate to="/" />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

function SyncBanner() {
  const { meta } = useSession();
  if (!meta.sync.stale) return null;
  return (
    <div className="alert alert-warning rounded-0 mb-0 py-2 px-4" role="alert">
      <strong>Pipeline data may be out of date.</strong> HubSpot was last synced {stamp(meta.sync.last_synced) || "never"}
      {meta.sync.since ? ` (stale since ${stamp(meta.sync.since)})` : ""}. {meta.sync.message ?? ""} The forecast still shows the last good data and you can keep editing.
    </div>
  );
}

function UserMenu({ name, roles, users, demo, onSwitch, onLogout }: { name: string; roles: string[]; users: { code: string; name: string; roles: string[] }[]; demo: boolean; onSwitch: (c: string) => void; onLogout: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="position-relative">
      <button className="btn btn-outline-secondary btn-sm" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen(!open)}>
        <strong>{name}</strong> <span className="text-muted">({roles.join(", ")})</span> ▾
      </button>
      {open && (
        <div className="dropdown-menu dropdown-menu-end show" style={{ maxHeight: "70vh", overflowY: "auto", minWidth: 280 }} role="menu">
          {demo && <h2 className="dropdown-header">Demo: view the app as</h2>}
          {demo && users.map((u) => (
            <button key={u.code} role="menuitem" className="dropdown-item" onClick={() => { setOpen(false); onSwitch(u.code); }}>{u.name} <span className="text-muted small">{u.roles.join(", ")}</span></button>
          ))}
          {demo && <div className="dropdown-divider" />}
          <button role="menuitem" className="dropdown-item" onClick={onLogout}>Sign out</button>
        </div>
      )}
    </div>
  );
}
