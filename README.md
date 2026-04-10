# A 股研究、预测与决策工作台

面向中国大陆 A 股市场的单用户研究与决策工作台。

项目当前定位不是“聊天式荐股”，也不是“自动实盘机器人”，而是一个以公开信息为事实源、以结构化输出为核心、以可追溯闭环为基础的产品系统。它已经具备可用的单票工作台、选股工作台、交易记录与复盘闭环；长期主线则继续向“因子发现、验证、组合与监控系统”演进。

## 1. 长期方向

项目今后的主线不是继续堆更多零散页面或报告模块，而是沿着两条并行主线持续推进：

1. 研究与决策工作台主线  
   保留现有 `workspace-bundle + workflow + trade/review` 产品外壳，持续提升稳定性、可解释性、可操作性和消费级体验。

2. 预测与评估主线  
   逐步补齐点时特征、标签、回测、预测、评估、模型版本治理，并最终服务于长期目标：因子发现、验证、组合与监控系统。

其中，以下三份文档定义了长期方向：

- [因子系统 PRD v1](docs/a_share_factor_prd_v1.md)
- [因子系统架构设计 v1](docs/a_share_architecture_design_spec_v1.md)
- [因子字典 v1](docs/a_share_factor_dictionary_v1.md)

## 2. 当前项目状态

截至当前版本，项目已经完成的主线能力包括：

- 单票工作台：`/stocks/[symbol]`
- 选股工作台：`/screener`
- 结构化研究输出：
  - `review-report v2`
  - `debate-review`
  - `strategy plan`
  - `decision brief`
- workflow 运行记录、轮询与局部失败可见性
- `bars / financial_summary / announcements` 数据清洗层
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

## 3. 当前主入口

### 单票主入口

- `GET /stocks/{symbol}/workspace-bundle`

前端页面：

- [http://127.0.0.1:3000/stocks/600519.SH](http://127.0.0.1:3000/stocks/600519.SH)

### 选股主入口

- `POST /workflows/screener/run`
- `GET /workflows/runs/{run_id}`

前端页面：

- [http://127.0.0.1:3000/screener](http://127.0.0.1:3000/screener)

### 深筛主入口

- `POST /workflows/deep-review/run`
- `GET /workflows/runs/{run_id}`

### 关键市场数据域入口

- `GET /market/benchmarks`
- `GET /market/benchmarks/{benchmark_symbol}/daily-bars`
- `GET /market/breadth`
- `GET /market/risk-proxies`
- `GET /stocks/{symbol}/classification`

### 交易与复盘主入口

- `POST /decision-snapshots`
- `POST /trades`
- `POST /reviews/from-trade/{trade_id}`

前端页面：

- [http://127.0.0.1:3000/trades](http://127.0.0.1:3000/trades)
- [http://127.0.0.1:3000/reviews](http://127.0.0.1:3000/reviews)

## 4. 数据源优先级

当前 `data_service` 的默认优先级已经收敛为：

- `tdx-api > mootdx > akshare > baostock`

补充说明：

- `tdx-api` 是本地 HTTP 主数据源，优先承担股票池、搜索、日线、行情等稳定链路。
- `mootdx` 是本地高速历史源，适合离线或批量历史读取，但必须经过新鲜度与完整性检查。
- `AKShare` 主要承担补充型、结构化型、研究型数据，不适合作为高频核心链路。
- `BaoStock` 是稳定兜底源，用于行情与证券基础数据 fallback。
- 公告类正式披露信息以 `CNINFO` 为准。

详见：[Provider 使用说明](docs/provider-notes.md)

当前后端还提供了最小只读 provider 诊断接口，便于联调和排障：

- `GET /providers/capabilities`
- `GET /providers/health`
- `GET /providers/health/{capability}`

## 5. 数据底座当前结论

从长期方向看，当前数据底座已经完成“多源接入”向“统一标准层”的第一步，但仍有几项需要继续补齐的关键能力：

1. 点时一致性仍需加强  
   长期因子验证要求所有特征与标签都能严格按 `as_of_date` 重建，避免未来函数与回看污染。

2. 数据域还不够完整  
   当前已经完成第一阶段补齐：`基准目录 / 行业与板块分类 / 市场广度 / 基础风险代理` 已有标准 schema、日级数据产品与只读接口；但真实指数行情链路、更多风格代理变量与更丰富的风险暴露输入仍需后续继续补齐。

3. 复权与公司行为口径需要继续集中化  
   长期回测和因子验证要求明确区分原始价、前复权价、后复权价，以及停牌、ST、退市、分红送转等事件处理口径。

当前已经完成前两阶段收口：

- 日线 schema 与响应层已显式暴露 `adjustment_mode`
- `/stocks/{symbol}/daily-bars` 已支持显式 `adjustment_mode=raw/qfq/hfq`
- `daily_bars` 本地存储已按 `symbol + trade_date + adjustment_mode` 区分保存
- 日线响应已统一暴露 `corporate_action_mode / corporate_action_warnings`

4. 数据血缘与重建能力仍需加强  
   长期上要能回答“这条特征来自哪个 provider、哪次落盘、哪个版本、是否发生过 fallback”，这对因子验证和模型评估很关键。

5. provider 健康度与能力矩阵还需继续收敛  
   当前已有 fallback 和可见性，且 capability 策略已经集中收口；后续重点不再是“再接更多源”，而是继续把数据域级能力表、stale fallback 边界和本地持久化要求制度化。

这些问题已经在文档中收口为“长期方向下必须补齐的有限缺口”，不是无休止优化项。详见：

- [系统架构](docs/architecture.md)
- [路线图](docs/roadmap.md)
- [当前阶段](docs/current_phase.md)
- [Provider 使用说明](docs/provider-notes.md)

## 6. 快速开始

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

## 7. 测试命令

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

## 8. 文档导航

### 当前执行基线

- [系统架构](docs/architecture.md)
- [路线图](docs/roadmap.md)
- [当前阶段](docs/current_phase.md)
- [项目任务书（v2.1，产品化增强版）](docs/taskbook-v2.1.md)
- [项目任务书（v2.2，数据底座与点时特征版）](docs/taskbook-v2.2.md)

### 数据底座

- [Provider 使用说明](docs/provider-notes.md)
- [Data 清洗层说明](docs/manuals/data-cleaning.md)
- [数据源与边界](docs/manuals/data-and-limitations.md)

### 使用手册

- [快速开始](docs/manuals/quickstart.md)
- [日常使用说明](docs/manuals/daily-usage.md)
- [故障排查](docs/manuals/troubleshooting.md)

### 历史稳定化审计

- [稳定性审计 v1](docs/audits/stability-review-v1.md)

### 长期北极星文档

- [因子系统 PRD v1](docs/a_share_factor_prd_v1.md)
- [因子系统架构设计 v1](docs/a_share_architecture_design_spec_v1.md)
- [因子字典 v1](docs/a_share_factor_dictionary_v1.md)

## 9. 当前边界

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

## 10. 文档状态说明

当前文档已经按“长期方向 > 当前阶段 > 使用手册”三层收口：

- 长期方向：回答项目最终要走向哪里
- 当前阶段：回答现在优先做什么、不做什么
- 使用手册：回答今天怎么把系统用起来

如果后续代码和文档出现差异，应优先按下面顺序理解：

1. `AGENTS.md`
2. `docs/architecture.md`
3. `docs/current_phase.md`
4. `docs/taskbook-v2.1.md`
5. `README.md`
