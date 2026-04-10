# 项目任务书（v2.2，数据底座与点时特征版）

## 1. 文档定位

本文档定义项目进入长期主线后的下一阶段执行包。

`v2.1` 已经完成了产品工作台壳层、预测最小接入与交易复盘最小闭环；`v2.2` 的目标不再是继续堆页面或扩散业务功能，而是把数据底座继续收口到足以支撑：

- 点时特征
- 标签构建
- 回测与评估
- 因子发现、验证、组合与监控系统

## 2. v2.2 总目标

`v2.2` 只做一件大事：

**把当前“可用的数据底座”升级成“可重建、可验证、可用于长期因子主线的数据底座”。**

成功标准不是页面更花，而是：

1. 任意 `symbol + as_of_date` 的关键输入可以重建
2. 关键数据域具备统一口径、统一质量状态、统一血缘信息
3. 后续点时特征和标签不再依赖临时拼接数据
4. provider 使用边界、fallback 边界、数据产品边界清楚

## 3. 本阶段边界

### 3.1 本阶段明确要做

- 点时一致性收口
- 关键数据域补齐规划与最小落地
- 复权与公司行为口径收口
- 数据血缘与版本追踪增强
- provider 能力矩阵制度化
- 为点时特征与标签构建打地基

### 3.2 本阶段明确不做

- 自动下单
- 券商接入
- 新一轮大前端重构
- 新的聊天式产品入口
- 无边界扩 provider
- 完整组合引擎
- 复杂调度 / 队列 / DAG 平台

## 4. v2.2 的五个任务包

## 包 1：点时一致性收口包

### 目标

把当前日级数据产品进一步收口为“可按 `as_of_date` 重建”的点时输入。

### 当前进度

- 已完成第一阶段：
  - 抽出统一的日级分析日策略与标签/回测安全分析日策略；
  - `daily data products / dataset_service / label_service / backtest_service / prediction_service / market_data_service` 已接入同一套默认分析日解析逻辑；
  - 已补对应测试，确保默认分析日与安全分析日不再在多处各自计算。
- 已完成第二阶段：
  - `workspace-bundle` 已支持显式 `as_of_date`，并把同一日期透传到日级数据产品读取、同日快照复用与预测快照读取链路；
  - `stocks/review-report`、`stocks/debate-review`、`strategy/{symbol}` 在显式 `as_of_date` 下改为“仅读取已有日级快照，不做历史重算”，避免把历史请求误算成当前数据；
  - `single_stock workflow` 与 `deep_review workflow` 已补齐 `as_of_date` 字段，并对不支持的历史重算路径返回受控失败，而不是静默混入当前结果；
  - 已补对应服务测试、workflow 测试与 API 契约测试，确保显式 `as_of_date` 的读取口径一致。

### 关键任务

- 明确日级产物的点时边界：
  - 哪些字段属于当日可见
  - 哪些字段属于后验补全
- 统一 `as_of_date / freshness_mode / source_mode`
- 明确 `force_refresh` 与本地快照复用的边界
- 为后续特征与标签生成准备统一的按日读取接口

### 涉及模块

- `data_products`
- `market_data_service`
- `freshness`
- 相关 schema

### 验收标准

- 任意核心日级产物都能说明自己对应的 `as_of_date`
- 上游 service 读取同一日期输入时不再出现口径漂移
- 为后续特征构建提供统一数据读取方式

## 包 2：关键数据域补齐包

### 目标

在不无边界扩源的前提下，补齐长期因子主线最需要的基础数据域。

### 当前进度

- 已完成第一阶段：
  - 新增静态且可复用的标准基准目录，当前内置 `上证指数 / 深证成指 / 沪深300 / 中证500 / 中证1000 / 创业板指 / 科创50`；
  - 新增 `industry_classification_daily`，把单票 `行业 + 板块 + 主基准映射` 固化为可按日读取的标准快照；
  - 新增 `market_breadth_daily`，基于现有 `universe + daily_bars(raw)` 计算 `上涨/下跌/平盘家数、MA20/MA60 之上比例、20 日新高/新低、breadth_score`；
  - 新增 `risk_proxy_daily`，在市场广度基础上生成最小可用的基础风险代理快照；
  - 新增只读接口：
    - `GET /market/benchmarks`
    - `GET /market/breadth`
    - `GET /market/risk-proxies`
    - `GET /stocks/{symbol}/classification`
  - 已补 service 与 API 测试，确认上述数据域已经可读、可算、可缓存、可回归。
