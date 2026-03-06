# PRD: AI-Native Autonomous Analytics Platform MVP

## Vision
Deliver a premium multi-tenant analytics SaaS that combines governed semantic modeling, dashboards, and AI-native analysis workflows for business teams.

## Problem
Traditional BI tools force teams to choose between governance and speed. Business users need trusted metrics, faster answers, and proactive insighting without losing control.

## Target Users
- Executive stakeholders (Viewer)
- Business analysts (Analyst)
- Data/BI admins (Admin)
- Workspace owners (Owner)

## Core MVP Outcomes
1. Sign up user and create organization/workspace
2. Connect data and sync metadata/data
3. Define semantic model (metrics + dimensions)
4. Query via natural language through semantic layer
5. Render chart and summary
6. Save AI result to dashboard widget
7. Create report schedule and alert rule
8. Capture audit events for critical operations

## Functional Scope
### In Scope
- JWT auth (access/refresh), RBAC, tenant isolation
- Connectors: PostgreSQL, MySQL, CSV, Google Sheets, Salesforce
- Connector discovery, preview, manual sync, scheduled sync jobs, sync run logs
- Dataset catalog and field typing
- Semantic model editor with versioning and validation
- Dashboard CRUD and widget save-from-AI
- NL analytics pipeline: plan -> safety -> SQL -> chart -> summary -> follow-ups
- Alerts and report scheduling
- Admin usage metrics and audit logs
- Worker for scheduled sync/alerts/reports

### Out of Scope (MVP)
- Billing/marketplace/SSO/SAML
- Embedded SDK/mobile
- Collaboration comments/workflows
- Advanced forecasting studio and writeback

## Non-Functional Requirements
- Multi-tenant boundaries at workspace scope
- Role enforcement on all protected endpoints
- Auditability for write-path actions
- Deterministic SQL safety checks against semantic definitions
- Local-first runnable via Docker Compose

## KPI Signals
- Time-to-first-insight < 20 minutes from signup
- 100% NL queries executed via semantic model (no raw table bypass)
- < 3 clicks from NL answer to dashboard save
- Daily/weekly automation success visibility via logs and audit
