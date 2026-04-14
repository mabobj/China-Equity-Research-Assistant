# 系统架构

本文描述当前真实架构、长期目标架构，以及数据底座在长期方向下仍需补齐的有限缺口。

## 1. 架构定位

当前项目是一套面向中国大陆 A 股市场的单用户研究、预测与决策工作台。

它包含两条并行主线：

1. 研究与决策工作台主线  
   负责把公开数据组织成结构化研究、结构化策略、选股结果、交易记录与复盘闭环。

2. 预测与评估主线  
   负责特征、标签、回测、预测、评估与版本治理，逐步服务于长期北极星：因子发现、验证、组合与监控系统。

当前代码已经具备第一条主线的完整壳层，并完成了第二条主线的最小底座接入。

## 2. 当前分层结构

```text
前端工作台（Next.js）
  -> API 路由层（FastAPI）
  -> Service 层（data / feature / review / debate / strategy / screener / workflow / trade-review / prediction）
  -> Provider 层（外部与本地数据源适配）
  -> 本地存储层（SQLite + DuckDB/Parquet + JSON artifacts）
  -> Schema 层（Pydantic typed contracts）
```

分层原则：

- 路由层只做请求接收、参数校验和响应封装
- 复杂业务逻辑集中在 service 层
- 所有外部数据访问必须通过 provider 层
- 统一输出 typed schema，不直接暴露原始 provider dict 或 dataframe

## 3. 当前产品主链路

### 3.1 单票主链路

主入口：

- `GET /stocks/{symbol}/workspace-bundle`

当前 bundle 聚合：

- `profile`
- `factor_snapshot`
- `review_report`
- `debate_review`
- `strategy_plan`
- `trigger_snapshot`
- `decision_brief`
- `predictive_snapshot`
- `module_status_summary`
- `evidence_manifest`
- `freshness_summary`

容错策略：

- 采用 `200 + module_status_summary`
- 单模块失败时整包仍返回主结果
- 同时暴露：
  - `provider_used`
  - `fallback_applied`
  - `fallback_reason`
  - `runtime_mode_requested`
  - `runtime_mode_effective`
  - `warning_messages`

### 3.2 选股与深筛主链路

主入口：

- `POST /workflows/screener/run`
- `POST /workflows/deep-review/run`
- `GET /workflows/runs/{run_id}`

当前形态：

- workflow 驱动，而非同步长请求
- 轮询获取运行步骤、局部失败、最终结果
- 支持批次结果台账与当前展示窗口

### 3.3 交易与复盘闭环

主入口：

- `POST /decision-snapshots`
- `POST /trades`
- `POST /reviews/from-trade/{trade_id}`

持久化对象：

- `decision_snapshots`
- `trade_records`
- `review_records`

这条链当前是“最小可用闭环”，不是持仓系统，也不是自动交易系统。

## 4. 数据底座当前形态

### 4.1 provider 优先级

当前默认优先级：

- `tdx-api > mootdx > akshare > baostock`

补充规则：

- 公告正式披露以 `CNINFO` 为准
- `mootdx` 作为本地高速历史源，但必须经过 freshness / validity 检查
- `AKShare` 主要承担补充型与结构化研究型数据
- `BaoStock` 承担稳定兜底角色

### 4.2 数据清洗层

当前已正式纳入统一清洗契约的对象：

- `bars`
- `financial_summary`
- `announcements`

统一链路：

`provider/local raw -> cleaning -> contracts -> market_data_service -> downstream`

统一质量字段：

- `quality_status`
- `cleaning_warnings`
- `missing_fields`
- `coerced_fields`
- `provider_used`
- `fallback_applied`
- `fallback_reason`
- `source_mode`
- `freshness_mode`

### 4.3 日级数据产品

当前已落地的日级数据产品包括：

- `daily_bars_daily`
- `announcements_daily`
- `financial_summary_daily`
- `factor_snapshot_daily`
- `review_report_daily`
- `debate_review_daily`
- `strategy_plan_daily`
- `decision_brief_daily`
- `screener_snapshot_daily`

