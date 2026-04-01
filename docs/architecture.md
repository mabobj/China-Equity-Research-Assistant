# 系统架构

本文描述当前已落地架构，重点是“稳定可运行”和“可解释可追溯”。

## 1. 分层结构

```text
前端工作台 (Next.js)
  -> API 路由层 (FastAPI)
  -> 服务层 (research/review/debate/strategy/screener/workflow/trade-review)
  -> provider 层 (外部数据适配)
  -> 本地存储层 (SQLite + DuckDB/Parquet + workflow artifacts)
  -> schema 层 (Pydantic typed contracts)
```

边界规则：
- 路由层只做请求接收和响应包装
- 业务逻辑集中在 service 层
- 外部数据访问只能走 provider 层
- 对外输出优先结构化字段，不依赖自由文本

## 2. 单票主链路

单票页主入口：
- `GET /stocks/{symbol}/workspace-bundle`

`workspace-bundle` 聚合：
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

容错策略：
- 使用 `200 + module_status_summary` 表达局部失败
- 暴露运行时可见字段：`provider_used`、`fallback_applied`、`fallback_reason`、`runtime_mode_*`、`warning_messages`

## 3. 选股与 workflow

当前前端主路径为 workflow 模式：
- `POST /workflows/screener/run`
- `POST /workflows/deep-review/run`
- `GET /workflows/runs/{run_id}`

特性：
- 运行提交后立即返回 `run_id`
- 前端轮询 run detail 展示步骤与最终摘要
- 深筛可容忍局部 symbol 失败，并通过 `failed_symbols` 暴露

兼容保留旧同步接口，但非主路径：
- `GET /screener/run`
- `GET /screener/deep-run`

初筛批次台账（产品化第一阶段）：
- `GET /screener/latest-batch`
- `GET /screener/batches/{batch_id}`
- `GET /screener/batches/{batch_id}/results`
- `GET /screener/batches/{batch_id}/results/{symbol}`
- `POST /screener/cursor/reset`

展示窗口口径（Asia/Shanghai）：
- 17:00 前：展示前一日 17:00（含）到当日 17:00（不含）完成结果
- 17:00 后：展示当日 17:00（含）到当前时刻完成结果

## 4. 日级数据产品与 freshness

数据产品目录：
- `backend/app/services/data_products/`

当前日级产物：
- `daily_bars_daily`
- `announcements_daily`
- `financial_summary_daily`
- `factor_snapshot_daily`
- `review_report_daily`
- `debate_review_daily`
- `strategy_plan_daily`
- `decision_brief_daily`
- `screener_snapshot_daily`

freshness 策略：
- 默认使用“最后一个已收盘交易日”
- 默认本地优先，缺失或过期才补远端
- `force_refresh=true` 才主动刷新远端
- 输出尽量带 `as_of_date`、`freshness_mode`、`source_mode`

## 5. Data 清洗层（v0.1）

统一链路：
`provider/local raw -> cleaning -> contracts -> market_data_service -> downstream`

已落地清洗对象：
- bars
- financial_summary
- announcements（公告索引层）

统一质量口径：
- `quality_status`: `ok | warning | degraded | failed`
- `cleaning_warnings`
- `missing_fields`（适用时）

## 6. 交易与复盘闭环（v0.1）

### 6.1 核心对象
- `DecisionSnapshot`
- `TradeRecord`
- `ReviewRecord`
- `PositionCase`（服务层聚合对象，非持仓引擎）

### 6.2 服务边界
- `decision_snapshot_service`
- `trade_service`
- `review_record_service`

注意：这里的 `review_record_service` 与 `review-report v2` 领域解耦，避免命名冲突。

### 6.3 持久化
- SQLite：`data/trade_review.sqlite3`
- 表：
  - `decision_snapshots`
  - `trade_records`
  - `review_records`

索引：
- `decision_snapshots(symbol, created_at DESC)`
- `trade_records(symbol, trade_date DESC)`
- `review_records(symbol, review_date DESC)`
- `trade_records(decision_snapshot_id)`
- `review_records(linked_trade_id)`

### 6.4 关键 API
- Decision Snapshot：
  - `POST /decision-snapshots`
  - `GET /decision-snapshots/{snapshot_id}`
  - `GET /decision-snapshots`
- Trades：
  - `POST /trades`
  - `GET /trades`
  - `GET /trades/{trade_id}`
  - `PATCH /trades/{trade_id}`
  - `POST /trades/from-current-decision`
- Reviews：
  - `POST /reviews`
  - `GET /reviews`
  - `GET /reviews/{review_id}`
  - `PATCH /reviews/{review_id}`
  - `POST /reviews/from-trade/{trade_id}`

### 6.5 行为约束
- `SKIP` 允许空价格/数量/金额
- 复盘草稿默认自动计算 `holding_days/MFE/MAE`，行情不足时返回受控 warning
- 不做自动下单，不做券商接入，不做组合级归因
- 交易动作与决策基线冲突时，默认记为 `not_aligned`
- 若冲突场景下手动指定 `aligned/partially_aligned`，必须提供 `alignment_override_reason`
- `reason_type` 与 `side` 做基础一致性校验（入场类仅 `BUY/ADD`，离场类仅 `SELL/REDUCE`，观察类仅 `SKIP`）
- `did_follow_plan` 会结合交易对齐状态做自动纠偏，避免“执行不一致但复盘写 yes”

### 6.6 决策基线口径（方向层与时机层）
- 方向层：用于交易一致性校验，优先读取 `decision_brief.action_now` 映射结果，回退到 `review_report.final_judgement.action`
- 时机层：保留 `decision_brief.action_now` 原始语义（`BUY_NOW / WAIT_PULLBACK / WAIT_BREAKOUT / RESEARCH_ONLY / AVOID`）
- 页面会同时展示“方向基线”和“执行动作（时机层）”；当两层口径不一致时给出显式提示

## 7. 前端页面职责

- `/stocks/[symbol]`：单票工作台 + 保存判断 + 记录交易
- `/screener`：workflow 驱动选股工作台
- `/trades`：交易记录录入与列表
- `/reviews`：从交易生成复盘草稿并编辑结论

## 8. 非目标（当前阶段）

- 自动交易执行
- 券商交易系统集成
- 调度器/队列/DAG 平台
- 复杂持仓引擎与组合归因
