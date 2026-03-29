# Architecture

## Purpose
This document describes the current implemented architecture, with emphasis on:
- layer boundaries
- main user-facing output chain
- daily data product reuse
- workflow/runtime visibility

This phase is focused on stability and maintainability, not feature expansion.

## Layered Structure
```text
Frontend workspace
  -> API routes (FastAPI + Next proxy)
  -> Services (research / debate / strategy / screener / workflow)
  -> Providers (external data adapters)
  -> Local storage (SQLite + DuckDB/Parquet + JSON artifacts)
  -> Schemas (typed request/response contracts)
```

Boundary rules:
- Route layer stays thin.
- Service layer owns business logic.
- External data access goes through providers.
- Structured schema is the default output form.

## Main Output Chain (Single Stock)
The converged output chain is:
1. `review-report v2` (primary research artifact)
2. `debate-review` (structured adjudication)
3. `strategy plan` (action layer)
4. `decision brief` (conclusion/evidence/action summary layer)

`/reviews` is a reserved route and is not part of the active output chain.

## Primary API Entrances
### Single-stock
- `GET /stocks/{symbol}/workspace-bundle`

Bundle includes:
- `profile`
- `factor_snapshot`
- `review_report`
- `debate_review`
- `strategy_plan`
- `trigger_snapshot`
- `decision_brief`
- `module_status_summary`
- `evidence_manifest`
- `freshness_summary`

### Screener/Deep review
- `POST /workflows/screener/run`
- `POST /workflows/deep-review/run`
- `GET /workflows/runs/{run_id}`

Legacy screener endpoints remain for compatibility:
- `GET /screener/run`
- `GET /screener/deep-run`

## Daily Data Product Layer
Path:
```text
backend/app/services/data_products/
```

Current daily products:
- `daily_bars_daily`
- `announcements_daily`
- `financial_summary_daily`
- `factor_snapshot_daily`
- `review_report_daily`
- `debate_review_daily`
- `strategy_plan_daily`
- `decision_brief_daily`
- `screener_snapshot_daily`

### Reuse policy
`workspace-bundle`, workflows, and single-module endpoints should:
1. read same-day local daily snapshots first
2. compute on demand only when missing/stale
3. use remote refresh only when `force_refresh=true`

## Freshness Policy
Default behavior:
- Daily analysis uses last closed trading day.
- Page loads do not force current-day remote daily fetch.
- Responses should expose `as_of_date`, `freshness_mode`, and `source_mode` where applicable.

## On-Demand Boundary
Still mostly on-demand in this phase:
- Intraday-heavy trigger snapshot paths.
- Runtime progress state objects.

This boundary is intentional to keep implementation stable without introducing heavy orchestration.

## Runtime/Fallback Visibility
Key responses expose structured runtime visibility:
- `provider_used`
- `provider_candidates` (optional)
- `fallback_applied`
- `fallback_reason`
- `runtime_mode_requested`
- `runtime_mode_effective`
- `warning_messages`

Partial-failure symbols for workflow runs are exposed through run detail fields such as `failed_symbols`.

## Workflow Runtime
Path:
```text
backend/app/services/workflow_runtime/
```

Role:
- explicit node orchestration
- `start_from` / `stop_after`
- run record persistence
- step summary and final summary aggregation

Out of scope:
- scheduler
- queue
- generic DAG editor

Run record storage:
```text
data/workflow_runs/{run_id}.json
```

Query in current phase is run-id based:
- `GET /workflows/runs/{run_id}`

No list/filter run-index API is introduced in this close-out round.