这套体系已经支撑“本地优先、按日复用、缺啥补啥”的当前链路。

当前在日线层还已进一步显式化：

- `adjustment_mode`：统一表达当前价格口径，第一阶段默认收口为 `raw`
- `trading_status`：为停牌等交易状态预留标准化承载位
- `corporate_action_flags`：为分红送转等公司行为影响预留标准化承载位
- `DailyBarResponse` 增加 `corporate_action_mode / corporate_action_warnings`，避免把“公司行为尚未完整建模”继续隐式化

## 5. 长期目标架构

长期目标不是继续把现有研究模块无限堆高，而是把现有工作台作为产品壳层，逐步接入更完整的预测与因子系统。

目标架构可以抽象为六层：

1. 数据与清洗层  
   provider、标准化、数据质量、日级数据产品。

2. 点时特征层  
   point-in-time 特征资产，支持任意 `symbol + as_of_date` 重建。

3. 标签与样本层  
   未来收益、超额收益、命中标签、setup 成功率标签等。

4. 预测与评估层  
   baseline、监督学习模型、walk-forward 回测、评估与校准。

5. 研究与策略层  
   继续负责结构化解释与行动计划，但逐步消费预测结果。

6. 交易与反馈层  
   记录实际执行、生成复盘、形成真实反馈，为后续因子验证和模型评估服务。

## 6. 数据底座在长期方向下仍需补齐的关键缺口

这里强调“有限缺口”，不是无止境优化清单。

### 6.1 点时一致性仍未完全工程化

当前系统已经有 `as_of_date`、日级快照和 freshness 规则，但长期因子验证要求：

- 任意交易日都能重建当时可见输入
- 特征与标签严格隔离未来信息
- 训练、预测、回测共享统一的点时数据定义

这是从“研究系统”升级到“可验证预测系统”的第一道门槛。

### 6.2 数据域还不够支撑长期因子主线

当前主链路主要围绕：

- 单票基本资料
- 行情 bars
- 财务摘要
- 公告索引

长期因子系统还需要逐步纳入：

- 指数与基准
- 行业与板块分类
- 市场广度
- 资金与风格代理变量
- 风险暴露与 regime 变量

不是立刻全做，而是要把这些列入明确的数据产品路线图。

当前已经完成这一方向的第一阶段收口：

- `BenchmarkCatalogResponse` 提供稳定的标准基准目录；
- `StockClassificationSnapshot` 把单票 `行业 + 板块 + 主基准映射` 固化为按日可读快照；
- `MarketBreadthSnapshot` 把市场广度收成统一 schema 与日级数据产品；
- `RiskProxySnapshot` 在市场广度基础上提供最小基础风险代理；
- 对外已提供最小只读接口：
 - `GET /market/benchmarks`
  - `GET /market/benchmarks/{benchmark_symbol}/daily-bars`
  - `GET /market/breadth`
  - `GET /market/risk-proxies`
  - `GET /stocks/{symbol}/classification`

这一步仍然是“关键数据域标准层”，不是完整指数行情系统；真实指数/基准行情链路与更丰富的风格代理变量，仍属于后续包内继续补齐的范围。

### 6.3 复权、公司行为与交易状态口径仍需继续集中化

长期回测与因子验证要求明确处理：

- 原始价 / 前复权 / 后复权
- 停牌
- ST / 退市
- 分红送转
- 缺失交易日与异常 bar

当前已经完成两步关键收口：

- `DailyBar / DailyBarResponse` 已显式暴露 `adjustment_mode`
- `daily_bars` 本地存储已按 `symbol + trade_date + adjustment_mode` 区分保存
- `market_data_service.get_daily_bars()` 与 `/stocks/{symbol}/daily-bars` 已支持显式 `adjustment_mode=raw/qfq/hfq`

但公司行为影响仍停留在“元数据承载 + 风险提示”层，尚未形成覆盖长期验证需求的完整调整引擎。

