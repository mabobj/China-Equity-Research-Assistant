# 项目任务书（v2.1，产品化增强版）

## 1. 目标定义

本阶段同时推进两条主线：

- 功能主线：在现有 `workspace-bundle + workflow + trade/review` 基础上，补齐“预测与评估”能力链。
- 体验主线：将当前工作台从“工程控制台”升级为“消费级可用产品”，让用户明确先看什么、先做什么、为什么这么做。

统一成功标准：

- 用户在 30 秒内看懂单票结论与下一步动作。
- 用户在 3 分钟内完成一次“选股 -> 单票判断 -> 记录交易”闭环。
- 任一交易都可回溯当时判断、数据质量、执行偏差与复盘结论。

## 2. 当前主链路基线（以代码为准）

- 单票主入口：`GET /stocks/{symbol}/workspace-bundle`
- 选股主入口：`POST /workflows/screener/run` + `GET /workflows/runs/{run_id}`
- 深筛主入口：`POST /workflows/deep-review/run` + `GET /workflows/runs/{run_id}`
- 交易与复盘入口：`/trades`、`/reviews`
- 数据清洗层：`bars`、`financial_summary`、`announcements` 已接入主链路
- 质量消费：`/research` 与 `/screener` 已消费 `quality_status`

## 3. 产品原则（v2.1）

- 先结论，再证据，后细节。
- 默认展示业务语言，技术细节下沉到“高级信息”。
- 长任务必须有进度与阶段反馈。
- 局部失败不阻断主链路，失败影响需可解释。
- 页面术语、API 字段、文档说明保持一致。

## 4. 范围与边界

纳入范围：

- 单票、选股、交易、复盘四个现有页面的结构优化
- 预测/回测/评估能力接入与版本化
- 文档与术语统一收口

不纳入范围：

- 自动下单与券商接入
- 复杂持仓引擎与组合归因
- 队列、DAG、调度平台重构
- 新增大量页面类型与重前端框架改造

## 5. 双轨任务拆分

### 5.1 功能轨（预测与评估）

F1 点时特征与标签底座：

- `dataset_service`
- `label_service`
- `feature_version / label_version`

F2 回测与评估底座：

- `backtest_service`
- `evaluation_service`
- walk-forward 评估流程

F3 预测服务 MVP：

- `prediction_service`
- `experiment_service`
- `predictive_score / model_confidence / model_version`

F4 接回产品主链：

- `workspace-bundle` 接入 `predictive_snapshot`
- `screener` 融合预测分（保留质量门控）
- `trade/review` 绑定模型版本与预测元数据

### 5.2 体验轨（消费级改造）

U1 首页与导航收口  
U2 单票页重构  
U3 选股页重构  
U4 交易与复盘重构

## 6. 分包交付与状态

说明：本任务书的“交付包”总数为 **6 个**；文档中的“## 1 ~ ## 10”是章节编号，不是交付包编号。

### 包 1：认知收口包（已完成）

- 清理“预留/未启用”旧叙事
- 发布 v2.1 任务书并接入 README 导航
- 前端 `type-check + lint` 通过

### 包 2：单票体验重构包（已完成）

- 单票改为“结论优先”
- 运行细节下沉到高级区
- 交易入口改为可选展开

### 包 3：选股体验重构包（已完成）

- 结构调整为“结果优先”
- 高级参数下沉
- 增加分桶分布摘要

### 包 4：交易复盘体验收口包（已完成）

- `/trades` 快速记录优先 + 高级参数折叠
- `/reviews` 待复盘交易优先
- 详情对照视图：原判断快照 / 执行路径 / 复盘结论 / 偏差诊断
- 增加动作-原因类型匹配提示与友好错误解释

### 包 5：预测底座包（已完成到第三步）

5.1 第一阶段（已完成）：

- 新增 `dataset/prediction/backtest/evaluation` schema
- 新增 `dataset/label/experiment/prediction/backtest/evaluation` 服务骨架
- 新增预测与回测 API 契约

5.2 第二阶段（已完成）：

- 特征数据集与标签数据集支持真实落盘（本地 JSON 台账）
- 预测服务优先消费真实特征，未命中时哈希回退并给 warning
- 回测服务消费预测候选与真实标签，输出可解释指标

