# Runbook

## Prerequisites
- Docker + Docker Compose
- Node.js 20+
- Python 3.12 (for non-docker local mode)

## Workflow Rule
- Before each implementation iteration, review [docs/TASK_CHECKLIST.md](docs/TASK_CHECKLIST.md)
- After each iteration, update checkboxes for completed and remaining work

## Quick Start (Docker)
1. `docker compose up --build`
2. API docs: `http://localhost:8000/docs`
3. Web app: `http://localhost:3000`
4. MailHog: `http://localhost:8025`

## Optional Observability Stack
1. `docker compose --profile observability up -d`
2. Prometheus: `http://localhost:9090`
3. Grafana: `http://localhost:3001` (admin/admin)
4. API metrics endpoint: `http://localhost:8000/metrics`

## Local Development (without Docker)
1. Start services:
   - PostgreSQL on `localhost:5432`
   - Redis on `localhost:6379`
2. Install web deps:
   - `npm install`
3. Install API deps:
   - `pip install -r apps/api/requirements.txt`
   - `pip install -e packages/connectors -e packages/semantic -e packages/analytics`
4. Set env from `apps/api/.env.example`
5. Start API:
   - `uvicorn app.main:app --reload --app-dir apps/api`
   - Startup automatically runs `alembic upgrade head`
6. Seed demo:
   - `python apps/api/app/db/seed.py`
7. Start worker:
   - `celery -A worker.celery_app worker --beat --loglevel=info --workdir apps/worker`
8. Start web:
   - `npm run dev --workspace apps/web`

## Build and Validation
- Backend matrix: `powershell -ExecutionPolicy Bypass -File infrastructure/scripts/backend-tests.ps1`
- Frontend type-check: `npm --workspace apps/web exec tsc --noEmit`
- Frontend production build: `npm --workspace apps/web run build`
- Frontend Playwright smoke: `npm --workspace apps/web run test:e2e`
- Combined gate: `powershell -ExecutionPolicy Bypass -File infrastructure/scripts/ci-gates.ps1`

Note: web build uses an in-process Next worker shim (`apps/web/scripts/next-inprocess-worker-shim.js`) to avoid Windows `spawn EPERM` failures in restricted environments.
Note: in restricted shells, Playwright may still need to run outside the sandbox; the latest smoke suite passed in unrestricted mode against the current build.


## Local File Upload Support
- Supported upload formats: `.csv`, `.tsv`, `.txt`, `.json`, `.jsonl`, `.ndjson`, `.xlsx`, `.xls`, `.ods`, `.parquet`, `.xml`
- Upload endpoint: `POST /api/v1/connections/files/upload`
- Backward-compatible alias: `POST /api/v1/connections/csv/upload`
- Spreadsheet uploads create one dataset per sheet by default; set `sheet_name` in the connector config to target a specific tab
- Dataset catalog entries surface ingestion quality score, completeness, duplicate ratio, cleaning impact, and field-level warnings after sync

## AI Data Prep Autopilot
- Dataset catalog now includes an `AI Data Prep Autopilot` panel for the active dataset
- UI route: `/datasets`
- API endpoints:
  - `GET /api/v1/semantic/datasets/{dataset_id}/prep-plan`
  - `POST /api/v1/semantic/datasets/{dataset_id}/prep-feedback`
- The plan surfaces reversible cleaning steps, join suggestions, union suggestions, calculated field suggestions, and ingestion lineage
- Approval or rejection feedback is written to audit logs and influences future recommendation confidence for the same dataset and prep step
- Apply or rollback endpoint: `POST /api/v1/semantic/datasets/{dataset_id}/prep-actions`
- Applied steps are tracked in governed autopilot lineage while raw synced tables remain unchanged until promoted downstream

## Launch Packs
- Dashboard home includes a `First Executive Pack Fast` flow for Finance, RevOps, Operations, and Leadership packs
- Requires an existing semantic model in the selected workspace
- API endpoints:
  - `GET /api/v1/onboarding/launch-packs`
  - `POST /api/v1/onboarding/launch-packs/provision`
- Provisioning creates a governed dashboard, auto-composed widgets, AI report pack, suggested alert watchlist, and optional first recurring report schedule

## Migration Assistant
- UI route: `/migration`
- Supports Tableau, Power BI, Domo, and generic BI asset bundles entered as dashboard names, report names, KPI names, and dimension names
- Requires an existing semantic model in the selected workspace
- Analyze endpoint: `POST /api/v1/onboarding/migration-assistant/analyze`
- Bootstrap endpoint: `POST /api/v1/onboarding/migration-assistant/bootstrap`
- The assistant returns KPI and dimension matches, launch-pack recommendations, trust-validation checks, and can provision a governed migration pack with a report schedule

## Multi-Agent Architecture Runtime
- Query agents execute for each NL request:
  - planner -> safety -> sql -> execution -> visualization -> insight -> narrative
- Agent trace is returned in `/api/v1/nl/query`
- Dashboard builder supports auto-composition from a semantic model plus raw custom ECharts options for highly customized widget layouts
- Dashboard builder can generate an AI report pack from the current dashboard with executive summary sections and suggested next actions
- Proactive insight agent runs hourly in worker beat schedule
- Alerts UI includes a `Proactive intelligence` section with manual sweep, proactive digest generation, audience routing, suggested actions, escalation guidance, and investigation paths
- API endpoints: `GET /api/v1/alerts/proactive-insights`, `GET /api/v1/alerts/proactive-digest`, `POST /api/v1/alerts/proactive-insights/run`

## Semantic Multi-Join Planning
- SQL is generated through semantic query planning only
- Join traversal resolves paths from base dataset alias to required aliases
- Filters are validated against allowed dimensions/operators before SQL generation

