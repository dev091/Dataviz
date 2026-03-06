# Live Launch Playbook

This playbook drives the project from MVP-complete to production-live.

## Gate Status
- Complete in repo: L1-L4, L9-L11
- Still requires real environment execution: L5-L8, L12-L14

## Commercial Boundary
- Implemented in repo:
  - organization-level subscription and entitlement metadata
  - admin API and UI to view/update plan tier, billing email, status, and seat limit
  - self-serve billing provider abstraction with local `log` mode and real Stripe-compatible checkout, portal, and webhook flows
  - audit logging for checkout creation, portal launches, and webhook-driven subscription state changes
- Still requires real environment execution:
  - live Stripe keys and webhook secret in secure deployment config
  - Stripe price objects mapped to production plans
  - real checkout, payment, cancellation, and portal validation in staging/production
- Still outside current repo scope:
  - invoicing and tax automation
  - dunning and card retries
  - proration and complex plan-change billing math

## L5. Staging Provisioning
1. Provision managed PostgreSQL 16 with pgvector enabled.
2. Provision managed Redis 7.
3. Provision object storage bucket for file persistence.
4. Set environment variables in staging secret store:
   - `DATABASE_URL`
   - `REDIS_URL`
   - `STORAGE_ROOT` or storage adapter config
   - `JWT_SECRET_KEY`
   - `OPENAI_API_KEY`
   - `BILLING_PROVIDER`
   - `STRIPE_SECRET_KEY`
   - `STRIPE_WEBHOOK_SECRET`
   - `STRIPE_PRICE_STARTER`
   - `STRIPE_PRICE_GROWTH`
   - `STRIPE_PRICE_ENTERPRISE`

## L6. Secrets and Key Rotation
1. Store all secrets in a secret manager (no plaintext `.env` in deployment runtime).
2. Rotate `JWT_SECRET_KEY` every 90 days.
3. Rotate Stripe webhook secret when regenerating webhook endpoints.
4. Keep `ENFORCE_SECURE_CONFIG=true` in staging/production.

## L7. Live Connector Validation
- Configure:
  - `LIVE_POSTGRES_URI`
  - `LIVE_MYSQL_URI`
  - `LIVE_GOOGLE_SHEETS_CSV_URL`
  - `LIVE_SALESFORCE_USERNAME`
  - `LIVE_SALESFORCE_PASSWORD`
  - `LIVE_SALESFORCE_SECURITY_TOKEN`
- Run:
  - `powershell -ExecutionPolicy Bypass -File infrastructure/scripts/live-connectors.ps1`

## L8. Performance and Load Validation
1. Install load test tool:
   - `pip install -r infrastructure/perf/requirements.txt`
2. Run baseline:
   - `powershell -ExecutionPolicy Bypass -File infrastructure/scripts/load-test.ps1 -Host http://localhost:8000 -Users 50 -SpawnRate 10 -Duration 5m`
3. Track p95 latency, error rate, and throughput.
4. Include billing checkout and admin settings paths in smoke traffic after deploying Stripe config.

## L9. CI/CD and Rollback
- Implemented:
  - `.github/workflows/ci.yml`
  - `.github/workflows/release.yml`
  - `infrastructure/scripts/backend-tests.ps1`
  - `infrastructure/scripts/ci-gates.ps1`
  - Playwright smoke job for admin/commercial and connector setup screens

## L10. Observability
- Implemented:
  - API structured request logging
  - `X-Request-Id` propagation
  - `/metrics` endpoint
  - Prometheus profile in Docker
  - Grafana profile in Docker

## L11. Security Baseline
- Implemented:
  - Runtime security validation (`ENFORCE_SECURE_CONFIG`)
  - API rate limiting
  - Dependency audit workflow (`pip-audit`, `npm audit`)
  - Container scan workflow (Trivy)
  - Audit verification already covered by backend flow tests
  - Stripe webhook signature verification in billing ingest path

## L12. Backup/Restore Drill
1. Backup:
   - `powershell -ExecutionPolicy Bypass -File infrastructure/scripts/backup-postgres.ps1`
2. Restore:
   - `powershell -ExecutionPolicy Bypass -File infrastructure/scripts/restore-postgres.ps1 -BackupFile <path> -ResetSchema`
3. Validate critical API paths post-restore.

## L13. UAT Sign-Off
- Validate complete business flow:
  - Signup -> Connection -> Sync -> Semantic model -> NL query -> Dashboard save -> Alert/schedule -> Audit logs.
- Validate commercial flow:
  - Plan selection -> Checkout -> Webhook update -> Billing portal access.
- Capture sign-off per workspace/tenant.

## L14. Production Cutover
1. Freeze deployments during migration window.
2. Apply `alembic upgrade head`.
3. Start services.
4. Execute smoke checks:
   - `powershell -ExecutionPolicy Bypass -File infrastructure/scripts/cutover-smoke.ps1`
5. Monitor logs/metrics for 60 minutes.
6. If failure, trigger release workflow rollback (`rollback_sha`).
