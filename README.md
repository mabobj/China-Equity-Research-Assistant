# A-Share Research Assistant

面向中国大陆 A 股市场的研究与交易决策辅助系统。

当前项目重点是把数据接入、技术分析、结构化研究、结构化策略和规则选股链路先做稳。现阶段仍不包含自动实盘交易、券商下单集成、高频交易和盘中自动执行。

## 当前已完成能力

- 股票代码标准化，系统内部统一使用 canonical symbol，例如 `600519.SH`
- 股票基础信息、日线行情、基础股票池
- 公告列表与基础财务摘要
- 技术分析底层与结构化 technical snapshot
- 结构化单票研究报告
- 结构化交易策略计划
- 全市场规则初筛选股器
- 基于初筛结果的深筛聚合选股器

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

## 测试方式

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test_backend.ps1
```

该脚本会显式设置 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`，用于规避当前 Windows 环境下全局 pytest 插件干扰，保证测试稳定运行。

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

## 当前开发约束

- 所有外部数据源访问都放在 `backend/app/services/data_service/providers/`
- API 层只负责参数接收与结构化响应返回
- 复杂业务逻辑放在 service 层
- 关键输出优先结构化，避免把核心结果放进自由文本
- 测试不依赖实时外网，优先用 fake provider、stub service 和 mock 验证
