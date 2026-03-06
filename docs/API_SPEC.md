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
- `POST /connections/csv/upload`
- `POST /connections/{id}/discover`
- `POST /connections/{id}/sync`
- `GET /connections/{id}/sync-runs`
- `POST /connections/{id}/sync-jobs`

## Semantic Layer
- `GET /semantic/datasets`
- `GET /semantic/models`
- `GET /semantic/models/{id}/metrics`
- `GET /semantic/models/{id}/versions`
- `POST /semantic/models/validate`
- `POST /semantic/models`

## Dashboards
- `GET /dashboards`
- `POST /dashboards`
- `GET /dashboards/{id}`
- `PUT /dashboards/{id}`
- `POST /dashboards/{id}/widgets`
- `POST /dashboards/{id}/widgets/from-ai`
- `GET /dashboards/{id}/executive-summary`

## NL Analytics
- `POST /nl/query`
  - Returns `plan`, `agent_trace`, `sql`, `rows`, `chart`, `summary`, `insights`, and `follow_up_questions`
  - SQL is generated through semantic model context with join-safe planning (no raw freeform SQL execution)

## Alerts & Scheduling
- `POST /alerts/report-schedules`
- `GET /alerts/report-schedules`
- `POST /alerts/rules`
- `GET /alerts/rules`
- `POST /alerts/rules/{id}/evaluate`
- `GET /alerts/events`
- Report delivery outcomes are persisted in audit logs (`report_schedule.delivered`, `report_schedule.delivery_failed`)

## Admin & Governance
- `GET /admin/usage`
- `GET /admin/audit-logs`
  - Includes workspace-scoped audit events plus organization-level billing/governance events for the current workspace's tenant
- `GET /admin/insights`
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
