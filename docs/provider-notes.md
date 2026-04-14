# Provider 使用说明

本文档回答三件事：

1. 当前项目各数据域的 provider 优先级是什么
2. 每个 provider 在架构中的职责是什么
3. 从长期因子主线看，哪些 provider 只是补充，哪些 provider 承担真相源或主链角色

## 1. 当前 provider 优先级

### daily_bars

- `tdx_api -> mootdx -> akshare -> baostock`

说明：

- `tdx_api` 是当前日线主链。
- `mootdx` 是本地高速历史源，但必须通过新鲜度和尾段完整性检查。
- `akshare` 与 `baostock` 只承担后续 fallback。

### universe

- `tdx_api -> akshare -> baostock`

### profile

- `tdx_api -> akshare -> baostock -> cninfo`

### announcements

- `cninfo -> akshare`

### financial_summary

- `local_financial_store -> tushare -> baostock -> akshare`

说明：

- `local_financial_store` 是本地结构化财务快照优先层。
- `tushare` 是可选启用的结构化主源。
- `baostock` 是免费结构化 fallback。
- `akshare` 已降级为最后级补充源，不再作为默认财务主源。

### financial_reports_index

- `cninfo`

说明：

- 该能力用于“官方披露原文索引”。
- 当前只保存报告索引、报告期、报告类型、发布时间和下载链接。
- 本轮不做 PDF/XBRL 正文解析。

## 2. 各 provider 的职责

### tdx_api

定位：

- 本地 HTTP 主数据源
- 负责股票池、搜索、日线、部分行情主链

### mootdx

定位：

- 本地高速历史源
- 适合离线、批量、历史回看场景

约束：

- 不能绕过 freshness / validity 检查直接当作永远可信主源

### tushare

定位：

- 可选启用的结构化财务主源
- 主要服务财务摘要统一口径

约束：

- 需要显式配置 `TUSHARE_ENABLED=true`
- 需要 `TUSHARE_TOKEN`
- 不可用时不能阻塞整条财务链

### baostock

定位：

- 免费结构化 fallback
- 承担历史补洞和稳定兜底

### akshare

定位：

- 结构化补充源
- 继续服务部分研究型或补洞型场景

约束：

- 不再承担默认财务主源角色
- 财务数据必须先过统一 mapping / normalize / quality

### cninfo

定位：

- 正式披露信息真相源
- 当前承担公告索引与财务定期报告索引能力

约束：

- 本轮只做索引层，不做正文解析层

## 3. 当前制度化规则

当前代码中已经集中收口的规则包括：

- symbol normalize 与 provider symbol convert 集中管理
- 单位标准化集中管理
- capability 级 provider 优先级集中到 policy 层
- `provider_used / fallback_applied / fallback_reason` 统一暴露
- 允许 stale fallback 的数据域和要求本地持久化的数据域，已经进入 capability policy

## 4. 财务链的特别说明

财务数据本轮明确分成三层：

1. 真相源层
   - `cninfo` 的定期报告索引
2. 结构化摘要层
   - `local_financial_store`
   - `tushare`
   - `baostock`
   - `akshare`
3. 下游消费层
   - `research / strategy / screener / factor system`

这意味着：

- 官方披露原文索引是校准源，不是当前直接返回 `financial-summary` 的正文解析源
- 统一财务字段只能从清洗后的结构化摘要进入下游
- 不允许把 provider 原始字段直接透传到 API 或研究链

## 5. 长期方向下的边界

当前最重要的不是继续无边界扩 provider，而是：

1. 保持 provider 职责清晰
2. 保持 capability policy 集中
3. 继续增强本地结构化快照的可追溯性
4. 为后续因子发现、验证、组合与监控系统提供稳定底座
