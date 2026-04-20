# 因子优先股票初筛方案需求设计书 v1

## 1. 文档目标

本文档基于项目当前实现状态，定义一套面向 A 股全市场初筛的“因子优先”方案系统。

目标不是直接构建完整的高自由度量化研究平台，而是在当前已有的：

- `ScreenerFactorSnapshot`
- `ScreenerBatchRecord / ScreenerSymbolResult`
- `screener_factor_snapshot_daily`
- `screener_selection_snapshot_daily`
- `trade / review / decision snapshot`

这些能力基础上，落地一个：

- 以因子为出发点的初筛逻辑；
- 支持用户自定义筛选方案；
- 可持久化记录每次筛选方案与结果；
- 可在后续交易与复盘中追踪方案有效性的系统。

本文档同时覆盖需求设计与落地设计约束，作为前后端重构的统一基线。

## 2. 背景与现状判断

### 2.1 当前项目现状

当前项目已经具备初筛因子化骨架，但尚未形成完整的“方案级”初筛系统。

已有基础能力：

- 初筛链路已支持 `ScreenerFactorSnapshot`，包含：
  - `raw_inputs`
  - `process_metrics`
  - `atomic_factors`
  - `cross_section_factors`
  - `composite_score`
  - `selection_decision`
- 初筛链路已支持批内横截面增强与持续性指标；
- 初筛结果已支持批次保存与窗口读取；
- 初筛因子快照已支持按日落盘与 lineage 追踪；
- 初筛结果已支持基础质量门控；
- 交易与复盘主线已经存在，可作为后续“方案效果反馈”的承接层。

当前不足：

- 初筛结果仍以“结果列表”视角为主，而非“因子方案”视角；
- 初筛没有独立的“筛选方案对象”，无法明确回答“这次是按哪套方案筛出来的”；
- 当前阈值与权重主要是工程经验值，缺少版本化管理；
- 初筛侧的财务与公告更多作为质量门控，而不是完整主评分因子；
- 单票侧 `FactorSnapshot` 与初筛侧 `ScreenerFactorSnapshot` 还未统一为同一套因子语言；
- 当前无法系统复盘“某套筛选方案在后续研究、交易、复盘中的表现”。

### 2.2 当前系统中与本设计直接相关的资产

当前设计应优先复用以下对象与服务：

- Schema
  - `ScreenerFactorSnapshot`
  - `ScreenerCandidate`
  - `ScreenerBatchRecord`
  - `ScreenerSymbolResult`
  - `DecisionSnapshot`
  - `TradeRecord`
  - `ReviewRecord`
- Service
  - `ScreenerPipeline`
  - `CrossSectionFactorService`
  - `ScreenerBatchService`
  - `LineageService`
  - `PredictionService`
- Data products
  - `screener_factor_snapshot_daily`
  - `screener_selection_snapshot_daily`

本方案明确要求：新功能优先建立在这些现有能力之上，而不是另起一套并行初筛系统。

## 3. 设计目标

### 3.1 核心目标

建设一个“因子优先”的股票初筛系统，使用户能够：

1. 以因子方案而不是固定内置规则发起初筛；
2. 自定义因子组合、部分权重、部分阈值和质量门控；
3. 保存每套筛选方案及其版本；
4. 保存每次运行时的完整方案快照与结果快照；
5. 在后续研究、交易、复盘中追踪方案产出的候选表现；
6. 逐步形成可记录、可复盘、可迭代的初筛方法论。

### 3.2 非目标

当前阶段明确不做：

- 开放无限制的自由 DSL 规则编排；
- 允许用户任意修改所有因子内部打分函数；
- 在初筛阶段完整执行 PRD 的全部四层因子与复杂验证逻辑；
- 直接把“用户自定义方案”包装成自动交易策略；
- 在没有版本化和复盘机制前开放高自由度调参。

## 4. 总体设计原则

### 4.1 因子优先，结果次之

用户首先操作的是“方案”和“因子解释”，其次才是结果列表。

### 4.2 方案化优先于自由调参

第一阶段先建设“筛选方案系统”，再逐步开放少量关键参数，不直接开放全量调参。

### 4.3 轻量初筛优先于完整研究

初筛只消费低成本、高覆盖、可解释的因子子集。

### 4.4 运行快照必须可重建

每次初筛运行都必须保存：

- 使用的方案版本；
- 使用时的参数快照；
- 运行上下文；
- 结果快照；
- 因子快照引用。

### 4.5 方案复盘必须贯穿交易反馈

筛选方案不能只保存“筛出了哪些票”，还必须可连接后续：

- 是否进入研究；
- 是否形成交易；
- 交易后结果如何；
- 哪类候选更有效。

## 5. 目标能力范围

### 5.1 第一阶段必须支持

