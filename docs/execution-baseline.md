# 执行基线

本文件记录当前阶段的执行基线，是代理与开发者在动手前必须阅读的“当前有效状态说明”。

当本文件与历史文档存在冲突时，以本文件列出的当前有效信息为准；实现完成后，如影响当前重点、有效需求或任务拆分，应同步更新本文件。

## 1. 文档职责

本文件只负责维护以下内容：

- 当前阶段；
- 当前优先级；
- 当前重点模块；
- 当前有效的需求文档；
- 当前有效的任务书；
- 任务前阅读要求；
- 文档更新规则。

以下内容不在本文件维护：

- 长期项目硬约束：见 `docs/project-constraints.md`
- 代理工作方式约束：见 `AGENTS.md`

补充说明：

- `docs/index.md` 是当前 `docs/` 目录的整理入口；
- 它不替代本文件，但用于区分“当前有效”和“历史参考”。

## 2. 当前阶段

当前项目处于：

- 从“已形成研究 / 选股 / 交易复盘主链的系统”向“因子驱动、可记录、可复盘的选股与验证系统”过渡阶段；
- 当前最重要的方向不是继续扩张页面数量，而是收敛选股主线、因子主线、记录与复盘主线之间的关系；
- 当前前端重构应围绕“因子优先的股票初筛”展开，而不是继续沿用以结果卡片为中心的旧交互。

## 3. 当前优先级

当前优先级按顺序为：

1. 因子优先的股票初筛重构
2. 初筛方案的记录、版本化与结果挂接
3. 初筛结果的可追踪、可解释、可复盘能力
4. 前端交互重构以适配方案化初筛
5. 深筛、研究、策略与交易复盘的后续衔接

当前正在推进：

- factor-first screener 包 1：方案对象与版本对象
- 已完成第一版 `ScreenerScheme` / `ScreenerSchemeVersion` / `ScreenerRunContextSnapshot` schema
- 已完成 file-backed `screener_scheme_service`、稳定 `snapshot_hash` 计算与 `/screener/schemes*` API 骨架
- 已完成 `ScreenerWorkflowRunRequest` / `WorkflowRunResponse` 的 `scheme_id / scheme_version / scheme_name / scheme_snapshot_hash` 扩展
- 已完成 screener workflow run 启动时的 scheme 解析与运行时方案快照落袋
- 已完成 scheme 元数据贯穿到 `ScreenerBatchRecord`、`ScreenerSymbolResult`、`ScreenerRunResponse`、`screener_factor_snapshot_daily` 与 `screener_selection_snapshot_daily` 参数哈希
- 已完成 `effective_scheme_config` 对初筛运行的有限接入：当前已支持 `factor_weight_config`、`threshold_config`、`quality_gate_config` 覆盖评分、分桶与质量门控
- 已补齐针对性回归：scheme metadata 透传、snapshot params hash 变更、batch/result 挂接均已通过测试
- 下一步进入方案级 runs / stats / feedback 聚合与查询阶段，为前端“方案中心化工作台”做后端闭环准备

## 4. 当前重点模块

当前重点模块为：

- `backend/app/services/screener_service/`
- `backend/app/services/feature_service/`
- `backend/app/services/data_products/`
- `backend/app/services/prediction_service/`
- `frontend/src/components/screener-workspace.tsx`
- 与初筛方案、因子快照、筛选结果、结果追踪相关的 schema、route、存储与前端状态管理

当前重点不是：

- 自动交易
- 高频执行
- 券商接入
- 全新的无关页面扩张

## 5. 当前有效需求文档

以下文档当前有效，涉及初筛、因子、前端重构、方案化筛选时必须阅读：

1. `docs/factor-first-screener-design-v1.md`
2. `docs/factor-first-screener-implementation-spec-v1.md`
3. `docs/factor-first-screener-api-storage-spec-v1.md`
4. `docs/factor-first-screener-frontend-spec-v1.md`

其职责是：

- 定义“以因子出发的股票初筛，可记录、可复盘”的目标形态；
- 说明当前项目现状能直接复用什么、还缺什么；
- 定义方案对象、版本对象、运行快照、结果挂接与复盘聚合方向。
- 定义第一阶段可直接编码的对象边界、模块落点、接入顺序。
- 定义后端 API、存储、版本与迁移规则。
- 定义前端交互主线、页面分区、依赖顺序与验收边界。

## 6. 当前有效任务书

以下任务书当前有效，涉及初筛重构落地时必须阅读：

