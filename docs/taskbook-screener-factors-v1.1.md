# 初筛因子体系项目任务书 v1.1

## 1. 文档定位

本任务书基于 [初筛因子体系设计文档_v1.1](/D:/dev/project/codex/China-Equity-Research-Assistant/docs/初筛因子体系设计文档_v1.1.md) 编制。

目标不是另起一套新系统，而是把设计文档收敛为一条可以在当前仓库持续落地的工程实施主线。

本任务书同时遵循：

- [AGENTS.md](/D:/dev/project/codex/China-Equity-Research-Assistant/AGENTS.md)
- [README.md](/D:/dev/project/codex/China-Equity-Research-Assistant/README.md)
- [docs/architecture.md](/D:/dev/project/codex/China-Equity-Research-Assistant/docs/architecture.md)
- [docs/roadmap.md](/D:/dev/project/codex/China-Equity-Research-Assistant/docs/roadmap.md)
- [docs/a_share_factor_prd_v1.md](/D:/dev/project/codex/China-Equity-Research-Assistant/docs/a_share_factor_prd_v1.md)
- [docs/a_share_architecture_design_spec_v1.md](/D:/dev/project/codex/China-Equity-Research-Assistant/docs/a_share_architecture_design_spec_v1.md)
- [docs/a_share_factor_dictionary_v1.md](/D:/dev/project/codex/China-Equity-Research-Assistant/docs/a_share_factor_dictionary_v1.md)

## 2. 产品定位

初筛不是最终交易决策器，而是：

**全市场轻量候选池生成器**

它负责：

- 在既有可用数据上做低成本、可批量、可解释的全市场筛选。
- 产出“值得进一步研究”的候选集合。
- 为深筛、研究、策略、回测、验证提供统一的日级快照输入。

它不负责：

- 输出最终买卖建议
- 替代研究报告或交易计划
- 在初筛阶段引入高成本 LLM 或重型研究链路

## 3. 目标架构

初筛因子体系按六层建设：

1. 原始数据层
2. 过程指标层
3. 原子因子层
4. 横截面与连续性因子层
5. 复合打分与规则结果层
6. 初筛快照与候选输出层

对应当前仓库分层：

- `data_service`：原始数据与标准化
- `feature_service`：过程指标、原子因子、连续性判断
- `screener_service`：横截面 enrichment、复合打分、候选分桶
- `data_products`：日级快照落袋
- `lineage_service`：血缘与版本追踪
- `workflow_runtime`：批量执行与结果持久化

## 4. 统一对象

当前任务书约束以下核心对象为正式工程对象：

- `ScreenerRawInputs`
- `ScreenerProcessMetrics`
- `ScreenerAtomicFactors`
- `ScreenerCrossSectionFactors`
- `ScreenerCompositeScore`
- `ScreenerSelectionDecision`
- `ScreenerFactorSnapshot`

快照产物统一为：

- `screener_factor_snapshot_daily`
- `screener_selection_snapshot_daily`

## 5. 数据口径

### 5.1 最小原始输入

- `symbol`
- `name`
- `market`
- `board`
- `list_date`
- `list_status`
- `is_st`
- `is_suspended`
- `industry`
- `latest_trade_date`
- 日线 `open/high/low/close/volume/amount`

### 5.2 过程指标

至少包括：

- `ma_5 / ma_10 / ma_20 / ma_60 / ma_120`
- `ma_20_slope / ma_60_slope`
- `close_percentile_60d`
- `return_20d / return_60d`
- `atr_20 / atr_20_pct`
- `volatility_20d`
- `avg_amount_5d / avg_amount_20d / amount_ratio_5d_20d`
- `support_level_20d / resistance_level_20d`
- `distance_to_support_pct / distance_to_resistance_pct`

### 5.3 原子因子

至少包括：

- 趋势因子
- 动量因子
- 波动与位置因子
- 流动性因子
- 风险过滤因子

### 5.4 横截面与连续性因子

至少包括：