- 方案创建、查看、复制、启停；
- 方案版本化；
- 基于方案发起初筛；
- 保存运行结果与方案快照；
- 在结果页展示方案相关信息；
- 在后续研究/交易/复盘中挂接方案来源；
- 提供基础的方案复盘视图。

### 5.2 第二阶段增强

- 多方案对比；
- 方案效果统计；
- 参数变更前后效果对比；
- 基于方案维度的候选命中、交易转化与复盘结果分析。

### 5.3 第三阶段增强

- 受控高级调参；
- 因子阈值实验；
- 简化版方案回放；
- 与验证/评估主线更紧密集成。

## 6. 因子优先初筛的设计边界

### 6.1 初筛使用的因子层

当前阶段初筛不直接使用完整四层因子引擎，而是使用其“适合全市场轻量扫描”的子集。

建议初筛默认因子池分为四类：

1. 技术趋势与位置类
   - 趋势状态
   - 趋势强度
   - 回踩接近度
   - 突破准备度
   - 收盘价区间位置
2. 横截面相对强弱类
   - 20 日收益分位
   - 趋势分位
   - 行业相对强弱分位
3. 流动性与稳定性类
   - 成交额水平
   - 成交额分位
   - 流动性持续性
   - 波动稳定性
4. 质量门控类
   - bars quality
   - financial quality
   - announcement quality

### 6.2 初筛暂不作为主评分核心的因子

以下能力当前可保留为扩展位或深筛能力，不作为第一阶段初筛主评分核心：

- 复杂行业扩散率与题材拥挤度；
- 高语义依赖的事件理解；
- 高频或微观结构类因子；
- 完整市场 regime 联动；
- 传播/情绪因子；
- 高维财务边际改善体系。

## 7. 目标用户故事

### 7.1 方案创建

作为用户，我希望创建一套“趋势强势 + 回踩观察”的初筛方案，选择我关心的因子组、设置基础门槛和权重，保存后反复使用。

### 7.2 方案运行

作为用户，我希望在初筛页选择某个方案执行，而不是固定运行系统内置规则。

### 7.3 方案追踪

作为用户，我希望知道当前结果列表是由哪套方案、哪个版本筛出来的。

### 7.4 方案复盘

作为用户，我希望查看某套方案过去 30 天筛出的股票中：

- 有多少进入了单票研究；
- 有多少最终记录了交易；
- 后续复盘表现如何；
- 哪类候选最有效。

## 8. 核心对象设计

### 8.1 ScreenerScheme

表示一套可复用的初筛方案。

建议字段：

- `scheme_id`
- `name`
- `description`
- `status`
  - `draft`
  - `active`
  - `archived`
- `owner`
- `created_at`
- `updated_at`
- `current_version`
- `default_for_workspace` 可选

### 8.2 ScreenerSchemeVersion

表示一套方案在某一时刻的固定版本。

建议字段：

- `scheme_id`
- `scheme_version`
- `version_label`
- `created_at`
- `change_note`
- `snapshot_hash`
- `is_active`

内容部分建议结构化存储为：

- `universe_filter_config`
- `factor_selection_config`
- `factor_weight_config`
- `threshold_config`
- `quality_gate_config`
- `bucket_rule_config`
- `output_display_config`

### 8.3 ScreenerRunContextSnapshot

表示某次运行时使用的完整上下文快照，防止后续方案版本变化后无法回溯。

建议字段：

- `run_id`
- `scheme_id`
- `scheme_version`
- `scheme_snapshot_hash`
- `trade_date`
- `started_at`
- `finished_at`
- `workflow_name`
- `batch_size`
- `max_symbols`
- `top_n`
- `force_refresh`
- `cursor_start_symbol`
- `cursor_start_index`
- `effective_params_snapshot`

### 8.4 SchemeResultLink

表示方案运行结果与候选、研究、交易、复盘之间的连接对象。

建议字段：

- `run_id`
- `batch_id`
- `symbol`
- `scheme_id`
- `scheme_version`
- `selection_bucket`
- `selection_rank`
- `selection_score`
- `factor_snapshot_dataset_version`
- `entered_research` 布尔
- `decision_snapshot_id` 可空
- `trade_id` 可空
- `review_id` 可空

## 9. 方案配置模型

### 9.1 UniverseFilterConfig

控制股票进入扫描前必须满足的条件。

建议第一阶段支持：

- 是否排除 ST
- 是否排除停牌
- 最低上市天数
- 最低日线数量
- 最低 20 日均成交额
- 是否允许北交所/科创板/创业板单独开关

### 9.2 FactorSelectionConfig

控制本方案启用哪些因子组。

建议第一阶段支持：

- trend_strength
- relative_return
- industry_relative_strength
- liquidity_level
- liquidity_persistence
- breakout_readiness
- support_distance
- volatility_regime_stability

