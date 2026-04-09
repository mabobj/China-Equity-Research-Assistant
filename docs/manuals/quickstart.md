# 快速开始

这份文档面向第一次在本地跑通项目的人。

如果你只想做一次最小验证，建议目标是：

1. 启动后端和前端
2. 打开单票工作台
3. 用 `600519.SH` 跑通一次单票链路
4. 再到选股工作台看一次 workflow 结果

## 1. 你需要知道的三个入口

- 单票工作台：`/stocks/[symbol]`
- 选股工作台：`/screener`
- 交易与复盘：`/trades`、`/reviews`

当前系统的长期方向是“因子发现、验证、组合与监控系统”，但你今天本地使用的入口，仍然是上面这几个工作台页面。

## 2. 环境准备

建议环境：

- Windows PowerShell
- Python 3.11+
- Node.js 20+
- npm

项目根目录示例：

```text
D:\dev\project\codex\China-Equity-Research-Assistant
```

## 3. 准备 `.env`

先复制环境变量模板：

```powershell
Copy-Item .env.example .env
```

### 最小可运行配置

如果你暂时不启用 LLM，也不接本地 `mootdx`，一般保留下面这类配置即可：

```env
APP_HOST=127.0.0.1
APP_PORT=8000
ENABLE_LLM_DEBATE=false
ENABLE_MOOTDX=false
```

### tdx-api 配置

当前数据源主优先级已经是：

`tdx-api > mootdx > AKShare > BaoStock`

如果你要启用本地 `tdx-api`，确认 `.env` 中有：

```env
TDX_API_BASE_URL=http://192.168.1.105:8080/
```

后续如果本地地址变化，只需要改这个配置项。

### 如需启用 LLM

```env
OPENAI_API_KEY=your_api_key
OPENAI_MODEL=gpt-5.4
OPENAI_BASE_URL=https://api.openai.com/v1
LLM_PROVIDER=auto
ENABLE_LLM_DEBATE=true
LLM_DEBATE_TIMEOUT_SECONDS=60
```

### 如需启用 mootdx

```env
ENABLE_MOOTDX=true
MOOTDX_TDX_DIR=C:/new_tdx
```

## 4. 安装后端依赖

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
```

## 5. 安装前端依赖

```powershell
Set-Location frontend
npm install
Set-Location ..
```

## 6. 启动后端

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_backend.ps1
```

启动后先检查：

- 健康检查：[http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- Swagger：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## 7. 启动前端

新开一个 PowerShell 窗口，执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_frontend.ps1
```

前端地址：

- [http://127.0.0.1:3000](http://127.0.0.1:3000)

## 8. 运行测试

### 后端

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest backend/tests/test_stocks_api.py backend/tests/test_workflow_api.py backend/tests/test_trade_review_api.py -q
```

### 前端

```powershell
Set-Location frontend
npm.cmd run lint
npm.cmd run type-check
npm.cmd run test:smoke
Set-Location ..
```

## 9. 最小验证：以 `600519.SH` 为例

### A. 打开首页

访问：

- [http://127.0.0.1:3000](http://127.0.0.1:3000)

### B. 进入单票工作台

输入：

```text
600519.SH
```

进入后，优先确认这些区域能正常显示：

- 决策简报
- 证据摘要
- 行动建议
- 详细模块

### C. 运行一次单票链路

在单票页确认：

- `workspace-bundle` 正常返回
- `review / debate / strategy / decision brief` 可见
- `predictive_snapshot` 若已命中数据，也能显示

### D. 去选股工作台

打开：

- [http://127.0.0.1:3000/screener](http://127.0.0.1:3000/screener)

只填一个最小参数：

- 本批次计算股票数量 `batch_size`

运行一次初筛 workflow，确认：

- 能拿到 `run_id`
- 页面能轮询状态
- 批次结果能展示

## 10. 如果失败，先看哪里

优先看：

1. 后端日志 `logs/backend-debug.log`
2. 浏览器页面错误提示
3. [故障排查](troubleshooting.md)

## 11. 文档阅读顺序

如果你已经跑通系统，建议下一步阅读：

1. [日常使用说明](daily-usage.md)
2. [数据源与边界](data-and-limitations.md)
3. [Data 清洗层说明](data-cleaning.md)
4. [系统架构](../architecture.md)
