# 项目硬性约束

本文件记录项目层面的长期硬约束。它服务于开发、重构、文档编写、测试与代理执行，不承担当前阶段进度与任务跟踪职责。

## 1. 项目定位

本项目是一个面向 **中国大陆 A 股市场** 的 **公开信息驱动的研究、选股、策略与因子系统**。

项目当前核心目标不是“聊天式荐股”，也不是“自动实盘机器人”，而是构建一个：

- 可持续接入与标准化 A 股公开数据；
- 可输出结构化研究报告与结构化交易计划；
- 可进行全市场初筛与候选深筛；
- 可积累交易记录并进行复盘学习；
- 可逐步演进为因子发现、验证、组合与监控系统。

## 2. 当前阶段硬边界

当前阶段明确要做：

- 全市场初筛与候选深筛；
- 单票研究报告；
- 单票交易策略计划；
- 公告、财务、技术输入统一结构化；
- 交易记录与复盘闭环；
- 因子字典与后续验证框架的工程落地准备。

当前阶段明确不做：

- 自动实盘下单；
- 无人确认的交易执行；
- 高频 / Tick 级自动化策略；
- 直接依赖内幕、未公开重大信息、小道消息的能力；
- 用自由文本 LLM 替代确定性计算与风控。

## 3. 第一原则

### 3.1 公开信息原则

系统只使用依法公开披露的信息和公开可观测市场数据作为事实源。

### 3.2 结构化优先于自由文本

所有关键输出必须优先结构化，文本只作为补充说明。

包括但不限于：

- 研究报告；
- 技术快照；
- 财务摘要；
- 公告列表；
- 交易策略；
- 选股结果；
- 交易记录；
- 复盘记录；
- 因子定义与验证结果。

### 3.3 代码与模型分工明确

必须由代码负责：

- 数据清洗与标准化；
- 股票代码转换与 provider 映射；
- 技术指标计算；
- 趋势、波动、支撑压力等结构判断；
- 规则筛选与打分；
- 风险边界与价格区间计算；
- 交易记录存储；
- 回测、验证、组合、复盘统计。

可以由 AI 负责：

- 财报、公告、新闻摘要；
- 事件分类与解释；
- 研究结论解释；
- 多信息源文本归纳；
- 复盘归因说明。

禁止把确定性计算交给 LLM。

### 3.4 简单、稳定、可解释优先

第一版优先选择：

- 朴素方案；
- 清晰边界；
- 易测试逻辑；
- 可维护代码。

不要为了“更智能”过早引入复杂黑盒。

## 4. 当前系统主线

当前系统主线分为四条：

1. 数据主线：`profile / daily bars / technical / announcements / financial summary`
2. 研究主线：`/research/{symbol}`
3. 策略主线：`/strategy/{symbol}`
4. 选股主线：`/screener/run` 以及后续 deep screener

后续增强主线：

5. 交易记录与复盘主线
6. 因子发现、验证、组合与衰减监控主线

## 5. 架构原则

### 5.1 严格分层

业务必须分层组织：

- API 层；
- Schema 层；
- Service 层；
- Provider 层；
- DB 层；
- Task / Scheduler 层。

禁止把复杂业务逻辑直接写在路由层。

### 5.2 数据源必须通过 provider

所有外部数据源都必须放在：

`backend/app/services/data_service/providers/`

禁止在业务层、研究层、策略层直接请求网页或第三方 API。

### 5.3 标准化必须集中管理

以下逻辑必须集中管理，不允许分散硬编码：

- symbol normalize；
- provider symbol convert；
- 日期格式转换；
- 数据字段映射；
- 统一错误处理。

### 5.4 研究、策略、选股必须分层

- `research_service` 负责研究结论；
- `strategy_planner` 负责交易计划；
- `screener_service` 负责全市场扫描与候选聚合。

禁止把选股、研究、策略逻辑混写在同一文件中。

### 5.5 因子系统与产品接口分离

未来因子开发、验证、组合与监控需要独立成层。

当前实现中，研究和策略可以复用因子结果，但不能把页面输出逻辑直接当成因子引擎。

## 6. 目录职责约束

### 6.1 API 层

目录：`backend/app/api/routes/`

职责：

- 接收请求；
- 参数校验；
- 调用 service；
- 返回 schema。

禁止：