### 6.4 数据血缘与重建能力仍偏弱

长期方向必须能回答：

- 这条特征来自哪个 provider
- 是否发生过 fallback
- 用的是什么版本的数据产品
- 是否能在后续重建同一份样本

当前已有 runtime / fallback 可见性，但数据集级血缘与版本治理还需要进一步收口。

### 6.5 provider 健康度与能力矩阵还需继续明确

现在已经有 fallback 和优先级，但长期稳定演进仍需要：

- 明确每个 provider 覆盖哪些数据域
- 明确哪些数据域允许 stale fallback，哪些不允许
- 明确哪些数据域必须本地落盘

这会直接影响因子系统的数据可信度边界。

## 7. 当前阶段结论

当前主要问题已经不再是“有没有页面、有没有接口”，而是：

- 如何让数据底座更适合长期因子与预测主线
- 如何让预测与评估链条逐步替代单纯规则加权成为新的核心增量
- 如何在不破坏现有工作台可用性的前提下，把系统继续往消费级产品推进

因此，当前项目的正确推进方式是：

- 保留现有工作台与 workflow 壳层
- 继续补强数据底座、特征、标签、回测、预测、评估
- 同时持续收敛文档、术语与用户体验

## 8. 文档角色说明

为避免再次出现文档讲述不同阶段故事，当前建议按下面顺序理解项目：

1. [AGENTS.md](../AGENTS.md)  
   项目长期硬约束。

2. [当前阶段](current_phase.md)  
   当前版本优先做什么、不做什么。

3. [路线图](roadmap.md)  
   从当前阶段到长期方向的推进顺序。

4. [项目任务书 v2.1](taskbook-v2.1.md)  
   当前这轮产品化增强任务的完成基线。

5. 长期北极星文档  
   - [因子系统 PRD v1](a_share_factor_prd_v1.md)
   - [因子系统架构设计 v1](a_share_architecture_design_spec_v1.md)
   - [因子字典 v1](a_share_factor_dictionary_v1.md)
## 9. 初筛数据消费与数据补全边界

为保证 `/screener` 能承担全市场批量初筛职责，当前架构正式采用下面的边界：

### 9.1 初筛链路

初筛链路只消费：

- 本地已有的日线数据；
- 已沉淀的财务摘要快照；
- 已沉淀的公告索引快照；
- 当前可快速读取的市场上下文。

如果某类输入缺失，初筛优先做：

- `quality_status` 降级；
- 候选分桶降级；
- 失败占位保留；

而不是在批量执行当下临时补全所有缺口。

### 9.2 数据补全链路

数据补全分成两层：

1. 公共底座数据补全  
   面向全市场，按日沉淀到本地数据产品，供初筛、研究、预测和回测复用。

2. 个股重数据补全  
   面向深筛 workflow、单票工作台、研究/策略生成阶段的少量候选，允许按需补全更完整的数据。

### 9.3 当前专项修复方向

针对 `/screener` 长任务卡住、刷新超时、运行态丢失的问题，当前专项只处理：

- workflow 运行态正确性；
- 首屏读取链路减负；
- 结构化日志与诊断增强；
- 后续再在稳定前提下做受控提速。

## 10. 财务数据源分层与真相源架构位

围绕 `financial_summary`，当前架构已经正式收口为四层：

1. 官方披露原文索引层  
   使用 `CNINFO` 定期报告索引作为真相源接口位，只保存：
   - `symbol`
   - `report_period`
   - `report_type`
   - `title`
   - `publish_date`
   - `url`
   - `source`

2. 本地结构化财务快照层  
   统一清洗后的 `FinancialSummary` 落袋到本地 `financial_reports`，作为主链优先读取对象。

3. 结构化主源 / 回退层  
   当前优先级为：
   - `tushare`（启用时）
   - `baostock`
   - `akshare`

4. 下游消费层  
   `market_data_service.get_stock_financial_summary()` 对外只输出统一后的 `FinancialSummary`，不暴露 provider 原始字段。

