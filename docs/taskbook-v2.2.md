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
