# 系统架构说明

## 文档目标

本文档说明当前版本的核心分层、前端工作台组织方式、workflow runtime 的职责边界，以及 review / debate / strategy / screener 之间的关系。

本文档只描述当前已经落地的架构，不描述未来设想中的调度平台或复杂 agent 系统。

## 系统定位

本项目服务于中国大陆 A 股市场的单用户研究场景，目标是稳定输出：

- 结构化研究结果
- 结构化策略计划
- 结构化选股结果
- 可追踪、可回看、可回退的 debate 与 workflow 结果

当前不包含：

- 自动实盘交易
- 券商下单
- 复杂权限系统
- 通用 DAG 编排平台

## 总体分层

```text
前端工作台
    ↓
API 层（FastAPI routes / Next.js 代理）
    ↓
Service 层（研究、选股、workflow、LLM debate 等）
    ↓
Provider 层（外部数据接入）
    ↓
DB / 文件存储（SQLite、DuckDB、Parquet、JSON artifacts）
```

同时独立保留：

- `Schema` 层：统一输入输出结构
- `workflow_runtime` 层：只负责编排，不承载核心研究算法

## 核心目录

```text
backend/app/api/
backend/app/core/
backend/app/db/
backend/app/schemas/
backend/app/services/
frontend/src/app/
frontend/src/components/
frontend/src/lib/
```

## API 层

API 层职责：

- 接收请求
- 进行参数校验
- 调用 service
- 返回结构化响应

当前已经保持较薄的路由层，复杂逻辑主要不在 route 文件内。

主要路由分组：

- `stocks.py`
- `screener.py`
- `strategy.py`
- `research.py`
- `data.py`
- `workflows.py`

## Service 层

### 1. 数据与行情

关键模块：

- `market_data_service`
- `trigger_snapshot_service`

职责：

- 标准化 symbol
- 按 capability 选择 provider
- 本地缓存与落盘
- 对上层暴露稳定接口

### 2. 因子与研究

关键模块：

- `factor_service`
- `review_service`
- `research_manager`
- `strategy_planner`

职责：

- 计算因子与分数
- 生成 review-report v2
- 生成旧版 research report
- 生成结构化 strategy plan

注意：

- `research_manager` 与 `review_service` 当前并存
- 前者偏旧入口，后者偏 v2 结构化研究主链路

### 3. 裁决与 LLM

关键模块：

- `debate_service`
- `llm_debate_service`

职责：

- 固定角色、固定轮次、固定 schema 的裁决流程
- 支持规则版与受控 LLM 版
- 在 LLM 失败时回退到 rule-based

Provider 适配层位于：

```text
backend/app/services/llm_debate_service/providers/
```

当前内置：

- `openai_compatible_provider.py`
- `volcengine_ark_provider.py`
- `registry.py`

### 4. 选股

关键模块：

- `screener pipeline`
- `deep screener`

职责：

- 运行规则初筛
- 输出 v2 分桶
- 聚合深筛结果

当前主展示分桶：

- `READY_TO_BUY`
- `WATCH_PULLBACK`
- `WATCH_BREAKOUT`
- `RESEARCH_ONLY`
- `AVOID`

旧字段 `list_type` 仍保留为兼容字段。

### 5. Workflow Runtime

目录：

```text
backend/app/services/workflow_runtime/
```

核心文件：

- `base.py`
- `context.py`
- `registry.py`
- `executor.py`
- `artifacts.py`
- `workflow_service.py`
- `definitions/single_stock_workflow.py`
- `definitions/deep_review_workflow.py`

职责边界：

- 定义节点与 workflow
- 顺序执行节点
- 处理 `start_from` / `stop_after`
- 汇总输入摘要、步骤摘要、最终输出摘要
- 持久化 run record

明确不负责：

- 调度器
- 队列
- 后台任务平台
- 通用 DAG 可视化

## Provider 层

所有外部数据源统一通过：

```text
backend/app/services/data_service/providers/
```

当前 provider 设计原则：

- capability-based registry
- 允许 provider 失败
- 允许空结果
- 统一字段标准化
- 尽量提供 fallback 或 graceful failure

当前涉及的数据源包括：

- AKShare
- Baostock
- CNINFO
- Eastmoney
- mootdx（本地验证版）

## Schema 层

结构化输出集中放在：

```text
backend/app/schemas/
```

重点 schema：

- `factor.py`
- `review.py`
- `debate.py`
- `strategy.py`
- `screener.py`
- `workflow.py`

原则：

- 关键输出必须结构化
- LLM 输出必须经 schema 校验
- route 与前端尽量直接使用 schema 定义的契约

## 存储层

当前存储策略：

- 应用记录：SQLite
- 行情与中间特征：DuckDB / Parquet
- workflow artifacts：JSON 文件

workflow 运行记录当前存放在：

```text
data/workflow_runs/{run_id}.json
```

这是一种刻意保持轻量的方案，优先满足稳定落地和可追踪性。

## 前端工作台

当前前端不追求页面数量扩张，而是强化已有页面的可用性。

### 1. 首页 `/`

职责：

- 展示系统能力
- 提供股票代码输入入口
- 提供进入单票分析、选股和 workflow 执行的入口

### 2. 单票页 `/stocks/[symbol]`

职责：

- 串联基础信息
- 串联 factor snapshot
- 串联 review-report v2
- 串联 debate-review
- 串联 strategy plan
- 串联 trigger snapshot
- 提供 `single_stock_full_review` workflow 入口

### 3. 选股页 `/screener`

职责：

- 串联数据补全
- 串联规则初筛
- 串联深筛结果
- 提供 `deep_candidate_review` workflow 入口

### 4. 占位页 `/trades` 与 `/reviews`

