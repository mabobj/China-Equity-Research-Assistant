# A-Share Research Assistant

面向中国大陆 A 股市场的研究与交易决策辅助系统。

当前项目重点是先把数据接入、技术分析、结构化研究、结构化策略、规则选股和轻前端链路做稳。现阶段仍不包含自动实盘交易、券商下单集成、高频交易和盘中自动执行。

## 当前已完成能力

- 股票代码标准化，系统内部统一使用 canonical symbol，例如 `600519.SH`
- 股票基础信息、日线行情、基础股票池
- 公告列表与基础财务摘要
- 技术分析底层与结构化 technical snapshot
- 结构化单票研究报告
- 结构化交易策略计划
- 全市场规则初筛选股器
- 基于初筛结果的深筛聚合选股器
- 最小可用前端页面接入

## 技术栈

- Backend: Python, FastAPI, Pydantic, pytest
- Frontend: Next.js, TypeScript, Tailwind CSS
- Storage planning: SQLite, DuckDB, Parquet

## 目录结构

```text
backend/   FastAPI 后端
frontend/  Next.js 前端
docs/      架构与路线图
scripts/   本地启动与测试脚本
```

## 本地启动

### 1. 准备环境变量

```powershell
Copy-Item .env.example .env
```

### 2. 安装后端依赖

