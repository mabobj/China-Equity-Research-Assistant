# A 股研究助手

面向中国大陆 A 股市场的单用户研究与决策工作台。当前强调“稳定、可解释、可追溯”，不做自动实盘交易。

## 当前能力

- 单票工作台（`/stocks/[symbol]`）
- 选股与深筛工作流（`/screener`）
- 结构化研究输出：`review-report v2`、`debate-review`、`strategy plan`、`decision brief`
- workflow 运行记录与轮询查看
- 初筛批次台账与结果回看（17:00 展示窗口口径）
- 数据清洗层（bars / financial_summary / announcements）
- 交易与复盘最小闭环（`decision snapshot -> trade -> review`）

## 主入口

- 单票主入口：`GET /stocks/{symbol}/workspace-bundle`
- 选股主入口：`POST /workflows/screener/run` + `GET /workflows/runs/{run_id}`
- 深筛主入口：`POST /workflows/deep-review/run` + `GET /workflows/runs/{run_id}`

兼容保留但非前端主路径：
- `GET /screener/run`
- `GET /screener/deep-run`

## 交易与复盘闭环（v0.1）

后端新增接口：
- `POST /decision-snapshots`
- `GET /decision-snapshots/{snapshot_id}`
- `GET /decision-snapshots?symbol=...&limit=...`
- `POST /trades`
- `GET /trades`
- `GET /trades/{trade_id}`
- `PATCH /trades/{trade_id}`
- `POST /trades/from-current-decision`
- `POST /reviews`
- `GET /reviews`
- `GET /reviews/{review_id}`
- `PATCH /reviews/{review_id}`
- `POST /reviews/from-trade/{trade_id}`

前端入口：
- `/stocks/[symbol]`：保存本次判断、记录交易
- `/trades`：新建交易记录、按股票过滤、查看关联快照摘要
- `/reviews`：从交易生成复盘草稿、编辑 outcome/summary/lesson tags

持久化：
- SQLite：`data/trade_review.sqlite3`
- 表：`decision_snapshots`、`trade_records`、`review_records`

规则要点：
- `SKIP` 允许 `price/quantity/amount` 为空
- 复盘草稿默认自动计算 `holding_days/MFE/MAE`（行情不足时返回受控 warning）
- 决策快照记录 `runtime_mode_requested/effective` 与数据质量摘要

## 交易一致性校验口径（2026-04）

为避免“同一只股票出现两套冲突结论”导致执行混乱，当前系统对交易一致性采用以下统一口径：

- 方向基线（用于 `strategy_alignment` 推断）按优先级确定：
  1. `decision_brief.action_now`（映射为 `BUY/WATCH/AVOID`）
  2. `review_report.final_judgement.action`
  3. `research.action`
- 若交易动作与方向基线冲突：
  - 系统默认判为 `not_aligned`
  - 若仍需手动指定 `aligned/partially_aligned`，必须提供 `alignment_override_reason`
- `reason_type` 与 `side` 必须匹配（如 `watch_only` 仅用于 `SKIP`，`stop_loss/take_profit` 仅用于 `SELL/REDUCE`）
- 复盘 `did_follow_plan` 会与交易对齐状态联动校正，避免“交易不一致但复盘写 yes”的语义冲突

## 数据清洗层（v0.1）

统一链路：
`provider/local raw -> cleaning contracts -> market_data_service -> data products -> API`

已落地对象：
- bars 清洗
- financial_summary 清洗
- announcements 清洗（索引层）

质量字段统一口径：
- `quality_status`: `ok | warning | degraded | failed`
- `cleaning_warnings`
- `missing_fields`（适用时）
- `provider_used` / `fallback_applied` / `fallback_reason`

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

启动后端：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_backend.ps1
```

启动前端：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_frontend.ps1
```

默认地址：
- 后端健康检查：[http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- 后端文档：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- 前端页面：[http://127.0.0.1:3000](http://127.0.0.1:3000)

## 测试命令

后端关键回归：

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest backend/tests/test_stocks_api.py backend/tests/test_workflow_api.py backend/tests/test_trade_review_store.py backend/tests/test_trade_review_api.py -q
```

前端检查：

```powershell
Set-Location frontend
npm.cmd run type-check
npm.cmd run lint
npm.cmd run test:smoke
```

## 文档导航

- [系统架构](docs/architecture.md)
- [路线图](docs/roadmap.md)
- [稳定性审计 v1](docs/audits/stability-review-v1.md)
- [快速开始](docs/manuals/quickstart.md)
- [日常使用说明](docs/manuals/daily-usage.md)
- [数据源与边界](docs/manuals/data-and-limitations.md)
- [Data 清洗层说明](docs/manuals/data-cleaning.md)
- [故障排查](docs/manuals/troubleshooting.md)
