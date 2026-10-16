# The Chosen One

A secure web application that replaces the "Chosen One" revenue-forecast spreadsheet. It keeps every customer project and its monthly revenue in a database, controls who can edit what, records every change, checks the data for mistakes, takes monthly snapshots, and shows committed, weighted (HubSpot pipeline) and total forecast side by side.

Stack: FastAPI, SQLAlchemy 2, Alembic, PostgreSQL (SQLite for local use), React, TypeScript, Vite, Bootstrap, AG Grid Community, Chart.js, openpyxl.

## What this app does

Sign in, then use the menu on the left: Overview, Forecast, Monthly review, Pipeline, Quality checks, Insights, Snapshots, History and (for Admins) Admin.

Numbers shown as **Committed** are signed work at 100%. **Weighted** is open HubSpot pipeline (amount x stage probability, spread over the months of the project). **Total** is both together. A deal is never counted in both.

How to use it, by role:

- **Client Partner.** Open Forecast, filter to your accounts, click a month and type a number. Only plain non-negative numbers are accepted (no formulas, no text). Review the pending edits and save; every edit records who, when, old and new value. Each month, use Monthly review to confirm your rows in the next three months. Add extensions (EE/EN) with "New project"; the app warns if a similar project already exists.
- **Seller.** Open Pipeline to see your HubSpot deals as weighted forecast. Change the monthly phasing of a deal if you know the start date differs. When a deal is Closed Won, a draft project appears for you; check the monthly schedule and confirm it. The weighted line then disappears.
- **Commercial Owner.** Keep start dates, phasing and change orders current on your signed projects. Work through Quality checks assigned to you: accept or dismiss each with a reason. The checks never change data; you do. Attest your rows in Monthly review.
- **Sales leadership / CRO.** Overview and Forecast show committed, weighted and total by month; filter by owner, practice, region, industry, category or customer. History shows every change. Quality checks lists what to fix before a forecast call, and "Ask about the forecast" answers plain-language questions. You can edit any row.
- **Finance.** Snapshots: take a snapshot on demand, download any snapshot or the current view as Excel or CSV, and upload monthly actuals. Insights > Accuracy compares each month to the forecast taken 1, 2 and 3 months earlier and flags anything outside plus or minus 5%.
- **Resourcing.** Read-only. Use Forecast and Insights, filtered by practice and month, to see upcoming demand.
- **Admin.** Admin screen: add or deactivate users and set roles, maintain reason codes and reference lists, set the forecast stage and stage probabilities, run a HubSpot sync, see sync and job history.

## Run it locally

Requires Python 3.12+ and Node 20+.

1. `cp .env.example backend/.env` (the sample works as is: demo sign-in, sample data dated 2026-10-01).
2. `cd backend && python -m venv .venv && source .venv/bin/activate && pip install -e . pytest ruff`
3. `cd ../frontend && npm install && npm run build` (use `npm run dev` instead for live reload on port 5173; it proxies /api to port 8000).
4. `cd ../backend && uvicorn app.main:app --port 8000` (the database is created, migrated and loaded with sample data on first start).
5. Open http://localhost:8000 and pick a person (try CRO, or AC for a Client Partner, or ADM for Admin).

Tests and checks: `cd backend && pytest && ruff check .`; `cd frontend && npm test && npm run build`.
Docker: `docker compose up --build` runs the app with PostgreSQL on port 8000.

Scheduled jobs (each is a plain command, run from `backend/`):

- `python -m app.jobs.sync_hubspot` (hourly)
- `python -m app.jobs.nightly_checks` (nightly)
- `python -m app.jobs.monthly_snapshot` (daily; it only acts on the first business day, or use `--force`)
- `python -m app.jobs.import_sheet FILE.xlsx [--commit]` (one-time sheet import; shows rejects and totals only unless `--commit` is given)

## Deploy to Railway