建议使用 Python 3.11+ 虚拟环境：

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
- Swagger 文档：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 5. 启动前端

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_frontend.ps1
```

默认地址：

- [http://localhost:3000/](http://localhost:3000/)

### 6. 前端代理说明

前端通过 Next.js rewrite 把 `/api/backend/*` 转发到后端，默认目标是：

- `http://127.0.0.1:8000`

如需修改，可在启动前设置：

```powershell
$env:BACKEND_API_BASE_URL = "http://127.0.0.1:8000"
```

## 测试与校验

### 后端测试

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test_backend.ps1
```

该脚本会显式设置 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`，用于规避当前 Windows 环境下全局 pytest 插件干扰，保证测试稳定运行。

### 前端校验

```powershell
Set-Location frontend
npm.cmd run lint
npx.cmd tsc --noEmit
```

### 全量初始化脚本（独立运行）

用于一次性初始化全市场数据，具备断点续传与失败重跑能力：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_full_data_init.ps1
```

常用参数：

```powershell
# 从头重跑（清空上次断点与错误日志）
powershell -ExecutionPolicy Bypass -File scripts\run_full_data_init.ps1 --reset

# 控制频率（毫秒）
powershell -ExecutionPolicy Bypass -File scripts\run_full_data_init.ps1 --symbol-sleep-ms 250 --daily-step-sleep-ms 400

# 如需启用 baostock 作为补充 provider（默认关闭）
powershell -ExecutionPolicy Bypass -File scripts\run_full_data_init.ps1 --enable-baostock
```

说明：
- 断点文件默认在 `data/bootstrap/full_init_state.json`
- 异常日志默认在 `data/bootstrap/full_init_errors.jsonl`
- 第一轮全量跑完后，脚本会自动仅重跑失败步骤
- 脚本会输出每个步骤（profile/daily/financial/announcements）的开始、完成与耗时日志
- 全量初始化默认不启用 `baostock`，用于降低长任务中的阻塞风险
- 脚本独立于 API 服务运行，不影响现有后端/前端调试流程

## 当前可用 API

### 健康检查

- `GET /health`

### 股票数据接口

- `GET /stocks/universe`
- `GET /stocks/{symbol}/profile`
- `GET /stocks/{symbol}/daily-bars`
- `GET /stocks/{symbol}/intraday-bars`
- `GET /stocks/{symbol}/timeline`
- `GET /stocks/{symbol}/trigger-snapshot`
- `GET /stocks/{symbol}/announcements`
- `GET /stocks/{symbol}/financial-summary`
- `GET /stocks/{symbol}/technical`
- `GET /stocks/{symbol}/factor-snapshot`

说明：
- 当前公开 API 仍保持兼容，继续提供 profile / daily-bars / universe / announcements / financial-summary。
- 数据层内部已重构为 capability-based provider 设计，provider 不再要求一次实现全部能力。
- `GET /stocks/{symbol}/daily-bars` 支持 `start_date` / `end_date`，格式为 `YYYY-MM-DD`。
- `GET /stocks/{symbol}/intraday-bars` 支持 `frequency=1m|5m`，并支持 `start_datetime` / `end_datetime`，格式为 `YYYY-MM-DDTHH:MM[:SS]`。
- `GET /stocks/{symbol}/timeline` 当前返回最新交易日的分时线预览，支持 `limit` 参数。
- `GET /stocks/{symbol}/trigger-snapshot` 基于日线技术快照和盘中快照返回轻量触发判断，支持 `frequency` 与 `limit` 参数。
- `GET /stocks/{symbol}/factor-snapshot` 返回结构化因子快照，供选股 v2 与后续研究工作流复用。

### 单票研究接口

- `GET /research/{symbol}`

返回字段概要：

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

### 结构化策略接口

- `GET /strategy/{symbol}`

返回字段概要：

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

### 数据补全接口

- `GET /data/refresh`
- `POST /data/refresh`

`POST /data/refresh` 用于启动一次手动数据补全后台任务，支持可选请求体：

```json
{
  "max_symbols": 200
}
```

说明：
- `max_symbols` 表示“本轮批量处理数量”，系统会基于本地游标轮转续扫，不会每次都从第一只股票开始。
- 日线补全默认规则为：首次补全最近 400 日；后续增量补全从“本地最新日线的下一天”补到当日（若本地已存在当日数据会跳过请求）。

留空时会按当前股票池执行全量补全。返回字段概要：

- `status`
- `is_running`
- `started_at`
- `finished_at`
- `universe_count`
- `total_symbols`
- `processed_symbols`
- `succeeded_symbols`
- `failed_symbols`
- `profiles_updated`
- `daily_bars_updated`
- `financial_summaries_updated`
- `announcements_updated`
- `universe_updated`
- `current_symbol`
- `current_stage`
- `message`
- `recent_warnings`
- `recent_errors`

### 数据库排查接口

- `GET /admin/db/tables`
- `POST /admin/db/query`

`POST /admin/db/query` 仅支持只读 SQL（`SELECT` / `WITH` / `PRAGMA` / `DESCRIBE` / `SHOW` / `EXPLAIN`），请求体示例：

```json
{
  "sql": "SELECT * FROM daily_bars ORDER BY trade_date DESC LIMIT 20",
  "limit": 200
}
```

### 初筛选股接口

- `GET /screener/run`

可选参数：

- `max_symbols`
- `top_n`

返回字段概要：

- `as_of_date`
- `total_symbols`
- `scanned_symbols`
- `buy_candidates`
- `watch_candidates`
- `avoid_candidates`

每个 candidate 当前包含：

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

### 深筛聚合接口

- `GET /screener/deep-run`

可选参数：

- `max_symbols`
- `top_n`
- `deep_top_k`

返回字段概要：

- `as_of_date`
- `total_symbols`
- `scanned_symbols`
- `selected_for_deep_review`
- `deep_candidates`

每个 deep candidate 当前包含：

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

## 当前前端页面

### `/`

- 项目简介
- 进入 `/screener` 的入口
- 股票代码输入框，可跳转到 `/stocks/[symbol]`

### `/screener`

- 支持通过按钮触发一次手动数据补全
- 可查看补全任务状态、进度、最近错误与各数据域完成数
- 可分别触发 `/screener/run` 与 `/screener/deep-run`
- 支持输入 `max_symbols`、`top_n`、`deep_top_k`
- 展示初筛和深筛的结构化结果
- 包含 loading / error / empty state

### `/stocks/[symbol]`

- 页面加载时同时请求 `/research/{symbol}` 与 `/strategy/{symbol}`
- 展示研究报告与策略计划的重点字段
- 支持切换股票代码
- 包含 loading / error / empty state

### `/trades`

- 清晰占位页

### `/reviews`

- 数据排查台（数据库表清单 + 只读 SQL 查询）

## 股票代码规范

系统内部统一使用 canonical symbol：

- `600519.SH`
- `000001.SZ`
- `300750.SZ`

API 当前支持以下输入格式：

- `600519`
- `600519.SH`
- `sh600519`
- `000001`
- `000001.SZ`
- `sz000001`

symbol 标准化与 provider symbol convert 统一集中在：

```text
backend/app/services/data_service/normalize.py
```

## 配置说明

后端配置统一从以下位置读取：

1. 仓库根目录 `.env`
2. `backend/.env`

统一使用方式：

```python
from app.core.config import get_settings

settings = get_settings()
```

补全与网络重试常用参数（可写到 `.env`）：

- `DATA_REFRESH_SYMBOL_SLEEP_MS`：补全时每只股票之间的节流间隔（毫秒），默认 `120`
- `DATA_REFRESH_ANNOUNCEMENT_LIMIT`：单只股票公告补全上限，默认 `2000`
- `AKSHARE_DAILY_RETRY_MAX_ATTEMPTS`：AKShare 日线请求最大重试次数，默认 `4`
- `AKSHARE_DAILY_RETRY_BACKOFF_SECONDS`：AKShare 日线重试指数退避基数（秒），默认 `0.8`
- `AKSHARE_DAILY_RETRY_JITTER_SECONDS`：AKShare 日线重试抖动（秒），默认 `0.2`
- `ENABLE_MOOTDX`：是否启用 mootdx 本地行情 provider，默认 `false`
- `MOOTDX_TDX_DIR`：通达信本地目录，例如 `C:/new_tdx`

## 数据层结构

当前数据层已从“大一统 provider 协议”收敛为 capability-based 设计。

核心 capability：
- `profile`
- `daily_bars`
- `universe`
- `announcements`
- `financial_summary`
- `intraday_bars`
- `timeline`

当前关键组件：
- `backend/app/services/data_service/providers/base.py`
- `backend/app/services/data_service/provider_registry.py`
- `backend/app/services/data_service/market_data_service.py`

设计说明：
- provider registry 会按 capability 选择 provider，而不是要求每个 provider 实现所有能力
- `MarketDataService` 仍作为统一入口，对现有 API/service 保持兼容
- 现有 provider 通过适配器接入 registry，因此这轮重构不要求一次性重写所有调用层

## mootdx 接入说明

当前 `mootdx` 只作为“本地行情验证版 provider”接入。

已支持：
- 本地通达信目录读取日线
- 本地通达信目录读取 `1m` / `5m` 分钟线
- 本地分时线读取（当前基于本地 `lc5` / `fzline` 数据做最新交易日预览）
- provider capability / health report

当前明确不支持：
- 财务数据
- 公告
- 股票池
- 在线 quotes 默认通路
- 复权默认支持
- 北交所专门支持
- 扩展市场 / 商品 / 期货支持

当前限制与说明：
- 当前以沪深 SH / SZ 本地标准市场为主，不保证北交所、扩展市场、商品、期货可用。
- 分钟线与 timeline 当前属于“验证版 + 最小可用版”，重点是本地读取、结构化返回和触发层输入，不包含复杂盘中策略。
- 如本地目录存在但对应 `.day` / `.lc1` / `.lc5` 文件缺失，接口会返回清晰错误。

启用方式：

```powershell
$env:ENABLE_MOOTDX = "true"
$env:MOOTDX_TDX_DIR = "C:/new_tdx"
```

或写入 `.env`：

```env
ENABLE_MOOTDX=true
MOOTDX_TDX_DIR=C:/new_tdx
```

## mootdx 验证脚本

验证脚本：
- `backend/app/scripts/validate_mootdx_provider.py`
- `backend/app/scripts/run_mootdx_validation_matrix.py`

运行示例：

```powershell
Set-Location backend
python -m app.scripts.validate_mootdx_provider --tdxdir C:/new_tdx --symbol 600519.SH --frequency 1m
```

输出内容包括：
- provider capability report
- provider health report
- 日线预览
- 分钟线预览
- 分时线预览或失败原因

批量验证示例：

```powershell
Set-Location backend
python -m app.scripts.run_mootdx_validation_matrix --tdxdir C:/new_tdx --symbols 600519.SH 000001.SZ 300750.SZ --frequencies 1m 5m --output-json ../data/mootdx_matrix.json --output-csv ../data/mootdx_matrix.csv
```

如需启用日线对比：

```powershell
Set-Location backend
python -m app.scripts.run_mootdx_validation_matrix --tdxdir C:/new_tdx --symbols 600519.SH 000001.SZ --frequencies 1m 5m --compare-provider akshare
```

批量验证输出包括：
- `symbol`
- `capability`
- `status`
- `source`
- `count`
- `latest_timestamp`
- `error_type`
- `error_message`
- `comparison_summary`

## 当前开发约束

- 所有外部数据源访问都放在 `backend/app/services/data_service/providers/`
- API 层只负责参数接收与结构化响应返回
- 复杂业务逻辑放在 service 层
- 关键输出优先结构化，避免把核心结果放进自由文本
- 测试不依赖实时外网，优先用 fake provider、stub service 和 mock 验证

## 选股 v2 因子框架地基

本轮开始把选股器从“技术规则初筛”收敛为“可扩展的多因子横截面框架”，但仍保持当前公开 API 尽量兼容。

当前新增的核心目录：
- `backend/app/services/factor_service/factor_snapshot_service.py`
- `backend/app/services/factor_service/reason_builder.py`
- `backend/app/services/factor_service/factor_library/`

当前最小因子集合：
- 趋势与相对强弱：`20日收益率`、`60日收益率`、`距52周高点距离`
- 质量：`ROE`、`净利率`、`负债率`、`EPS`、`财务数据完整度`
- 成长：`revenue_yoy`、`net_profit_yoy`
- 低波动与风险效率：`20日波动率`、`60日波动率`、`ATR/close`、`最近60日最大回撤`
- 事件：`最近30日公告数量`、`公告关键词打分`、`事件新鲜度`

当前分数语义：
- `alpha_score`：这只股票值不值得进入优先候选池
- `trigger_score`：当前是否接近回踩或突破这类可观察买点
- `risk_score`：风险分，数值越高表示风险越高

### Factor Snapshot API

- `GET /stocks/{symbol}/factor-snapshot`

返回字段概要：
- `symbol`
- `as_of_date`
- `raw_factors`
- `normalized_factors`
- `factor_group_scores`
- `alpha_score`
- `trigger_score`
- `risk_score`

### /screener/run 兼容过渡说明

`/screener/run` 继续保留旧字段，便于当前前端和深筛链路继续工作：
- 旧字段继续保留：`buy_candidates`、`watch_candidates`、`avoid_candidates`
- 旧候选字段继续保留：`list_type`、`screener_score`

同时新增 v2 字段：
- 新分桶：`ready_to_buy_candidates`、`watch_pullback_candidates`、`watch_breakout_candidates`、`research_only_candidates`
- 新候选字段：`v2_list_type`、`alpha_score`、`trigger_score`、`risk_score`
- 新理由字段：`top_positive_factors`、`top_negative_factors`、`risk_notes`、`short_reason`

当前兼容映射关系：
- `READY_TO_BUY` -> `BUY_CANDIDATE`
- `WATCH_PULLBACK` / `WATCH_BREAKOUT` / `RESEARCH_ONLY` -> `WATCHLIST`
- `AVOID` -> `AVOID`

## 个股研判 v2 结构化地基

本轮新增了独立的 `review_service`，用于把单票研判从轻量 `research report v1` 升级为多维结构化输出，但不删除旧接口。

核心目录：
- `backend/app/services/review_service/factor_profile_builder.py`
- `backend/app/services/review_service/technical_view_builder.py`
- `backend/app/services/review_service/fundamental_view_builder.py`
- `backend/app/services/review_service/event_view_builder.py`
- `backend/app/services/review_service/sentiment_view_builder.py`
- `backend/app/services/review_service/bull_bear_builder.py`
- `backend/app/services/review_service/chief_judgement_builder.py`
- `backend/app/services/review_service/stock_review_service.py`

### 新旧研究接口关系

- `GET /research/{symbol}`
- 现有轻量研究接口，输出 `technical_score / fundamental_score / event_score / overall_score / action / thesis`
- `GET /stocks/{symbol}/review-report`
- 新的多维研判接口，输出六块固定画像、多空分歧、最终裁决和策略摘要

### /stocks/{symbol}/review-report

- `GET /stocks/{symbol}/review-report`

返回字段概要：
- `symbol`
- `name`
- `as_of_date`
- `factor_profile`
- `technical_view`
- `fundamental_view`
- `event_view`
- `sentiment_view`
- `bull_case`
- `bear_case`
- `key_disagreements`
- `final_judgement`
- `strategy_summary`
- `confidence`

### 六块研判输出含义

- `factor_profile`
- 因子层总结，聚焦 `alpha_score / trigger_score / risk_score` 与最强、最弱因子组
- `technical_view`
- 日线趋势、盘中触发状态、关键价位和技术失效提示
- `fundamental_view`
- 质量、成长、杠杆和财务字段完整度的结构化解读
- `event_view`
- 最近公告催化、风险扰动、事件热度和简短事件摘要
- `sentiment_view`
- 基于相对强弱、量能、波动和关键位置构造的轻量情绪画像
- `bull_case / bear_case / final_judgement`
- 分别承载看多理由、看空理由和最终裁决，全部由规则和模板化输出生成，不依赖 LLM

### 角色边界

- `bull_case`
- 只负责提炼“为什么值得继续关注或买入”的最强 2-3 条理由
- `bear_case`
- 只负责提炼“为什么要谨慎、回避或延后执行”的最强 2-3 条理由
- `final_judgement`
- 作为首席裁决层，综合多空分歧与现有策略计划，给出简洁结论与执行重点

## debate-review 角色化裁决骨架

本轮在 `review-report` 之上新增了 `debate_service`，目标不是引入真正的 LLM 多轮辩论，而是先把角色边界、节点流和结构化输出固定下来。

核心目录：
- `backend/app/services/debate_service/analyst_views_builder.py`
- `backend/app/services/debate_service/technical_analyst.py`
- `backend/app/services/debate_service/fundamental_analyst.py`
- `backend/app/services/debate_service/event_analyst.py`
- `backend/app/services/debate_service/sentiment_analyst.py`
- `backend/app/services/debate_service/bull_researcher.py`
- `backend/app/services/debate_service/bear_researcher.py`
- `backend/app/services/debate_service/chief_analyst.py`
- `backend/app/services/debate_service/risk_reviewer.py`
- `backend/app/services/debate_service/debate_orchestrator.py`

### 与 review-report 的关系

- `GET /stocks/{symbol}/review-report`
- 多维研判 v2，重点是静态聚合后的结构化画像
- `GET /stocks/{symbol}/debate-review`
- 角色化裁决骨架版，重点是 analyst 观点、多空研究员、首席裁决与风险复核

### 当前仍不是 LLM 运行时

- 当前所有角色输出都来自规则和模板化 builder
- 当前没有真正多轮循环对话
- 当前没有 OpenAI/LLM 调用
- 当前只是为未来有限轮多 agent 裁决预埋正式结构

### /stocks/{symbol}/debate-review

- `GET /stocks/{symbol}/debate-review`

返回字段概要：
- `symbol`
- `name`
- `as_of_date`
- `analyst_views`
- `bull_case`
- `bear_case`
- `key_disagreements`
- `chief_judgement`
- `risk_review`
- `final_action`
- `strategy_summary`
- `confidence`

### 角色边界

- `technical_analyst`
- 负责技术面观点、关键价位、入场和失效提示
- `fundamental_analyst`
- 负责质量、成长和财务风险提示
- `event_analyst`
- 负责近期催化、近期风险和事件温度
- `sentiment_analyst`
- 负责市场偏好、拥挤度提示和动量环境
- `bull_researcher`
- 负责提炼支持交易的最强 2-3 条理由
- `bear_researcher`
- 负责提炼反对交易或建议谨慎的最强 2-3 条理由
- `chief_analyst`
- 负责最终裁决、核心分歧点和 final_action
- `risk_reviewer`
- 负责风险结论和执行提醒

### workflow 节点骨架

当前单票角色化链路已显式拆成以下节点：
- `SingleStockResearchInputs`
- `AnalystViewsBuild`
- `BullBearDebateBuild`
- `ChiefJudgementBuild`
- `StrategyFinalize`

这些节点目前由轻量 `debate_orchestrator` 串联，后续可以从中间节点继续扩展，而不需要推翻现有 schema。
