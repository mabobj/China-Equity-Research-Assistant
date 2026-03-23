# A-Share Research Assistant

面向中国大陆 A 股市场的研究与交易决策辅助系统。

当前仓库处于早期建设阶段。已完成项目骨架、最小前后端空壳，以及 Phase 1-1 的第一段数据层 MVP：

- 股票代码标准化
- 单票基础信息
- 单票日线行情
- 基础股票池

并已完成 Phase 2-A 的第一段技术分析底层 MVP：

- 常用技术指标计算
- 最新交易日 technical snapshot
- 最小技术分析 API

当前仍然不包含：

- 公告抓取
- 新闻抓取
- AI 研究总结
- 策略生成
- 定时任务
- 自动实盘交易

## 技术栈

- Backend: Python, FastAPI, Pydantic, pytest
- Frontend: Next.js, TypeScript, Tailwind CSS
- Storage planning: SQLite, DuckDB, Parquet

## 目录结构

```text
backend/   FastAPI 后端
frontend/  Next.js 前端
docs/      架构与路线图
scripts/   本地开发与测试脚本
```

## 本地启动方式

### 1. 准备环境变量

```powershell
Copy-Item .env.example .env
```

### 2. 准备后端依赖

建议使用 Python 3.11+ 虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
```

### 3. 准备前端依赖

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

## 测试方式

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test_backend.ps1
```

该脚本会显式设置 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`，避免当前 Windows 环境下全局 pytest 插件干扰测试执行。

## 当前可用 API

### 健康检查

- `GET /health`

### A 股基础数据接口

- `GET /stocks/universe`
- `GET /stocks/{symbol}/profile`
- `GET /stocks/{symbol}/daily-bars`
- `GET /stocks/{symbol}/technical`

`/stocks/{symbol}/daily-bars` 支持可选查询参数：

- `start_date=YYYY-MM-DD`
- `end_date=YYYY-MM-DD`

`/stocks/{symbol}/technical` 同样支持可选查询参数：

- `start_date=YYYY-MM-DD`
- `end_date=YYYY-MM-DD`

返回的是结构化技术分析快照，包含：

- 最新收盘价与成交量
- MA / EMA
- MACD
- RSI14
- ATR14
- 布林带
- 成交量均线
- 趋势状态与趋势分数
- 波动状态
- 第一版支撑位与压力位

## 股票代码规范

系统内部统一使用 canonical symbol：

- `600519.SH`
- `000001.SZ`
- `300750.SZ`

API 层当前支持以下输入格式：

- `600519`
- `600519.SH`
- `sh600519`
- `000001`
- `000001.SZ`
- `sz000001`

代码标准化与 provider symbol convert 统一集中在：

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

## 当前开发说明

当前数据层实现遵循以下原则：

- 所有外部数据源访问都放在 `backend/app/services/data_service/providers/`
- service 层统一完成 symbol normalize
- provider 层的 symbol 转换集中实现，不在多个文件硬编码
- API 层只负责参数接收和结构化响应返回
- 测试不依赖实时外部网络，主要通过 fake provider 和 stub service 验证

当前技术分析底层实现遵循以下原则：

- 指标计算集中在 `backend/app/services/feature_service/`
- 不依赖 TA-Lib，只使用 pandas / numpy
- 技术快照只面向最新交易日输出
- 趋势、波动、支撑压力逻辑保持朴素、可解释
- 本轮不包含 AI 研究、选股、策略生成或复杂形态识别
