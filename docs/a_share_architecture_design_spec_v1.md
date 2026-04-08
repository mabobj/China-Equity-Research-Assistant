# 《A股公开信息驱动的因子发现与交易决策系统》系统架构设计说明书

**版本**：v1.0  
**文档类型**：系统架构设计说明书  
**适用范围**：A股公开信息驱动的因子发现、验证、组合、研究与交易决策系统  
**基线日期**：2026-04-08  
**配套文档**：产品需求文档（PRD）、后续开发任务书、数据库设计说明、接口设计说明

---

## 1. 文档目标

本文档用于把《A股公开信息驱动的因子发现与交易决策系统》从产品层描述，进一步细化为工程可落地的系统架构方案。  
文档重点回答以下问题：

1. 系统由哪些核心模块构成；
2. 模块之间的数据流和调用关系是什么；
3. 各层的职责边界如何划分；
4. 因子引擎、验证引擎、组合引擎、监控引擎如何协同工作；
5. 第一阶段应当如何实现，后续如何扩展。

本文档的目标不是写代码，而是作为后续仓库设计、Codex 任务拆解、测试规划与迭代评审的统一技术基线。

---

## 2. 设计原则

### 2.1 公开信息原则
系统仅使用依法公开披露的信息与市场可观测数据作为事实输入，不依赖内幕信息、未公开重大信息或“小道消息”。

### 2.2 分层架构原则
系统采用严格分层设计，避免“路由层写业务、模型层写逻辑、数据源直连策略层”的混乱结构。  
每一层只负责自己的职责，并通过清晰 schema 交互。

### 2.3 结构化优先原则
事件、研究结论、策略、因子、验证结果、交易记录、复盘结果必须优先结构化；文本说明只作为辅助解释层。

### 2.4 规则与模型分工原则
- **代码负责**：指标计算、事件结构化、打分、验证、风控、组合构建、成本建模；
- **AI 负责**：文本抽取、事件归类、研究解释、复盘归因、提示组织。

### 2.5 条件化建模原则
国际形势、市场 regime、行业强弱、板块阶段不是简单并列因子，而是下层因子的条件上下文。  
同一个个股因子在不同状态下，权重和解释都应不同。

### 2.6 成本优先原则
任何因子或策略在进入组合层前，必须考虑换手、滑点、T+1、涨跌停、流动性和容量约束。

### 2.7 可演进原则
架构设计既要支持第一阶段轻量落地，也要预留以下扩展能力：
- 深度研究与候选深筛；
- 交易日志与复盘；
- 因子衰减监控；
- paper trading；
- 半自动执行；
- Agent 接口化。

---

## 3. 系统定位

本系统的定位不是“聊天式荐股助手”，而是：

**一个面向A股的公开信息驱动、多层条件化、多因子、可验证、可迭代的研究与交易决策系统。**

它包含三条主链路：

1. **研究链路**：输入股票或候选池，输出结构化研究报告；
2. **策略链路**：基于研究结果输出结构化交易计划；
3. **因子链路**：持续生成、验证、组合并监控因子表现。

---

## 4. 总体架构

系统总体采用“八层架构 + 两条横向能力带”的设计：

```text
数据真相层
→ 标准化与事件抽取层
→ 顶层状态层
→ 行业/板块上下文层
→ 个股因子工厂
→ 因子验证层
→ 组合与风控层
→ 输出与监控层

横向能力带 A：AI 研究与解释能力
横向能力带 B：调度、日志、缓存、版本与观测能力
```

---

## 5. 分层设计

## 5.1 数据真相层

### 职责
负责从外部系统获取原始事实数据，构成全系统的唯一输入源。

### 输入来源
1. **正式披露源**
   - 巨潮资讯
   - 上交所 / 深交所
   - 上市公司正式公告与定期报告
2. **行情源**
   - AKShare
   - BaoStock
   - 指数、行业、板块行情
3. **辅助公开源**
   - 东方财富等门户公开数据
   - 股票社区公开页面（后期）
4. **外部状态源**
   - 汇率、商品、海外指数等公开市场数据（后期）

