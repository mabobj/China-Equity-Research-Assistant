# A 股研究、预测与决策工作台

面向中国大陆 A 股市场的单用户研究、选股、策略与复盘系统。

项目当前定位不是“聊天式荐股”，也不是“自动实盘机器人”，而是一个以公开信息为事实源、以结构化输出为核心、以可追溯闭环为基础的产品系统。当前已经具备可用的单票工作台、选股工作台、交易记录与复盘闭环；长期主线则继续向“因子发现、验证、组合与监控系统”演进。

## 1. 当前状态

截至当前版本，项目已经具备的主线能力包括：

- 单票工作台：`/stocks/[symbol]`
- 选股工作台：`/screener`
- 结构化研究输出：
  - `review-report v2`
  - `debate-review`
  - `strategy plan`
  - `decision brief`
- workflow 运行记录、轮询与局部失败可见性
- `bars / financial_summary / announcements` 数据清洗层
- 初筛因子主链：
  - `screener_factor_snapshot_daily`
  - `screener_selection_snapshot_daily`
  - 初筛 factor / selection 血缘诊断入口
- 交易与复盘最小闭环：
  - `decision snapshot -> trade -> review`
- 预测主线最小底座：
  - dataset / label / prediction / backtest / evaluation
  - `predictive_snapshot`
  - 模型版本评估建议

当前系统已经“可用”，但仍处于长期主线的前中期阶段，尚未进入：

- 自动下单
- 券商接入
- 组合级归因与持仓引擎
- 实盘执行系统

## 2. 当前主入口

### 单票主入口

