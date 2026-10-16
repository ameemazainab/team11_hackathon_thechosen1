import { useEffect, useState } from "react";
import { api } from "./api";
import { ErrorBox, Spinner, errText } from "./ui";

interface DemoUser { code: string; name: string; roles: string[]; notes: string | null }
interface AuthConfig { mode: "demo" | "google"; google_configured: boolean; demo_default_user: string }

const MESSAGES: Record<string, string> = {
  denied: "That Google account has not been set up for The Chosen One. Ask an administrator to add you.",
  failed: "Google sign-in did not complete. Please try again.",
  unverified: "Google could not confirm that email address.",
  domain: "Please sign in with your BIG Google Workspace account.",
};

export default function Login({ onDone }: { onDone: () => void }) {
  const [cfg, setCfg] = useState<AuthConfig | null>(null);
  const [users, setUsers] = useState<DemoUser[]>([]);
  const [pick, setPick] = useState("");
  const [error, setError] = useState<string | null>(null);
  const reason = new URLSearchParams(window.location.search).get("signin");

  useEffect(() => {
    api.get<AuthConfig>("/auth/config").then(async (c) => {
      setCfg(c);
      if (c.mode === "demo") {
        const u = await api.get<DemoUser[]>("/auth/demo-users");
        setUsers(u);
        setPick(u.find((x) => x.code === c.demo_default_user)?.code ?? u[0]?.code ?? "");
      }
    }).catch((e) => setError(errText(e)));
  }, []);

  const demoLogin = async (code: string) => {
    try { await api.post("/auth/demo-login", { code }); onDone(); } catch (e) { setError(errText(e)); }
  };

  return (
    <main className="d-flex align-items-center justify-content-center min-vh-100 p-3">
      <div className="card shadow" style={{ width: "min(560px, 100%)" }}>
        <div className="card-body p-4">
          <div className="d-flex align-items-center gap-2 mb-3">
            <span className="logo" style={{ width: 40, height: 40, borderRadius: 10, background: "#f5b301", color: "#1f3a5f", display: "grid", placeItems: "center", fontWeight: 800 }}>1</span>
            <h1 className="h3 mb-0">The Chosen One</h1>
          </div>
          <p className="text-muted">The revenue forecast for BIG: every project by month, committed revenue and weighted pipeline side by side.</p>
          {reason && <div className="alert alert-warning" role="alert">{MESSAGES[reason] ?? "Sign-in did not work."}</div>}
          {error && <ErrorBox error={error} />}
          {!cfg && !error && <Spinner />}
          {cfg?.mode === "google" && (
            <>
              <a className="btn btn-primary btn-lg w-100" href="/api/auth/login">Sign in with Google</a>
              {!cfg.google_configured && <p className="text-danger mt-3 mb-0">Google sign-in is not set up yet. Ask an administrator.</p>}
              <p className="form-text mt-3">Only people an administrator has added can sign in.</p>
            </>
          )}
          {cfg?.mode === "demo" && (
            <>
              <div className="alert alert-info py-2"><strong>Demo sign-in.</strong> Pick anyone to see the app through their eyes. This is only for demonstrations and is switched off in production.</div>
              <label htmlFor="demo-user" className="form-label fw-semibold">Sign in as</label>
              <select id="demo-user" className="form-select mb-3" value={pick} onChange={(e) => setPick(e.target.value)}>
                {users.map((u) => <option key={u.code} value={u.code}>{u.name} ({u.roles.join(", ")})</option>)}
              </select>
              <button className="btn btn-primary btn-lg w-100" disabled={!pick} onClick={() => demoLogin(pick)}>Continue</button>
            </>
          )}
        </div>
      </div>
    </main>
  );
}
