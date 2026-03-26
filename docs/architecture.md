# 系统架构说明

## 文档目标

本文档说明当前版本的核心分层，以及本轮新增的 LLM provider 适配层、角色提示词配置层和受控裁决运行时。

## 系统定位

本系统服务于中国大陆 A 股市场的单用户研究场景，目标是稳定输出：

- 结构化研究报告
- 结构化交易策略
- 结构化选股结果
- 可追踪、可回退的 LLM 裁决结果

当前不包含自动实盘交易与开放式 agent 平台。

## 总体分层

```text
API 层
  -> Service 层
    -> Provider 层
      -> 本地存储 / 外部数据源
```

同时保留独立的：

- `Schema` 层：统一输入输出结构
- `DB` 层：SQLite / DuckDB / Parquet
- `LLM Debate` 层：固定角色、固定轮次、固定 schema 的受控运行时

## 核心目录

```text
backend/app/api/
backend/app/core/
backend/app/db/
backend/app/schemas/
backend/app/services/
```

## 数据层

### Provider 层

所有外部数据源必须位于：

```text
backend/app/services/data_service/providers/
```

当前 provider 负责：

- 抓取或读取原始数据
- 做最小必要的字段标准化
- 允许失败、空结果和 graceful fallback

业务层不直接访问第三方网页或接口。

### MarketDataService

`MarketDataService` 是统一的数据访问门面，负责：

- symbol 标准化
- 根据 capability 选择 provider
- 本地缓存与本地落盘
- 对上层暴露稳定接口

## 研究与策略层

### review_service

`review_service` 负责多维结构化研究输出，核心包括：

- `factor_profile`
- `technical_view`
- `fundamental_view`
- `event_view`
- `sentiment_view`
- `bull_case`
- `bear_case`
- `final_judgement`

### debate_service

`debate_service` 是规则版角色化裁决层。它不依赖 LLM，而是把角色边界和节点顺序固定下来，作为受控运行时的稳定基线。

固定角色包括：

- `technical_analyst`
- `fundamental_analyst`
- `event_analyst`
- `sentiment_analyst`
- `bull_researcher`
- `bear_researcher`
- `chief_analyst`
- `risk_reviewer`

## LLM Debate 架构

### 设计目标

LLM debate 不是开放式多 agent 系统，而是：

- 固定角色
- 固定轮次
- 固定输出 schema
- 可回退到规则版

这样可以保证研究结果可解释、可验证、可维护。

### 模块拆分

当前目录：

```text
backend/app/services/llm_debate_service/
  base.py
  llm_role_runner.py
  llm_debate_orchestrator.py
  fallback.py
  providers/
  prompts/
```

职责划分如下。

### 1. `llm_role_runner.py`

职责：

- 执行单个角色
- 统一发起 `chat.completions`
- 解析 JSON
- 做 schema 校验
- 对常见输出漂移做轻量纠偏

纠偏范围只限结构层，不替代业务规则，例如：

- `list[str] -> list[{title, detail}]`
- 缺失 `action_bias` 时推断默认值
- 缺失 `chief_judgement.summary` 时自动补齐

### 2. `providers/`

这是本轮新增的 provider 适配层，用来隔离不同 OpenAI 兼容网关的能力差异。

当前包含：

- `openai_compatible_provider.py`
- `volcengine_ark_provider.py`
- `registry.py`

适配层负责：

- 创建底层客户端
- 决定支持哪些 `response_format` 策略

例如：

- 标准 OpenAI 兼容网关：
  - `json_schema`
  - `json_object`
  - `prompt_only_json`
- 火山方舟 coding/plan：
  - 直接走 `prompt_only_json`

这样后续接入新的 LLM 时，只需要新增 provider 模块，不需要改 `llm_role_runner` 的核心逻辑。

### 3. `prompts/`

角色提示词已统一改为独立配置文件：

```text
TECHNICAL_ANALYST_AGENT.md
FUNDAMENTAL_ANALYST_AGENT.md
EVENT_ANALYST_AGENT.md
SENTIMENT_ANALYST_AGENT.md
BULL_RESEARCHER_AGENT.md
BEAR_RESEARCHER_AGENT.md
CHIEF_ANALYST_AGENT.md
RISK_REVIEWER_AGENT.md
```

这些文件承担两层职责：

- 角色说明文件
- 提示词配置入口

因此后续修改角色边界时，应先改这里，而不是把提示词散落在 Python 代码中。

### 4. `fallback.py`

`fallback.py` 统一管理运行时选择：

- `rule_based`
- `llm`

回退条件包括：

- LLM 未启用
- API key 缺失
- 网关调用失败
- 输出未通过 schema 校验
- 请求超时

回退后仍然返回同一份结构化 `DebateReviewReport`，只是在 `runtime_mode` 中标记为 `rule_based`。

## 火山方舟适配策略

### 当前问题

火山方舟 coding/plan 套餐不支持：

- `response_format.type=json_schema`
- `response_format.type=json_object`

如果继续按通用模式依次尝试，会在每个角色上先打两次无意义的 `400`。

### 当前实现

通过 `providers/volcengine_ark_provider.py` 把这部分差异单独封装：

- 自动识别方舟 `base_url`
- 直接走 `prompt_only_json`
- 对方舟把实际超时下限提升到 `60s`
- 关闭 SDK 自动重试，避免同一角色被重复超时
- 由运行器继续做 JSON 解析和 schema 校验

### 后续扩展

若要新增其他 LLM 网关，推荐步骤：

1. 在 `providers/` 下新增一个适配模块
2. 实现 `create_client()` 与 `build_attempts()`
3. 在 `registry.py` 中注册识别逻辑
4. 不修改业务层和编排层 schema

