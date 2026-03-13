# API Specification

Base prefix: `/api/v1`

## Platform Endpoints
- `GET /health`
- `GET /metrics`

## Auth
- `POST /auth/signup`
- `POST /auth/login`
- `POST /auth/refresh`
- `GET /auth/me`

## Workspaces
- `GET /workspaces`
- `POST /workspaces`

## Connections
- `GET /connections`
- `POST /connections`
- `POST /connections/files/upload`
  - Accepts common structured analyst file formats: CSV, TSV, TXT, JSON, JSONL/NDJSON, Excel (`.xlsx`, `.xls`), ODS, Parquet, and XML
- `POST /connections/csv/upload`
  - Backward-compatible alias for the broader file upload endpoint
- `POST /connections/{id}/discover`
  - Includes retry metadata in `meta.retry`
- `POST /connections/{id}/sync`
- `GET /connections/{id}/sync-runs`
  - Sync logs include retry metadata when connector retries occur
- `POST /connections/{id}/sync-jobs`

## Semantic Layer
- `GET /semantic/datasets`
  - Returns dataset catalog entries with `quality_status`, `quality_profile`, field-level quality signals, and cleaned sync metadata
- `GET /semantic/datasets/{id}/prep-plan`
  - Returns reversible cleaning steps, join and union suggestions, calculated-field suggestions, transformation lineage, and autopilot notes for the selected dataset
- `POST /semantic/datasets/{id}/prep-feedback`
  - Captures analyst approval or rejection on a prep step and updates feedback counts used to influence future recommendations
- `POST /semantic/datasets/{id}/prep-actions`
  - Applies or rolls back a reversible prep step in governed autopilot history without mutating the raw synced table
- `GET /semantic/models`
- `POST /semantic/models/draft`
  - Generates an AI-ready semantic draft from a synced dataset with inferred metrics, dimensions, calculated fields, and modeling notes
- `GET /semantic/models/{id}`
  - Returns joins, metrics, dimensions, calculated fields, governance metadata, metric certification notes, and metric lineage for full semantic model inspection
- `GET /semantic/models/{id}/trust-panel`
  - Returns semantic governance status, lineage summary including metric-lineage coverage, recent trust activity, and open trust gaps for the selected model
- `GET /semantic/models/{id}/metrics`
- `GET /semantic/models/{id}/versions`
- `POST /semantic/models/validate`
- `POST /semantic/models`

## Onboarding and Migration
- `GET /onboarding/launch-packs`
  - Returns the available executive launch-pack templates for Finance, RevOps, Operations, and Leadership workflows
- `POST /onboarding/launch-packs/provision`
  - Provisions a template-driven executive dashboard, AI report pack, suggested alert watchlist, and optional first recurring schedule from a governed semantic model
- `GET /onboarding/launch-packs/{template_id}/playbook`
  - Returns an onboarding readiness score, KPI validation checklist, milestones, stakeholders, and adoption signals for the selected launch pack and semantic model

- `POST /onboarding/migration-assistant/import-workbook`
  - Accepts Tableau workbook uploads (`.twb`, `.twbx`) plus JSON-style Power BI, Domo, and generic BI bundle manifests and extracts dashboards, reports, KPI definitions, and benchmark-ready metadata
- `POST /onboarding/migration-assistant/analyze`
  - Maps incumbent BI dashboard, report, KPI, and dimension names to the governed semantic layer and returns trust-validation guidance plus launch-pack recommendations
- `POST /onboarding/migration-assistant/bootstrap`
  - Uses the migration analysis to provision a governed replacement dashboard, AI report pack, suggested alert watchlist, and optional first recurring schedule
- `POST /onboarding/migration-assistant/review-kpis`
  - Builds a certification review plan for imported KPI definitions with readiness scoring, blockers, suggested synonyms, benchmark evidence, and lineage preview before promotion
- `POST /onboarding/migration-assistant/promote-kpis`
  - Promotes imported KPI definitions into a new governed semantic model version, reusing existing governed matches when possible, persisting certification metadata and lineage, and auditing every promotion result