## Semantic Governance and Trust
- Semantic editor route: `/semantic`
- Semantic editor now captures model governance, metric synonyms, metric ownership, dimension hierarchies, and certification controls
- Trust panel endpoint: `GET /api/v1/semantic/models/{semantic_model_id}/trust-panel`
- Detail endpoint: `GET /api/v1/semantic/models/{semantic_model_id}`
- Use the trust panel to review owner assignment, certification note, lineage summary, recent audit and NL activity, and open governance gaps before exposing a model broadly
- Admin settings now include an `AI Trust History` timeline for recent NL prompts, report-pack generations, and proactive artifacts with trust-signal labels

## Runtime Security Controls
- Startup security validation warns or blocks startup in staging/production depending on `ENFORCE_SECURE_CONFIG`
- Default per-client rate limiting middleware enabled with `RATE_LIMIT_REQUESTS_PER_MINUTE`
- Request IDs are propagated via `X-Request-Id`
- When `BILLING_PROVIDER=stripe`, startup validates that Stripe secret and plan price IDs are configured


## AI Provider Configuration
- Set `AI_PROVIDER=openai`
- Set `OPENAI_API_KEY` to an API credential for your OpenAI-compatible provider
- Set `OPENAI_MODEL` to a supported model available to your account, for example `gpt-5.4`
- Optional: set `OPENAI_BASE_URL` for OpenAI-compatible gateways
- The backend uses API-based provider auth. Consumer ChatGPT sign-in or ChatGPT-account OAuth is not the runtime auth mechanism for this service.
## Self-Serve Billing
- Provider abstraction supports:
  - `log` provider for local/dev checkout and portal simulation
  - `stripe` provider for real subscription checkout, customer portal, and webhook-driven state sync
- Required Stripe env vars:
  - `BILLING_PROVIDER=stripe`
  - `STRIPE_SECRET_KEY`
  - `STRIPE_WEBHOOK_SECRET`
  - `STRIPE_PRICE_STARTER`
  - `STRIPE_PRICE_GROWTH`
  - `STRIPE_PRICE_ENTERPRISE`
- Core commercial endpoints:
  - `POST /api/v1/billing/checkout-session`
  - `POST /api/v1/billing/portal-session`
  - `POST /api/v1/billing/webhooks/stripe`

## Email Delivery
- Provider abstraction supports:
  - `log` provider (default local mode)
  - `smtp` provider (Docker uses MailHog)
- Worker writes delivery success/failure into audit logs:
  - `report_schedule.delivered`
  - `report_schedule.delivery_failed`

## Live Connector Integration Tests (env-gated)
- `LIVE_POSTGRES_URI`
- `LIVE_MYSQL_URI`
- `LIVE_GOOGLE_SHEETS_CSV_URL`
- `LIVE_SALESFORCE_USERNAME`
- `LIVE_SALESFORCE_PASSWORD`
- `LIVE_SALESFORCE_SECURITY_TOKEN`
- Optional: `LIVE_SALESFORCE_DOMAIN`, `LIVE_SALESFORCE_OBJECT`

Run:
- `pytest apps/api/tests/test_connectors_live.py -q`
- `powershell -ExecutionPolicy Bypass -File infrastructure/scripts/live-connectors.ps1`

## Launch Verification
- Run combined operational verification:
  - `powershell -ExecutionPolicy Bypass -File infrastructure/scripts/ops-verify.ps1 -ApiBase http://localhost:8000 -WebBase http://localhost:3000 -Email owner@dataviz.com -Password Password123! -IncludeBilling -IncludeLoad -LoadUsers 5 -LoadSpawnRate 2 -LoadDuration 30s`
- Verification evidence is written under `infrastructure/tmp/ops-verify`.

## Load and Security Scans
- Install perf dependencies:
  - `pip install -r infrastructure/perf/requirements.txt`
- Run load test:
  - `powershell -ExecutionPolicy Bypass -File infrastructure/scripts/load-test.ps1 -ApiBase http://localhost:8000 -Users 50 -SpawnRate 10 -Duration 5m`
- Run dependency and container security scans in CI:
  - `.github/workflows/security.yml`
- Run local dependency scan:
  - `powershell -ExecutionPolicy Bypass -File infrastructure/scripts/security-scan.ps1 -InstallTools`

## Backup and Restore
- Backup PostgreSQL:
  - `powershell -ExecutionPolicy Bypass -File infrastructure/scripts/backup-postgres.ps1`
- Restore PostgreSQL:
  - `powershell -ExecutionPolicy Bypass -File infrastructure/scripts/restore-postgres.ps1 -BackupFile <path> -ResetSchema`

## Cutover Smoke
- `powershell -ExecutionPolicy Bypass -File infrastructure/scripts/cutover-smoke.ps1`

## Demo Credentials
- Email: `owner@dataviz.com`
- Password: `Password123!`

## Operational Checks
- Health: `GET /health`
- Metrics: `GET /metrics`
- Audit trail: `GET /api/v1/admin/audit-logs`
- Sync status: `GET /api/v1/connections/{id}/sync-runs`
- Recent insights: `GET /api/v1/admin/insights`
- AI trust history: `GET /api/v1/admin/ai-trust-history`
- Commercial state: `GET /api/v1/admin/subscription`

## Common Issues
- Missing Python 3.12: install Python and ensure PATH
- SQL connection errors: verify `DATABASE_URL`
- Connector discovery errors: validate connector config payloads
- Empty dashboards: run sync and create semantic model before NL query
- Security warning at startup: set strong `JWT_SECRET_KEY` and tune auth settings
- Stripe webhook rejected: verify `STRIPE_WEBHOOK_SECRET` and inbound signature header
- Docker unavailable in PATH: install Docker Desktop or add Docker CLI to PATH before smoke checks





