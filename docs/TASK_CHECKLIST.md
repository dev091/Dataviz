# MVP Task Checklist

Last updated: 2026-03-06

Legend:
- [x] Completed
- [ ] Not completed / needs follow-up

## Operating rule (always enforced)
- [x] Before starting new implementation work, review this checklist and mark current status.
- [x] After each implementation batch, update this checklist with completed and remaining tasks.
- [x] Keep this file as the single source of truth for delivery progress.

## Phase 1: Product and system definition
- [x] 1. PRD
- [x] 2. MVP boundary definition
- [x] 3. High-level architecture
- [x] 4. Monorepo structure
- [x] 5. Domain model
- [x] 6. Database schema
- [x] 7. API surface

## Phase 2: Backend foundation
- [x] 8. FastAPI app structure
- [x] 9. Authentication and tenancy
- [x] 10. Core models and migrations (full Alembic initial schema, startup runs `upgrade head`)
- [x] 11. Connector framework
- [x] 12. Sync job framework
- [x] 13. Semantic layer services
- [x] 14. Dashboards and alerts APIs
- [x] 15. Audit logging
- [x] 16. AI orchestration layer
- [x] 16a. Multi-agent NL orchestration pipeline (planner, safety, SQL, execution, visualization, insight, narrative)
- [x] 16b. Agent trace persisted and returned in NL response
- [x] 16c. Proactive insight agent run in worker schedule

## Phase 3: Frontend foundation
- [x] 17. Next.js app shell
- [x] 18. Auth flows
- [x] 19. Workspace UI
- [x] 20. Connections UI
- [x] 21. Dataset catalog UI
- [x] 22. Semantic model editor UI
- [x] 23. Dashboard builder UI
- [x] 24. NL analytics UI
- [x] 25. Alerts/admin UI
- [x] 25a. Agent trace visibility in NL analytics screen

## Phase 4: Working product flows
- [x] 26. Connect source and sync metadata
- [x] 27. Create semantic model
- [x] 28. Ask a natural language question
- [x] 29. Render chart and summary
- [x] 30. Save to dashboard
- [x] 31. Schedule report
- [x] 32. Create alert
- [x] 33. Produce audit events

## Phase 5: Quality and packaging
- [x] 34. Seed data
- [x] 35. Tests (backend flow + frontend smoke + semantic SQL builder + report delivery + live connector integration suite + runtime hardening + subscription admin + billing flow coverage)
- [x] 36. Dockerized local setup
- [x] 37. Docs
- [x] 38. Final run instructions

## Definition of Done tracking
- [x] 1. User signs up and creates an organization
- [x] 2. User adds a data connection
- [x] 3. System discovers schema and syncs metadata
- [x] 4. User defines at least one metric and one dimension in semantic model
- [x] 5. User asks a natural-language business question
- [x] 6. System returns a chart and summary
- [x] 7. User saves result to a dashboard
- [x] 8. User creates scheduled report or alert
- [x] 9. System records audit logs for critical actions
- [x] 10. Repository can be started with documented local steps

## Hardening follow-ups
- [x] Resolve `next build` EPERM in this local environment (in-process worker build shim)
- [x] Replace no-op Alembic with full migration scripts for strict production rollout
- [x] Add real SMTP email provider integration for report delivery
- [x] Expand semantic planner to robust multi-join SQL planning
- [x] Add deeper connector integration tests for live PostgreSQL/MySQL/Sheets/Salesforce environments (env-gated)
- [x] Replace deprecated FastAPI startup event hooks with lifespan handlers
- [x] Add runtime observability (`/metrics`, structured request logs, request IDs)
- [x] Add baseline runtime security controls (startup config validation, rate limiting)
- [x] Add organization subscription and entitlement scaffold for commercial readiness
- [x] Upgrade connection setup UX from raw JSON to typed connector-specific forms
- [x] Add self-serve billing provider abstraction with Stripe-compatible checkout, portal, and webhook support
- [x] Expand workspace audit visibility to include organization-level commercial events
- [x] Add Playwright smoke coverage for admin billing and typed connector setup screens

## Validation snapshot
- [x] Backend module matrix -> passed in slices (`test_admin_subscription.py`: 1 passed; `test_billing.py`: 2 passed; `test_core_flow.py` + `test_report_delivery.py`: 2 passed; `test_semantic_sql_builder.py` + `test_runtime_hardening.py`: 5 passed; `test_connectors_live.py`: 4 skipped env-gated)
- [x] `npm --workspace apps/web exec tsc --noEmit` -> passed
- [x] `npm --workspace apps/web run build` -> passed
- [x] `npm --workspace apps/web run test:e2e -- --workers=1` -> passed (4 Playwright smoke tests)
- [ ] `docker compose` smoke was not rerun in this shell because Docker CLI is not available in PATH here

## Current Delivery Status
- [x] All required MVP tasks (Phases 1-5 and Definition of Done) are complete.
- [x] Multi-agent architecture is implemented and active in NL analytics flow.
- [x] Production-live foundation artifacts are implemented in-repo for CI/CD, observability, security scans, backup/restore scripts, cutover workflow, and self-serve commercial subscription scaffolding.

## Remaining (Post-MVP / Production Readiness)
- [ ] Provision staging environment with managed Postgres/Redis and persistent object storage.
- [ ] Configure production secret management and JWT/key rotation policy in the real deployment environment.
- [ ] Configure live Stripe keys, webhook endpoint, and production plan price IDs in the deployment environment.
- [ ] Execute live connector validation in staging with real PostgreSQL/MySQL/Google Sheets/Salesforce credentials.
- [ ] Execute real self-serve billing validation in staging (checkout -> webhook -> portal -> cancel/update).
- [ ] Run load/performance tests on sync, NL query, dashboard, and worker paths against non-trivial datasets.
- [ ] Execute backup/restore drill, pilot tenant UAT, and production cutover in a real environment.

## Live Launch Checklist (Target: 100% Live)
- [x] L1. Local dockerized stack boots end-to-end (API, worker, web, Postgres, Redis, MailHog).
- [x] L2. DB migrations run automatically and schema is reproducible.
- [x] L3. Core automated checks pass locally (backend matrix + frontend typecheck/build).
- [x] L4. Runbook documents local setup and critical flows.
- [ ] L5. Provision staging environment with managed Postgres/Redis and persistent object storage.
- [ ] L6. Configure production-grade secrets management and key rotation policy.
- [ ] L7. Run live connector validation in staging with real PostgreSQL/MySQL/Google Sheets/Salesforce credentials.
- [ ] L8. Execute load/performance test suite for sync, NL query, dashboard rendering, and worker throughput.
- [x] L9. Add CI/CD gates (tests/typecheck/build/docker smoke) and deployment pipeline with rollback strategy.
- [x] L10. Add observability stack (structured logs, metrics, traces, alerting dashboards).
- [x] L11. Complete security hardening baseline (dependency scan, container scan, auth/rate-limit review, audit verification, webhook signature checks).
- [ ] L12. Run backup/restore drill and failover recovery rehearsal.
- [ ] L13. Perform UAT with pilot tenant and capture acceptance sign-off.
- [ ] L14. Production cutover checklist (DNS/TLS, env config, migration window, smoke verification) executed.