### 输出对象
- `RawDailyBars`
- `RawMinuteBars`
- `RawAnnouncement`
- `RawFinancialSummary`
- `RawUniverseItem`
- `RawMarketContext`

### 设计要求
- provider 必须独立封装；
- provider 不允许直接被研究层或策略层调用；
- provider 必须集中处理错误与空结果；
- 不允许原始第三方异常泄漏到 API 层。

---

## 5.2 标准化与事件抽取层

### 职责
把不同来源、不同字段口径、不同时间格式的数据统一为系统内部标准对象。  
同时把公告、财务摘要等文本数据抽取为结构化事件卡。

### 关键能力
1. 股票代码标准化
   - 输入兼容：`600519`、`sh600519`、`600519.SH`
   - 内部统一：`600519.SH`
2. 时间标准化
   - 交易日
   - 公告发布时间
   - 生效时间
3. 字段映射
   - OHLCV
   - 财务字段
   - 公告字段
4. 事件抽取
   - 业绩预告
   - 回购
   - 增持 / 减持
   - 问询 / 立案 / 风险提示
   - 重大合同 / 中标

### 核心对象：EventCard
建议统一结构如下：

- `event_id`
- `symbol`
- `event_type`
- `direction`
- `magnitude`
- `certainty`
- `publish_time`
- `effective_date`
- `source`
- `source_url`
- `extracted_numbers`
- `text_excerpt`
- `parse_confidence`

### 原理说明
系统后续所有事件因子，必须都从 `EventCard` 生成。  
也就是说，文本不会直接进入策略层，而是先转成标准化事件对象。

---

## 5.3 顶层状态层

### 职责
识别市场当前处于什么 regime，并把这个 regime 作为下游因子的条件变量。

### 覆盖范围
- 市场趋势状态
- 市场波动状态
- 风格状态（大盘/小盘、成长/价值）
- 外部风险冲击状态
- 风险偏好扩张 / 收缩状态

### 输出对象：MarketRegimeSnapshot
建议字段：

- `as_of_date`
- `market_trend_state`
- `market_volatility_state`
- `style_state`
- `external_risk_state`
- `risk_appetite_state`
- `regime_score`
- `regime_notes`

### 使用方式
该层不会直接生成买卖建议，而是：
- 启用 / 降权 / 禁用部分下层因子；
- 决定组合风险预算；
- 调整选股和交易策略阈值。

### 原理说明
A 股很多因子只在特定市场状态下有效，例如：
- 趋势类因子在强趋势市更有效；
- 回踩类因子在低波动上升阶段更有效；
- 情绪扩散因子在主线明朗时更有效。

因此，顶层状态层是整个系统的“条件开关”。

---

## 5.4 行业 / 板块上下文层

### 职责
为个股因子提供行业和板块层面的上下文，避免把行业 beta 误判成个股 alpha。

### 关键子模块
1. **行业相对强弱**
2. **题材热度**
3. **题材扩散率**
4. **板块拥挤度**
5. **龙头带动性**
6. **板块分歧状态**

### 输出对象：SectorContextSnapshot
建议字段：

- `sector_id`
- `sector_name`
- `relative_strength_score`
- `theme_heat_score`
- `diffusion_rate`
- `crowding_score`
- `leader_strength_score`
- `dispersion_score`
- `sector_state`

### 使用方式
- 给同板块个股信号做加权 / 降权；
- 为选股器提供优先级；
- 作为深筛环节的解释条件。

### 原理说明
A 股中很多机会并不是“个股独立发现”，而是：
- 板块先形成主线；
- 龙头先走强；
- 跟风扩散；
- 后期拥挤；
- 末端退潮。

如果不显式建模行业和板块层，就无法稳定理解“为什么这只票会在此时启动”。

---

## 5.5 个股因子工厂

### 职责
生成面向单只股票的直接信号，是整个系统的 alpha 生产核心。

### 因子簇
1. **事件因子**
2. **技术因子**
3. **财务边际因子**
4. **传播 / 社交因子**
5. **微观结构 / 量化痕迹因子**