### 9.3 FactorWeightConfig

控制启用因子在总评分中的权重。

建议要求：

- 权重和必须为 1.0；
- 未启用因子不得配置权重；
- 第一阶段只允许配置组级权重，不开放原子因子级自由权重。

### 9.4 ThresholdConfig

控制少量关键阈值。

建议第一阶段允许修改：

- 最低均成交额
- 最低 alpha_score
- 最低 trigger_score
- 最高 risk_score
- `READY_TO_BUY` 进入门槛
- `WATCH` 进入门槛

暂不开放：

- 所有内部 piecewise 映射阈值；
- 所有原子因子分类边界；
- 所有 scoring bonus/penalty 数值。

### 9.5 QualityGateConfig

控制数据质量门槛与折损策略。

建议第一阶段支持：

- 是否允许 `warning` 进入高优先级候选；
- `degraded` 是否直接降为 `RESEARCH_ONLY`；
- `failed` 是否直接排除；
- bars / financial / announcement 三类质量权重；
- 是否开启分数折损。

### 9.6 BucketRuleConfig

控制最终候选分桶。

建议第一阶段仍限制为固定桶集合：

- `READY_TO_BUY`
- `WATCH_PULLBACK`
- `WATCH_BREAKOUT`
- `RESEARCH_ONLY`
- `AVOID`

用户只允许配置：

- 每个桶的进入条件阈值；
- 是否启用某个桶；
- 每个桶的展示优先级。

## 10. 方案执行流程

### 10.1 运行前

1. 用户选择方案；
2. 系统解析当前激活版本；
3. 生成本次 `ScreenerRunContextSnapshot`；
4. 计算 `scheme_snapshot_hash`；
5. 将运行上下文写入 workflow 输入。

### 10.2 运行中

1. 读取 universe；
2. 执行 universe filters；
3. 对每只股票构建 `ScreenerFactorSnapshot`；
4. 批内执行横截面增强；
5. 根据方案权重与阈值评分；
6. 执行 quality gate；
7. 生成 candidate / bucket / selection decision；
8. 持久化因子快照；
9. 持久化结果快照；
10. 保存运行批次与结果列表。

### 10.3 运行后

1. 保存 `ScreenerBatchRecord`；
2. 保存 `ScreenerSymbolResult`；
3. 保存 `SchemeResultLink`；
4. 将 `scheme_id / scheme_version / scheme_snapshot_hash` 写入批次与结果元信息；
5. 允许前端按方案维度回看。

## 11. 存储与版本设计

### 11.1 必须新增的持久化信息

当前已有：

- 批次记录
- 结果记录
- 因子快照

本方案新增要求：

- 方案主表
- 方案版本表
- 运行时方案上下文快照
- 结果与方案关联表

### 11.2 版本策略

每次发生以下变更之一，必须生成新 `scheme_version`：

- 因子集合变化；
- 权重变化；
- 阈值变化；
- 质量门控变化；
- 分桶规则变化；
- universe 过滤规则变化。

禁止仅修改现有版本内容而不升版。

### 11.3 参数哈希

每次运行必须保存一份 `scheme_snapshot_hash`。

作用：

- 防止“版本号相同但内容不同”；
- 支撑后续回放与结果追踪；
- 支撑方案效果归因。

## 12. 结果记录设计

### 12.1 结果对象必须新增的元信息

在现有 `ScreenerCandidate / ScreenerSymbolResult` 基础上，建议增加：

- `scheme_id`
- `scheme_version`
- `scheme_name`
- `scheme_snapshot_hash`
- `selected_factor_groups`
- `scoring_profile_name`
- `quality_gate_profile_name`

### 12.2 结果页必须展示

第一阶段至少展示：

- 本批次使用的方案名
- 方案版本
- 关键参数摘要
- 当前 bucket 规则摘要
- 当前质量门槛摘要

## 13. 方案复盘设计

### 13.1 复盘目标

不是只看“筛出多少股票”，而是看：

- 候选到研究的转化率；
- 候选到交易的转化率；
- 交易到正向复盘结果的比例；
- 不同 bucket 的后续质量差异；
- 因子组合是否稳定。

### 13.2 基础复盘指标

第一阶段建议支持：

- 运行次数
- 总候选数
- 各 bucket 数量
- 进入单票研究数
- 生成 decision snapshot 数
- 产生交易记录数
- 产生 review 记录数
- review 中 success / failure / no_trade 比例

### 13.3 扩展复盘指标

第二阶段建议支持：

- 不同 bucket 的交易转化率
- 方案筛选后 5/10/20 日表现统计
- 按行业拆分的候选表现
- 按质量状态拆分的候选表现
- 因子组合稳定性与漂移监控

