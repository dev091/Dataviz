---
name: connector-excellence
description: Build and harden premium connector experiences for this analytics platform. Use when improving connection setup UX, connector validation, discovery, sync operations, scheduling, error handling, and connector-specific testing.
---

# Connector Excellence

1. Preserve the existing connector registry and contract in `packages/connectors`.
2. Prefer typed, connector-specific UX over raw JSON inputs.
3. Keep each connector consistent across setup, discovery, sync, scheduling, and logs.
4. Validate configs at the API boundary and again inside connector implementations.
5. Add env-gated live tests for external systems instead of fake happy-path mocks.
6. When improving connector UX, verify both typecheck and production build before closing the task.