### 输出对象：StockFactorSnapshot
建议字段：

- `symbol`
- `as_of_date`
- `event_score`
- `technical_score`
- `financial_score`
- `propagation_score`
- `microstructure_score`
- `risk_penalty_score`
- `composite_alpha_score`
- `factor_details`

### 原理说明
个股层不是简单做“总分加法”，而是：
- 上层 regime 给权重；
- 行业/板块层给上下文；
- 个股层生成直接 alpha；
- 风险惩罚层做最终约束。

---

## 5.6 因子验证层

### 职责
判断一个因子是否可以进入实盘候选范围。

### 核心验证项目
1. 样本内表现
2. 样本外表现
3. Walk-forward 稳定性
4. IC / RankIC
5. 分层收益
6. 成本后收益
7. 不同 regime 分层表现
8. 不同行业分层表现
9. 最大回撤
10. 换手 / 容量 / 拥挤度

### 输出对象：FactorValidationReport
建议字段：

- `factor_name`
- `validation_window`
- `in_sample_metrics`
- `out_of_sample_metrics`
- `rank_ic_mean`
- `turnover`
- `cost_adjusted_return`
- `capacity_score`
- `regime_stability_score`
- `decision`
- `notes`

### 决策状态
- `candidate`
- `approved`
- `watch`
- `degraded`
- `rejected`

### 原理说明
这层是整个系统的生命线。  
任何“看起来很聪明”的因子，如果没有通过验证层，就只能留在实验池，不能进入组合层。

---

## 5.7 组合与风控层

### 职责
把单票信号转成可执行的组合建议，并加入风险边界。

### 子模块划分
1. **候选池构建**
2. **多因子聚合**
3. **持仓与仓位建议**
4. **风控约束**
5. **执行约束**

### 约束项
- 单票最大权重
- 行业最大暴露
- 最大回撤阈值
- T+1 限制
- 涨跌停不可成交限制
- 流动性阈值
- 拥挤惩罚
- 事件黑名单（如重大负向监管事件）

### 输出对象
- `ResearchReport`
- `StrategyPlan`
- `ScreenerRunResponse`
- `DeepScreenerRunResponse`

### 原理说明
信号层只负责“机会”；  
组合与风控层负责“能不能做、该不该做、做多大”。

---

## 5.8 输出与监控层

### 职责
把系统结果输出给用户，并持续监控其表现。

### 输出内容
1. 单票研究报告
2. 单票交易计划
3. 全市场初筛结果
4. 深筛候选清单
5. 交易记录
6. 复盘报告
7. 因子衰减报告

### 监控内容
- 因子近期 IC
- 因子胜率
- 回撤变化
- 成本后收益变化
- 拥挤度变化
- regime 适配度变化

### 因子生命周期
- Candidate
- In Validation
- Approved
- Live
- Decay
- Retired

### 原理说明
系统的“自成长”不是自己乱改，而是通过生命周期管理和监控实现。

---

## 6. 横向能力带

## 6.1 AI 研究与解释能力带

### 作用
不负责底层计算，只负责：
- 抽取文本事件
- 生成研究解释
- 输出 thesis / reasons / risks
- 做复盘归因
- 做深筛阶段的精炼摘要

### 约束
- 不允许 AI 直接输出未经结构化约束的买卖决策；
- 不允许 AI 代替指标计算、回测和验证。

---

## 6.2 调度、日志、缓存、版本与观测能力带

### 作用
为整个系统提供基础运行保障。

### 包含能力
- 定时任务调度
- provider 调用日志
- 缓存管理
- 模型 / prompt / 数据版本记录
- 实验结果归档
- API 监控
- 错误告警

### 关键组件
- Scheduler
- Logger
- Cache
- Experiment Tracker
- Metrics Collector

---

## 7. 核心业务对象

## 7.1 ResearchReport
字段建议：

- `symbol`
- `name`
- `as_of_date`
- `technical_score`
- `fundamental_score`
- `event_score`
- `risk_score`
- `overall_score`
- `action`
- `confidence`
- `thesis`
- `key_reasons`
- `risks`
- `triggers`
- `invalidations`