- `GET /stocks/{symbol}/workspace-bundle`
- 前端页面：[http://127.0.0.1:3000/stocks/600519.SH](http://127.0.0.1:3000/stocks/600519.SH)

### 选股主入口

- `POST /workflows/screener/run`
- `GET /workflows/runs/{run_id}`
- `GET /screener/diagnostics/selection-lineage/latest`
- `GET /screener/diagnostics/factor-lineage/{symbol}`
- 前端页面：[http://127.0.0.1:3000/screener](http://127.0.0.1:3000/screener)

### 深筛主入口

- `POST /workflows/deep-review/run`
- `GET /workflows/runs/{run_id}`

### 关键市场数据域入口

- `GET /market/benchmarks`
- `GET /market/benchmarks/{benchmark_symbol}/daily-bars`
- `GET /market/breadth`
- `GET /market/risk-proxies`
- `GET /stocks/{symbol}/classification`

### 交易与复盘入口

- `POST /decision-snapshots`
- `POST /trades`
- `POST /reviews/from-trade/{trade_id}`
- 前端页面：
  - [http://127.0.0.1:3000/trades](http://127.0.0.1:3000/trades)
  - [http://127.0.0.1:3000/reviews](http://127.0.0.1:3000/reviews)

## 3. 数据源优先级

当前 `data_service` 的默认优先级已经收敛为：

- `tdx-api > mootdx > akshare > baostock`

补充说明：

- `tdx-api` 是本地 HTTP 主数据源，优先承担股票池、搜索、日线、行情等稳定链路
- `mootdx` 是本地高速历史源，适合离线或批量历史读取，但必须经过新鲜度与完整性检查
- `AKShare` 主要承担补充型、结构化型、研究型数据，不适合作为高频核心链路
- `BaoStock` 是稳定兜底源，用于行情与证券基础数据 fallback
- 公告类正式披露信息以 `CNINFO` 为准

详见：[Provider 使用说明](docs/provider-notes.md)

当前后端还提供了最小只读 provider 诊断接口，便于联调和排障：

- `GET /providers/capabilities`
- `GET /providers/health`
- `GET /providers/health/{capability}`

## 4. 快速开始

环境建议：

- Windows PowerShell
- Python 3.11+
- Node.js 20+

最小启动步骤：

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
Set-Location frontend
npm install
Set-Location ..
```

启动后端：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_backend.ps1
```

启动前端：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_frontend.ps1
```

更多细节见：

- [快速开始](docs/manuals/quickstart.md)
- [日常使用说明](docs/manuals/daily-usage.md)

## 5. 测试命令

后端关键回归：

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest backend/tests/test_stocks_api.py backend/tests/test_workflow_api.py backend/tests/test_trade_review_store.py backend/tests/test_trade_review_api.py -q
python -m pytest backend/tests/test_prediction_pipeline_services.py backend/tests/test_prediction_api.py backend/tests/test_workflow_runtime_service.py -q
```

前端检查：

```powershell
Set-Location frontend
npm.cmd run type-check
npm.cmd run lint
npm.cmd run test:smoke
```

## 6. 文档导航

### 首先阅读

- [AGENTS.md](AGENTS.md)
- [项目硬性约束](docs/project-constraints.md)
- [当前执行基线](docs/execution-baseline.md)
- [Docs 索引](docs/index.md)

### 当前有效需求与任务书

- [因子优先初筛设计 v1](docs/factor-first-screener-design-v1.md)
- [因子优先初筛任务书 v1](docs/taskbook-factor-first-screener-v1.md)
- [因子优先初筛实现规格 v1](docs/factor-first-screener-implementation-spec-v1.md)
- [因子优先初筛 API 与存储规格 v1](docs/factor-first-screener-api-storage-spec-v1.md)
- [因子优先初筛前端交互规格 v1](docs/factor-first-screener-frontend-spec-v1.md)

### 项目架构与长期方向

- [系统架构](docs/architecture.md)
- [路线图](docs/roadmap.md)
- [因子系统 PRD v1](docs/a_share_factor_prd_v1.md)
- [因子系统架构设计 v1](docs/a_share_architecture_design_spec_v1.md)
- [因子字典 v1](docs/a_share_factor_dictionary_v1.md)

### 数据底座

- [Provider 使用说明](docs/provider-notes.md)
- [Data 清洗层说明](docs/manuals/data-cleaning.md)
- [数据源与边界](docs/manuals/data-and-limitations.md)

### 使用手册

- [快速开始](docs/manuals/quickstart.md)
- [日常使用说明](docs/manuals/daily-usage.md)
- [故障排查](docs/manuals/troubleshooting.md)

### 历史审计文档

- [稳定性审计 v1](docs/audits/stability-review-v1.md)

## 7. 当前边界

当前系统适合：

- 单票研究与结构化决策
- 规则选股与 workflow 编排
- 预测信号的最小接入与评估
- 交易记录与复盘闭环
- 为长期因子系统做工程准备

当前系统不适合：

- 自动实盘交易
- 未经确认的交易执行
- 高频交易
- 把自由文本 LLM 结果直接当作交易指令

## 8. 文档使用说明

当前文档体系已经收口为“agent 约束 > 项目硬约束 > 当前执行基线 > 当前有效需求 / 任务书 > 使用手册 / 历史文档”。

- `AGENTS.md`：只用于约束 agent 的工作方式、任务前阅读要求和文档同步要求
- `docs/project-constraints.md`：维护项目长期稳定的硬边界与架构约束
- `docs/execution-baseline.md`：维护当前阶段、当前优先级、当前重点模块、当前有效需求与任务书
- `docs/index.md`：整理 `docs/` 目录，区分当前有效、长期参考、使用文档与历史文档
- 当前有效的需求与任务书：以 `docs/execution-baseline.md` 中声明的文档为准
- `README.md`：只作为项目总览与入口导航，不再承担“当前有效规则源”的职责

如果代码与文档出现差异，应优先按下面顺序理解：

1. `AGENTS.md`（仅限 agent 行为与执行要求）
2. `docs/project-constraints.md`
3. `docs/execution-baseline.md`
4. `docs/execution-baseline.md` 中声明的当前有效需求与任务书
5. `README.md`

## 9. 财务数据源分层策略

当前财务摘要主链已收口为：

- 官方披露原文索引：`CNINFO`
- 本地结构化财务快照：`financial_reports`
- 结构化主源：`Tushare`（可选启用）
- 免费 fallback：`BaoStock`
- 最后级补充源：`AKShare`

补充说明：

- `AKShare` 不再作为默认财务主源，只承担最后级补洞和临时 fallback
- `Tushare` 通过 `TUSHARE_ENABLED=true` 与 `TUSHARE_TOKEN=...` 启用；未启用时链路自动退化为 `local -> baostock -> akshare`
- 官方披露原文本轮只做“报告索引 + 下载链接”接口位，不做 PDF/XBRL 正文解析
- 财务摘要内部统一口径字段包括：
  - `revenue / net_profit`：单位统一为“元”
  - `roe / debt_ratio / revenue_yoy / net_profit_yoy / gross_margin`：统一为百分数
  - `eps / bps`：统一为元/股
  - `report_period`：`YYYY-MM-DD`
  - `report_type`：`q1 / half / q3 / annual / ttm / unknown`

## 10. 数据血缘与版本追踪

当前项目已经完成 Phase 4 的主链落地，目标是把分散存在的：

- workflow runs
- screener batches
- daily products
- factor snapshots
- predictive snapshots
- evaluation / backtest artifacts

逐步收敛到统一的“数据来源、版本、参数、回放依据”体系中。

现阶段重点是：

- 让初筛结果能追溯到因子快照、方案版本和质量门控结果
- 让预测与评估结果具备更明确的版本信息与重建依据
- 为后续因子验证、策略复盘与方案比较提供统一底座
