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
Note: this Codex shell still blocks Playwright worker spawning with `EPERM`, so local UI validation here was limited to TypeScript/build checks plus spec collection logic and CI wiring.

## Multi-Agent Architecture Runtime
- Query agents execute for each NL request:
  - planner -> safety -> sql -> execution -> visualization -> insight -> narrative
- Agent trace is returned in `/api/v1/nl/query`
- Proactive insight agent runs hourly in worker beat schedule

## Semantic Multi-Join Planning
- SQL is generated through semantic query planning only
- Join traversal resolves paths from base dataset alias to required aliases
- Filters are validated against allowed dimensions/operators before SQL generation

## Runtime Security Controls
- Startup security validation warns or blocks startup in staging/production depending on `ENFORCE_SECURE_CONFIG`
- Default per-client rate limiting middleware enabled with `RATE_LIMIT_REQUESTS_PER_MINUTE`
- Request IDs are propagated via `X-Request-Id`
- When `BILLING_PROVIDER=stripe`, startup validates that Stripe secret and plan price IDs are configured

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

## Load and Security Scans
- Install perf dependencies:
  - `pip install -r infrastructure/perf/requirements.txt`
- Run load test:
  - `powershell -ExecutionPolicy Bypass -File infrastructure/scripts/load-test.ps1 -Host http://localhost:8000 -Users 50 -SpawnRate 10 -Duration 5m`
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
- Commercial state: `GET /api/v1/admin/subscription`

## Common Issues
- Missing Python 3.12: install Python and ensure PATH
- SQL connection errors: verify `DATABASE_URL`
- Connector discovery errors: validate connector config payloads
- Empty dashboards: run sync and create semantic model before NL query
- Security warning at startup: set strong `JWT_SECRET_KEY` and tune auth settings
- Stripe webhook rejected: verify `STRIPE_WEBHOOK_SECRET` and inbound signature header
- Docker unavailable in PATH: install Docker Desktop or add Docker CLI to PATH before smoke checks
