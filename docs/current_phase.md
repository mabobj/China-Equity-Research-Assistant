# 当前阶段

## 阶段定义

当前项目处于：

**v2.2：长期主线对齐与数据底座收口阶段**

这意味着：

- `workspace-bundle + workflow + trade/review` 的产品壳层已经基本成型；
- 当前优先级不再是无边界扩页面，而是把数据底座继续收成“可重建、可验证、可追溯”的状态；
- 长期方向已经明确收敛到：**因子发现、验证、组合与监控系统**。

## 当前阶段要完成什么

### 1. 数据底座收口

当前仍在推进的主线包括：

1. 点时一致性
2. 关键市场数据域补齐
3. 复权与公司行为口径统一
4. 数据血缘与版本追踪
5. provider 能力矩阵与健康度制度化

### 2. 保持现有产品入口可回归

以下入口必须持续可用：

- `/stocks/[symbol]`
- `/screener`
- `/trades`
- `/reviews`
- dataset / label / prediction / backtest / evaluation API

### 3. 受控维护选股工作台稳定性

在 `v2.2` 主线之外，当前还并行维护一个受控专项：

**选股工作台稳定性修复**

边界明确如下：

- 不改 research / strategy 主链
- 不改初筛评分逻辑
- 不做新的前端大重构
- 只修稳定性、刷新链路、日志诊断和批量执行效率

## 当前阶段明确不做

当前阶段不进入：

- 自动下单
- 券商接入
- 高频交易
- 组合归因与完整持仓引擎
- 新一轮大规模前端重构
- 无边界增加 provider
- 新调度系统 / 消息队列 / DAG 平台

## 当前进度

### v2.2 主线

已完成：

1. 包 1：点时一致性收口
   - 阶段一已完成
   - 阶段二已完成

2. 包 5：provider 能力矩阵与健康度
   - 阶段一已完成
   - 阶段二已完成

3. 包 3：复权与公司行为口径收口
   - 阶段一已完成
   - 阶段二已完成

4. 包 2：关键数据域补齐
   - 阶段一已完成
   - 阶段二已完成

5. 包 4：数据血缘与版本追踪
   - 统一 lineage schema 已落地
   - 日级数据产品已统一接入 `dataset_version / provider_used / warning_messages / lineage_metadata`
   - repository 型数据产品已支持随快照保存并读回 lineage 元数据
   - feature / label / prediction / backtest / evaluation 已统一接入 lineage service
   - 本地 `dataset_lineage_records` 登记簿已落地
   - 只读 lineage API 已落地
   - `workspace-bundle` 已新增模块级 `lineage_summary`
   - 当前状态：**主链完成，回归验证与主文档同步中**

### 选股工作台稳定性专项

已完成：

1. 运行态不丢失
2. 刷新链路减负
3. 日志与诊断增强
4. 批量执行提速

## 当前阶段成功标准

达到下面几条，就可以认为当前阶段基本收口：

1. 文档、代码、接口口径一致，不再出现多套阶段叙事
2. 关键日级数据产物都具备稳定的 `as_of_date / source_mode / freshness_mode`
3. provider 选择与 fallback 规则可查询、可解释
4. feature / label / prediction / backtest / evaluation 都能回答“这版结果依赖了什么版本的数据”
5. 单票工作台与选股工作台在真实使用中稳定可回归

## 下一步

当前最直接的下一步是：

1. 完成包 4 的回归测试与接口验收
2. 同步 README / architecture 等主文档中的 lineage 说明
3. 再决定是否进入下一轮“点时特征与标签资产化增强”
