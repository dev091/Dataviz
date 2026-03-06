# Architecture

## High-Level Components
- `apps/web` (Next.js 15, TypeScript, Tailwind, React Query, Zustand, ECharts)
- `apps/api` (FastAPI, SQLAlchemy, Pydantic, JWT auth, tenancy, semantic and AI orchestration)
- `apps/worker` (Celery + Redis scheduled jobs)
- `packages/connectors` (connector framework + implementations)
- `packages/semantic` (query plan IR, validation, SQL builder)
- `packages/analytics` (chart recommendation, deterministic insights/summaries)
- `packages/prompts` (AI prompt templates)
- `infrastructure` (docker, db init, scripts)

## Multi-Agent AI Architecture
NL analytics runs through specialized agents orchestrated by a coordinator service:
1. `planner_agent`: converts user question into structured semantic query plan
2. `safety_agent`: validates requested metrics/dimensions/sorts/filters/limits against governance rules
3. `sql_agent`: compiles safe SQL from approved semantic expressions and join graph only
4. `query_execution_agent`: executes SQL and normalizes result rows
5. `visualization_agent`: recommends best chart type by result shape and intent
6. `insight_agent`: detects anomalies/trends/rank shifts from result data
7. `narrative_agent`: generates executive summary and suggested follow-up questions

Agent execution trace is returned to the client and stored with query sessions for auditability.

## Request Flow: NL Analytics
1. User submits question + semantic model ID
2. API loads semantic model context (metrics/dimensions/base dataset + join topology)
3. Multi-agent coordinator runs planner -> safety -> SQL -> execution -> visualization -> insight -> narrative
4. SQL builder resolves required aliases and join paths from base dataset to requested fields
5. API persists `AIQuerySession` with plan, SQL, results, and agent trace
6. Insight artifacts are persisted for downstream review

## Multi-Tenant & RBAC
- Workspace context enforced via `X-Workspace-Id` header
- Role assignments support org-level and workspace-level scopes
- Route-level role guards (`Viewer`, `Analyst`, `Admin`, `Owner`)
- Audit logs capture actor/action/entity + metadata

## Sync Architecture
- Connector registry resolves connector by type
- `discover` and `preview_schema` for metadata and field cataloging
- `sync` yields dataframes persisted to workspace-specific physical tables
- `SyncRun` captures status, record counts, structured logs
- `SyncJob` stores daily/weekly schedules
- Celery beat executes due jobs

## Report Delivery
- Email provider abstraction with `log` and `smtp` providers
- Worker executes due report schedules and dispatches email payloads
- Delivery success/failure is written to audit logs with provider metadata
- Docker default SMTP target is MailHog for local verification

## Proactive Agent Runs
- Worker executes `run_proactive_insights` hourly
- Proactive agent scans active semantic models and metrics
- Generates `InsightArtifact` entries and audit event for each run

## Runtime Observability
- HTTP request middleware emits structured logs (`event`, `request_id`, route, status, latency)
- `X-Request-Id` header is propagated to clients
- In-process metrics registry exposes counters and latency histogram via `/metrics`
- Optional Prometheus + Grafana stack is provided in Docker profile `observability`

## Runtime Security Controls
- Startup security validation checks JWT key strength and risky auth settings
- `ENFORCE_SECURE_CONFIG=true` can hard-fail startup in staging/production
- API rate limiting middleware is enabled by default (`RATE_LIMIT_REQUESTS_PER_MINUTE`)

## AI Layer Design
- Provider abstraction (`AIProvider`) with OpenAI-compatible implementation
- Prompt templates separated under `packages/prompts`
- Deterministic fallback for plan and summary when LLM unavailable
- Safety-first approach: no direct freeform SQL generation

## Delivery Pipeline
- CI workflow gates backend tests, frontend typecheck/build, and docker-compose smoke
- Security workflow runs dependency audits (Python and Node)
- Release workflow includes rollback SHA path for controlled recovery

## Extensibility Hooks
- Connector interface supports new systems without API changes
- Semantic package and analytics package isolated for upgrade
- Storage service interface supports future S3 swap
- Agent interface allows plugging additional specialist agents without changing API contracts
