# AGENTS.md

本文件定义本项目对 Codex 和其他代码代理的长期约束。

## 项目定位

这是一个面向**中国大陆 A 股市场**的投资研究与交易决策辅助系统。

当前阶段目标：
- 全市场选股
- 单票研究
- 交易策略输出
- 交易记录
- 复盘学习

当前阶段不包含：
- 自动实盘交易
- 券商下单集成
- 高频交易
- 实时盘中自动执行

## 第一原则

### 1. 研究优先于炫技
优先保证：
- 数据可靠
- 逻辑清晰
- 输出可解释
- 系统可维护

不要为了追求“智能感”而牺牲工程稳定性。

### 2. 结构化优先于自由文本
所有关键输出都必须尽量结构化。

包括但不限于：
- 研究报告
- 选股结果
- 交易策略
- 复盘记录

自由文本只能作为补充说明，不能作为唯一机器可读结果。

### 3. 规则与模型分工明确
必须遵守以下分工：

#### 由代码负责
- 技术指标计算
- 数据清洗与标准化
- 规则筛选
- 风险边界
- 价格区间与条件判定
- 交易记录存储
- 复盘统计

#### 由 AI 负责
- 财报/公告/新闻摘要
- 研究结论解释
- 多信息源综合判断
- 复盘归因说明
- 研究文本生成

不要把确定性计算交给 LLM。

## 架构原则

### 1. 分层架构
业务必须分层组织：
- API 层
- Service 层
- Provider 层
- DB 层
- Schema 层

禁止把复杂业务逻辑直接写在路由层。

### 2. 数据源必须通过 provider
所有外部数据源都必须放在：

`backend/app/services/data_service/providers/`

禁止在业务层直接请求网页或 API。

### 3. 必须允许 provider 失效
免费数据源和网页抓取会失效，因此：
- 必须写异常处理
- 必须允许空结果
- 必须支持 fallback 或 graceful failure
- 必须把字段标准化集中管理

### 4. 研究模块必须可单独测试
以下模块应可独立调用与测试：
- technical_researcher
- fundamental_researcher
- event_researcher
- strategy_planner
- research_manager
- screener pipeline
- reviewer

## 编码约束

### Python 约束
- 使用 Python 3.11+
- 所有公开函数必须有类型标注
- 使用 Pydantic 定义 API 输入输出
- 业务逻辑优先写成纯函数或清晰 service
- 复杂逻辑必须拆函数，不允许单函数过长

### FastAPI 约束
- 路由只做请求接收和响应返回
- 参数校验依赖 schema
- 不在路由里直接访问第三方数据源
- 不在路由里写复杂策略判断

### 数据库约束
- 应用记录优先使用 SQLite
- 历史行情与中间特征优先使用 DuckDB/Parquet
- 所有表模型集中放在 `db/models`
- 迁移统一走 Alembic

### 前端约束
- 前端保持轻量
- 优先构建简单、稳定、可读的页面
- 不引入不必要的复杂状态管理
- 页面优先服务于研究结果展示和记录录入

## 项目目标用户

当前阶段只服务单用户。

因此：
- 不必提前构建复杂权限系统
- 不必过度工程化多租户
- 不必为未来未知需求过度抽象

但仍需保证：
- 目录清晰
- 模块可扩展
- 数据结构可迭代

## 输出规范

### 研究报告必须包含核心字段
至少应包含：
- symbol
- as_of_date
- technical_score
- fundamental_score
- event_score
- risk_score
- overall_score
- action
- confidence
- thesis
- key_reasons
- triggers
- invalidations

### 交易策略必须结构化
至少应包含：
- action
- entry_type
- ideal_entry_range
- add_position_rules
- stop_loss_rule
- take_profit_rule
- hold_rule
- sell_rule
- review_timeframe

### 选股结果必须机器可读
至少应包含：
- symbol
- name
- screener_score
- rank
- list_type
- short_reason

## 测试要求

优先补单元测试的模块：
1. 指标计算
2. 趋势评分
3. 支撑/压力位识别
4. 选股规则
5. 策略输出校验
6. API 健康检查

对于抓取型 provider：
- 可先以 smoke test 为主
- 必须允许接口变更导致的失败
- 不要写过于脆弱的硬编码断言

## 禁止事项

### 禁止 1
禁止把交易决策完全交给自由文本 LLM。

### 禁止 2
禁止在多个文件中散落重复字段映射逻辑。

### 禁止 3
禁止在 route 文件中实现复杂研究逻辑。

### 禁止 4
禁止为了“先跑起来”而省略核心 schema。

### 禁止 5
禁止将未来实盘执行能力混入当前研究系统核心。

## 开发优先级

当前优先级按顺序为：
1. 项目骨架
2. 数据接入
3. 技术分析底层
4. 单票研究
5. 选股器
6. 交易记录
7. 复盘学习
8. 轻量前端优化

## Codex 工作方式建议

当 Codex 在本项目中工作时，应遵守：
1. 先阅读 `README.md`、`docs/architecture.md`、`docs/roadmap.md`
2. 每次只完成一个清晰的子任务
3. 修改前先确认目录与职责边界
4. 优先补齐 schema 和测试，再扩展功能
5. 生成代码时优先选择清晰、稳定、朴素方案

## 本项目的成功标准

成功不是“看起来很智能”，而是：
- 能稳定接入 A 股数据
- 能输出可信的研究结果
- 能给出明确的交易策略
- 能积累交易记录
- 能做有价值的复盘
- 能在后续逐步演进成真正可靠的研究助手
