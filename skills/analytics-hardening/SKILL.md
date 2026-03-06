---
name: analytics-hardening
description: Deliver and verify production-grade hardening for this AI-native analytics platform. Use when closing checklist gaps in docs/TASK_CHECKLIST.md, validating multi-agent NL analytics safety, tightening reliability, and preparing release-quality gates.
---

# Analytics Hardening

1. Review `docs/TASK_CHECKLIST.md` first and list unchecked items.
2. Implement one hardening slice end-to-end before starting the next slice.
3. Preserve the multi-agent analytics contract:
   - planner -> safety -> SQL -> execution -> visualization -> insight -> narrative
   - no direct raw SQL generation outside semantic planning
4. Validate every batch with:
   - `pytest apps/api/tests -q`
   - `npm --workspace apps/web exec tsc --noEmit`
   - `npm --workspace apps/web run build`
5. Prefer env-gated live integration tests over fake mocks for connector and external-service flows.
6. Update `docs/TASK_CHECKLIST.md` with completed and remaining items after each batch.
7. Update `docs/RUNBOOK.md` when operational behavior or setup changes.
8. Report residual risk explicitly if any task cannot be verified in this environment.
