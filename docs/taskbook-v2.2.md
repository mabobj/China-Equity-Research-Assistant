# 项目任务书（v2.2，数据底座与点时特征版）

## 1. 文档定位

`v2.1` 解决的是产品壳、最小预测接入和交易/复盘闭环。  
`v2.2` 不再继续无边界堆页面，而是把系统收口到真正支撑长期主线的数据底座上。

长期主线已经明确为：

**因子发现、验证、组合与监控系统**

因此，`v2.2` 的核心目标只有一个：

**把当前“可用的数据底座”，升级为“可重建、可验证、可追溯的数据底座”。**

## 2. 总目标

完成 `v2.2` 后，系统至少要能稳定回答：

1. 任意 `symbol + as_of_date` 的关键输入能否重建。
2. 关键数据域是否有统一 schema、统一质量状态、统一 provider 边界。
3. 特征、标签、预测、回测、评估是否都能说明依赖了哪一版上游数据。
4. provider 选择、fallback 和本地持久化要求是否可解释、可查询。

## 3. 本阶段边界

### 本阶段要做

- 点时一致性收口
- 关键市场数据域补齐
- 复权与公司行为口径统一
- 数据血缘与版本追踪
- provider 能力矩阵与健康度制度化
- 为后续点时特征、标签、回测与因子验证打底

### 本阶段不做

- 自动下单
- 券商接入
- 高频交易
- 新一轮大规模前端重构
- 无边界扩 provider
- 新调度系统 / 消息队列 / DAG 平台

## 4. 五个任务包

## 包 1：点时一致性收口

### 目标

把日级数据读取收口为统一 `as_of_date` 口径，避免“历史请求混入今天结果”。

### 状态

- 阶段一：已完成
- 阶段二：已完成

### 已完成内容

- 抽出统一的默认分析日策略
- 日级数据产品、dataset、label、prediction、backtest 统一接入默认分析日
- `workspace-bundle`、关键单票 route、workflow 已支持显式 `as_of_date`
- 对当前不支持安全历史重算的路径改为受控失败，而不是静默用当前结果替代

### 验收

- 任意日级产物都能说明自己的 `as_of_date`
- 历史请求口径一致

## 包 2：关键数据域补齐

### 目标

补齐长期主线真正需要的基础市场上下文，而不是无边界扩源。

### 状态

- 阶段一：已完成
- 阶段二：已完成

### 已完成内容

- 基准目录
- 行业 / 板块分类
- 市场广度
- 基础风险代理
- 基准日线读取链路
- `GET /market/benchmarks`
- `GET /market/benchmarks/{benchmark_symbol}/daily-bars`
- `GET /market/breadth`
- `GET /market/risk-proxies`
- `GET /stocks/{symbol}/classification`

### 验收

- 新数据域有统一 schema
- provider/source/fallback 边界清晰
- 能按日沉淀为本地可复用产物

## 包 3：复权与公司行为口径收口

### 目标

统一长期回测、因子验证绕不过去的价格口径问题。

### 状态

- 阶段一：已完成
- 阶段二：已完成

### 已完成内容

- `DailyBar / DailyBarResponse` 显式补齐 `adjustment_mode` 与公司行为元数据
- 日线 schema / normalize / local store / API 输出已统一
- `/stocks/{symbol}/daily-bars` 已支持 `adjustment_mode=raw/qfq/hfq`
- `daily_bars` 本地存储已按 `symbol + trade_date + adjustment_mode` 区分保存
- 响应已暴露 `corporate_action_mode / corporate_action_warnings`

### 验收

- 价格口径统一且可追溯
- 后续 feature/backtest 不再混用不同口径

## 包 4：数据血缘与版本追踪

### 目标

把零散存在的：

- `as_of_date`
- `generated_at`
- `feature_version`
- `label_version`
- `model_version`
- `provider_used`

统一收口成可落袋、可查询、可回溯的数据血缘体系。

### 当前状态

- 统一 lineage schema：已完成
- 日级数据产品版本与血缘元数据接入：已完成
- feature / label / prediction / backtest / evaluation 统一版本与依赖引用：已完成
- 本地 lineage repository：已完成
- 只读 lineage API：已完成
- workspace 模块级 lineage summary：已完成
- repository 型日级数据产品的 lineage 保存与读回：已完成
- 测试与主文档同步：进行中

### 已完成内容

- 新增 schema：
  - `LineageSourceRef`
  - `LineageDependency`
  - `LineageMetadata`
  - `LineageListResponse`
  - `WorkspaceLineageItem`
  - `LineageSummary`
- `DataProductResult` 已补齐：
  - `dataset_version`
  - `provider_used`
  - `warning_messages`
  - `lineage_metadata`
- feature/label manifest 已记录：
  - `generated_at`
  - `schema_version`
  - `dependencies`
- 新增本地登记簿：
  - `dataset_lineage_records`
- 新增只读接口：
  - `GET /lineage/datasets`
  - `GET /lineage/datasets/{dataset}/{dataset_version}`
  - `GET /datasets/features/{dataset_version}/lineage`
  - `GET /datasets/labels/{label_version}/lineage`
  - `GET /predictions/{symbol}/lineage`
  - `GET /stocks/{symbol}/workspace-lineage`
- `workspace-bundle` 已新增：
  - `lineage_summary`

### 剩余收尾

1. 继续补齐 API / repository / workspace 相关回归测试
2. 做一轮只读接口验收，确保新增字段仅做增强，不破坏现有调用
3. 把 lineage 规则同步回主文档

### 验收

- 能回答“这版 feature / label / prediction / evaluation 来自哪版数据”
- 能回答“当前 workspace 关键模块依赖了哪版日级产物”
- 旧接口兼容，新字段只做增强

## 包 5：provider 能力矩阵与健康度

### 目标

把 provider 规则从“写在 service 里的隐式经验”升级为“可解释、可测试的制度化策略”。

### 状态

- 阶段一：已完成
- 阶段二：已完成

### 已完成内容

- capability -> provider 优先级矩阵已集中收口
- 明确了：
  - `preferred_providers`
  - `allow_stale_fallback`
  - `require_local_persistence`
- 新增 capability 级健康报告
- 新增只读诊断接口：
  - `GET /providers/capabilities`
  - `GET /providers/health`
  - `GET /providers/health/{capability}`

### 验收

- provider 选择规则可解释、可测试、可回归

## 5. 推荐实施顺序

`v2.2` 严格按下面顺序推进：

1. 包 1：点时一致性
2. 包 5：provider 能力矩阵与健康度
3. 包 3：复权与公司行为口径
4. 包 2：关键数据域补齐
5. 包 4：数据血缘与版本追踪

## 6. 当前结论

当前 `v2.2` 的整体状态可以概括为：

- 包 1：完成
- 包 5：完成
- 包 3：完成
- 包 2：完成
- 包 4：主链完成，测试与主文档同步中

也就是说，项目已经从“产品壳成型”正式进入了“为长期因子主线打地基”的阶段。
