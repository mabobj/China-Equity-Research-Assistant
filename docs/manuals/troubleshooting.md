# 故障排查

这份文档按“先看什么、再怎么定位”的顺序写，尽量避免一上来就翻代码。

## 1. 先看三个地方

遇到问题时，优先检查：

1. PowerShell 启动窗口的报错
2. 后端日志 `logs/backend-debug.log`
3. `.env` 配置是否和当前机器一致

## 2. 后端启动失败

建议顺序：

1. 确认已经创建并激活 `.venv`
2. 确认已执行 `pip install -r backend\requirements.txt`
3. 确认 `APP_HOST` 和 `APP_PORT` 未被占用
4. 如启用 LLM，确认相关依赖和密钥可用

快速验证：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## 3. 前端启动失败

建议顺序：

1. 确认已执行 `npm install`
2. 确认 Node 版本满足要求
3. 先跑 `lint` 和 `type-check`

```powershell
Set-Location frontend
npm.cmd run lint
npm.cmd run type-check
```

如果前端能启动但页面请求失败，通常优先排查后端或代理，不是前端页面本身。

## 4. `.env` 最容易出错的项

重点检查：

- `TDX_API_BASE_URL`
- `ENABLE_MOOTDX`
- `MOOTDX_TDX_DIR`
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `LLM_PROVIDER`
- `ENABLE_LLM_DEBATE`

建议排查顺序：

1. 先把不需要的能力关掉
2. 先跑通最小链路
3. 再逐项打开 tdx-api、mootdx、LLM

## 5. provider 问题怎么判断

先看日志里具体是哪一类问题：

- provider 不可用
- capability 缺失
- stale / invalid
- fallback

当前项目已经尽量把这些状态结构化暴露出来，所以不要只看“有没有结果”，还要看：

- `provider_used`
- `fallback_applied`
- `fallback_reason`
- `warning_messages`
- `quality_status`

## 6. mootdx 问题怎么查

如果启用了：

```env
ENABLE_MOOTDX=true
MOOTDX_TDX_DIR=C:/new_tdx
```

但系统仍未使用 `mootdx`，优先检查：

1. 目录是否真实存在
2. 是否是正确的通达信数据目录
3. 本地数据是否足够新
4. 请求区间尾段是否完整

注意：

- `mootdx` 是本地高速历史源，不代表永远最新
- freshness 或完整性不达标时，系统会自动降级

## 7. 如何判断是“无数据”还是“降级”

重点看这些字段：

- `quality_status`
- `cleaning_warnings`
- `provider_used`
- `fallback_applied`
- `fallback_reason`
- `source_mode`
- `freshness_mode`

经验判断：

- `count=0` 且有 `fallback_reason` 或 warning，通常是 provider 问题或降级
- `count=0` 且无明显 warning，更可能是当前窗口确实没有数据

## 8. LLM 模式为什么会回退

你可以从三个地方判断：

1. 页面里的运行模式提示
2. API 返回中的：
   - `runtime_mode_requested`
   - `runtime_mode_effective`
3. 日志中的 fallback 说明

如果你传了 `use_llm=true`，但最终是规则版，通常是：

- API key 不可用
- 超时
- provider 或 schema 问题

## 9. workflow 一直不出结果怎么办

优先看：

1. 页面里的 `run_id`
2. `GET /workflows/runs/{run_id}`
3. 本地 run 记录和后端日志

重点检查：

- `status`
- `error_message`
- 每个 step 的摘要
- `failed_symbols`

## 10. 单票页或选股页出现模块级失败怎么办

先确认是不是“局部失败”而不是整页失败。

当前系统允许：

- 单个模块失败
- 主结果继续返回

所以你需要先看：

1. 失败模块名
2. 对应的 `module_status_summary`
3. 日志里是 provider 问题、数据质量问题，还是预测 / workflow / LLM 问题

## 11. pytest 启动卡住怎么办

在部分本机环境里，`pytest` 可能因为插件自动加载卡住。

建议先这样跑：

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest backend/tests/test_workspace_bundle_service.py -q
```

如果这样能正常跑，再继续执行更完整的测试命令。

## 12. 文档应该按什么顺序看

如果你不确定问题属于哪条主线，建议按下面顺序看文档：

1. [快速开始](quickstart.md)
2. [日常使用说明](daily-usage.md)
3. [数据源与边界](data-and-limitations.md)
4. [Data 清洗层说明](data-cleaning.md)
5. [系统架构](../architecture.md)
6. [当前阶段](../current_phase.md)
