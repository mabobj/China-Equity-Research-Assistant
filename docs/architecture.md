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

当前限制：
- 当前只保证沪深 SH / SZ 本地标准市场路径。
- `intraday_bars` 当前只支持 `1m` / `5m`。
- `timeline` 当前基于本地 `fzline/lc5` 数据提取最新交易日预览，不是完整盘中分析引擎。
- 若本地目录存在但对应数据文件缺失，会返回清晰业务错误。

## mootdx 接入策略

### 1. 启用方式

通过环境变量控制：
- `ENABLE_MOOTDX`
- `MOOTDX_TDX_DIR`

### 2. 当前验证方式

独立验证脚本：
- `backend/app/scripts/validate_mootdx_provider.py`
- `backend/app/scripts/run_mootdx_validation_matrix.py`

脚本职责：
- 输出 capability report
- 输出 health report
- 验证日线读取
- 验证分钟线读取
- 尝试分时线读取
- 失败时打印清晰错误原因

批量验证矩阵补充：
- 支持多 symbol、多频率批量验证
- 可选与 `akshare` / `baostock` 做最近 20 个交易日日线对比
- 输出结构化 JSON / CSV，便于实测验收与问题排查

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
- 基于 `TechnicalSnapshot + IntradaySnapshot` 生成 `TriggerSnapshot`
- 让 screener 开始依赖 factor snapshot / trigger 结构

当前边界：
- 不是完整横截面多因子系统
- 不是行业中性化框架
- 不是回测引擎
- 只是为下一阶段扩展预留稳定接口

## 盘中能力层

当前新增的最小盘中结构分为两层：
- `backend/app/services/data_service/intraday_service.py`
- `backend/app/services/factor_service/trigger_snapshot_service.py`

职责划分：
- `IntradayService`：基于分钟线构建 `IntradaySnapshot`
- `TriggerSnapshotService`：组合日线 `TechnicalSnapshot` 与 `IntradaySnapshot`，输出轻量 `TriggerSnapshot`

当前公开接口保持克制：
- `GET /stocks/{symbol}/intraday-bars`
- `GET /stocks/{symbol}/trigger-snapshot`

说明：
- `intraday-bars` 负责结构化分钟线返回
- `trigger-snapshot` 负责给出接近日线支撑、接近突破、拉伸过度等轻量触发判断
- 盘中层当前不实现复杂盘中策略、自动交易或图表分析

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

## 选股 v2 因子框架

本轮开始把 `factor_service` 从“预埋占位”升级为“最小可用因子框架”。

当前核心文件：
- `backend/app/services/factor_service/base.py`
- `backend/app/services/factor_service/preprocess.py`
- `backend/app/services/factor_service/factor_snapshot_service.py`
- `backend/app/services/factor_service/composite.py`
- `backend/app/services/factor_service/reason_builder.py`
- `backend/app/services/factor_service/factor_library/trend_factors.py`
- `backend/app/services/factor_service/factor_library/quality_factors.py`
- `backend/app/services/factor_service/factor_library/growth_factors.py`
- `backend/app/services/factor_service/factor_library/low_vol_factors.py`
- `backend/app/services/factor_service/factor_library/event_factors.py`

### 输入来源

本轮因子框架只复用现有输入，不扩外部数据面：
- `DailyBarResponse`
- `TechnicalSnapshot`
- `FinancialSummary`
- `AnnouncementListResponse`

### 输出结构

当前统一输出 `FactorSnapshot`，至少包含：
- `raw_factors`
- `normalized_factors`
- `factor_group_scores`
- `alpha_score`
- `trigger_score`
- `risk_score`

其中：
- `alpha_score` 表示横截面优先级
- `trigger_score` 表示当前是否接近“回踩/突破”型观察点
- `risk_score` 是风险分，数值越高表示风险越高

### 当前最小因子集合

当前已落地的因子组：
- `trend`
  - `return_20d`
  - `return_60d`
  - `distance_to_52w_high`
  - `relative_hs300_strength` 预留
  - `relative_industry_strength` 预留
- `quality`
  - `roe`
  - `net_margin`
  - `debt_ratio`
  - `eps`
  - `financial_data_completeness`
- `growth`
  - `revenue_yoy`
  - `net_profit_yoy`
  - `revenue_acceleration` 预留
  - `net_profit_acceleration` 预留