- `amount_rank_pct`
- `return_20d_rank_pct`
- `trend_score_rank_pct`
- `atr_pct_rank_pct`
- `industry_relative_strength_rank_pct`
- `trend_persistence_5d`
- `liquidity_persistence_5d`
- `breakout_readiness_persistence_5d`
- `volatility_regime_stability`

## 6. 实施包

### 包 1：Schema 与字段口径收口包

目标：

- 建立正式 schema
- 固化命名与含义

状态：

- **已完成**

已交付：

- `backend/app/schemas/screener_factors.py`
- `ScreenerFactorSnapshot` 等核心 schema
- `list_type / v2_list_type / quality_status` 统一口径

### 包 2：过程指标与原子因子包

目标：

- 把设计文档中的确定性计算正式工程化

状态：

- **已完成第一阶段并收口**

已交付：

- `backend/app/services/feature_service/screener_factor_service.py`
- MA、slope、ATR、收益率、分位、流动性、支撑压力计算
- 趋势、波动、流动性、风险过滤原子因子
- 对应单元测试

### 包 3：横截面与连续性因子包

目标：

- 建立同日同池的对比能力

状态：

- **已完成第一阶段并收口**

已交付：

- `backend/app/services/screener_service/cross_section_factor_service.py`
- 横截面 rank enrichment
- 连续性指标接入 `ScreenerFactorSnapshot`
- 对应单元测试

### 包 4：复合打分与候选分桶包

目标：

- 把因子快照转换为可消费的初筛结果

状态：

- **已完成两阶段**

已交付：

- `score_screener_factor_snapshot`
- `apply_score_to_screener_factor_snapshot`
- `ScreenerPipeline` 新旧双轨兼容
- `composite_score / selection_decision` 回写快照
- pipeline 与 scoring 回归测试

### 包 5：快照落袋、血缘与诊断包

目标：

- 让初筛因子产物可回溯、可验证、可复用

状态：

- **已完成两阶段**

已交付：

- `ScreenerFactorSnapshotDailyDataset`
- `ScreenerSelectionSnapshotDailyDataset`
- workflow 内 selection snapshot 落袋
- factor snapshot 到 selection snapshot 的直接 lineage 依赖
- 诊断接口：
  - `GET /screener/diagnostics/selection-lineage/latest`
  - `GET /screener/diagnostics/factor-lineage/{symbol}`
- round-trip、workflow、route 回归测试

### 包 6：回归测试与文档收口包

目标：

- 保证实现真正可维护
- 保证文档和代码处于同一状态

状态：

- **已完成第一轮收口**

本轮完成内容：

- 修复 `screener_workflow.py` 中的损坏字符串和提示文案
- 修复 `backend/app/api/routes/screener.py` 中的损坏中文文案
- 修复 `backend/tests/test_screener_api.py` 中的损坏测试文案
- 回归测试通过：
  - `backend/tests/test_screener_workflow_cursor.py`
  - `backend/tests/test_screener_api.py`
  - `backend/tests/test_workflow_runtime_service.py`
- 同步主文档：
  - `README.md`
  - `docs/architecture.md`
  - `docs/current_phase.md`
  - `docs/roadmap.md`

## 7. 当前阶段验收结论

截至本任务书当前版本，可以确认：

1. 初筛因子对象已经正式化，不再依赖匿名 dict。
2. 初筛链已经分层，不再把指标、因子、打分全部混在一起。
3. 候选结果可以回溯到因子快照。
4. 因子快照和选择快照都已可按日落袋。
5. 初筛链已经具备最小血缘与诊断能力。
6. 关键 workflow / route 回归已通过。

## 8. 下一步建议

当前不建议回头继续重构骨架。

下一步更合理的是：

1. 把 `screener_factor_snapshot_daily` 正式接入后续验证与复用链路。
2. 将初筛因子结果与更长期的点时特征资产化主线收口。
3. 在不破坏当前工作台体验的前提下，逐步增强筛选解释与验证消费入口。
