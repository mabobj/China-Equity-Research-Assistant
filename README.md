# A 股研究助手

面向中国大陆 A 股市场的单用户研究与决策辅助工作台。

## 当前范围

当前阶段已包含：
- 单票工作台
- 选股与深筛工作流
- 结构化输出（`review-report v2`、`debate-review`、`strategy plan`、`decision brief`）
- 工作流运行记录

当前阶段不包含：
- 自动实盘交易
- 券商下单集成
- 交易复盘自动化闭环
- 调度器/队列/DAG 平台

## 术语统一

- `review-report v2`：单票主研究产物。
- `debate-review`：结构化裁决层。
- `strategy plan`：结构化行动建议层。
- `workflow run record`：工作流运行元数据、节点摘要与最终摘要。
- `/reviews`：预留路由，当前未启用。

## 主入口

- 单票主入口：`GET /stocks/{symbol}/workspace-bundle`
- 初筛工作流主入口：`POST /workflows/screener/run` + `GET /workflows/runs/{run_id}`
- 深筛工作流主入口：`POST /workflows/deep-review/run` + `GET /workflows/runs/{run_id}`

兼容旧入口（保留但不作为前端主路径）：
- `GET /screener/run`
- `GET /screener/deep-run`

## Workspace Bundle

`GET /stocks/{symbol}/workspace-bundle` 一次返回：
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

行为约定：
- 采用 `200 + module_status_summary` 表达部分模块失败。
- 保留细粒度旧接口以兼容现有调用。
- 在 bundle 和相关模块中暴露 runtime/fallback 可见字段。

## 日级数据产品

当前日级数据产品包括：
- `daily_bars_daily`
- `announcements_daily`
- `financial_summary_daily`
- `factor_snapshot_daily`
- `review_report_daily`
- `debate_review_daily`
- `strategy_plan_daily`
- `decision_brief_daily`
- `screener_snapshot_daily`

## Freshness 与复用策略

默认策略：
- 默认使用最后一个已收盘交易日（`as_of_date`）。
- 优先读取本地日级产物。
- 仅在缺失或过期时重算。
- 仅在 `force_refresh=true` 时主动刷新远端。

日级输出应尽量携带：
- `as_of_date`
- `freshness_mode`
- `source_mode`

## 日级与按需计算边界

优先按日快照复用：
- factor/review/debate/strategy/decision brief/screener snapshot。

仍主要按需计算：
- 依赖盘中数据的 `trigger_snapshot`。
- 运行进度类实时状态对象（例如 debate 进度轮询）。

## Runtime/Fallback 可见字段

关键响应（`debate-review`、`workspace-bundle`、`workflows/runs/{run_id}`）暴露：
- `provider_used`
- `provider_candidates`（可选）
- `fallback_applied`
- `fallback_reason`
- `runtime_mode_requested`
- `runtime_mode_effective`
- `warning_messages`

深筛工作流明细中可见局部失败符号（`failed_symbols`）。

## 工作流运行记录

- 本地落盘路径：`data/workflow_runs/{run_id}.json`
- 当前官方查询方式：`GET /workflows/runs/{run_id}`
- 本轮未引入按日期/名称筛选的列表检索 API

## 前端路由

- `/`：工作台首页
- `/stocks/[symbol]`：单票工作台
- `/screener`：选股工作台（工作流模式）
- `/trades`：预留
- `/reviews`：预留

## 文档导航

- [系统架构](docs/architecture.md)
- [路线图](docs/roadmap.md)
- [稳定性审计 v1（含结案更新）](docs/audits/stability-review-v1.md)
- [快速开始](docs/manuals/quickstart.md)
- [日常使用说明](docs/manuals/daily-usage.md)
- [数据源与边界](docs/manuals/data-and-limitations.md)
- [故障排查](docs/manuals/troubleshooting.md)

## 本地启动

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
Set-Location frontend
npm install
Set-Location ..
```

启动服务：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_backend.ps1
powershell -ExecutionPolicy Bypass -File scripts\run_frontend.ps1
```

默认地址：
- 后端健康检查：[http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- 后端文档：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- 前端页面：[http://127.0.0.1:3000](http://127.0.0.1:3000)

## 测试命令

后端：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test_backend.ps1
```

前端：

```powershell
Set-Location frontend
npm.cmd run lint
npm.cmd run type-check
npm.cmd run test:smoke
```

稳定性重点测试：

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest backend/tests/test_workspace_bundle_service.py backend/tests/test_stocks_api.py backend/tests/test_workflow_api.py -q
```

## 架构原则

- 路由层保持轻薄。
- 业务逻辑集中在服务层。
- 外部数据统一通过 provider 层接入。
- 核心输出优先结构化与类型化。
- 以稳定、可解释、可维护为先。
