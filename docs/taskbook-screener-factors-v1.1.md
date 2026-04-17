# 初筛因子体系项目任务书 v1.1

## 1. 文档定位

本任务书基于《[初筛因子体系设计文档_v1.1](/D:/dev/project/codex/China-Equity-Research-Assistant/docs/初筛因子体系设计文档_v1.1.md)》编制，目标不是重新设计一套独立系统，而是把该设计文档收敛为**可以在当前仓库真实落地的工程实施方案**。

### 1.1 当前实施进度

- `包 1：Schema 与字段口径收口包`：已完成第一版落地。
- `包 2：过程指标与原子因子包`：已完成第一阶段落地。
- `包 3：横截面与连续性因子包`：已完成第一阶段落地。
- `包 4：复合打分与候选分桶包`：已完成第一阶段落地。
- `包 4：复合打分与候选分桶包`：已完成第二阶段落地。
- `包 5：快照落袋与血缘登记包`：已完成第一阶段落地。
- `包 5：快照落袋与血缘登记包`：已完成第二阶段落地。
- 已新增 `screener_factors` 专用 schema，并将初筛 `list_type / v2_list_type / quality_status` 类型口径收口到统一定义。
- 已新增 `ScreenerFactorService`，可基于日线 bars 输出 `ScreenerProcessMetrics`、`ScreenerAtomicFactors` 与 `ScreenerFactorSnapshot`。
- 已补齐 MA、slope、ATR20、收益率、区间位置、流动性、支撑/压力距离等过程指标计算。
- 已补齐趋势、波动、流动性、新股/ST/停牌风险等原子因子判断。
- 已新增 `CrossSectionFactorService`，可对同批次 `ScreenerFactorSnapshot` 进行横截面 rank enrichment。
- 已补齐 `trend_score_raw`、`amount_rank_pct`、`return_20d_rank_pct`、`trend_score_rank_pct`、`atr_pct_rank_pct`、`industry_relative_strength_rank_pct`。
- 已补齐 `trend_persistence_5d`、`liquidity_persistence_5d`、`breakout_readiness_persistence_5d`、`volatility_regime_stability`。
- 已新增 `score_screener_factor_snapshot` 复合打分链路。
- 已在 `ScreenerPipeline` 中接入“`ScreenerFactorSnapshot` 优先、旧 `FactorSnapshot` 回退”的双轨兼容模式。
- 已补齐基于新因子快照的打分测试与 pipeline 回归测试。
- 已支持将 `composite_score / selection_decision` 正式回写到 `ScreenerFactorSnapshot`。
- 已让 `ScreenerCandidate` 展示字段优先复用快照内的 `selection_decision`。
- 已新增 `ScreenerFactorSnapshotDailyDataset`，用于按日、按运行上下文持久化单票初筛因子快照。
- 已在 `ScreenerPipeline` 中接入 `screener_factor_snapshot_daily + lineage_service`，在候选生成后自动落袋并登记血缘。
- 已补齐单票初筛因子快照 round-trip 测试与 pipeline 侧保存/登记测试。
- 已新增 `ScreenerSelectionSnapshotDailyDataset`，用于按批次保存初筛候选选择结果快照。
- 已在 `screener_workflow` 中为批次级 selection snapshot 建立基于 `screener_factor_snapshot_daily` 的直接血缘依赖。
- 已新增 `/screener/diagnostics/selection-lineage/latest` 与 `/screener/diagnostics/factor-lineage/{symbol}` 只读诊断接口。
- 已补齐 selection snapshot round-trip、workflow 落袋/登记、screener 诊断路由测试。
- 已补充最小 schema 测试，后续包将在此基础上继续推进过程指标、原子因子、横截面因子与复合打分实现。

本任务书同时遵循以下项目约束：

- [AGENTS.md](/D:/dev/project/codex/China-Equity-Research-Assistant/AGENTS.md)
- [README.md](/D:/dev/project/codex/China-Equity-Research-Assistant/README.md)
- [docs/architecture.md](/D:/dev/project/codex/China-Equity-Research-Assistant/docs/architecture.md)
- [docs/roadmap.md](/D:/dev/project/codex/China-Equity-Research-Assistant/docs/roadmap.md)
- [docs/a_share_factor_prd_v1.md](/D:/dev/project/codex/China-Equity-Research-Assistant/docs/a_share_factor_prd_v1.md)
- [docs/a_share_architecture_design_spec_v1.md](/D:/dev/project/codex/China-Equity-Research-Assistant/docs/a_share_architecture_design_spec_v1.md)
- [docs/a_share_factor_dictionary_v1.md](/D:/dev/project/codex/China-Equity-Research-Assistant/docs/a_share_factor_dictionary_v1.md)

