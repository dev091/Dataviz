# MVP Scope Boundary

## Included in MVP
- Multi-tenant auth with Owner/Admin/Analyst/Viewer roles
- Five connectors with standardized interface
- Governed semantic model with metrics/dimensions/calculated fields and versioning
- Dashboard builder with persisted widgets and report view mode
- NL analytics with planning and SQL safety
- Alerts, report schedules, worker automation
- Audit logs and workspace usage metrics

## Excluded for MVP
- Billing and subscription controls
- Enterprise SSO/SAML
- Plugin marketplace and full extensibility SDK
- Collaborative comments/approval flows
- Reverse ETL and writeback workflows

## Opinionated MVP Decisions
- Single-tenant physical DB with workspace-scoped logical isolation
- Single-table semantic query execution for first release
- SQL safety constrained by approved semantic fields/formulas
- Email delivery represented by delivery audit logs in MVP
