---
name: live-launch-ops
description: Drive this analytics platform from MVP-complete to production-live. Use when validating staging readiness, CI/CD rollout, observability, security scans, billing go-live checks, backup and restore drills, pilot UAT, load testing, or production cutover tasks.
---

# Live Launch Ops

1. Review `docs/TASK_CHECKLIST.md` and `docs/LIVE_LAUNCH.md` first.
2. Distinguish in-repo implementation work from external-environment execution work.
3. Use the existing operational scripts before inventing new commands:
   - `infrastructure/scripts/ops-verify.ps1`
   - `infrastructure/scripts/backend-tests.ps1`
   - `infrastructure/scripts/ci-gates.ps1`
   - `infrastructure/scripts/staging-preflight.ps1`
   - `infrastructure/scripts/billing-smoke.ps1`
   - `infrastructure/scripts/live-connectors.ps1`
   - `infrastructure/scripts/load-test.ps1`
   - `infrastructure/scripts/security-scan.ps1`
   - `infrastructure/scripts/backup-postgres.ps1`
   - `infrastructure/scripts/restore-postgres.ps1`
   - `infrastructure/scripts/cutover-smoke.ps1`
4. Prefer authenticated smoke checks over anonymous checks when demo or staging credentials are available.
5. Preserve the multi-agent analytics path and tenant isolation while hardening operations.
6. Mark checklist items complete only when the exact requirement has been implemented or executed.
7. Call out blockers that require real credentials, cloud infrastructure, DNS, TLS, payment provider secrets, or user sign-off.