本任务书聚焦的对象是：

- `初筛因子体系`
- `初筛快照与血缘`
- `基于因子的全市场轻量初筛`

本任务书明确**不**覆盖：

- 深筛研究报告重构
- 交易策略规划重构
- 组合构建与组合监控
- 自动交易执行
- 前端整体重设计

---

## 2. 目标重定义

### 2.1 初筛的产品定位

初筛不是最终交易决策器，而是全市场候选池生成器。

它的职责是：

- 在既有可用数据上，对全市场股票做**轻量、稳定、可批量执行**的筛选；
- 用尽量少、尽量稳、尽量便宜的数据，产出“值得进一步研究”的候选集；
- 为后续深筛、研究、策略与因子验证提供统一的日级输入快照。

它**不负责**：

- 输出最终买卖建议；
- 替代单票研究与策略计划；
- 承担完整财务深挖、事件深挖和公告语义理解；
- 在初筛阶段引入高成本 LLM 或重型研究链路。

### 2.2 本轮工程目标

本轮要把《初筛因子体系设计文档_v1.1》的设计思想，落成一条与当前代码兼容的工程主线：

1. 原始数据层
2. 过程指标层
3. 原子因子层
4. 横截面与连续性因子层
5. 复合因子与规则结果层
6. 初筛快照与候选列表输出层

同时保证：

- 因子定义统一、可测试、可回放；
- 日级快照可落袋、可追踪血缘；
- 不破坏现有 `screener`、`workflow_runtime`、`workspace-bundle` 主链路；
- 与长期方向“因子发现、验证、组合与监控系统”保持一致。

---

## 3. 当前项目现状评估

结合当前仓库代码与文档，项目已经具备以下基础：

### 3.1 已具备的底座

- `data_service` 已形成相对明确的 provider 分层；
- `market_data_service` 已提供 `profile / daily_bars / announcements / financial_summary / universe` 等统一入口；
- `workflow_runtime` 已承担初筛工作流的异步执行与状态查询；
- `workspace-bundle` 已成为单票聚合主壳；
- `trade / review` 闭环已经打通；
- `prediction / dataset / label / backtest / evaluation` 已有基础骨架；
- `lineage` 已进入正式架构，开始记录数据版本与依赖关系。

### 3.2 当前初筛链路的不足

当前初筛能力虽然能运行，但仍存在以下工程问题：

- 初筛因子口径仍偏分散，尚未形成一份正式、唯一、可复用的因子定义清单；
- `screener` 更像“规则筛选集合”，还没有完全升格为“因子快照 -> 评分 -> 结果”的清晰流水线；
- 原始数据、过程指标、原子因子、复合因子的层级边界还不够硬；
- 横截面排名、行业相对强弱、连续性状态等设计文档中的要素尚未完整沉淀；
- 初筛结果与后续因子验证、回测、组合层的衔接接口还不够标准；
- 对“为什么被筛中 / 为什么被排除”的解释性仍偏结果导向，因子视图不够强。

### 3.3 本任务书的工程原则

因此，本任务书不主张推翻已有 `screener_service`，而是主张：

- 保留现有工作流与路由壳；
- 将初筛内部逐步重构为“因子快照优先”的结构；
- 用数据产品、schema、lineage 和 manifest 把它固定下来；
- 让未来的因子验证与组合层直接复用这些产物。

---

## 4. 范围边界

### 4.1 本轮要做

1. 建立初筛因子体系的正式工程任务包。
2. 明确初筛所需的最小原始字段与统一口径。
3. 将过程指标、原子因子、横截面因子、连续性因子、复合因子分层。
4. 设计 `screener factor snapshot` 的统一 schema 与版本策略。
5. 让初筛结果从“直接打分”升级为“因子快照 -> 规则/评分 -> 候选结果”。
6. 明确初筛与数据血缘、版本追踪、评估链路的衔接方式。
7. 给出分阶段实施包、每阶段交付物与验收标准。

### 4.2 本轮不做

1. 不重做前端页面。
2. 不把深筛研究逻辑塞进初筛。
3. 不在初筛引入 LLM 摘要作为硬依赖。
4. 不在本轮直接实现完整因子回测平台。
5. 不在本轮进入组合优化或组合约束。
6. 不引入新的自动调度系统。

