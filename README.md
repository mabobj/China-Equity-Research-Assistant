# A-Share Research Assistant

面向中国大陆 A 股市场的研究与交易决策辅助系统。

当前阶段已经具备的核心能力：

- 全市场初筛与深筛
- 单票结构化研究
- 角色化 debate 裁决
- 结构化 strategy plan
- 显式 workflow 执行
- 轻量前端工作台

当前阶段明确不做：

- 自动实盘交易
- 券商下单集成
- 高频交易
- 复杂调度系统或通用 DAG 平台

## 如何使用系统

推荐先看这些文档：

- [快速开始](docs/manuals/quickstart.md)
- [日常使用说明](docs/manuals/daily-usage.md)
- [数据源与边界说明](docs/manuals/data-and-limitations.md)
- [故障排查](docs/manuals/troubleshooting.md)
- [系统架构](docs/architecture.md)
- [稳定性审计 v1](docs/audits/stability-review-v1.md)

## 当前推荐主链路

如果你是第一次使用，推荐按下面顺序验证：

1. 按 [快速开始](docs/manuals/quickstart.md) 启动后端和前端。
2. 在首页输入 `600519.SH`，进入单票工作台。
3. 在单票页依次查看：
   - 股票基础信息
   - factor snapshot
   - review-report v2
   - debate-review
   - strategy plan
   - trigger snapshot
4. 在单票页运行 `single_stock_full_review` workflow。
5. 打开 `/screener`，运行规则初筛、深筛和 `deep_candidate_review` workflow。

## 前端工作台

当前前端不是原始 API 的简单展示，而是三个可用入口：

- `/`
  - 首页
  - 系统能力说明
  - 股票代码输入
  - workflow 执行入口导航
- `/stocks/[symbol]`
  - 单票工作台
  - 串联基础信息、factor、review、debate、strategy、trigger
  - 内置 `single_stock_full_review` workflow 入口
- `/screener`
  - 选股工作台
  - 串联数据补全、规则初筛、深筛结果
  - 内置 `deep_candidate_review` workflow 入口

`/trades` 和 `/reviews` 当前仍为诚实占位页，不伪造未上线业务。

## Workflow 执行器 v1

当前已支持两个同步 workflow：

### 1. `single_stock_full_review`

节点顺序：

1. `SingleStockResearchInputs`
2. `FactorSnapshotBuild`
3. `ReviewReportBuild`
4. `DebateReviewBuild`
5. `StrategyPlanBuild`

### 2. `deep_candidate_review`

节点顺序：

1. `ScreenerRun`
2. `DeepCandidateSelect`
3. `CandidateReviewBuild`
4. `CandidateDebateBuild`
5. `CandidateStrategyBuild`

当前 workflow 的边界：

- 只做同步执行
- 支持 `start_from`
- 支持 `stop_after`
- 支持 `use_llm`（如对应节点适用）
- 每次运行都会生成 `run_id`
- 会记录输入摘要、步骤摘要、最终输出摘要和运行状态

运行记录当前存放在：

```text
data/workflow_runs/{run_id}.json
```

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

### 5. 启动前端

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_frontend.ps1
```

默认地址：

- 后端健康检查：[http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- 后端文档：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- 前端页面：[http://127.0.0.1:3000](http://127.0.0.1:3000)

## 关键环境变量

最常用的变量如下：

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-5.4
OPENAI_BASE_URL=https://api.openai.com/v1
LLM_PROVIDER=auto
ENABLE_LLM_DEBATE=false
LLM_DEBATE_TIMEOUT_SECONDS=20
ENABLE_MOOTDX=false
MOOTDX_TDX_DIR=C:/new_tdx
```

说明：

- `LLM_PROVIDER=auto` 会根据 `OPENAI_BASE_URL` 自动识别 provider。
- 如果接的是火山方舟 coding/plan 套餐，建议至少设置：
  - `OPENAI_BASE_URL=https://ark.cn-beijing.volces.com/api/coding/v3`
  - `LLM_PROVIDER=auto`
  - `LLM_DEBATE_TIMEOUT_SECONDS=60`
- `ENABLE_MOOTDX=true` 时，需要正确设置 `MOOTDX_TDX_DIR`。

## LLM debate 说明

`GET /stocks/{symbol}/debate-review` 支持两种运行模式：

- `rule_based`
- `llm`

控制方式：

- 显式传 `use_llm=true/false`
- 或由 `ENABLE_LLM_DEBATE` 决定默认行为

当前边界：

- LLM 只做结构化判断与说明
- 指标计算、因子分数、风险边界仍由代码负责
- 当 LLM 调用失败、超时或 schema 校验失败时，会自动回退到规则版

## 测试与校验

### 后端测试

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test_backend.ps1
```

### 前端校验

```powershell
Set-Location frontend
npm.cmd run lint
npm.cmd run type-check
```

## 主要接口

- `GET /health`
- `GET /stocks/{symbol}/profile`
- `GET /stocks/{symbol}/factor-snapshot`
- `GET /stocks/{symbol}/review-report`
- `GET /stocks/{symbol}/debate-review`
- `GET /strategy/{symbol}`
- `GET /screener/run`
- `GET /screener/deep-run`
- `POST /workflows/single-stock/run`
- `POST /workflows/deep-review/run`
- `GET /workflows/runs/{run_id}`

## 设计原则

- 研究优先于炫技
- 结构化优先于自由文本
- 规则与模型分工明确
- route 层只做请求接收与响应返回
- 外部数据源统一走 provider
- 免费 provider 必须允许失效与回退

## 目录结构

```text
backend/   FastAPI 后端
frontend/  Next.js 前端
docs/      架构、路线图、使用手册、审计报告
scripts/   本地启动与测试脚本
data/      DuckDB、workflow run records 等本地数据
logs/      后端日志
```