5.3 第三阶段（已完成）：

- `backtest_service` 完成 walk-forward 切片聚合评估
- `evaluation_service` 从占位评估升级为“真实回测引用评估”
- `/evaluations/models/{model_version}` 新增：
  - `backtest_references`
  - `comparison`（非默认版本自动对比默认模型）
- 指标兼容保留：
  - `precision_at_20`
  - `hit_rate_5d`
  - `excess_return_10d`
- 指标新增：
  - `screener_win_rate`
  - `screener_top_k_avg_return`
  - `screener_max_drawdown`
  - `screener_slice_count`
  - `quality_score`

边界说明：

- 仍用于研究与版本筛选，不作为自动交易执行入口。
- 交易成本、滑点、组合级归因暂未纳入本轮。

### 包 6：预测接入包（已完成第三阶段）

- `workspace-bundle` 增加 `predictive_snapshot`（可选字段，兼容保留）
- screener candidate / batch result 写入预测字段：
  - `predictive_score`
  - `predictive_confidence`
  - `predictive_model_version`
- deep-review 候选透传预测字段
- 决策快照固化预测元数据（供交易与复盘对照）
- 前端单票、选股、深筛、交易、复盘已做最小可见化

6.2 第二阶段（已完成）：

- 预测字段解释一致性落地（单票页与选股页统一展示“预测分解释 + 置信度等级”）
- `/evaluations/models/{model_version}` 新增 `recommendation`：
  - `recommendation`（`promote_candidate / keep_baseline / observe`）
  - `recommended_model_version`
  - `reason`
  - `supporting_metrics`
  - `guardrails`
- 单票页“预测快照（辅助）”增加模型版本建议面板
- 选股页候选详情按 `predictive_model_version` 懒加载并展示模型版本建议
- 增补后端与前端契约测试，覆盖 recommendation 字段与前端展示契约

6.3 第三阶段（已完成）：

- workflow 运行详情（`GET /workflows/runs/{run_id}`）接入模型版本建议快照：
  - 新增 `model_recommendation`（可选，兼容保留）
  - 新增 `version_recommendation_alert`（可选，兼容保留）
- `WorkflowRuntimeService` 支持在 run detail 级别提取预测模型版本并加载评估建议
- 增加“版本建议变化告警”最小机制：
  - 当建议版本与当前默认版本不一致时，返回结构化提醒文案
  - 不自动切换默认模型，仅用于人工决策提示
- 前端 `workflow-run-summary` 增加：
  - 模型版本建议展示
  - 版本建议变化提醒展示
- 增补回归测试：
  - `test_workflow_runtime_service.py`（run detail 级别建议与告警）
  - `test_workflow_api.py`（workflow 轮询链路建议字段契约）
  - 前端 smoke 增补 workflow 建议面板契约检查

## 7. 关键验收标准

体验验收：

- 主链路“选股 -> 单票 -> 交易 -> 复盘”可连续完成
- 冲突提示可回答“是什么冲突、为什么冲突、怎么继续”

功能验收：

- 点时特征与标签可重建、可回看、可版本化
- 回测可重复运行并输出稳定指标
- 评估可追溯到具体回测引用与版本对比

稳定性验收：

- 局部模块失败不阻断主结果
- fallback/runtime 字段保持可解释
- 新增测试不依赖实时外网

## 8. 风险与应对

- 风险：功能开发压过体验收口  
  应对：每个包必须同时包含代码、测试、文档交付

- 风险：术语继续漂移  
  应对：统一词汇表并在页面/接口/文档同源复用

- 风险：预测接入破坏现有主链  
  应对：保持可选字段接入，保留回退路径

## 9. 协作方式

- 每个任务包都要提交：代码 + 测试 + 文档。
- 每次收尾都要输出：变更摘要、验证结果、残留风险。
- 优先做用户可感知价值最高的改动，再做技术扩展。

## 10. 当前收口状态

`v2.1` 任务书定义的 6 个任务包已全部完成。  
后续建议进入 `v2.2` 规划阶段，重点放在：

- 预测评估样本扩容与稳定性统计
- 模型版本治理策略（灰度、回退与人工审批）
- 工作台“可解释性 + 可操作性”持续优化