---

## 5. 目标架构

### 5.1 六层结构

初筛因子体系按以下六层建设：

1. **原始数据层**
2. **过程指标层**
3. **原子因子层**
4. **横截面 / 连续性因子层**
5. **复合因子与规则结果层**
6. **初筛候选输出层**

### 5.2 与当前仓库目录的对应关系

建议保持与现有目录职责一致：

- `backend/app/services/data_service/`
  - 提供原始数据与标准化入口
- `backend/app/services/feature_service/`
  - 承接过程指标、原子因子、结构状态识别
- `backend/app/services/screener_service/`
  - 承接横截面处理、复合打分、候选输出
- `backend/app/services/lineage_service/`
  - 记录初筛快照血缘
- `backend/app/schemas/`
  - 定义因子快照、评分结果、候选输出 schema
- `backend/app/api/routes/`
  - 只暴露只读结果与工作流入口，不落复杂逻辑

### 5.3 推荐新增的工程对象

建议新增或补齐以下对象：

- `ScreenerRawInputs`
- `ScreenerProcessMetrics`
- `ScreenerAtomicFactors`
- `ScreenerCrossSectionFactors`
- `ScreenerCompositeScore`
- `ScreenerFactorSnapshot`
- `ScreenerSelectionDecision`

这些对象不一定全部单独暴露为 API，但必须在内部形成清晰边界。

---

## 6. 数据口径与统一定义

### 6.1 最小原始输入

根据设计文档 v1.1，初筛最小原始输入锁定为：

#### 股票基础信息

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

#### 日线行情

- `trade_date`
- `open`
- `high`
- `low`
- `close`
- `volume`
- `amount`

#### 可选异常标记

- 停牌标记
- ST 标记
- 异常状态标记

### 6.2 过程指标层

本层负责将原始行情转为可复用的中间指标，建议至少包括：

- `ma_5`
- `ma_10`
- `ma_20`
- `ma_60`
- `ma_120`
- `ma_20_slope`
- `ma_60_slope`
- `close_percentile_60d`
- `return_20d`
- `return_60d`
- `atr_20`
- `atr_20_pct`
- `range_20d`
- `volatility_20d`
- `avg_amount_5d`
- `avg_amount_20d`
- `amount_ratio_5d_20d`
- `support_level_20d`
- `resistance_level_20d`
- `distance_to_support_pct`
- `distance_to_resistance_pct`

原则：

- 过程指标只做确定性计算，不夹带“好坏判断”；
- 统一在 `feature_service` 内计算；
- 与日级 `as_of_date` 强绑定。

### 6.3 原子因子层

建议将初筛原子因子按以下维度收口：

#### 趋势因子

- `close_above_ma20`
- `close_above_ma60`
- `ma20_above_ma60`
- `ma20_slope_positive`
- `ma60_slope_positive`
- `trend_state_basic`

#### 动量因子

- `return_20d_strength`
- `return_60d_strength`
- `close_percentile_strength`

#### 波动与位置因子

- `atr_pct_state`
- `range_state`
- `near_support`
- `breakout_ready`
- `distance_to_resistance_state`

#### 流动性因子

- `amount_level_state`
- `amount_ratio_state`
- `liquidity_pass`

#### 风险过滤因子

- `is_new_listing_risk`
- `is_st_risk`
- `is_suspended_risk`
- `basic_universe_eligibility`

### 6.4 横截面因子层

建议至少落地以下横截面指标：

- `amount_rank_pct`
- `return_20d_rank_pct`
- `trend_score_rank_pct`
- `atr_pct_rank_pct`
- `industry_relative_strength_rank_pct`

原则：

- 横截面只在“同批次、同 as_of_date、同 universe”内计算；
- 其版本必须绑定当日的 universe 快照；
- 必须明确使用的股票池范围，不能隐式变化。

### 6.5 连续性因子层

连续性因子用于提高稳定性，避免单日偶然波动导致误筛：

- `trend_persistence_5d`
- `liquidity_persistence_5d`
- `breakout_readiness_persistence_5d`
- `volatility_regime_stability`

本层建议采用朴素规则实现，不引入复杂状态机。

### 6.6 复合因子与结果分桶

建议输出至少三类结果分桶：

- `BUY_CANDIDATE`
- `WATCHLIST`
- `AVOID`

并统一配套：

- `screener_score`
- `factor_summary`
- `selection_reasons`
- `exclusion_reasons`
- `quality_flags`

---

