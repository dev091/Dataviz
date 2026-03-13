---
name: go-live-verification
description: Verify launch readiness for this analytics platform using the staged ops scripts and evidence artifacts. Use when running preflight, billing smoke, load testing, connector validation, or combined go-live verification.
---

# Go Live Verification

1. Review `docs/TASK_CHECKLIST.md` and `docs/LIVE_LAUNCH.md` before running checks.
2. Prefer the orchestration script first:
   - `infrastructure/scripts/ops-verify.ps1`
3. Use direct scripts only when isolating a failing stage:
   - `staging-preflight.ps1`
   - `billing-smoke.ps1`
   - `load-test.ps1`
   - `live-connectors.ps1`
   - `cutover-smoke.ps1`
4. Capture evidence under `infrastructure/tmp/ops-verify` or a stage-specific artifact directory.
5. Mark checklist items complete only when the check ran successfully against the intended environment.
6. Distinguish local proof, staging proof, and production proof in every status update.
