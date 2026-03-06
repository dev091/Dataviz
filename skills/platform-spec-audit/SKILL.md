---
name: platform-spec-audit
description: Audit this analytics platform against its PRD, MVP scope, architecture, and checklist. Use when verifying whether implemented code actually satisfies the promised product scope, connectors, UX flows, AI path, governance, and launch-readiness claims.
---

# Platform Spec Audit

1. Start with `docs/PRD.md`, `docs/MVP_SCOPE.md`, `docs/ARCHITECTURE.md`, and `docs/TASK_CHECKLIST.md`.
2. Verify claims against code, not against older checklist language.
3. Separate findings into three buckets:
   - implemented and verified
   - implemented but not fully validated in this environment
   - not yet implemented or only partially implemented
4. Treat external-environment tasks separately from repo tasks.
5. Do not mark items complete unless code or execution evidence exists.
6. Prefer updating the checklist and runbook immediately after each audit pass.