1. `docs/taskbook-factor-first-screener-v1.md`

其职责是：

- 记录当前设计对应的任务拆分顺序；
- 标记当前建议的实施包与优先实现顺序；
- 作为后续包级技术设计与开发推进的基础。

## 7. 任务前阅读要求

### 7.1 所有任务通用

所有代理在执行任何任务前，必须阅读：

1. `README.md`
2. `docs/project-constraints.md`
3. `docs/execution-baseline.md`

### 7.2 初筛 / 因子 / 前端重构相关任务

如果任务涉及以下任一主题：

- 股票初筛
- 因子快照
- 因子方案
- 方案记录与版本化
- 初筛结果持久化
- 初筛结果复盘
- 初筛相关前端重构

则还必须继续阅读：

1. `docs/factor-first-screener-design-v1.md`
2. `docs/taskbook-factor-first-screener-v1.md`
3. `docs/factor-first-screener-implementation-spec-v1.md`
4. `docs/factor-first-screener-api-storage-spec-v1.md`
5. `docs/factor-first-screener-frontend-spec-v1.md`

### 7.3 其他模块任务

如果未来出现新的重点模块或新的当前有效需求文档 / 任务书，必须在本文件新增对应阅读清单，并要求代理在执行前先读。

## 8. 更新规则

以下情况必须更新本文件：

1. 当前阶段判断发生变化；
2. 当前优先级发生变化；
3. 当前重点模块发生变化；
4. 当前有效需求文档发生替换、失效或新增；
5. 当前有效任务书发生替换、失效或新增；
6. 任务前阅读清单需要调整。

更新要求：

- 保持“当前有效”而不是“历史堆积”；
- 避免把历史版本长期并列为同等有效；
- 当文档失效时，应明确替换关系或移出当前有效清单；
- 当实现已经偏离文档时，优先更新文档，再继续让代理引用。

## 9. 当前文档整理状态

当前 `docs/` 目录已经按下列方式收口：

- 当前有效入口：见 `docs/index.md`
- 当前有效需求与技术规格：见本文件第 5、6 节
- 历史阶段文档继续保留，但不再作为当前实现依据

后续新增文档时，必须同步更新：

1. `docs/index.md`
2. 本文件的当前有效清单

## 10. 2026-04-21 Update

本次基线同步补充如下：

- factor-first screener 包 4 后端第一阶段已完成。
- 已新增方案级只读聚合能力：
  - `GET /screener/schemes/{scheme_id}/runs`
  - `GET /screener/schemes/{scheme_id}/stats`
  - `GET /screener/schemes/{scheme_id}/feedback`
- 已新增 `backend/app/services/screener_service/scheme_review_service.py`，复用现有 batch 与 trade/review 存储完成方案级 runs / stats / feedback 聚合。
- 当前方案级反馈统计口径为：
  - 以方案批次命中的股票集合为主键；
  - 向本地 `decision_snapshot / trade / review` 记录做符号级聚合；
  - 用于包 4 第一阶段的“可查询、可回看”目标；
  - 不是最终的一对一严格归因模型，后续可在 journal 显式挂接 scheme 外键后继续收紧。
- 当前下一步切换为包 5：前端初筛工作台方案中心化改造，围绕“方案 -> 运行 -> 结果 -> 反馈”重组主交互。

## 11. 2026-04-21 Package 5 Update

本次继续补充如下：

- factor-first screener 包 5 第一阶段已完成。
- 前端 `/screener` 已从“批次/结果中心”重组为四段式主线：
  - 方案
  - 运行
  - 结果
  - 反馈
- 已补齐前端对后端方案能力的消费：
  - 方案列表与方案详情
  - 方案级 runs / stats / feedback
  - workflow run 的 scheme 元数据
  - batch / symbol result 的 scheme 元数据
- 已完成 `frontend/src/components/screener-workspace.tsx` 顶层状态重组，并拆出：
  - `screener-scheme-panel.tsx`
  - `screener-run-panel.tsx`
  - `screener-result-panel.tsx`
  - `screener-review-panel.tsx`
- 当前结果区已切换为“按已选方案的历史运行批次查看”，不再默认只围绕全局 latest batch 展开。
- 前端校验已通过：
  - `frontend` `npm run type-check`
  - `frontend` `npm run lint`
- 当前下一步进入包 5 第二阶段：继续细化方案页体验，包括运行完成后的方案/批次联动、结果区与反馈区的信息密度优化，以及必要的中文展示和说明补齐。
