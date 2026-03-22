# A-Share Research Assistant

面向中国大陆 A 股市场的研究与交易决策辅助系统。

当前仓库仍处于 Phase 0，只完成项目骨架、最小前后端空壳、配置脚手架和基础测试，不包含任何数据接入、研究分析或交易业务逻辑。

## 当前范围

- 全市场选股骨架
- 单票研究骨架
- 交易策略输出骨架
- 交易记录骨架
- 复盘记录骨架

当前阶段明确不包含：

- 自动实盘交易
- 券商下单集成
- 高频交易
- 盘中自动执行

## 技术栈

- Backend: Python, FastAPI, Pydantic, pytest
- Frontend: Next.js, TypeScript, Tailwind CSS
- Storage planning: SQLite, DuckDB, Parquet

## 目录结构

```text
backend/   FastAPI 后端骨架
frontend/  Next.js 前端骨架
docs/      架构与路线图
scripts/   本地开发与测试脚本
```

## 本地启动方式

### 1. 准备环境变量

在仓库根目录创建 `.env`：

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

默认会启动 FastAPI 开发服务，并提供健康检查接口：

```text
GET /health
```

### 5. 启动前端

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_frontend.ps1
```

默认启动 Next.js 开发服务，当前仅包含以下 Phase 0 占位页面：

- `/`
- `/screener`
- `/stocks/[symbol]`
- `/trades`
- `/reviews`

## 测试方式

后端测试脚本：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test_backend.ps1
```

该脚本会在当前 Windows 环境下显式设置 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`，避免全局 pytest 插件导致测试卡住。

## 配置说明

后端配置统一在 `backend/app/core/config.py` 中读取，使用方式如下：

```python
from app.core.config import get_settings

settings = get_settings()
```

当前 Phase 0 只提供最小配置能力，包括：

- 应用名称、版本、环境
- 调试开关
- API 前缀
- 本地开发主机与端口
- SQLite / DuckDB / cache / data 路径
- 预留的 OpenAI 与数据源开关字段

## 当前状态

本仓库当前目标是先把骨架打稳，再进入后续阶段：

1. Phase 0: 项目初始化与最小可运行骨架
2. Phase 1: 数据接入
3. Phase 2: 技术分析底层
4. Phase 3: 单票研究
5. Phase 4: 选股器
6. Phase 5: 交易记录与复盘
7. Phase 6: 轻量前端完善
8. Phase 7: 策略优化与学习增强
