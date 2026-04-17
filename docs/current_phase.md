# 当前阶段

## 阶段定义

当前项目处于：

**v2.2：长期主线对齐与数据底座收口阶段**

这意味着：

- `workspace-bundle + workflow + trade/review` 的产品壳层已经基本成型。
- 当前优先级不是无边界扩页面，而是把数据底座继续收成“可重建、可验证、可追溯”的状态。
- 长期方向已经明确收敛到：**因子发现、验证、组合与监控系统**。

## 当前阶段要完成什么

### 1. 数据底座继续收口

当前仍在推进的主线包括：

1. 点时一致性
2. 关键市场数据域补齐
3. 复权与公司行为口径统一
4. 数据血缘与版本追踪
5. provider 能力矩阵与健康度治理

### 2. 保持现有产品入口可回归

以下入口必须持续可用：

- `/stocks/[symbol]`
- `/screener`
- `/trades`
- `/reviews`
- dataset / label / prediction / backtest / evaluation API

### 3. 受控推进初筛因子体系工程化

当前已经把“初筛因子体系”作为一条正式工程主线接入：

- 已形成统一 `screener_factors` schema。
- 已落地过程指标、原子因子、横截面因子、连续性因子。
- 已接入复合打分与候选分桶。
- 已落袋 `screener_factor_snapshot_daily`。
- 已落袋 `screener_selection_snapshot_daily`。
- 已提供只读诊断入口：
  - `GET /screener/diagnostics/selection-lineage/latest`
  - `GET /screener/diagnostics/factor-lineage/{symbol}`

当前状态：

- **包 1 到包 5 已完成**
- **包 6 已完成第一轮回归测试与文档收口**

### 4. 受控维护选股工作台稳定性

在 `v2.2` 主线之外，仍保留一个受控专项：

**选股工作台稳定性修复**

边界如下：

- 不改 research / strategy 主链
- 不改成另一套新的前端框架
- 只修稳定性、刷新链路、日志诊断和批量执行效率

## 当前阶段明确不做

当前阶段不进入：

- 自动下单
- 券商接入
- 高频交易
- 完整持仓引擎
- 大规模前端重构
- 无边界新增 provider
- 新调度系统 / 消息队列 / DAG 平台

## 当前进度

### v2.2 主线

已完成：

1. 包 1：点时一致性收口
2. 包 2：关键数据域补齐
3. 包 3：复权与公司行为口径收口
4. 包 4：数据血缘与版本追踪主链
5. 包 5：provider 能力矩阵与健康度阶段性收口

其中包 4 当前已经落地：

- 统一 lineage schema
- 日级数据产品统一接入 `dataset_version / provider_used / warning_messages / lineage_metadata`
- feature / label / prediction / backtest / evaluation 接入 lineage service
- 本地 `dataset_lineage_records` 登记簿
- 只读 lineage API
- `workspace-bundle` 模块级 `lineage_summary`

### 初筛因子体系任务书

已完成：

1. 包 1：Schema 与字段口径收口
2. 包 2：过程指标与原子因子
3. 包 3：横截面与连续性因子
4. 包 4：复合打分与候选分桶
5. 包 5：快照落袋、血缘与诊断
6. 包 6：第一轮回归测试与文档收口

本轮额外完成：

- 修复 `screener_workflow.py` 中的编码损坏字符串
- 修复 `screener.py` 路由中的损坏中文文案
- 修复 `test_screener_api.py` 中的损坏字符串
- 回归测试通过：
  - `backend/tests/test_screener_workflow_cursor.py`
  - `backend/tests/test_screener_api.py`
  - `backend/tests/test_workflow_runtime_service.py`

## 当前阶段成功标准

达到下面几条，就可以认为当前阶段基本收口：

1. 文档、代码、接口口径一致，不再出现多套阶段叙事。
2. 关键日级数据产品都具备稳定的 `as_of_date / source_mode / freshness_mode / dataset_version`。
3. provider 选择与 fallback 规则可查询、可解释。
4. feature / label / prediction / backtest / evaluation 都能回答“这版结果依赖了什么版本的数据”。
5. 单票工作台与选股工作台在真实使用中稳定可回归。
6. 初筛因子链可以回答“为何入选/为何未入选/依赖了哪版快照”。

## 下一步

当前最直接的下一步是：

1. 继续做初筛因子体系的扩展使用，而不是再回头拆基础骨架。
2. 把 `screener_factor_snapshot_daily / screener_selection_snapshot_daily` 接入后续验证与复用链路。
3. 在不破坏现有工作台的前提下，推进“点时特征与标签资产化”的下一轮增强。