## 7. 模块拆分建议

### 7.1 Schema 包

建议新增或补齐：

- `backend/app/schemas/screener_factors.py`

至少包含：

- `ScreenerProcessMetrics`
- `ScreenerAtomicFactors`
- `ScreenerCrossSectionFactors`
- `ScreenerCompositeScore`
- `ScreenerFactorSnapshot`
- `ScreenerSelectionDecision`

### 7.2 Feature Service 包

在 `feature_service` 中集中承接：

- 日线过程指标计算
- 原子因子状态识别
- 支撑/压力、波动、趋势状态识别
- 连续性因子计算

禁止把这些逻辑散落回 `screener_service`。

### 7.3 Screener Service 包

在 `screener_service` 中集中承接：

- universe 过滤
- 横截面排序
- 行业相对强弱计算
- 复合打分
- 候选分桶
- 结果摘要

### 7.4 Data Product / Lineage 包

建议将初筛核心产物纳入统一数据产品口径：

- `screener_factor_snapshot_daily`
- `screener_selection_snapshot_daily`

每个产物都应带：

- `dataset`
- `dataset_version`
- `as_of_date`
- `symbol` 或 `global`
- `provider_used`
- `source_mode`
- `freshness_mode`
- `generated_at`
- `lineage_metadata`

### 7.5 Workflow 集成包

不改现有初筛工作流入口，但内部流程建议重排为：

1. universe 获取
2. 原始数据批量获取
3. 过程指标计算
4. 原子因子计算
5. 横截面与连续性因子计算
6. 复合打分与分桶
7. 候选列表输出与快照落袋

---

## 8. 分阶段实施包

## 8.1 包 1：Schema 与字段口径收口包

### 目标

先把初筛因子体系的字段、对象与口径固定下来。

### 交付物

- `screener_factors.py` schema 文件
- 因子字段字典
- 统一命名与中文解释
- 初筛快照版本命名规则

### 验收标准

- 初筛相关对象不再使用大段匿名 dict；
- 每个核心因子字段都有唯一含义；
- 日级快照可以被 typed schema 表达。

## 8.2 包 2：过程指标与原子因子包

### 目标

把设计文档中的计算公式正式工程化。

### 当前进度

- 已完成第一阶段：
  - 新增 `feature_service.screener_factor_service`
  - 输出 `ScreenerFactorSnapshot`
  - 落地过程指标与原子因子
  - 补充单元测试并完成最小回归
- 下一阶段将进入：
  - 横截面因子所需的 batch 上下文准备
  - 与初筛 pipeline 的结构化衔接

### 交付物

- MA / slope / percentile / ATR / 波动 / 流动性 / 支撑压力计算
- 趋势、动量、位置、流动性、风险过滤原子因子
- 单元测试

### 验收标准

- 关键指标计算可重复；
- 不依赖 LLM；
- 测试不依赖实时外网。

## 8.3 包 3：横截面与连续性因子包

### 目标

实现“同日同池比较”的核心能力。

### 当前进度

- 已完成第一阶段：
  - 单票连续性指标已在 `ScreenerFactorService` 内落地
  - 同批次 rank enrichment 已在 `CrossSectionFactorService` 内落地
  - 已补充单元测试并完成最小回归
- 下一阶段将进入：
  - 与初筛 pipeline 的结果对象衔接
  - 为包 4 的复合打分与候选分桶做结构准备

### 交付物

- rank pct 系列指标
- 行业相对强弱指标
- 连续性指标
- batch 级快照上下文定义

### 验收标准

- 同一批次结果稳定；
- 明确使用的 universe；
- 可解释“该票为何在同批股票中更强/更弱”。

## 8.4 包 4：复合打分与候选分桶包

### 目标

将因子快照转为初筛结果。

### 当前进度

- 已完成第一阶段：
  - 新增 `score_screener_factor_snapshot`
  - 基于 `ScreenerFactorSnapshot` 计算 `alpha_score / trigger_score / risk_score / screener_score`
  - 保留现有 `FactorSnapshot` 打分链路作为兼容回退
  - `ScreenerPipeline` 已能消费新的初筛因子快照并完成候选分桶
  - 已补充单元测试与 pipeline 回归测试
- 已完成第二阶段：
  - 已将 `composite_score / selection_decision` 回写到 `ScreenerFactorSnapshot`
  - 已让初筛候选结果优先复用快照中的决策摘要
- 下一阶段将进入：
  - 快照落袋、血缘登记与只读诊断能力

### 交付物

