# 系统架构

## 文档目标

本文档描述当前已落地的架构状态，重点覆盖：
- 分层边界
- 用户主输出链路
- 日级数据产品复用机制
- 工作流与运行时可见性

当前阶段聚焦稳定性与可维护性，不扩展新业务能力。

## 分层结构

```text
前端工作台
  -> API 路由层（FastAPI + Next 代理）
  -> 服务层（review / debate / strategy / screener / workflow）
  -> Provider 层（外部数据适配）
  -> 本地存储层（SQLite + DuckDB/Parquet + JSON artifacts）
  -> Schema 层（类型化请求/响应契约）
```

边界规则：
- 路由层保持轻薄。
- 业务逻辑集中在服务层。
- 外部数据访问统一通过 provider 层。
- 关键输出默认结构化。

## 单票主输出链路

当前统一主链路为：
1. `review-report v2`（主研究产物）
2. `debate-review`（结构化裁决）
3. `strategy plan`（行动层）
4. `decision brief`（结论/证据/动作聚合层）

`/reviews` 是预留路由，不属于当前主链路。

## 主要 API 入口

### 单票
- `GET /stocks/{symbol}/workspace-bundle`

bundle 返回：
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

### 选股与深筛
- `POST /workflows/screener/run`
- `POST /workflows/deep-review/run`
- `GET /workflows/runs/{run_id}`

兼容旧入口：
- `GET /screener/run`
- `GET /screener/deep-run`

## 日级数据产品层

目录：

```text
backend/app/services/data_products/
```

当前日级数据产品：
- `daily_bars_daily`
- `announcements_daily`
- `financial_summary_daily`
- `factor_snapshot_daily`
- `review_report_daily`
- `debate_review_daily`
- `strategy_plan_daily`
- `decision_brief_daily`
- `screener_snapshot_daily`

### 复用策略

`workspace-bundle`、工作流和单模块接口尽量遵循：
1. 先读同日本地快照
2. 缺失或过期才按需计算
3. `force_refresh=true` 时才主动刷新远端

## Freshness 策略

默认行为：
- 日级分析使用最后一个已收盘交易日。
- 页面访问不默认追当天远端日线。
- 响应尽量携带 `as_of_date`、`freshness_mode`、`source_mode`。

## 按需计算边界

当前仍主要按需计算：
- 强依赖盘中数据的 `trigger_snapshot`
- 运行进度类状态对象

该边界是有意保留，用于控制复杂度与稳定性风险。

## Runtime / Fallback 可见性

关键响应暴露以下字段：
- `provider_used`
- `provider_candidates`（可选）
- `fallback_applied`
- `fallback_reason`
- `runtime_mode_requested`
- `runtime_mode_effective`
- `warning_messages`

工作流局部失败会通过 `failed_symbols` 等字段体现。

## Workflow Runtime

目录：

```text
backend/app/services/workflow_runtime/
```

职责：
- 节点编排执行
- `start_from` / `stop_after`
- 运行记录持久化
- 步骤摘要与最终摘要聚合

明确不做：
- 调度器
- 队列
- DAG 可视化编辑器

运行记录存储：

```text
data/workflow_runs/{run_id}.json
```

当前查询方式：
- `GET /workflows/runs/{run_id}`

本轮未引入运行记录列表检索接口。

## Screener 批次持久化

为解决 `/screener` 重复触发和结果不可追溯问题，新增轻量批次台账层：

目录：
```text
backend/app/services/screener_service/batch_service.py
```

核心模型：
- `ScreenerBatchRecord`
- `ScreenerSymbolResult`

设计要点：
- `screener_run` 增加业务级互斥，运行中再次触发会复用 existing run。
- `screener_run` 主输入收敛为 `batch_size`，一次仅处理当前游标窗口内的固定数量股票（兼容 `max_symbols/top_n`）。
- workflow 完成后将 `final_output` 落盘为批次摘要 + 股票结果明细；每次运行生成新 `batch_id`，不覆盖历史。
- `17:00` 后首次触发会自动重置游标；`17:00` 前不自动重置，跑到尾部时返回受控提示。
- `/screener/latest-batch` 按时间窗口聚合展示：
  - `<17:00`：前一日 `17:00`（含）~ 当日 `17:00`（不含）
  - `>=17:00`：当日 `17:00`（含）~ 当前时刻
- 聚合结果默认按每只股票“最新一条”展示，历史明细保留在批次结果文件中。
- 前端 `/screener` 以“运行状态 + 当前窗口批次摘要 + 可筛选结果表 + 单股详情”方式展示。

查询接口：
- `POST /workflows/screener/run`
- `GET /screener/latest-batch`
- `GET /screener/batches/{batch_id}`
- `GET /screener/batches/{batch_id}/results`
- `GET /screener/batches/{batch_id}/results/{symbol}`
- `POST /screener/cursor/reset`
## Data 清洗层（v0.1）

当前正式链路：

`provider raw -> data_service.cleaning -> contracts -> market_data_service -> data_products`

本轮已落地：
- `backend/app/services/data_service/cleaning/`
  - `symbol.py`：symbol/date 规范化
  - `field_maps.py`：字段映射统一入口
  - `types.py`：类型与单位归一化
  - `rules.py`：行级业务校验
  - `quality.py`：质量摘要聚合
  - `bars.py`：bars 清洗总入口
  - `financials.py`：财务摘要清洗总入口
  - `announcements.py`：公告索引清洗总入口
- `backend/app/services/data_service/contracts/`
  - `bars.py`
    - `CleanDailyBar`
    - `CleanDailyBarsResult`
    - `DailyBarsCleaningSummary`
  - `financials.py`
    - `CleanFinancialSummary`
    - `CleanFinancialSummaryResult`
    - `FinancialSummaryCleaningSummary`
  - `announcements.py`
    - `CleanAnnouncementItem`
    - `CleanAnnouncementListResult`
    - `AnnouncementCleaningSummary`

设计约束：
- provider 层只负责“取数 + 基础解析”
- 清洗与质量评估在 cleaning 层集中处理
- service 层统一消费清洗结果，避免字段映射逻辑散落

## 财务摘要清洗接入现状

`market_data_service.get_stock_financial_summary()` 已统一走财务清洗与归一化：
- 实时抓取路径与缓存命中路径都补齐 `report_type`、`quality_status`、`missing_fields`。
- 对历史旧缓存会做响应层二次归一，避免“关键字段缺失但 quality=ok”的误判。
- `financial_summary_daily` 复用同一服务入口与清洗结果。

## 公告索引清洗接入现状

`market_data_service.get_stock_announcements()` 已统一接入公告清洗：
- 本地缓存命中路径与远端 provider 路径都经过同一清洗入口。
- 清洗后统一输出 `publish_date`、`announcement_type`、`dedupe_key`、质量摘要字段。
- 去重规则：`symbol + publish_date + normalized_title`，冲突时优先保留有 URL 的记录。
- 排序规则：`publish_date desc`，同日按标题稳定排序。

## mootdx 优先策略

对以下 capability，默认 provider 优先级统一为：

`mootdx -> baostock -> akshare`

适用范围：
- `daily_bars`
- `intraday_bars`
- `timeline`

批量选股（screener pipeline）同样使用该优先级，保证“本地优先，缺失再回退”。

补充说明：
- 财务摘要链路当前仍是 `local -> akshare`。
- 公告索引链路当前按已注册公告 provider 顺序执行，并通过清洗层统一 source/type/quality 口径。