职责：

- 诚实表达当前未上线的业务能力
- 不伪造交易与复盘功能

## Workflow Runtime v1

当前已支持两个 workflow。

### 1. `single_stock_full_review`

节点顺序：

1. `SingleStockResearchInputs`
2. `FactorSnapshotBuild`
3. `ReviewReportBuild`
4. `DebateReviewBuild`
5. `StrategyPlanBuild`

与现有 service 的关系：

- `SingleStockResearchInputs`：复用既有研究输入构建逻辑
- `FactorSnapshotBuild`：复用 factor_service
- `ReviewReportBuild`：复用 review_service
- `DebateReviewBuild`：复用 debate runtime
- `StrategyPlanBuild`：复用 strategy planner

### 2. `deep_candidate_review`

节点顺序：

1. `ScreenerRun`
2. `DeepCandidateSelect`
3. `CandidateReviewBuild`
4. `CandidateDebateBuild`
5. `CandidateStrategyBuild`

与现有 service 的关系：

- `ScreenerRun`：复用 screener pipeline
- `DeepCandidateSelect`：对初筛结果做进一步收敛
- `CandidateReviewBuild`：复用 review_service
- `CandidateDebateBuild`：复用 debate runtime
- `CandidateStrategyBuild`：复用 strategy planner

### `start_from` 与 `stop_after`

语义：

- `start_from`
  - 指定从哪个节点开始正式执行
  - 之前节点会标记为 `skipped`
- `stop_after`
  - 指定执行到哪个节点后停止
  - 之后节点会标记为 `skipped`

注意：

- 它们不会改变 workflow 的定义顺序
- 当前版本仍是同步执行，不是调度平台

## review / debate / strategy / workflow 的关系

可以把它们理解成四层：

1. `review`
   - 输出多维研究判断
2. `debate`
   - 把多角色观点与裁决结构化
3. `strategy`
   - 把研究结论收敛为可执行的计划
4. `workflow`
   - 把已有能力按显式节点顺序串起来

因此：

- workflow 不是新的研究算法
- workflow 是对已有 service 的薄编排
- 现有单接口依然保留，适合按需直接调用

## fallback 设计

当前系统已经存在两类 fallback：

### provider fallback

- 外部数据源可能失效
- provider registry 允许 capability 不可用
- service 层允许空结果或降级结果

### debate fallback

- LLM 可能超时、失败或输出不合格
- `llm_debate_service` 会自动回退到规则版
- 输出仍保持统一 schema

## 当前非目标

本阶段明确不做：

- 大规模后端重构
- 通用 workflow 引擎
- 队列与调度系统
- DAG 可视化编辑器
- 自动复盘与持仓管理
- 新的核心业务能力扩张
## Workspace Bundle 主入口

当前单票页的主后端入口已经调整为：

```text
GET /stocks/{symbol}/workspace-bundle
```

它一次性组装：

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

设计原则：

- 页面优先只调用一个主入口
- 单模块失败时保留 `200 + 模块级状态`
- 详细模块独立接口仍保留，但不再是前端主路径

## 日级数据产品层

当前正式引入：

```text
backend/app/services/data_products/
```

本轮优先接入：

- `daily_bars_daily`
- `announcements_daily`
- `financial_summary_daily`
- `factor_snapshot_daily`
- `decision_brief_daily`
- `screener_snapshot_daily`

核心职责：

- 统一按“日”为粒度管理研究产物
- 本地优先、按日复用、缺啥补啥
- 只有在显式 `force_refresh=true` 时才主动刷新远端

## Freshness Policy

当前统一规则为：

1. 日级分析默认使用最后一个已收盘交易日
2. 页面访问时不默认追当天日线
3. 本地已有同日结果时优先复用
4. 日级产物尽量携带：
   - `as_of_date`
   - `freshness_mode`
   - `source_mode`

## Screener Workflow 模式

`/screener` 页面已经从同步长请求切换为 workflow 模式：

1. 提交 workflow
2. 立即拿到 `run_id`
3. 轮询 `GET /workflows/runs/{run_id}`
4. 展示步骤摘要与最终结果

当前主路径：

- `POST /workflows/screener/run`
- `POST /workflows/deep-review/run`

兼容旧路径：

- `GET /screener/run`
- `GET /screener/deep-run`

## 证据链

当前新增统一证据链结构：

- `EvidenceRef`
- `EvidenceBundle`
- `EvidenceManifest`

这层只回答“结论来自哪里”，不暴露内部思维链。

## DecisionBrief 主输出层

当前单票页新增了一个独立的输出整合层：

```text
backend/app/services/decision_brief_service/
```

这一层不负责新增分析能力，只负责把已有结果整理成统一的“结论 -> 依据 -> 动作”。

它依赖的下层输入包括：

- `FactorSnapshot`
- `ReviewReport v2`
- `DebateReviewReport`
- `StrategyPlan`
- `TriggerSnapshot`
- `StockProfile`

关系可以理解为：

1. `factor / review / debate / strategy / trigger`
   - 提供原始结构化依据
2. `decision_brief_service`
   - 把这些依据整合成更适合直接阅读和执行的主输出
3. `frontend stock workspace`
   - 先展示 `DecisionBrief`
   - 再展示证据层
   - 最后下沉到详细模块

推荐顺序：

1. 先看 `DecisionBrief`
2. 再看证据层
3. 最后看详细模块

对应接口关系：

- `GET /stocks/{symbol}/decision-brief`
  - 主输出层
- `GET /stocks/{symbol}/factor-snapshot`
- `GET /stocks/{symbol}/review-report`
- `GET /stocks/{symbol}/debate-review`
- `GET /strategy/{symbol}`
  - 下层依据接口，继续保留，不做删除
