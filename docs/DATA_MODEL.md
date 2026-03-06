# Data Model

## Core Entities
- `Organization`: tenant owner boundary plus commercial state (`plan_tier`, `subscription_status`, `billing_provider`, `billing_email`, `billing_customer_id`, `billing_subscription_id`, `billing_price_id`, `seat_limit`, `trial_ends_at`)
- `Workspace`: analytics workspace under organization
- `User`: authenticated principal
- `RoleAssignment`: role at organization/workspace scope
- `DataConnection`: connector configuration and status
- `SyncJob`: recurring sync schedule config
- `SyncRun`: sync execution log
- `Dataset`: warehouse dataset generated from sync
- `DatasetField`: dataset schema catalog
- `DatasetRelation`: join metadata
- `SemanticModel`: governed model definition + version
- `SemanticMetric`: named business metric formula
- `SemanticDimension`: named dimension mapping
- `CalculatedField`: reusable computed expression
- `Dashboard`: report canvas metadata
- `DashboardWidget`: persisted visualization block
- `ReportSchedule`: dashboard delivery schedule
- `AlertRule`: threshold rule on semantic metric
- `AlertEvent`: alert evaluation event
- `AuditLog`: immutable audit trail
- `AIQuerySession`: NL query trace (plan/sql/result/summary)
- `InsightArtifact`: generated insight record

## Key Relationships
- Organization 1:N Workspace
- Workspace 1:N DataConnection, Dataset, SemanticModel, Dashboard
- DataConnection 1:N SyncJob, SyncRun, Dataset
- SemanticModel 1:N SemanticMetric, SemanticDimension, CalculatedField
- Dashboard 1:N DashboardWidget
- AlertRule 1:N AlertEvent

## Versioning
- `SemanticModel` uses (`workspace_id`, `model_key`, `version`) unique key

## Governance
- Visibility fields on semantic dimensions and metrics
- Audit logs on critical create/update/execute flows
- Commercial state changes are auditable through:
  - `organization.subscription.update`
  - `billing.checkout_session.created`
  - `billing.portal_session.created`
  - `billing.webhook.processed`

## Billing State Rules
- `billing_provider` tracks the linked external provider for the organization (`manual`, `log`, `stripe`)
- `billing_customer_id`, `billing_subscription_id`, and `billing_price_id` are nullable until checkout/webhook linkage occurs
- Stripe webhook events map raw provider state into governed platform states (`trial`, `active`, `past_due`, `canceled`)