- 直接访问 provider；
- 写复杂研究逻辑；
- 写复杂评分逻辑；
- 写抓取逻辑。

### 6.2 Schema 层

目录：`backend/app/schemas/`

职责：

- 定义 API 输入输出；
- 定义结构化研究对象；
- 定义结构化策略对象；
- 定义结构化选股对象；
- 定义研究输入对象。

要求：

- 所有 API 都返回 typed Pydantic schema；
- 不允许 API 直接返回 dataframe 或第三方原始 dict。

### 6.3 Data Service 层

目录：`backend/app/services/data_service/`

职责：

- 封装 provider；
- 标准化 symbol 和字段；
- 向上提供统一数据接口。

要求：

- provider 异常不能直接泄漏到 API；
- 必须允许空结果和 graceful failure；
- 必须可 mock 测试。

### 6.4 Feature Service 层

目录：`backend/app/services/feature_service/`

职责：

- 技术指标计算；
- 趋势/波动状态识别；
- 支撑/压力位计算；
- 结构化技术快照输出。

要求：

- 优先使用 pandas / numpy 的朴素实现；
- 保持可解释、可测试。

### 6.5 Research Service 层

目录：`backend/app/services/research_service/`

职责：

- technical researcher；
- fundamental researcher；
- event researcher；
- research_manager；
- strategy_planner。

要求：

- 先规则化、结构化、模板化；
- 不把自由文本生成当核心能力；
- 研究结论必须可以被测试和复现。

### 6.6 Screener Service 层

目录：`backend/app/services/screener_service/`

职责：

- universe 获取；
- filters；
- scoring；
- pipeline；
- 后续 deep_pipeline。

要求：

- 初筛必须轻量、可扩展；
- 深筛必须复用 research / strategy 能力；
- 单个 symbol 失败不能中断整个扫描。

### 6.7 Review / Trade Service 层

目录：

- `backend/app/services/trade_service/`
- `backend/app/services/review_service/`

职责：

- 保存交易记录；
- 绑定研究 / 策略快照；
- 生成复盘结果；
- 为后续学习和因子验证提供真实反馈。

## 7. 输出规范

### 7.1 研究报告必须结构化

至少应包含：

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

### 7.2 交易策略必须结构化

至少应包含：

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

### 7.3 选股结果必须机器可读

至少应包含：

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

### 7.4 深筛结果必须可直接行动

后续 deep screener 至少应包含：

- `base_screener_score`
- `research_overall_score`
- `research_action`
- `strategy_action`
- `strategy_type`
- `ideal_entry_range`
- `stop_loss_price`
- `take_profit_range`
- `priority_score`

## 8. 测试要求

优先保证以下模块有单元测试或 API 测试：

1. symbol normalize / convert
2. 指标计算
3. 趋势评分
4. 支撑 / 压力位识别
5. 研究聚合逻辑
6. 策略输出逻辑
7. 选股 filters / scoring / pipeline
8. API 健康检查与关键接口

对于抓取型 provider：

- 可先以 smoke test 为主；
- 测试不要强依赖实时外网；
- 允许 mock provider；
- 不要写过于脆弱的硬编码断言。

## 9. 禁止事项

### 禁止 1

禁止把交易决策完全交给自由文本 LLM。

### 禁止 2

禁止在多个文件中散落重复字段映射、symbol 转换或日期标准化逻辑。

### 禁止 3

禁止在 route 文件中实现复杂研究、选股、策略或抓取逻辑。

### 禁止 4

禁止为了“先跑起来”而省略核心 schema。

### 禁止 5

禁止把未来自动实盘执行能力混入当前研究系统核心。

### 禁止 6

禁止在全市场扫描阶段引入过重的研究逻辑或高成本外部调用。

### 禁止 7

禁止在没有样本外、成本后与风险约束的前提下，直接把“好看分数”包装成可交易因子。

## 10. 成功标准

成功不是“看起来很聪明”，而是：

- 能稳定接入 A 股关键公开数据；
- 能输出可信、结构化的研究报告；
- 能输出清晰、结构化的交易计划；
- 能从全市场里初筛并逐步深筛候选；
- 能积累交易记录并做有价值复盘；
- 能逐步演进到因子发现、验证、组合与监控系统；
- 能在后续平滑扩展到 paper trading 和更高级执行体系。