- 已完成第二阶段：
  - 新增 `benchmark_bars_daily`，把静态基准目录推进为“可按日读取的基准行情链路”；
  - `MarketContextService` 新增基准日线读取入口，并增加只读接口：`GET /market/benchmarks/{benchmark_symbol}/daily-bars`；
  - `risk_proxy_daily` 已从“仅由市场广度派生”升级为“市场广度 + 主基准收益/趋势”的保守组合代理；
  - 风险代理响应现已补充 `primary_benchmark_symbol / benchmark_return_1d / benchmark_return_20d / benchmark_trend_state` 等字段；
  - 已补 service / API 回归测试，确保基准日线和增强风险代理不会破坏既有市场上下文接口。

### 优先数据域

- 指数 / 基准
- 行业 / 板块分类
- 市场广度
- 基础风险代理变量

### 原则

- 不追求一步到位
- 先做最少但最关键的数据域
- 必须走 provider -> cleaning -> contract -> data product 链路

### 验收标准

- 新数据域有明确 schema
- 有明确 provider 来源与 fallback 边界
- 能按日落为本地可复用产物

## 包 3：复权与公司行为口径收口包

### 目标

把长期回测和因子验证绕不过去的价格口径问题集中化处理。

### 当前进度

- 已完成第一阶段：
  - `DailyBar / DailyBarResponse` 已显式补齐 `adjustment_mode` 与公司行为元数据承载位，不再把“默认原始价”只放在隐式约定里；
  - `normalize.py` 已集中承载复权口径标准化、交易状态标准化与公司行为标记标准化；
  - `daily_bars` 本地存储已增量补齐 `adjustment_mode / trading_status / corporate_action_flags_json` 列，并保持旧库自动兼容；
  - `market_data_service` 已在日线响应层输出统一的 `adjustment_mode / corporate_action_mode / corporate_action_warnings`；
  - 已补 store / service / API 契约测试，确保价格口径与公司行为元数据不丢失。
- 已完成第二阶段：
  - `/stocks/{symbol}/daily-bars` 已支持显式 `adjustment_mode=raw/qfq/hfq` 请求参数，默认仍保持 `raw` 兼容；
  - `market_data_service.get_daily_bars()` 已把复权口径贯通到 route / service / provider / local store，不再只停留在响应元数据层；
  - `daily_bars` 本地存储已升级为按 `symbol + trade_date + adjustment_mode` 区分保存，不同复权模式不会互相覆盖；
  - `tdx-api / mootdx` 当前仍只稳定支持 `raw` 日线，请求 `qfq/hfq` 时会受控降级到后续 provider；
  - 已补 provider 透传、store 分口径回读与 API 契约测试，确保复权模式可请求、可存储、可稳定回读。

### 关键任务

- 明确原始价 / 前复权 / 后复权口径
- 明确停牌、ST、退市、分红送转等事件在数据层的表达方式
- 不允许这些规则散落在 feature、research、strategy、screener 多处

### 涉及模块

- `normalize.py`
- `cleaning`
- `data_products`
- 相关 schema 与 metadata

### 验收标准

- 价格口径统一且可追溯
- 同一回测或特征链路不再混用复权口径
- 公司行为影响可被后续特征与回测读取

## 包 4：数据血缘与版本追踪包

### 目标

让数据集、日级产物、特征和标签都具备可追溯性。

### 关键任务

- 为关键数据产品补齐：
  - provider 来源
  - fallback 记录
  - 版本号
  - 生成时间
  - 依赖关系
- 为特征与标签定义：
  - `feature_version`
  - `label_version`
  - 上游依赖快照

### 验收标准

