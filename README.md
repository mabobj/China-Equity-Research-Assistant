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
- `GET /stocks/{symbol}/announcements`
- `GET /stocks/{symbol}/financial-summary`
- `GET /stocks/{symbol}/technical`

说明：
- 当前公开 API 仍保持兼容，继续提供 profile / daily-bars / universe / announcements / financial-summary。
- 数据层内部已重构为 capability-based provider 设计，provider 不再要求一次实现全部能力。
- 分钟线与分时线能力目前作为内部 service / 验证脚本能力预埋，暂未暴露新的公开 API。

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
- 本地通达信目录读取分钟线
- 本地分时线读取（timeline）
- provider capability / health report

当前明确不支持：
- 财务数据
- 公告
- 股票池
- 在线 quotes 默认通路
- 复权默认支持
- 北交所专门支持
- 扩展市场 / 商品 / 期货支持

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

## 当前开发约束

- 所有外部数据源访问都放在 `backend/app/services/data_service/providers/`
- API 层只负责参数接收与结构化响应返回
- 复杂业务逻辑放在 service 层
- 关键输出优先结构化，避免把核心结果放进自由文本
- 测试不依赖实时外网，优先用 fake provider、stub service 和 mock 验证