## 7.2 StrategyPlan
字段建议：

- `symbol`
- `name`
- `as_of_date`
- `action`
- `strategy_type`
- `entry_window`
- `ideal_entry_range`
- `entry_triggers`
- `avoid_if`
- `initial_position_hint`
- `stop_loss_price`
- `stop_loss_rule`
- `take_profit_range`
- `take_profit_rule`
- `hold_rule`
- `sell_rule`
- `review_timeframe`
- `confidence`

## 7.3 ScreenerCandidate
字段建议：

- `symbol`
- `name`
- `list_type`
- `rank`
- `screener_score`
- `trend_state`
- `trend_score`
- `latest_close`
- `support_level`
- `resistance_level`
- `short_reason`

## 7.4 DeepScreenerCandidate
字段建议：

- `symbol`
- `name`
- `base_list_type`
- `base_rank`
- `base_screener_score`
- `research_action`
- `research_overall_score`
- `research_confidence`
- `strategy_action`
- `strategy_type`
- `ideal_entry_range`
- `stop_loss_price`
- `take_profit_range`
- `review_timeframe`
- `thesis`
- `short_reason`
- `priority_score`

## 7.5 TradeRecord
字段建议：

- `symbol`
- `name`
- `side`
- `trade_date`
- `price`
- `quantity`
- `reason`
- `research_snapshot`
- `strategy_snapshot`
- `result_note`

## 7.6 ReviewRecord
字段建议：

- `trade_id`
- `review_date`
- `execution_score`
- `timing_score`
- `risk_control_score`
- `holding_score`
- `mistake_tags`
- `improvement_suggestions`

---

## 8. 服务拆分

建议后端服务拆分如下：

### data_service
负责数据拉取、标准化、provider 封装与缓存。

### feature_service
负责技术指标、趋势、波动、支撑阻力、量价结构等计算。

### context_service
负责顶层状态识别、行业强弱、题材扩散、拥挤度。

### factor_service
负责事件因子、技术因子、财务边际因子、传播因子、微观结构因子生成。

### research_service
负责结构化研究结果与结构化策略生成。

### screener_service
负责全市场初筛与候选深筛。

### validation_service
负责因子回测、验证、样本外检验、成本和容量分析。

### trade_service
负责交易记录录入、持仓视图、交易快照绑定。

### review_service
负责复盘、归因、策略建议更新。

### monitoring_service
负责因子衰减、拥挤度、风控告警、运行状态监控。

---

## 9. 数据流设计

## 9.1 单票研究流

```text
输入 symbol
→ data_service 获取 profile / daily bars / announcements / financial summary
→ feature_service 生成 technical snapshot
→ factor_service 生成中间因子
→ research_service 聚合成 ResearchReport
→ research_service 生成 StrategyPlan
→ API 返回 / 前端展示 / 可落库
```

## 9.2 全市场初筛流

```text
载入 universe
→ 逐票获取日线和技术快照
→ 规则过滤
→ 规则评分
→ 输出 BUY_CANDIDATE / WATCHLIST / AVOID
→ 返回 screener run 结果
```

## 9.3 候选深筛流

```text
读取初筛结果
→ 选择 BUY_CANDIDATE + WATCHLIST 头部候选
→ 逐票调用 get_research_report
→ 逐票调用 get_strategy_plan
→ 聚合 priority_score
→ 输出 deep screener run 结果
```

## 9.4 交易记录与复盘流

```text
用户提交 TradeRecord
→ 保存 research snapshot / strategy snapshot
→ 到期触发 review job
→ review_service 读取 trade + market context + result
→ 生成 ReviewRecord
→ 写回改进建议
```

## 9.5 因子验证流

```text
定义候选因子
→ 构建样本
→ 计算因子值
→ 做样本内/样本外/Walk-forward
→ 计算 IC / 分层收益 / 成本后收益
→ 输出 FactorValidationReport
→ 决定 approved / watch / reject
```

---

## 10. 技术架构建议

## 10.1 后端
- Python 3.11+
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic

## 10.2 分析与研究
- pandas
- numpy
- DuckDB
- pyarrow
- vectorbt（参数实验和组合实验）
- 可选：Qlib（后续用于更大规模因子实验）

## 10.3 存储
- SQLite：系统记录层
- DuckDB：研究与筛选分析层
- Parquet：批量行情与中间特征
- Redis：缓存（后期）

## 10.4 前端
- Next.js
- React
- Tailwind CSS

## 10.5 AI 层
- OpenAI API
- 结构化输出
- Prompt 模板化
- 后期再接 LangGraph 或 agent 编排

---

## 11. 目录结构建议

```text
project/
  docs/
    prd.md
    architecture.md
    roadmap.md
    factor-catalog.md

  backend/
    app/
      api/
      core/
      db/
      schemas/
      services/
        data_service/
        feature_service/
        context_service/
        factor_service/
        research_service/
        screener_service/
        validation_service/
        trade_service/
        review_service/
        monitoring_service/
      tasks/
      tests/

  frontend/
    src/app/
    src/components/
    src/lib/

  scripts/
```

---

## 12. 第一阶段落地范围

第一阶段不做全部架构，只先落地以下主链路：

1. 市场数据
2. 技术分析
3. 公告与财务摘要
4. 单票研究报告
5. 单票交易策略
6. 全市场规则初筛
7. 候选深筛
8. 轻前端接入
9. 交易记录与复盘

### 第一阶段暂不做
- 自动实盘执行
- 高频分钟级复杂策略
- 完整社交舆情引擎
- 完整因子验证实验室
- 强化学习实盘闭环

---

## 13. 非功能要求

### 性能
- 单票研究接口应在可接受时间内返回；
- 初筛允许带 `max_symbols` 控制规模；
- 深筛只对头部候选执行。

### 可维护性
- provider 失效时局部降级；
- symbol / date / field mapping 必须集中管理；
- 所有关键输出 schema 固定。

### 可测试性
- 核心服务必须可 mock；
- 测试不依赖外网；
- 因子与策略逻辑必须可单测。

### 可扩展性
- 后续可扩展 paper trading、因子实验室、Agent 接口、执行模块。

---

## 14. 风险与应对

### 风险 1：免费数据源不稳定
应对：
- provider 封装
- fallback 设计
- 缓存和降级
- 关键事实源优先官方披露

### 风险 2：过拟合
应对：
- 强制样本外
- Walk-forward
- regime 分层
- 成本后收益
- 因子淘汰机制

### 风险 3：结构复杂度过高
应对：
- 分阶段落地
- 第一阶段先做轻量 MVP
- 深筛和验证层逐步加重

### 风险 4：AI 过度介入
应对：
- AI 只做抽取与解释
- 所有决策核心字段结构化
- 规则与验证层保留在代码中

---

## 15. 结论

本系统的核心不是“做一个会聊天的股票助手”，而是：

**搭建一套面向 A 股、公开信息驱动、条件化多因子、可验证、可迭代的研究与交易决策系统。**

它的工程本质是：

- 上层识别市场与行业环境；
- 中层构建上下文；
- 下层生成个股 alpha；
- 最后由验证、组合、风控和监控层决定哪些东西真正可做。

只要这份《系统架构设计说明书》作为基线固定下来，后续就可以非常自然地继续产出：

1. 数据库设计说明；
2. 因子字典；
3. 接口设计说明；
4. 第一阶段 Codex 开发任务书；
5. 测试计划；
6. paper trading 设计说明。

---

## 附录 A：建议优先落地的核心因子方向

第一批优先：

- 市场趋势状态
- 市场波动状态
- 行业相对强弱
- 题材扩散率
- 板块拥挤与分歧
- 业绩预告意外度
- 回购 / 增持事件
- 减持 / 问询 / 立案风险
- 突破保持率
- 缩量回踩质量
- 财务边际改善

第二批增强：

- 外部风险冲击
- 重大合同 / 中标强度
- 日内资金路径一致性
- 板块同步交易强度
- 注意力扩散冲击