1. Push this repo to GitHub. In Railway create a project, add a **PostgreSQL** database, then add a service from the GitHub repo (it builds the `Dockerfile` via `railway.json`).
2. In the app service Variables set `APP_ENV=production`, `DATABASE_URL` (reference the Postgres variable), `SECRET_KEY` (long random), `BASE_URL` (the public https address), `AUTH_MODE=google`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_HOSTED_DOMAIN`, `BOOTSTRAP_ADMIN_EMAIL` (your own address, so you can sign in first).
3. In Google Cloud create an OAuth client (Internal) with redirect address `BASE_URL/api/auth/callback`.
4. Optional: `HUBSPOT_TOKEN` (read-only private app), `ANTHROPIC_API_KEY`. Leave `SEED_ON_STARTUP=false` and `AS_OF_DATE` empty for real data; then import the sheet with the import job.
5. Add three Railway cron services using the same image and these start commands: `python -m app.jobs.sync_hubspot` (`0 * * * *`), `python -m app.jobs.nightly_checks` (`0 6 * * *`), `python -m app.jobs.monthly_snapshot` (`0 7 * * *`). The health check is `/api/health`. Migrations run automatically on start.

The app refuses to start in production with demo sign-in or the default secret.

## Settings

| Variable | Purpose | Default |
|---|---|---|
| APP_ENV | local, development or production | local |
| DATABASE_URL | Database address (SQLite file or PostgreSQL) | local SQLite file |
| SECRET_KEY | Signs login cookies; required in production | dev value |
| BASE_URL | Public address of the app | http://localhost:8000 |
| AUTH_MODE | demo or google (demo only by default when local) | demo local, google otherwise |
| ALLOW_DEMO_AUTH_IN_PRODUCTION | Escape hatch for demos | false |
| GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET | Google sign-in | empty |
| GOOGLE_HOSTED_DOMAIN | Restrict to a Workspace domain | empty |
| BOOTSTRAP_ADMIN_EMAIL | Creates this person as Admin | empty |
| AS_OF_DATE | Fixes "today" (sample data is 2026-10-01) | today |
| SEED_ON_STARTUP | Load sample data into an empty database | true |
| HUBSPOT_TOKEN | Read-only token; empty uses sample deals | empty |
| HUBSPOT_PIPELINE_ID, HUBSPOT_PROP_* | Which pipeline and which deal properties to read | see .env.example |
| SYNC_STALE_MINUTES | Minutes before the "sync is stale" banner | 120 |
| ANTHROPIC_API_KEY | Enables Claude for Ask; empty uses built-in answers | empty |
| ANTHROPIC_MODEL | Claude model name | claude-sonnet-4-5 |
| AI_MONTHLY_COST_CEILING_USD | Stops Claude calls above this monthly cost | 250 |

## Requirement traceability

| FR | Status | Where |
|---|---|---|
| FR-01 Google sign-in, only provisioned users | Implemented, not tested against live Google | api/auth.py |
| FR-02 Edit rights by owner, leadership and Admin | Implemented and tested | engine.py, test_forecast_api |
| FR-03 Project fields | Implemented | models.py |
| FR-04 Month grid, edit, filter, sort, subtotals | Implemented | ForecastGrid.tsx |
| FR-05 Numbers only, no formulas or negatives | Implemented and tested | engine.parse_value |
| FR-06 One-time sheet import with reject list | Implemented, dry run by default; tested | services/importer.py |
| FR-07 HubSpot sync hourly and on demand | Implemented; live HubSpot untested (sample deals used) | hubspot_sync.py |
| FR-08 Weighted values | Implemented and tested | engine.weighted_lines |
| FR-09 Closed Won creates a draft, owner confirms | Implemented and tested. Owner notification is on screen only, no email | engine.sync_drafts |
| FR-10 Lost or below-stage removed and logged | Implemented and tested | hubspot_sync.py |
| FR-11 No double counting | Implemented and tested (unique Deal ID) | models.py |
| FR-12 Committed, weighted, total with filters | Implemented | Overview, Forecast |
| FR-13 Full audit and per-row history | Implemented and tested | change_log |
| FR-14 Immutable snapshots, first business day and on demand | Implemented and tested | monthly_snapshot job |
| FR-15 Export xlsx and csv with timestamp and filters | Implemented and tested | exports.py |
| FR-16 Actuals upload and M-1/M-2/M-3 variance | Implemented | services/actuals.py |
| FR-17 Nightly and on-demand checks | Implemented as fixed rules. The HubSpot amount mismatch check exists but is off by default | engine.run_checks |
| FR-18 Findings with evidence, human accept or dismiss, no data changes | Implemented and tested. Routing is by owner filter on screen, no email | checks.py |
| FR-19 Duplicate warning on create | Implemented and tested | engine.find_duplicates |
| FR-20 Attestation by owner | Implemented | MonthlyReview.tsx |
| FR-21 Phasing override | Implemented | Pipeline.tsx |
| FR-22 Demand by practice and month | Implemented as Insights view | Insights.tsx |
| FR-23 Admin screens | Implemented; not visually tested end to end | Admin.tsx |
| FR-24 Ask with citations | Implemented; built-in answers always work, Claude only with a key (untested live) | services/ai.py |

## Known gaps

- No email or Slack notifications. Alerts appear in the app only.
- Live HubSpot and live Google sign-in were not tested here; sample deals and demo sign-in were.
- PostgreSQL and the Docker build were not run in the build environment (SQLite was).
- The sample data has no "Alberta Blue Cross - SRH Go Get" row, so that exact FR-19 example is not demonstrable; the duplicate rule is tested with other rows.
- Performance targets (1,000 projects, p95) were not measured.
- Encryption at rest, backups and MFA are provided by the hosting and Google, not by this code.
- The front-end bundle is large (about 1.4 MB) and not split.