## Dashboards
- `GET /dashboards`
- `POST /dashboards`
- `GET /dashboards/{id}`
- `PUT /dashboards/{id}`
- `POST /dashboards/{id}/widgets`
- `PUT /dashboards/{id}/widgets/{widget_id}`
- `DELETE /dashboards/{id}/widgets/{widget_id}`
- `POST /dashboards/{id}/widgets/from-ai`
- `POST /dashboards/{id}/auto-compose`
  - Auto-generates a governed dashboard layout from a semantic model with KPI, trend, mix, scatter, and detail widgets
- `POST /dashboards/{id}/report-pack`
  - Generates an executive-ready AI report pack from the current dashboard state, including summary sections and suggested next actions
- `GET /dashboards/{id}/executive-summary`

## NL Analytics
- `POST /nl/query`
  - Returns `plan`, `agent_trace`, `sql`, `rows`, `chart`, `summary`, `insights`, `follow_up_questions`, and `related_queries`
  - SQL is generated through semantic model context with join-safe planning (no raw freeform SQL execution)
  - NL queries persist embeddings and reuse the nearest prior analyses through pgvector on PostgreSQL with deterministic fallback on SQLite

## Alerts & Scheduling
- `POST /alerts/report-schedules`
- `GET /alerts/report-schedules`
- `GET /alerts/delivery-logs`
  - Returns delivered/failed report runs with provider metadata, recipients, dashboard linkage, and timestamps
- `POST /alerts/rules`
- `GET /alerts/rules`
- `POST /alerts/rules/{id}/evaluate`
- `GET /alerts/events`
- `GET /alerts/proactive-insights`
  - Returns proactive pacing, freshness, anomaly, and trend-break artifacts with audience routing, investigation paths, suggested actions, and escalation guidance
- `GET /alerts/proactive-digest`
  - Returns an audience-aware proactive digest with summary, recommended recipients, suggested actions, top insights, and escalation policies
- `POST /alerts/proactive-insights/run`
  - Manually triggers the proactive monitoring sweep for the current workspace
- Report delivery outcomes are persisted in audit logs (`report_schedule.delivered`, `report_schedule.delivery_failed`)

## Admin & Governance
- `GET /admin/usage`
- `GET /admin/audit-logs`
  - Includes workspace-scoped audit events plus organization-level billing/governance events for the current workspace's tenant
- `GET /admin/insights`
- `GET /admin/ai-trust-history`
  - Returns a unified trust timeline for NL prompts, report-pack generations, dashboard auto-compose actions, and proactive artifacts with trust-signal labels
- `GET /admin/subscription`
- `PUT /admin/subscription`
  - Returns organization commercial state, provider linkage, entitlements, trial state, and self-serve billing capability flags

## Billing
- `POST /billing/checkout-session`
  - Owner-only endpoint to create a self-serve subscription checkout session for `starter`, `growth`, or `enterprise`
  - Uses provider abstraction (`log` in local/dev, `stripe` for real checkout)
- `POST /billing/portal-session`
  - Owner-only endpoint to open the customer billing portal for subscription management
- `POST /billing/webhooks/stripe`
  - Public endpoint that validates Stripe signature headers and updates subscription state from safe, mapped webhook events

## Headers
- `Authorization: Bearer <access_token>` for protected endpoints
- `X-Workspace-Id: <workspace_uuid>` for workspace-scoped endpoints
- `X-Request-Id` is accepted and echoed by API responses

## Runtime Safety and Limits
- Startup security validation checks JWT key quality, auth settings, and billing secret completeness when Stripe is enabled
- Rate limiting returns HTTP `429` with `Retry-After` when threshold is exceeded
- Billing webhooks are verified against `STRIPE_WEBHOOK_SECRET` before any subscription state is mutated
- Storage backend is selected through `STORAGE_BACKEND`; local development uses filesystem storage and the service boundary is ready for alternate adapters