- 能回答“这条特征 / 标签 / 预测结果来自什么数据版本”
- 回测和评估能引用明确的版本信息

## 包 5：provider 能力矩阵与健康度包

### 目标

把当前 provider 策略从“写在代码里的经验规则”升级为“可解释的制度化规则”。

### 当前进度

- 已完成第一阶段：
  - capability 级 provider 优先顺序已从 `market_data_service` 的散落常量收拢到集中策略模块；
  - 已明确各数据域的 `preferred_providers / allow_stale_fallback / require_local_persistence`；
  - `ProviderCapabilityReport` 与 `ProviderHealthReport` 已能表达主用数据域、fallback 数据域、需本地落盘数据域与基础健康状态；
  - `market_data_service` 已改为通过集中策略解析 provider 顺序，并在 `daily_bars` 远端失败时按制度化规则决定是否允许退回本地快照；
  - 已补对应单元测试，确保矩阵规则可解释、可测试、可维护。
- 已完成第二阶段：
  - 新增 `CapabilityHealthReport`，可以从 capability 视角查看 `preferred/configured/available/selected provider`、stale fallback 边界与本地持久化要求；
  - `market_data_service` 已提供统一的 capability 健康判定逻辑，不再让调用方自行拼装“主用 provider 是否可用、是否已降级、是否缺本地持久化”的判断；
  - 后端已新增只读诊断接口：`GET /providers/capabilities`、`GET /providers/health`、`GET /providers/health/{capability}`；
  - 已补对应服务测试与 API 契约测试，确保 provider 诊断输出可读、可测、可回归。

### 关键任务

- 定义每个 provider 覆盖的数据域
- 定义每个数据域的优先级与 fallback 边界
- 定义哪些数据域允许 stale fallback，哪些不允许
- 定义哪些数据域必须本地落盘
- 建立最小健康度检查与能力说明

### 验收标准

- provider 选择规则可说明、可测试、可维护
- 文档、配置、service 口径一致

## 5. 推荐实施顺序

v2.2 推荐严格按下面顺序推进：

1. 包 1：点时一致性收口
2. 包 5：provider 能力矩阵与健康度
3. 包 3：复权与公司行为口径
4. 包 2：关键数据域补齐
5. 包 4：数据血缘与版本追踪

原因：

- 如果点时边界没收好，后面所有特征和标签都会污染
- 如果 provider 能力边界不清楚，数据域补齐会越来越乱
- 如果价格口径不统一，长期验证结果没有可信度

## 6. 对后续阶段的直接支撑

`v2.2` 完成后，后面的“点时特征与标签工程化”才能真正进入主线。

它直接服务于：

- `dataset_service`
- `label_service`
- `prediction_service`
- `backtest_service`
- `evaluation_service`
- 长期因子验证与组合系统

## 7. 交付要求

每个任务包都必须同时交付：

- schema
- service / data product 逻辑
- API 或内部读取接口
- 测试
- README / docs 同步

不接受只改代码不改文档，也不接受只写文档不落工程边界。

## 8. 当前结论

可以把 `v2.2` 理解为：

**项目从“产品壳层已成型”正式转入“为长期因子主线打地基”的阶段。**

这一步做得越稳，后面因子发现、验证、组合与监控系统越不会返工。
## 9. 数据补全分层原则

为避免把初筛链路做成“点击一次就临时补全全世界”的重型系统，`v2.2` 正式采用下面的分层原则：

### 9.1 初筛只消费已有可用数据

初筛的职责是：

- 基于本地已有、可快速读取的数据完成全市场批量筛选；
- 在缺少部分数据时给出质量降级，而不是阻塞整批任务；
- 为后续深筛、单票研究和交易决策提供候选集合。

初筛明确不负责：

- 逐票远程补全财务摘要；
- 逐票远程补全公告窗口；
- 为了补全个股重数据而显著拉长批量运行时间。

### 9.2 公共底座数据在日级准备阶段补全

面向全市场复用、且后续长期因子主线必须依赖的数据，应在“数据底座准备阶段”按日沉淀为本地数据产品，而不是在用户点击初筛时临时抓取。

