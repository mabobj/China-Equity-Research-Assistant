# A-Share Research Assistant

面向中国大陆 A 股市场的研究与交易决策辅助系统。

当前阶段重点是把数据接入、技术分析、结构化研究、结构化策略、规则选股和轻量前端链路做稳。当前阶段不包含自动实盘交易、券商下单集成和高频交易。

## 当前能力

- 股票基础信息、日线行情、公告、财务摘要
- 技术分析与因子快照
- 单票研究报告与交易策略
- 规则版 `debate-review`
- 受控 LLM 版 `debate-review`
- 全市场初筛与深筛

## 本地启动

### 1. 准备环境变量

```powershell
Copy-Item .env.example .env
```

### 2. 安装后端依赖

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
```

### 3. 安装前端依赖

```powershell
Set-Location frontend
npm install
Set-Location ..
```

### 4. 启动后端

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_backend.ps1
```

默认地址：

- 健康检查：[http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- Swagger：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 5. 启动前端

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_frontend.ps1
```

## 关键环境变量

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-5.4
OPENAI_BASE_URL=https://api.openai.com/v1
LLM_PROVIDER=auto
ENABLE_LLM_DEBATE=false
LLM_DEBATE_TIMEOUT_SECONDS=20
```

说明：

- `LLM_PROVIDER=auto` 表示按 `OPENAI_BASE_URL` 自动识别 provider。
- 当前内置 provider：
  - `openai_compatible`
  - `volcengine_ark`
- 如果你接的是火山方舟 coding/plan 套餐，建议保留：
  - `OPENAI_BASE_URL=https://ark.cn-beijing.volces.com/api/coding/v3`
  - `LLM_PROVIDER=auto`
  - `LLM_DEBATE_TIMEOUT_SECONDS` 建议至少 `60`

## LLM 裁决运行时

`GET /stocks/{symbol}/debate-review` 当前支持两种运行时：

- `rule_based`
- `llm`

可通过 `use_llm=true/false` 显式控制；如果未传，则由 `ENABLE_LLM_DEBATE` 决定。

### 当前 LLM 设计边界

- 只允许固定角色、固定轮次、固定 schema
- LLM 只负责结构化文本判断
- 数据抓取、技术指标、因子计算、风险边界仍由代码负责
- 任一角色输出未通过 schema 校验时，会自动回退规则版

### 火山方舟适配说明

火山方舟 coding/plan 套餐不支持 `response_format=json_schema/json_object`。项目已经把这部分兼容逻辑独立为 provider 适配层：

- `backend/app/services/llm_debate_service/providers/openai_compatible_provider.py`
- `backend/app/services/llm_debate_service/providers/volcengine_ark_provider.py`
- `backend/app/services/llm_debate_service/providers/registry.py`

其中：

- 标准 OpenAI 兼容网关会按 `json_schema -> json_object -> prompt_only_json` 依次尝试
- 火山方舟会直接进入 `prompt_only_json`，避免无意义的 `400 Bad Request`
- 火山方舟会把实际超时下限提升到 `60s`，并关闭 SDK 自动重试，避免深度思考模型被 20 秒过早打断

后续如果接入新的 LLM，只需要新增一个 provider 适配模块，再在 registry 中注册即可，不需要再改核心角色执行器。

## Agent 提示词配置

各个角色的系统提示词已经统一改为独立配置文件，目录如下：

```text
backend/app/services/llm_debate_service/prompts/
  TECHNICAL_ANALYST_AGENT.md
  FUNDAMENTAL_ANALYST_AGENT.md
  EVENT_ANALYST_AGENT.md
  SENTIMENT_ANALYST_AGENT.md
  BULL_RESEARCHER_AGENT.md
  BEAR_RESEARCHER_AGENT.md
  CHIEF_ANALYST_AGENT.md
  RISK_REVIEWER_AGENT.md
```

这些文件既是角色说明文件，也是当前的提示词配置入口。后续如果要调整角色边界、输出约束或新增角色，优先改这里。

## 目录结构

```text
backend/   FastAPI 后端
frontend/  Next.js 前端
docs/      架构与路线说明
scripts/   本地运行与测试脚本
```

## 测试

### 后端测试

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test_backend.ps1
```

### 前端校验

```powershell
Set-Location frontend
npm.cmd run lint
npx.cmd tsc --noEmit
```

## 主要接口

- `GET /health`
- `GET /stocks/{symbol}/profile`
- `GET /stocks/{symbol}/daily-bars`
- `GET /stocks/{symbol}/announcements`
- `GET /stocks/{symbol}/financial-summary`
- `GET /stocks/{symbol}/factor-snapshot`
- `GET /stocks/{symbol}/review-report`
- `GET /stocks/{symbol}/debate-review`
- `GET /research/{symbol}`
- `GET /strategy/{symbol}`
- `GET /screener/run`
- `GET /screener/deep-run`

## 设计原则

- 研究优先于炫技
- 结构化优先于自由文本
- 规则与模型分工明确
- API 层只负责接收与返回
- 外部数据源统一走 provider
- 免费 provider 必须允许失败和回退

## Workflow 执行器 v1

当前版本新增了一个轻量、同步、可从中间节点启动的 workflow 执行器层，目录位于：

```text
backend/app/services/workflow_runtime/
```

设计边界：

- 只做显式顺序执行，不引入队列、调度器或 DAG 平台
- 每个节点都有明确的 `name / input contract / output contract`
- 每次运行都会生成 `run_id`
- 会记录输入摘要、节点摘要、最终输出摘要和运行状态
- 公开 API 仍保持轻量，不引入认证和后台任务

### 已支持的 workflow

#### 1. `single_stock_full_review`

节点顺序：

1. `SingleStockResearchInputs`
2. `FactorSnapshotBuild`
3. `ReviewReportBuild`
4. `DebateReviewBuild`
5. `StrategyPlanBuild`

能力说明：

- 复用现有 `review_service / debate_service / llm_debate_service / strategy_planner / factor_service`
- `DebateReviewBuild` 支持 `use_llm=true/false`
- 可通过 `start_from` 从中间节点启动
- 即使从中间节点启动，也会用现有 service 自动补齐前置输入

#### 2. `deep_candidate_review`

节点顺序：

1. `ScreenerRun`
2. `DeepCandidateSelect`
3. `CandidateReviewBuild`
4. `CandidateDebateBuild`
5. `CandidateStrategyBuild`

能力说明：

- 复用现有 `screener / review / debate / strategy`
- 第一版只做同步执行
- 支持 `max_symbols / top_n / deep_top_k / use_llm`
- 个别 symbol 失败时会跳过，但会在最终结果和步骤摘要中记录失败信息

### `start_from` 与 `stop_after`

- `start_from`：指定从哪个节点开始正式执行，之前节点会标记为 `skipped`
- `stop_after`：指定执行到哪个节点后停止，之后节点会标记为 `skipped`
- 二者都不会改变节点定义顺序，只影响本次运行边界
- 如果从中间节点启动，workflow 会按需要自动补齐前置输入，但不会把前置节点记为已执行完成

### 运行记录

当前版本会把 workflow 运行记录持久化到：

```text
data/workflow_runs/
```

每次运行至少记录：

- `run_id`
- `workflow_name`
- `started_at`
- `finished_at`
- `input_summary`
- `step summaries`
- `final_output_summary`
- `status`

### Workflow API

新增接口：

- `POST /workflows/single-stock/run`
- `POST /workflows/deep-review/run`
- `GET /workflows/runs/{run_id}`

这些接口与现有 `review / debate / strategy / screener` 的关系是：

- 现有接口继续保留，适合单能力直接调用
- workflow 接口负责把这些既有能力按显式节点组织起来
- workflow 本身不是新的研究算法层，而是一个薄编排层
