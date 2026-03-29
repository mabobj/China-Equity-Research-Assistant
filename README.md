# A-Share Research Assistant

Single-user research and decision-support workspace for China A-share equities.

## Scope
Current phase includes:
- Single-stock workspace
- Screener and deep-review workflows
- Structured outputs (`review-report v2`, `debate-review`, `strategy plan`, `decision brief`)
- Workflow run records

Current phase does **not** include:
- Live trading execution
- Broker order integration
- Trade journal/replay automation
- Scheduler/queue/DAG platform

## Terminology Convergence
- `review-report v2`: primary single-stock research artifact.
- `debate-review`: structured adjudication layer.
- `strategy plan`: structured action planning layer.
- `workflow run record`: persisted workflow metadata, step summaries, and final summary.
- `/reviews`: reserved route, not enabled in current phase.

## Main Entrances
- Single-stock main entrance: `GET /stocks/{symbol}/workspace-bundle`
- Screener main entrance: `POST /workflows/screener/run` + `GET /workflows/runs/{run_id}`
- Deep review main entrance: `POST /workflows/deep-review/run` + `GET /workflows/runs/{run_id}`

Compatible legacy endpoints are still available but are no longer the primary UI path:
- `GET /screener/run`
- `GET /screener/deep-run`

## Workspace Bundle
`GET /stocks/{symbol}/workspace-bundle` returns one bundle:
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

Bundle behavior:
- Uses `200 + module_status_summary` for partial failures.
- Keeps old detail endpoints for compatibility.
- Exposes runtime/fallback visibility fields at bundle level and module level where available.

## Daily Data Products
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

## Freshness and Reuse Policy
Default policy:
- Use last closed trading day (`as_of_date`) by default.
- Read local daily artifact first.
- Recompute only missing/stale parts.
- Remote refresh is triggered only when `force_refresh=true`.

Daily outputs should expose:
- `as_of_date`
- `freshness_mode`
- `source_mode`

## Daily vs On-Demand Boundary
Daily snapshot first:
- Factor/review/debate/strategy/decision brief/screener snapshot.

Still mostly on-demand:
- Intraday-heavy `trigger_snapshot`.
- Real-time progress state objects (for example debate progress polling state).

## Runtime/Fallback Visibility Fields
Key responses (`debate-review`, `workspace-bundle`, `workflows/runs/{run_id}`) expose:
- `provider_used`
- `provider_candidates` (optional)
- `fallback_applied`
- `fallback_reason`
- `runtime_mode_requested`
- `runtime_mode_effective`
- `warning_messages`

Deep-review run details also expose partial-failure symbols (`failed_symbols`) when available.

## Workflow Run Records
- Persisted locally under `data/workflow_runs/{run_id}.json`.
- Official query path in this phase: `GET /workflows/runs/{run_id}`.
- Lightweight list/filter retrieval is not introduced in this close-out round.

## Frontend Routes
- `/`: workspace landing page
- `/stocks/[symbol]`: single-stock workspace
- `/screener`: screener workspace (workflow mode)
- `/trades`: reserved
- `/reviews`: reserved

## Docs Navigation
- [Architecture](docs/architecture.md)
- [Roadmap](docs/roadmap.md)
- [Stability Audit v1](docs/audits/stability-review-v1.md)
- [Quickstart](docs/manuals/quickstart.md)
- [Daily Usage](docs/manuals/daily-usage.md)
- [Data and Limitations](docs/manuals/data-and-limitations.md)
- [Troubleshooting](docs/manuals/troubleshooting.md)

## Local Setup
```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
Set-Location frontend
npm install
Set-Location ..
```

Start services:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_backend.ps1
powershell -ExecutionPolicy Bypass -File scripts\run_frontend.ps1
```

Default URLs:
- Backend health: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- Backend docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Frontend: [http://127.0.0.1:3000](http://127.0.0.1:3000)

## Test Commands
Backend:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\test_backend.ps1
```

Frontend:
```powershell
Set-Location frontend
npm.cmd run lint
npm.cmd run type-check
npm.cmd run test:smoke
```

Focused stability checks:
```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest backend/tests/test_workspace_bundle_service.py backend/tests/test_stocks_api.py backend/tests/test_workflow_api.py -q
```

## Architecture Principles
- Keep routes thin.
- Keep business logic in services.
- Access external data via providers only.
- Keep core outputs typed and structured.
- Prefer stable, explainable logic over flashy behavior.