典型对象包括：

- 日线行情主表；
- 基础股票池与代码表；
- 行业分类、基准、市场广度、风险代理；
- 财务摘要快照；
- 公告索引快照。

### 9.3 个股重数据在深筛/单票研究阶段按需补全

进入深筛 workflow、单票工作台、研究/策略生成阶段的少量候选，可以按需补全更完整的数据输入。

典型对象包括：

- 更完整的财务字段；
- 更完整的公告窗口；
- 更细粒度的技术上下文；
- 解释型、决策型的增强输入。

### 9.4 判断标准

判断某类数据是否应在初筛中补全，统一使用这条规则：

**如果该数据缺失，更合理的处理应是“让单票降级”，而不是“让整批停下来等待补全”，那么它就不应属于初筛执行当下的补全职责。**

## 10. 选股工作台稳定性修复包（进行中）

### 10.1 问题定义

当前 `/screener` 主链路已经具备 workflow、批次台账与结果展示能力，但在 `batch_size=50` 等真实使用场景下暴露出三类高优先级问题：

1. 初筛执行模型过重，批量运行时间过长；
2. 长时间运行后，workflow 可能被误判为 stale，刷新后丢失“运行中”状态；
3. 页面刷新时依赖的最新批次接口过重，容易触发超时。

### 10.2 修复目标

本专项只解决稳定性与可观测性，不改初筛评分策略，不改研究/策略主链路。目标是：

1. 运行中的初筛任务不会在读取状态时被误判为失败；
2. 页面刷新后仍能恢复当前运行中的任务；
3. 首屏查询不再依赖重型结果重建；
4. 日志能够明确定位任务卡点、provider 使用、fallback 原因与每批进度。

### 10.3 分阶段实施顺序

#### 阶段 A：运行态不丢失

- 修正 `WorkflowRuntimeService` 的 stale 判定策略；
- 读状态接口不得因为运行时长过长而把任务直接标记为失败；
- 为 screener 提供轻量的“当前活动任务”只读查询入口。

#### 阶段 B：刷新链路减负

- 将“当前运行状态”查询与“最新批次结果”查询拆分；
- 首屏优先读取轻量摘要，不在刷新时重建整窗结果；
- 将结果表读取从首屏加载中分离。

#### 阶段 C：日志与诊断增强

- 为 screener run 引入统一上下文字段：`run_id / batch_id / batch_size / cursor_start / cursor_end`；
- 增加结构化阶段日志：`started / progress / completed / failed / stale_marked / result_persisted`；
- 增加单票耗时与数据域耗时日志，便于后续定位性能瓶颈。

#### 阶段 D：批量执行提速

- 初筛批量执行继续坚持“轻量优先”原则；
- 对财务摘要、公告索引采用更严格的本地优先 / 缺失降级策略；
- 视阶段风险再引入受控并发，不在当前阶段一次性重构整个 pipeline。

### 10.4 当前约束

本专项明确不做：

- 重写初筛评分逻辑；
- 将单票研究逻辑直接塞进初筛；
- 在本轮引入新的定时任务系统；
- 让页面刷新时同步补全预测、财务、公告所有缺口。

### 10.5 当前进度更新（2026-04-10）

- 第一阶段“运行态不丢失”已完成：
  - 已修正 `WorkflowRuntimeService` 在读取运行状态时的 stale 误判；
  - 已新增 `/screener/active-run` 轻量接口；
  - 前端刷新时会优先恢复当前运行中的初筛任务。
- 第二阶段“刷新链路减负”已完成：
  - 已新增 `/screener/latest-batch-summary`，首屏只读取窗口摘要与最新批次，不再默认重建整窗结果；
  - 已新增 `/screener/latest-batch/results`，结果列表改为按需延迟加载；
  - `batch_service` 已支持 `hydrate_predictive=False` 的轻量读取模式，首屏摘要与窗口结果默认不触发预测字段补齐；
  - 前端 `/screener` 已改为“先摘要、后结果”的两段式加载流程；
  - 已补相应 API 测试，确保旧接口兼容不回退。