- `low_vol`
  - `volatility_20d`
  - `volatility_60d`
  - `atr_to_close`
  - `max_drawdown_60d`
- `event`
  - `announcement_count_30d`
  - `announcement_keyword_score`
  - `event_freshness_score`

### 推荐理由生成

`reason_builder.py` 的职责是把因子贡献收敛为结构化短理由，而不是生成自由文本长文。

当前输出：
- `top_positive_factors`
- `top_negative_factors`
- `short_reason`
- `risk_notes`

这些字段直接来自因子组信号，不依赖 LLM。

## Screener v2 兼容收敛

当前 `ScreenerPipeline` 已切换为以下结构：
- `universe constraints`
- `technical snapshot`
- `factor snapshot`
- `alpha / trigger / risk scoring`
- `list classification`

当前新版分桶：
- `READY_TO_BUY`
- `WATCH_PULLBACK`
- `WATCH_BREAKOUT`
- `RESEARCH_ONLY`
- `AVOID`

为了兼容现有前端与深筛链路，公开响应暂时同时保留：
- 旧字段：`buy_candidates`、`watch_candidates`、`avoid_candidates`
- 新字段：`ready_to_buy_candidates`、`watch_pullback_candidates`、`watch_breakout_candidates`、`research_only_candidates`

映射关系：
- `READY_TO_BUY` -> `BUY_CANDIDATE`
- `WATCH_PULLBACK` / `WATCH_BREAKOUT` / `RESEARCH_ONLY` -> `WATCHLIST`
- `AVOID` -> `AVOID`

这意味着：
- 旧前端和深筛流程可以继续工作
- 新的因子分数和理由字段已经能被上层消费
- 后续可以继续演进为真正的横截面多因子排序，而不必再次推翻 screener 结构

## 个股研判 v2 结构化地基

本轮没有删除原有 `research_service`，而是在其旁边新增 `review_service`，用于承载更清晰的多维研判框架，并为后续有限轮多 agent 裁决预埋角色边界。

核心文件：
- `backend/app/services/review_service/factor_profile_builder.py`
- `backend/app/services/review_service/technical_view_builder.py`
- `backend/app/services/review_service/fundamental_view_builder.py`
- `backend/app/services/review_service/event_view_builder.py`
- `backend/app/services/review_service/sentiment_view_builder.py`
- `backend/app/services/review_service/bull_bear_builder.py`
- `backend/app/services/review_service/chief_judgement_builder.py`
- `backend/app/services/review_service/stock_review_service.py`
- `backend/app/schemas/review.py`

### 输入复用

`StockReviewService` 不新增外部数据面，只复用现有能力：
- `get_stock_profile`
- `get_technical_snapshot`
- `get_trigger_snapshot`
- `get_stock_financial_summary`
- `get_stock_announcements`
- `get_factor_snapshot`
- `get_strategy_plan`

### 六块固定输出

`StockReviewReport` 当前固定包含：
- `factor_profile`
- `technical_view`
- `fundamental_view`
- `event_view`
- `sentiment_view`
- `bull_case / bear_case / key_disagreements / final_judgement`

其设计目标不是生成长文，而是把后续 agent 化之前的角色边界先固定下来。

### 角色边界

- `factor_profile`
- 更像因子分析员输出，负责总结强弱因子组与 `alpha / trigger / risk`
- `technical_view`
- 更像技术分析员输出，负责趋势、触发与关键位
- `fundamental_view`
- 更像基本面分析员输出，负责质量、成长、杠杆与财务完整度
- `event_view`
- 更像事件分析员输出，负责公告催化与风险扰动
- `sentiment_view`
- 是当前的轻量情绪占位层，先用已有强弱、量能、波动和位置数据构造
- `bull_case`
- 只提炼支持继续关注或买入的最强理由
- `bear_case`
- 只提炼反对交易或要求谨慎的最强理由
- `final_judgement`
- 作为首席裁决层，整合多空分歧与现有策略计划

### 与旧 research 接口的关系

- `GET /research/{symbol}`
- 保留，继续作为轻量研究接口
- `GET /stocks/{symbol}/review-report`
- 新增，作为多维结构化研判接口

这意味着：
- 旧前端和旧调用方不需要立刻迁移
- 新的研判结构已经可以单独消费
- 后续若接入多 agent，有了天然的角色输出边界，而不需要重写底层 schema
