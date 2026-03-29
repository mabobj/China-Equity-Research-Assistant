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