### 13.4 复盘归因要求

复盘页面应能回答：

- 这笔交易来自哪次初筛运行？
- 该次运行使用了哪套方案？
- 当时这只股票被选中时主要正负因子是什么？
- 当时是否存在质量折损？

## 14. 当前阈值与参数的治理要求

### 14.1 当前阈值的性质

项目当前多数阈值属于工程经验阈值，而非严格验证后的最优参数。

因此设计上必须承认：

- 参数是“版本内假设”，不是“客观真理”；
- 参数变化应被视为新方案版本；
- 同一方案不同参数不可直接混看。

### 14.2 参数治理要求

第一阶段：

- 只开放少量关键参数；
- 每次变更自动升版；
- 所有结果挂到具体版本。

第二阶段：

- 补充参数变更说明；
- 支持版本对比；
- 支持参数影响分析。

## 15. 前端交互要求

### 15.1 交互主线

新的初筛前端建议从“结果列表中心”改为“方案中心”：

1. 选择方案
2. 查看方案说明
3. 运行方案
4. 查看结果
5. 查看结果背后的因子解释
6. 进入单票研究
7. 进入交易与复盘

### 15.2 页面结构建议

建议拆为四个主区域：

1. 方案区
   - 当前方案
   - 方案版本
   - 因子组
   - 关键参数
2. 运行区
   - 运行状态
   - 批次信息
   - 运行摘要
3. 结果区
   - 候选列表
   - bucket 分布
   - 排序与过滤
4. 复盘区
   - 方案历史表现
   - 转化与复盘统计

### 15.3 第一阶段前端限制

不建议第一阶段直接支持：

- 任意编辑所有原子因子；
- 任意新增自由表达式；
- 前端直接拼接复杂规则 DSL。

## 16. 后端落地建议

### 16.1 Phase A：方案对象与版本对象

新增：

- `ScreenerScheme`
- `ScreenerSchemeVersion`
- 读写 service
- schema
- API

### 16.2 Phase B：运行时方案快照接入 ScreenerPipeline

要求：

- pipeline 支持从 scheme version 读取配置；
- 将配置转成运行时评分参数；
- 把方案上下文写入 run context。

### 16.3 Phase C：结果与方案挂接

要求：

- batch/result 增加方案元信息；
- 支持按方案维度查询结果；
- 支持 lineage 与方案联合查询。

### 16.4 Phase D：方案复盘统计

要求：

- 提供方案级 summary 接口；
- 聚合 research / decision snapshot / trade / review。

## 17. 测试要求

新增功能必须至少覆盖以下测试：

1. 方案 schema 校验
2. 方案版本化
3. 方案参数哈希一致性
4. 方案驱动的初筛运行
5. 结果记录包含方案元信息
6. 方案复盘统计聚合
7. 参数变更后结果版本隔离

禁止只做前端页面逻辑，不补后端对象与测试。

## 18. 验收标准

### 18.1 第一阶段验收

满足以下条件可视为通过：

- 能创建并保存至少 3 套方案；
- 能按方案发起初筛；
- 每次运行结果能追溯到具体方案版本；
- 候选结果页能看到方案摘要；
- 可从方案维度查看历史运行记录；
- 可统计某方案筛出的候选后续进入研究/交易/复盘的数量。

### 18.2 第二阶段验收

- 可对比两个方案在同一窗口内的结果差异；
- 可查看参数变化前后的表现差异；
- 可按 bucket 维度查看后续反馈统计。

## 19. 风险与应对

### 风险 1：开放过早调参导致系统失控

应对：

- 第一阶段限制参数范围；
- 仅开放少量关键阈值；
- 高级调参必须放到后续阶段。

### 风险 2：没有方案版本化，结果不可复盘

应对：

- 每次变更强制升版；
- 每次运行写入 `scheme_snapshot_hash`。

### 风险 3：把初筛变成重型研究系统

应对：

- 严格限制初筛因子池；
- 保持初筛轻量；
- 深筛与单票研究承接复杂分析。

### 风险 4：当前参数大多为经验值，用户误以为已验证

应对：

- 在产品与文档中明确“当前为经验参数版本”；
- 方案页显示参数说明与风险提示；
- 后续逐步接入验证层。

## 20. 最终结论

基于项目现状，建设“因子优先、可记录、可复盘”的股票初筛系统是可行的，而且应当作为前端与初筛主线重构的下一阶段核心目标。

但落地方式必须遵守以下原则：

- 先建设方案系统，再谨慎开放调参；
- 先做轻量因子优先初筛，再逐步走向完整四层因子框架；
- 先保证可记录、可回看、可复盘，再扩展高级灵活性。

本设计书定义的不是一个“自由量化平台”，而是一套适配当前项目阶段、能真正落地的“因子优先初筛方案系统”。
