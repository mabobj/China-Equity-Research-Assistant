# 系统架构说明

## 文档目标

本文件描述当前版本 A-Share Research Assistant 的核心分层，以及本轮“架构收敛 + mootdx 接入验证”后的结构变化。

这份文档重点回答 4 个问题：
- 数据层现在如何分层
- provider 如何按 capability 管理
- factor_service 预埋到了哪里
- workflow 节点化未来将如何承接流程

## 系统定位

本系统面向中国大陆 A 股市场，当前阶段聚焦：
- 全市场选股
- 单票研究
- 结构化交易策略
- 交易记录与复盘预留

当前不包含：
- 自动实盘交易
- 券商下单集成
- 高频交易
- 复杂多 agent 运行时

## 总体分层

```text
外部数据源 / 本地数据目录
  -> Provider 层
  -> MarketDataService / FactorService / FeatureService
  -> Research / Strategy / Screener
  -> API 层
  -> 前端页面
```

主要职责：
- Provider 层：屏蔽外部数据源差异，只负责取数与原始字段映射
- Service 层：做标准化、缓存、本地落盘、评分、研究整合
- Schema 层：提供结构化输入输出
- API 层：只做参数接收和响应返回

## 数据层重构

### 1. 旧问题

旧版 `MarketDataProvider` 是一个过大的协议，默认要求 provider 同时具备：
- profile
- daily bars
- universe
- announcements
- financial summary

这会导致两个问题：
- 新 provider 接入成本高
- provider 经常出现空实现或无意义兜底

### 2. 新结构

本轮把数据层收敛为 capability-based provider 设计。

当前 capability：
- `profile`
- `daily_bars`
- `universe`
- `announcements`
- `financial_summary`
- `intraday_bars`
- `timeline`

关键文件：
- `backend/app/services/data_service/providers/base.py`
- `backend/app/services/data_service/provider_registry.py`
- `backend/app/services/data_service/market_data_service.py`

### 3. ProviderRegistry

`ProviderRegistry` 的职责：
- 注册 provider
- 输出 capability report
- 输出 health report
- 按 capability 选择 provider
- 只把可用 provider 暴露给 `MarketDataService`

这意味着：
- provider 不再需要一次性实现所有能力
- `MarketDataService` 可以继续保持统一入口
- 现有 API 不需要因为内部重构而整体改写

### 4. MarketDataService 的定位

`MarketDataService` 仍然是上层统一访问入口，但内部实现已经改为：
- 先标准化 symbol
- 再按 capability 从 registry 选择 provider
- 再做本地缓存 / DuckDB 存储 / 范围覆盖逻辑

这样它继续承担“统一访问门面”，但不再直接依赖“大而全 provider 协议”。

## 当前 Provider 分工

### AKShare

当前 capability：
- `profile`
- `daily_bars`
- `universe`
- `financial_summary`

适用场景：
- 基础行情
- 股票池
- 财务摘要

### BaoStock

当前 capability：
- `profile`
- `daily_bars`
- `universe`

适用场景：
- 行情补充
- 会话型批量请求

### CNINFO

当前 capability：
- `announcements`

适用场景：
- 公告列表

### mootdx

当前 capability：
- `daily_bars`
- `intraday_bars`
- `timeline`

定位：
- 作为本地通达信目录行情 provider
- 为未来分钟级分析和 workflow 提供本地数据输入

当前明确不支持：
- 财务
- 公告
- 股票池
- 在线 quotes 默认通道
- 默认复权
- 北交所专门支持
- 扩展市场 / 商品 / 期货

## mootdx 接入策略

### 1. 启用方式

通过环境变量控制：
- `ENABLE_MOOTDX`
- `MOOTDX_TDX_DIR`

### 2. 当前验证方式

独立验证脚本：
- `backend/app/scripts/validate_mootdx_provider.py`

脚本职责：
- 输出 capability report
- 输出 health report
- 验证日线读取
- 验证分钟线读取
- 尝试分时线读取
- 失败时打印清晰错误原因

### 3. 设计原则

`mootdx` 目前只作为可选 provider，不直接改变公开 API 行为，也不强制接管所有日线请求。

## factor_service 预埋结构

本轮不实现完整多因子引擎，但显式建立了 `factor_service`。

目录：
- `backend/app/services/factor_service/base.py`
- `backend/app/services/factor_service/snapshot.py`
- `backend/app/services/factor_service/registry.py`
- `backend/app/services/factor_service/preprocess.py`
- `backend/app/services/factor_service/composite.py`

当前能力：
- 从 `TechnicalSnapshot` 生成 `FactorSnapshot`
- 生成 `AlphaScore`
- 生成 `TriggerScore`
- 让 screener 开始依赖 factor snapshot / trigger 结构

当前边界：
- 不是完整横截面多因子系统
- 不是行业中性化框架
- 不是回测引擎
- 只是为下一阶段扩展预留稳定接口

## Screener 架构收敛

### 当前状态

当前 screener 仍保留原有行为兼容，但内部已经开始向两层收敛：
- `factor snapshot`
- `technical trigger`

当前 pipeline 结构：
- universe 过滤
- 日线数据过滤
- technical snapshot
- factor snapshot
- screener scoring

这样后续再加入：
- 横截面 alpha 排序
- 行业内标准化
- trigger engine

就不需要把所有逻辑继续堆进 `pipeline.py`。

## Workflow 预埋结构

本轮没有引入 LangGraph 或复杂运行时框架，但已经显式定义 workflow 节点 schema。

当前节点类型：
- `MarketDataSync`
- `FactorSnapshotBuild`
- `ScreenerRun`
- `CandidateDeepReview`
- `SingleStockResearch`
- `SingleStockStrategy`

关键文件：
- `backend/app/schemas/workflow.py`
- `backend/app/services/workflow_service/orchestrator.py`

当前定位：
- 先把 workflow 节点和结果结构显式化
- 为未来“从中间节点启动流程”做准备
- 暂时只提供轻量 orchestration 占位

## 当前边界

本轮没有做：
- 自动复盘
- 持仓管理
- 多 agent 运行时
- LLM 集成
- 新前端页面
- 新图表
- 新通知
- 完整多因子回测

## 设计原则

当前阶段的优先顺序仍然是：
1. 数据结构清晰
2. provider 职责明确
3. 输出结构化
4. 可测试
5. 可扩展

不是：
- 一次性堆很多新功能
- 为了“智能感”牺牲可维护性
- 让数据层继续膨胀成所有逻辑的汇集点

