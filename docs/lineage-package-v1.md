# 数据血缘与版本追踪包（包 4）状态说明

## 目标

包 4 的目标是把项目中零散存在的：

- `as_of_date`
- `generated_at`
- `feature_version`
- `label_version`
- `model_version`
- `provider_used`

统一收口成一套可落袋、可查询、可回溯的数据血缘体系。

本轮只做底层元数据与只读诊断能力，不改 research / strategy / screener 的业务评分逻辑，不做前端重构，也不引入新的调度系统。

## 当前已落地能力

### 1. 统一 lineage schema

已新增：

- `LineageSourceRef`
- `LineageDependency`
- `LineageMetadata`
- `LineageListResponse`
- `WorkspaceLineageItem`
- `LineageSummary`

位置：

- `backend/app/schemas/lineage.py`

### 2. 日级数据产品统一版本与血缘入口

`DataProductResult` 已新增：

- `dataset_version`
- `provider_used`
- `warning_messages`
- `lineage_metadata`

默认版本规则：

- `{dataset}:{as_of_date}:{symbol-or-global}:v1`

例如：

- `daily_bars_daily:2026-04-14:000001.SZ:v1`
- `market_breadth_daily:2026-04-14:global:v1`

### 3. repository 型日级数据产品已支持 lineage 保存与读回

当前已经覆盖：

- `factor_snapshot_daily`
- `review_report_daily`
- `strategy_plan_daily`
- `debate_review_daily`
- `decision_brief_daily`
- `industry_classification_daily`
- `market_breadth_daily`
- `risk_proxy_daily`
- `screener_snapshot_daily`

这些产物在保存到文件型 repository 时，会同步保存：

- `dataset_version`
- `provider_used`
- `warning_messages`
- `lineage_metadata`

再次从缓存读取时，也会把这些字段完整带回。

### 4. feature / label / prediction / backtest / evaluation 统一增强

以下链路已经接入 `lineage_service`：

- `dataset_service`
- `label_service`
- `prediction_service`
- `backtest_service`
- `evaluation_service`

当前会记录：

- `generated_at`
- `schema_version`
- `dependencies`
- `dataset_version`

### 5. 本地 lineage 登记簿

已新增轻量本地登记簿：

- `dataset_lineage_records`

位置：

- `backend/app/services/lineage_service/repository.py`

用途：

- 记录 feature / label / prediction / backtest / evaluation 的 lineage metadata
- 记录关键日级产物的 lineage 摘要
- 支持只读查询，不参与业务主流程决策

### 6. 只读 lineage API

已新增：

- `GET /lineage/datasets`
- `GET /lineage/datasets/{dataset}/{dataset_version}`
- `GET /datasets/features/{dataset_version}/lineage`
- `GET /datasets/labels/{label_version}/lineage`
- `GET /predictions/{symbol}/lineage`
- `GET /stocks/{symbol}/workspace-lineage`

### 7. Workspace Bundle 模块级血缘摘要

`workspace-bundle` 已新增：

- `lineage_summary`

当前会汇总这些模块的版本摘要：

- `daily_bars_daily`
- `announcements_daily`
- `financial_summary_daily`
- `factor_snapshot_daily`
- `review_report_daily`
- `strategy_plan_daily`
- `debate_review_daily`
- `decision_brief_daily`
- `predictive_snapshot`

## 当前边界

本轮仍然不做：

- 递归展开完整依赖图
- 前端血缘展示改造
- 调度系统与消息队列
- 外部元数据仓库

## 当前剩余收尾

1. 继续补齐 API / repository / workspace 的回归测试
2. 做一轮只读接口验收，确认旧接口兼容且新增字段仅做增强
3. 把 lineage 规则同步进 README / architecture 等主文档