## 接口与 Schema

核心输出统一放在：

```text
backend/app/schemas/
```

重点包括：

- `review.py`
- `debate.py`

约束原则：

- 关键研究结果必须结构化
- 关键策略结果必须结构化
- LLM 输出必须经过 Pydantic 校验

## 测试策略

本项目优先保证以下模块可单测：

- 指标计算
- 趋势评分
- 支撑压力识别
- 选股规则
- 策略输出校验
- API 健康检查
- LLM 角色执行器与 provider 适配层

其中 LLM 相关测试采用 stub client，不依赖外网。

## 当前边界

当前架构仍然坚持以下原则：

- 不把确定性计算交给 LLM
- 不在路由层写复杂逻辑
- 不把未来实盘能力混入当前研究核心
- 不为了“像 agent”而牺牲可维护性

成功标准不是“更像聊天机器人”，而是：

- 数据接入稳定
- 研究结果可信
- 策略边界清晰
- 回退路径明确
- 后续扩展新 provider 成本低

## Workflow Runtime v1

### 设计目标

当前版本新增 `workflow_runtime` 层，用来把已经存在的能力组织成显式 workflow，同时保持：

- 轻量
- 同步
- 可测试
- 可解释
- 可从中间节点启动

它不是调度平台，也不是通用 DAG 引擎，更不是后台任务系统。

目录结构：

```text
backend/app/services/workflow_runtime/
  base.py
  context.py
  registry.py
  executor.py
  artifacts.py
  workflow_service.py
  definitions/
    single_stock_workflow.py
    deep_review_workflow.py
```

### 运行时分层

`workflow_runtime` 内部职责划分如下：

- `base.py`
  - 定义 `WorkflowNode`
  - 定义 `WorkflowDefinition`
  - 定义 `WorkflowStepResult`
  - 定义 `WorkflowRunResult`
  - 定义 `WorkflowArtifact`
- `context.py`
  - 保存本次运行的 request、选项和节点输出
- `registry.py`
  - 注册 workflow definition
- `executor.py`
  - 按顺序同步执行节点
  - 处理 `start_from / stop_after`
  - 在节点失败时生成清晰状态与错误摘要
- `artifacts.py`
  - 以轻量 JSON 文件持久化运行记录
- `workflow_service.py`
  - 作为 API 层的薄门面

### 单票 Workflow

名称：`single_stock_full_review`

节点顺序：

1. `SingleStockResearchInputs`
2. `FactorSnapshotBuild`
3. `ReviewReportBuild`
4. `DebateReviewBuild`
5. `StrategyPlanBuild`

节点与既有服务关系：

- `SingleStockResearchInputs`
  - 复用 `DebateOrchestrator.build_inputs`
- `FactorSnapshotBuild`
  - 复用 `FactorSnapshotService`
- `ReviewReportBuild`
  - 复用 `StockReviewService`
- `DebateReviewBuild`
  - 复用 `DebateRuntimeService`
  - 支持 `use_llm=true/false`
- `StrategyPlanBuild`
  - 复用 `StrategyPlanner`

统一输出会聚合：

- `research_inputs`
- `factor_snapshot`
- `review_report`
- `debate_review`
- `strategy_plan`

### 深筛 Workflow

名称：`deep_candidate_review`

节点顺序：

1. `ScreenerRun`
2. `DeepCandidateSelect`
3. `CandidateReviewBuild`
4. `CandidateDebateBuild`
5. `CandidateStrategyBuild`

节点与既有服务关系：

- `ScreenerRun`
  - 复用 `ScreenerPipeline`
- `DeepCandidateSelect`
  - 基于初筛结果选出深筛候选
- `CandidateReviewBuild`
  - 对候选逐个复用 `StockReviewService`
- `CandidateDebateBuild`
  - 对候选逐个复用 `DebateRuntimeService`
- `CandidateStrategyBuild`
  - 对候选逐个复用 `StrategyPlanner`

当前版本允许个别 symbol 失败：

- 单个标的失败不会中断整个 workflow
- 会在批量节点输出和最终输出中记录失败摘要

### `start_from` 与 `stop_after`

`executor.py` 当前支持两个边界参数：

- `start_from`
  - 从指定节点开始执行
  - 之前节点在 step summary 中标记为 `skipped`
- `stop_after`
  - 执行到指定节点后停止
  - 之后节点在 step summary 中标记为 `skipped`

语义约束：

- 只改变本次执行边界，不改变 workflow 定义顺序
- 如果从中间节点启动，节点内部可以通过已有 service 自动补齐前置输入
- 自动补齐输入不等同于把前置节点记为已执行完成

### 运行记录与产物

当前版本使用最简单稳定的文件持久化：

```text
data/workflow_runs/{run_id}.json
```

记录内容包括：

- `workflow_name`
- `started_at`
- `finished_at`
- `input_summary`
- `step summaries`
- `final_output_summary`
- `status`
- `error_message`

### API 关系

新增接口：

- `POST /workflows/single-stock/run`
- `POST /workflows/deep-review/run`
- `GET /workflows/runs/{run_id}`

与现有接口的关系：

- `review-report / debate-review / strategy / screener` 继续保留
- workflow API 只是把这些既有能力按节点顺序显式编排起来
- 路由层只负责请求接收与响应返回，不承载 workflow 编排逻辑

### 当前边界

本轮明确不做：

- 后台调度器
- 队列
- 自动复盘
- DAG 可视化
- 前端 workflow 控制台
- 任意复杂通用 workflow 引擎