本轮明确不做：
- PDF 全量解析；
- XBRL 批量入库；
- 财报正文 NLP；
- 基于财务源重构 research / strategy / screener 逻辑。

这一步的目的不是把财务链做成“大而全”的财报系统，而是先建立：
- 真相源接口位；
- 统一字段口径；
- 统一质量判断；
- 可解释 fallback；
- 本地结构化落袋。
## 11. 数据血缘与版本追踪架构位

围绕 `v2.2` 的包 4，当前系统已经正式引入一层独立的 lineage 能力，用来回答：

- 这条 `daily bars / financial summary / announcements / market context` 来自哪个 provider、哪一天、哪种 freshness/source mode。
- 这版 feature / label / prediction / evaluation 使用了哪些上游数据版本。
- 这次 `workspace-bundle` 的关键模块各自依赖了哪一版日级产物。

### 11.1 统一 schema

当前统一采用：

- `LineageSourceRef`
- `LineageDependency`
- `LineageMetadata`

并在 workspace 层补充：

- `WorkspaceLineageItem`
- `LineageSummary`

它们的职责分工是：

- `LineageSourceRef`：描述一个直接上游来源
- `LineageDependency`：描述当前产物与上游来源的角色关系
- `LineageMetadata`：描述单个数据产物自身的版本与直接依赖
- `LineageSummary`：描述面向 UI / bundle 的模块级血缘摘要

### 11.2 数据产品层

当前所有日级数据产品已经统一携带：

- `dataset_version`
- `provider_used`
- `warning_messages`
- `lineage_metadata`

其中日级数据产品的默认版本规则统一为：

- `{dataset}:{as_of_date}:{symbol-or-global}:v1`

这一步的意义在于：

- 日级快照不再只是“有 payload”
- 它同时成为后续 feature / label / prediction 的可追溯上游引用

### 11.3 预测与评估链

当前以下链条已经统一接入 lineage service：

- `dataset_service`
- `label_service`
- `prediction_service`
- `backtest_service`
- `evaluation_service`

当前这些对象除了保留原有版本字段外，还统一补齐：

- `dataset_version`
- `generated_at`
- `schema_version`
- `dependencies`
- `lineage_metadata`

原则锁定如下：

- 保留原有 `feature_version / label_version / model_version`
- `run_id` 继续只是运行标识，不替代 dataset version
- `lineage_metadata.dependencies` 只记录真正被本次运行使用的直接上游

### 11.4 本地 lineage repository

当前系统已经新增轻量本地登记簿：

- `dataset_lineage_records`

用途是：

- 记录 feature / label / prediction / backtest / evaluation 的 lineage metadata
- 记录关键日级产物的 lineage 摘要
- 提供只读查询，不参与主业务流程决策

这一步的目标不是建设一个大型外部元数据平台，而是先把当前仓库内部的“版本与依赖说明”收成稳定能力。

### 11.5 Workspace 与诊断接口

当前 `workspace-bundle` 已新增：

- `lineage_summary`

用于输出：

- `daily_bars_daily`
- `announcements_daily`
- `financial_summary_daily`
- `factor_snapshot_daily`
- `review_report_daily`
- `strategy_plan_daily`
- `debate_review_daily`
- `decision_brief_daily`
- `predictive_snapshot`

对应的只读 lineage 诊断接口包括：

- `GET /lineage/datasets`
- `GET /lineage/datasets/{dataset}/{dataset_version}`
- `GET /datasets/features/{dataset_version}/lineage`
- `GET /datasets/labels/{label_version}/lineage`
- `GET /predictions/{symbol}/lineage`
- `GET /stocks/{symbol}/workspace-lineage`

### 11.6 当前边界

当前 lineage 架构位仍然保持克制：

- 只记录直接上游依赖
- 不做递归依赖图展开
- 不做新的前端展示重构
- 不引入新的调度系统、消息队列或外部元数据仓库

这保证了当前包 4 是“底层可用、后续可扩”的工程能力，而不是过早建设过重的平台层。
