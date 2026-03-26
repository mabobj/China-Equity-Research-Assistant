# 故障排查

这份文档按“先看什么、再怎么定位”的顺序写，尽量避免你一上来就翻代码。

## 1. 启动失败时先看哪里

优先检查这三处：

1. PowerShell 启动窗口里的报错
2. 后端日志 `logs/backend-debug.log`
3. `.env` 是否和当前机器一致

## 2. 后端启动失败

常见现象：

- `run_backend.ps1` 直接退出
- `uvicorn` 无法启动
- 页面提示无法连接后端

建议按顺序检查：

1. 是否已经创建并激活 `.venv`
2. 是否执行过 `pip install -r backend\requirements.txt`
3. `APP_HOST` 和 `APP_PORT` 是否被其他进程占用
4. `ENABLE_LLM_DEBATE=true` 时，是否真的安装了 `openai`

快速验证：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

如果仍失败，优先看日志，而不是直接改业务代码。

## 3. 前端启动失败

常见原因：

- 没执行 `npm install`
- Node 版本过旧
- TypeScript 或 lint 报错

建议命令：

```powershell
Set-Location frontend
npm install
npm.cmd run lint
npm.cmd run type-check
```

如果前端能启动但页面提示请求失败，往往不是前端本身的问题，而是后端或代理配置问题。

## 4. `.env` 配置问题怎么查

最容易出错的是下面这些变量：

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `LLM_PROVIDER`
- `ENABLE_LLM_DEBATE`
- `ENABLE_MOOTDX`
- `MOOTDX_TDX_DIR`

排查思路：

1. 先把不需要的能力关掉
2. 先保证最小链路能跑
3. 再逐个打开 LLM 或 mootdx

例如，如果你只是验证单票链路：

```env
ENABLE_LLM_DEBATE=false
ENABLE_MOOTDX=false
```

先这样跑通，之后再逐步加配置。

## 5. provider 不可用如何排查

常见现象：

- 单票页某个模块加载失败
- 初筛或深筛结果为空
- 后端日志里出现 provider 不可用或 capability 缺失

排查步骤：

1. 看后端日志里具体是哪一个 provider 失败
2. 看失败的是：
   - 网络类问题
   - 认证类问题
   - 本地目录类问题
   - capability 不支持
3. 确认系统是否已经优雅回退

注意：

- provider 失败不一定代表系统整体不可用
- 当前架构允许 provider 失效后部分模块继续工作

## 6. mootdx 本地目录问题怎么查

如果开启：

```env
ENABLE_MOOTDX=true
MOOTDX_TDX_DIR=C:/new_tdx
```

但仍无法使用，优先检查：

1. 路径是否真实存在
2. 是否是通达信实际数据目录
3. 当前目录权限是否允许进程读取
4. 本机数据是否完整

建议做法：

- 如果你不确定目录是否正确，先把 `ENABLE_MOOTDX=false`
- 先验证其他 provider 能否跑通
- 再单独回头排 mootdx

## 7. LLM debate 回退机制怎么判断

你可以从三个位置判断是否已经回退到规则版。

### A. 前端页面

单票页 `Debate Review` 模块里会显示：

- `运行模式`
  - `LLM`
  - `规则版`

### B. API 返回字段

看 `debate-review` 返回里的：

- `runtime_mode`

### C. 后端日志

常见日志关键词：

- `debate.runtime.select`
- `llm.role.start`
- `llm.role.done`
- `LLM debate 执行失败，自动回退规则版`

如果你明明传了 `use_llm=true`，但最终返回 `rule_based`，通常说明：

- API key 不可用
- provider 不支持当前请求形式
- 请求超时
- schema 校验失败

## 8. workflow 运行失败怎么查

优先看下面三个地方：

1. 页面上的 `run_id`
2. `GET /workflows/runs/{run_id}`
3. 本地 run record 文件

运行记录文件位置：

```text
data/workflow_runs/{run_id}.json
```

排查顺序建议：

1. 先看 `status`
2. 再看 `error_message`
3. 再看每个 step 的 `output_summary` 和 `error_message`

如果是深筛 workflow，还要看是否只是个别 symbol 失败，而不是整个 workflow 失败。

## 9. 页面只显示“部分模块加载失败”怎么办

先不要急着怀疑整个系统坏了。

这通常意味着：

- 某个 API 正常
- 某个 API 失败
- 前端仍把成功部分展示出来了

推荐排查：

1. 看页面上失败的是哪个模块
2. 去 Swagger 或浏览器直接请求对应接口
3. 再看后端日志

## 10. 火山方舟超时问题

如果你使用火山方舟 coding/plan 模型，当前建议：

```env
OPENAI_BASE_URL=https://ark.cn-beijing.volces.com/api/coding/v3
LLM_PROVIDER=auto
ENABLE_LLM_DEBATE=true
LLM_DEBATE_TIMEOUT_SECONDS=60
```

原因：

- 深度思考模型响应可能明显长于普通接口
- 超时过短时，会直接触发 LLM 回退

如果仍偶发超时，可以先把 `LLM_DEBATE_TIMEOUT_SECONDS` 提到 `90` 再观察。

## 11. 什么时候应该直接看源码或架构文档

如果你遇到的是下面这些问题，直接看文档通常更快：

- 不确定 workflow 和 review / debate / strategy 的关系
- 不知道该从哪个页面入口开始用
- 不知道某个能力是不是已经正式上线

建议顺序：

1. [快速开始](quickstart.md)
2. [日常使用说明](daily-usage.md)
3. [数据源与边界说明](data-and-limitations.md)
4. [系统架构](../architecture.md)
5. [稳定性审计 v1](../audits/stability-review-v1.md)
