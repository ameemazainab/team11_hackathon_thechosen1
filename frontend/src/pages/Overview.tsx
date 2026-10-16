import { Link } from "react-router-dom";
import { api, type Overview } from "../api";
import { day, money, moneyK, monthLabel } from "../format";
import { useSession } from "../session";
import { Card, ErrorBox, Page, SeverityBadge, Spinner, Stat, useApi } from "../ui";
import { Chart, PALETTE, moneyAxis } from "../Chart";

export default function OverviewPage() {
  const { me } = useSession();
  const { data: o, error, loading, reload } = useApi(() => api.get<Overview>("/overview"));
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (loading || !o) return <Spinner />;
  const config = {
    type: "bar" as const,
    data: {
      labels: o.series.map((s) => s.label),
      datasets: [
        { label: "Committed", data: o.series.map((s) => s.committed), backgroundColor: PALETTE.committed, stack: "a" },
        { label: "Weighted pipeline", data: o.series.map((s) => s.weighted), backgroundColor: PALETTE.weighted, stack: "a" },
      ],
    },
    options: { scales: { x: { stacked: true }, y: { stacked: true, ...moneyAxis } }, plugins: { tooltip: { callbacks: { label: (c: { dataset: { label?: string }; parsed: { y: number | null } }) => `${c.dataset.label}: ${money(c.parsed.y)}` } } } },
  };
  const todo = [
    o.review.my_todo > 0 && { to: "/review", text: `${o.review.my_todo} of your ${o.review.my_rows} rows still need your monthly review (due ${o.review.due})` },
    o.checks.mine > 0 && { to: "/checks", text: `${o.checks.mine} quality check${o.checks.mine === 1 ? "" : "s"} waiting for you` },
    ...o.drafts.map((d) => ({ to: "/forecast?q=" + d.id, text: `Confirm the monthly schedule for ${d.customer} - ${d.project} (Closed Won ${d.closed_at ?? ""}, ${money(d.amount)})` })),
  ].filter(Boolean) as { to: string; text: string }[];

  return (
    <Page title="Overview" subtitle={`Hello ${me.user.name.split(" ")[0]}. As of ${o.as_of}. Look-ahead window: ${o.kpis.window.join(", ")}.`}>
      <div className="row g-3 mb-3">
        <div className="col-6 col-lg-3"><Stat label="Committed, next 3 months" value={moneyK(o.kpis.committed)} hint="Counts at 100%" /></div>
        <div className="col-6 col-lg-3"><Stat label="Weighted pipeline, next 3 months" value={moneyK(o.kpis.weighted)} hint={`${moneyK(o.kpis.unphased)} not phased yet`} /></div>
        <div className="col-6 col-lg-3"><Stat label="Total forecast, next 3 months" value={moneyK(o.kpis.total)} hint={`Committed next 12 months ${moneyK(o.kpis.next12_committed)}`} /></div>
        <div className="col-6 col-lg-3"><Stat label="Open quality checks" value={o.checks.open} tone={o.checks.high ? "danger" : undefined} hint={`${o.checks.high} high priority`} /></div>
      </div>
      <div className="row g-3">
        <div className="col-lg-8">
          <Card title="Forecast by month: committed and weighted pipeline">
            <Chart config={config} summary={`Stacked bars of committed and weighted pipeline for ${o.series.length} months, from ${monthLabel(o.series[0].month)}.`} />
            <div className="table-responsive mt-2"><table className="table table-sm mb-0"><thead><tr><th scope="col">Month</th>{o.series.slice(0, 6).map((s) => <th key={s.month} className="num" scope="col">{s.label}</th>)}</tr></thead>
              <tbody><tr><th scope="row">Committed</th>{o.series.slice(0, 6).map((s) => <td key={s.month} className="num">{money(s.committed)}</td>)}</tr><tr><th scope="row">Weighted</th>{o.series.slice(0, 6).map((s) => <td key={s.month} className="num">{money(s.weighted)}</td>)}</tr><tr><th scope="row">Total</th>{o.series.slice(0, 6).map((s) => <td key={s.month} className="num fw-bold">{money(s.total)}</td>)}</tr></tbody></table></div>
          </Card>
          <Card title={o.snapshot ? `Biggest changes since the ${o.snapshot.date} snapshot` : "Biggest changes"} actions={<Link to="/insights" className="small">See all</Link>}>
            {o.movers.length === 0 ? <p className="text-muted mb-0">No changes yet.</p> : (
              <table className="table table-sm mb-0"><tbody>{o.movers.map((m) => (
                <tr key={m.row_id}><td>{m.customer} <span className="text-muted">- {m.project}</span></td><td className={`num ${m.delta < 0 ? "text-danger" : "text-success"}`}>{money(m.delta)}</td><td className="small">{m.is_new ? "New row" : m.reason ?? <span className="text-danger">No reason recorded</span>}</td></tr>))}</tbody></table>
            )}
          </Card>
        </div>
        <div className="col-lg-4">
          <Card title="Needs your attention">
            {todo.length === 0 ? <p className="text-muted mb-0">Nothing waiting for you. Nice.</p> : <ul className="list-unstyled mb-0">{todo.map((t, i) => <li key={i} className="mb-2"><Link to={t.to}>{t.text}</Link></li>)}</ul>}
          </Card>
          <Card title="Monthly review progress" actions={<Link to="/review" className="small">Open</Link>}>
            <div className="progress mb-1" role="progressbar" aria-label="Rows reviewed" aria-valuenow={o.review.pct} aria-valuemin={0} aria-valuemax={100}><div className="progress-bar bg-success" style={{ width: o.review.pct + "%" }} /></div>
            <div className="small">{o.review.attested} of {o.review.rows} rows in the 3-month window reviewed by their owners ({o.review.pct}%). Due {o.review.due}.</div>
          </Card>
          <Card title="Top quality checks" actions={<Link to="/checks" className="small">All {o.checks.open}</Link>}>
            {o.checks.top.map((f) => <div key={f.id} className="mb-2"><SeverityBadge s={f.severity} /> <span className="small">{f.title}</span></div>)}
            <div className="small text-muted">Last run {o.checks.last_run ? day(o.checks.last_run) : "not yet"}. Checks only read the data. People decide what to change.</div>
          </Card>
        </div>
      </div>
    </Page>
  );
}
