# 快速开始

这份文档面向第一次在本地跑通项目的人。

如果你只想做一次最小验证，推荐目标是：启动后端和前端，然后在浏览器里完成一次 `600519.SH` 的单票分析与 workflow 执行。

## 1. 环境准备

建议环境：

- Windows PowerShell
- Python 3.11+
- Node.js 20+
- npm

项目根目录假定为：

```text
D:\dev\project\codex\China-Equity-Research-Assistant
```

## 2. 准备 `.env`

先复制环境变量模板：

```powershell
Copy-Item .env.example .env
```

### 最小可运行配置

如果你暂时不打算启用 LLM，也不打算接入 mootdx，本地最小配置通常只需要保留默认值。

重点确认：

```env
APP_HOST=127.0.0.1
APP_PORT=8000
ENABLE_LLM_DEBATE=false
ENABLE_MOOTDX=false
```

### 如需启用 LLM debate

至少需要：

```env
OPENAI_API_KEY=your_api_key
OPENAI_MODEL=gpt-5.4
OPENAI_BASE_URL=https://api.openai.com/v1
LLM_PROVIDER=auto
ENABLE_LLM_DEBATE=true
LLM_DEBATE_TIMEOUT_SECONDS=20
```

如果你接的是火山方舟 coding/plan 套餐，建议：

```env
OPENAI_BASE_URL=https://ark.cn-beijing.volces.com/api/coding/v3
LLM_PROVIDER=auto
ENABLE_LLM_DEBATE=true
LLM_DEBATE_TIMEOUT_SECONDS=60
```

### 如需启用 mootdx

```env
ENABLE_MOOTDX=true
MOOTDX_TDX_DIR=C:/new_tdx
```

只有在本机确实存在通达信目录时才建议开启。

## 3. 安装后端依赖

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
```

## 4. 安装前端依赖

```powershell
Set-Location frontend
npm install
Set-Location ..
```

## 5. 启动后端

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_backend.ps1
```

启动成功后，先检查：

- 健康检查：[http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- Swagger 文档：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

后端日志默认写到：

```text
logs/backend-debug.log
```

## 6. 启动前端

新开一个 PowerShell 窗口，执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_frontend.ps1
```

前端默认地址：

- [http://127.0.0.1:3000](http://127.0.0.1:3000)

## 7. 运行测试

### 后端测试

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test_backend.ps1
```

### 前端校验

```powershell
Set-Location frontend
npm.cmd run lint
npm.cmd run type-check
Set-Location ..
```

## 8. 最小验证：以 `600519.SH` 为例

推荐按下面顺序做一次最小验证。

### A. 打开首页

访问：

- [http://127.0.0.1:3000](http://127.0.0.1:3000)

首页应该能看到：

- 系统能力说明
- 股票代码输入框
- 单票分析、选股、workflow 的入口

### B. 进入单票工作台

在首页输入：

```text
600519.SH
```

进入单票页后，至少应能看到：

- 股票基础信息
- Factor Snapshot 摘要
- Review Report v2
- Debate Review
- Strategy Plan
- Trigger Snapshot

### C. 运行单票 workflow

在单票页找到 `单票 Workflow` 区块，点击：

- `运行 single_stock_full_review`

正常情况下你会看到：

- `run_id`
- 步骤摘要
- 最终输出摘要

### D. 运行选股

打开：

- [http://127.0.0.1:3000/screener](http://127.0.0.1:3000/screener)

依次操作：

1. 可选：执行一次数据补全
2. 运行规则初筛
3. 运行深筛
4. 运行 `deep_candidate_review` workflow

## 9. 如果最小验证失败

优先看这几个位置：

1. 后端日志 `logs/backend-debug.log`
2. 浏览器页面上的错误块
3. [故障排查文档](troubleshooting.md)

如果你是 LLM 或 provider 问题，先不要盲目改代码，先确认 `.env` 和本地数据目录配置是否正确。