- `screener_score` 规则
- `BUY_CANDIDATE / WATCHLIST / AVOID` 分桶规则
- `selection_reasons / exclusion_reasons`
- 与现有 `screener` 输出 schema 的兼容映射

### 验收标准

- 初筛结果不再只是黑盒分数；
- 每个结果能回溯到因子原因；
- 单票失败不影响整批执行。

## 8.5 包 5：快照落袋、血缘与诊断包

### 目标

让初筛因子产物可以被回溯、验证和复用。

### 交付物

- `screener_factor_snapshot_daily`
- `screener_selection_snapshot_daily`
- lineage metadata 挂接
- manifest / repository 登记
- 只读诊断接口或内部查询能力

### 验收标准

- 能回答“这只股票这一天为什么被筛出来”；
- 能回答“使用了哪一版日线与 universe 数据”；
- 能为后续回测与验证复用。

## 8.6 包 6：回归测试与文档收口包

### 目标

保证实现真正可维护。

### 交付物

- schema 测试
- feature 计算测试
- screener pipeline 回归测试
- lineage 回归测试
- README / architecture / current_phase / roadmap 的最小同步

### 验收标准

- 关键链路测试可脱网运行；
- 文档与代码一致；
- 不出现第二套冲突叙事。

---

## 9. 关键验收标准

本任务书完成后，系统至少要满足以下标准：

1. 初筛因子定义形成正式、唯一、可引用的工程对象。
2. 初筛链路明确分层，不再把过程指标、原子因子、横截面因子、复合打分混在一起。
3. 初筛输出能解释“为什么入选”和“为什么未入选”。
4. 初筛结果能落袋为日级快照，而不是只停留在临时运行结果。
5. 初筛快照带血缘元数据，可追溯上游数据版本与 provider。
6. 初筛因子产物可被后续回测、验证、组合层复用。
7. 不破坏当前 `workflow_runtime` 与现有 API 主入口。

---

## 10. 风险与约束

### 10.1 禁止事项

- 禁止把深筛研究逻辑搬进初筛；
- 禁止在初筛阶段直接依赖高成本公告/财报全文分析；
- 禁止把 provider 映射、日期标准化、单位换算散落到多个模块；
- 禁止为了“先跑起来”返回非结构化结果；
- 禁止绕开现有 lineage 与 dataset version 体系另搞一套命名。

### 10.2 主要风险

- universe 范围不固定会导致横截面指标漂移；
- 数据补全策略不清会导致同日因子快照不稳定；
- 过程指标与原子因子边界不清会导致代码不断重复；
- 结果层若过早写死大量权重，会阻碍后续因子验证。

### 10.3 控制原则

- 先定义字段，再写计算；
- 先写快照，再谈评分；
- 先稳定批量执行，再逐步优化分数；
- 初筛优先高召回、可解释、低成本，而不是追求“看起来很聪明”。

---

## 11. 与长期主线的衔接

这套初筛因子体系不是临时模块，而是未来主线的一部分。

它将直接衔接到以下长期方向：

1. **因子字典主线**
   - 初筛原子因子和横截面因子将成为因子字典的正式候选条目。
2. **因子验证主线**
   - 日级快照可直接进入样本外验证与分层测试。
3. **组合主线**
   - 初筛结果未来可以作为组合候选池入口。
4. **监控主线**
   - 连续性因子与状态变化可进入因子衰减与监控。

因此，本任务书的本质不是“把当前 screener 修漂亮”，而是：

**把初筛正式升级为因子系统的前置生产线。**

---

## 12. 推荐实施顺序

建议按以下顺序推进：

1. 包 1：Schema 与字段口径收口包
2. 包 2：过程指标与原子因子包
3. 包 3：横截面与连续性因子包
4. 包 4：复合打分与候选分桶包
5. 包 5：快照落袋、血缘与诊断包
6. 包 6：回归测试与文档收口包

不建议跳过前两包直接改 `screener` 结果页，因为那会把“因子体系建设”再次退化成“页面临时展示改造”。

---

## 13. 本轮结论

基于《初筛因子体系设计文档_v1.1》和当前仓库现状，本项目下一阶段最合适的推进方式不是继续零散优化 `screener` 规则，而是正式立项为：

**“初筛因子体系工程化任务”**

它的核心价值在于：

- 让初筛结果更稳定；
- 让初筛理由更可解释；
- 让初筛产物可验证；
- 让初筛真正并入长期的因子发现、验证、组合与监控系统主线。
