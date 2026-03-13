# Master Roadmap Checklist

Last updated: 2026-03-07

Legend:
- [x] Completed
- [~] Partially completed
- [ ] Not completed / needs follow-up

## Governing Rule
- [x] `docs/MASTER_ROADMAP.md` is the only governing roadmap.
- [x] This checklist tracks progress directly against that roadmap.
- [x] Older phase-based planning is no longer the governing completion standard.

## Master Roadmap Progress Snapshot
- [x] Overall strict completion: `45.33%` (`136/300` roadmap items fully complete)
- [x] Overall weighted completion: `68.83%` (`136 complete + 141 partial at half weight`)
- [x] Complete roadmap items: `136`
- [x] Partial roadmap items: `141`
- [x] Open roadmap items: `23`

## Roadmap Capability Family Progress
- [~] Universal enterprise connectivity: `50.00%` weighted
- [~] AI Data Prep Autopilot: `70.00%` weighted
- [~] Governed semantic KPI layer: `88.46%` weighted
- [~] Autonomous executive output generation: `55.56%` weighted
- [~] Natural-language analytics: `71.43%` weighted
- [x] Proactive intelligence: `94.44%` weighted
- [~] Governance and trust: `55.00%` weighted
- [~] Deliverables audit: `85.14%` weighted

## Current Roadmap Status
- [x] Local core product foundation exists and is validated.
- [~] Strategic positioning, commercial model, onboarding motion, and GTM artifacts are defined but not fully operationalized.
- [~] Launch wedge support is real in-product with packaged operating views, exception reporting, onboarding playbooks, KPI validation checklists, and adoption instrumentation, but not yet fully productized for repeatable customer onboarding.
- [~] Migration leverage exists through governed mapping, direct workbook import, benchmark-driven trust comparison, certification review, lineage-aware bulk KPI promotion, and governed bootstrap, but broader automated comparison coverage and richer incumbent coverage remain incomplete.
- [~] AI Data Prep Autopilot, semantic governance, trust review, and proactive intelligence are materially implemented, but not complete end to end.
- [ ] Production-live execution remains incomplete.

## What Is Complete Against The Roadmap
- [x] Multi-tenant auth, workspaces, RBAC, auditability, and tenant-aware platform structure
- [x] Launch connectors, sync framework, schema discovery, logs, retry metadata, and structured file ingestion
- [x] Governed semantic KPI layer with metrics, dimensions, joins, calculated fields, synonyms, hierarchies, ownership, validation, and versioning
- [x] Natural-language analytics grounded in the semantic layer with plan, safety, trace, chart recommendation, summary, and follow-ups
- [x] Autonomous dashboard composition, widget builder, executive summaries, operating views, exception reports, alerts, schedules, and delivery logs
- [x] Proactive intelligence with threshold, anomaly, pacing, trend-break, freshness, digest, suggested action, audience routing, and investigation support
- [x] Admin governance, semantic trust panel, AI trust history, billing scaffold, observability, runtime security, operational verification scripts, dedicated core capability libraries, and an expanded native visualization library with advanced chart families plus custom ECharts escape hatch

## Highest Priority Remaining Roadmap Gaps
- [ ] Broader launch-wedge operating systems and repeatable onboarding depth; playbooks and KPI validation instrumentation now exist but real customer validation is still missing
- [ ] Broader incumbent BI parsing coverage and richer automated trust comparison beyond the current certification review workflow
- [ ] Complete metric lineage coverage beyond migrated KPIs, transformation lineage, and full prompt or action history across all AI artifacts
- [ ] Live usefulness instrumentation, alert policy depth, and broader trust coverage across all AI-generated outputs
- [ ] Real staging and production execution: infra, secrets, live billing, real connector validation, load, backup/restore, UAT, and cutover

## Validation Snapshot
- [x] `pytest apps/api/tests/test_proactive_insights.py apps/api/tests/test_report_delivery.py apps/api/tests/test_core_flow.py -q` -> `3 passed`
- [x] `pytest apps/api/tests/test_core_flow.py apps/api/tests/test_admin_subscription.py -q` -> `2 passed`
- [x] `pytest apps/api/tests/test_data_prep_autopilot.py apps/api/tests/test_core_flow.py -q` -> `2 passed`
- [x] `pytest apps/api/tests/test_launch_packs.py apps/api/tests/test_migration_assistant.py apps/api/tests/test_data_prep_autopilot.py apps/api/tests/test_proactive_insights.py -q` -> `4 passed`
- [x] `pytest apps/api/tests/test_migration_import_promotion.py apps/api/tests/test_migration_assistant.py apps/api/tests/test_launch_packs.py -q` -> `3 passed`
- [x] `pytest apps/api/tests/test_launch_packs.py apps/api/tests/test_core_flow.py -q` -> `2 passed`
- [x] `pytest apps/api/tests/test_core_flow.py -q` -> `1 passed`
- [x] `pytest apps/api/tests/test_migration_import_promotion.py apps/api/tests/test_migration_assistant.py -q` -> `2 passed`
- [x] `pytest apps/api/tests/test_core_flow.py apps/api/tests/test_report_delivery.py -q` -> `2 passed`
- [x] `npm --workspace apps/web run build` -> passed
- [x] `pytest apps/api/tests/test_chart_recommendation.py apps/api/tests/test_core_flow.py apps/api/tests/test_report_delivery.py apps/api/tests/test_migration_assistant.py apps/api/tests/test_migration_import_promotion.py apps/api/tests/test_data_prep_autopilot.py apps/api/tests/test_proactive_insights.py -q` -> `9 passed`
- [x] `npm --workspace apps/web exec -- tsc --noEmit` -> passed
- [x] `npm --workspace apps/web run test:e2e -- --workers=1` -> `12 passed` (run with `PLAYWRIGHT_SKIP_WEBSERVER=1` against `next start` in this environment)
- [ ] `docker compose` smoke was not rerun in this shell because Docker CLI is not available in PATH here

## Historical Baseline
- [x] The original local product foundation, initial flow set, and Definition of Done are already satisfied and retained in code, tests, and docs.
- [x] Those historical milestones are no longer the governing roadmap for completion claims.

## Production-Live Blockers
- [ ] Provision staging environment with managed Postgres, Redis, and persistent object storage.
- [ ] Configure production-grade secrets management and key rotation policy.
- [ ] Configure live billing environment and validate checkout, webhook, and portal behavior.
- [ ] Execute live connector validation with real PostgreSQL, MySQL, Google Sheets, and Salesforce credentials.
- [ ] Run non-trivial load and performance tests across sync, NL query, dashboards, and worker paths.
- [ ] Execute backup and restore drill, pilot UAT, and production cutover.









