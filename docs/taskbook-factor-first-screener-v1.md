# 因子优先初筛任务书 v1

## 1. 文档定位

本文档是 [factor-first-screener-design-v1.md](D:/dev/project/codex/China-Equity-Research-Assistant/docs/factor-first-screener-design-v1.md) 的执行任务书。

用途：

- 将“因子优先、可记录、可复盘”的初筛方案系统拆成可落地任务包；
- 明确当前项目基础上哪些内容可以直接复用，哪些需要新增；
- 为后端、前端、测试、文档提供统一施工顺序；
- 避免在没有方案对象、版本对象和复盘对象的前提下，直接进入高自由度前端重构。

本文档不替代设计书，而是将设计书转换为执行阶段的工作包与验收项。

## 2. 总目标

在当前项目已有的：

- `ScreenerPipeline`
- `ScreenerFactorSnapshot`
- `ScreenerBatchService`
- `screener_factor_snapshot_daily`
- `screener_selection_snapshot_daily`
- `trade / review / decision snapshot`

这些能力基础上，建设一套：

- 以因子方案为入口的股票初筛系统；
- 支持方案版本化；
- 支持运行结果与方案快照绑定；
- 支持后续研究、交易、复盘回挂；
- 支持方案级复盘统计；
- 为前端“方案中心化”重构提供稳定后端基础。

## 3. 本阶段边界

### 本阶段要做

- 新增“筛选方案”与“方案版本”对象；
- 允许方案驱动初筛运行；
- 保存运行时方案快照；
- 在批次与结果中挂接方案信息；
- 支持方案级历史运行查看；
- 支持方案级基础复盘统计；
- 重构前端初筛主入口为“方案 -> 运行 -> 结果 -> 复盘”主线。

### 本阶段不做

- 自由 DSL 规则引擎；
- 完整四层因子引擎全部接入初筛；
- 开放所有原子因子参数调节；
- 复杂因子验证平台；
- 自动调参或参数寻优；
- 基于方案的自动交易执行。

## 4. 当前基础判断

### 4.1 已具备的基础

- 初筛主链已支持 `ScreenerFactorSnapshot`；
- 初筛结果已可按批次落盘；
- 初筛因子快照已支持日级落盘与 lineage；
- 单票研究、交易、复盘链路已存在；
- 预测快照与模型版本字段已存在；
- 前端已有初筛工作台与单票工作台，可作为重构基础。

### 4.2 当前主要缺口

- 没有 `ScreenerScheme / ScreenerSchemeVersion`；
- 初筛运行结果未绑定到方案版本；
- 当前 `rule_version` 仍是固定工作流版本，不足以表达用户方案；
- 没有方案级复盘统计对象；
- 前端仍以结果列表为入口，缺少方案中心区；
- 没有清晰的“参数变更即升版”机制。

## 5. 推荐实施顺序

建议按 6 个任务包推进：

1. 方案对象与版本对象
2. 方案驱动的初筛运行接入
3. 批次、结果与因子快照的方案挂接
4. 方案级复盘统计
5. 前端初筛工作台重构
6. 测试、文档与迁移收口

以下各包应尽量按顺序推进，避免前端先行但后端对象不稳。

## 6. 包 1：方案对象与版本对象

### 当前进度

已完成第一阶段：

- 已新增 `ScreenerScheme`、`ScreenerSchemeVersion`、`ScreenerRunContextSnapshot` 及对应 request / response schema
- 已新增 file-backed `screener_scheme_service` 与稳定 `snapshot_hash` 计算工具
- 已新增 `GET /screener/schemes`、`POST /screener/schemes`、`GET /screener/schemes/{scheme_id}`、`PATCH /screener/schemes/{scheme_id}`、`GET /screener/schemes/{scheme_id}/versions`、`POST /screener/schemes/{scheme_id}/versions`、`GET /screener/schemes/{scheme_id}/versions/{scheme_version}`
- 已内置 `default_builtin_scheme / legacy_v1` 作为默认兼容方案

下一阶段：

- batch / result / factor snapshot 挂接 scheme 元数据
- workflow detail / batch detail / symbol result 透出完整 scheme 上下文
- 方案级 runs / stats / feedback 聚合

### 目标

建立“筛选方案系统”的最小后端骨架。

### 需要新增

- Schema
  - `ScreenerScheme`
  - `ScreenerSchemeVersion`
  - `CreateScreenerSchemeRequest`
  - `UpdateScreenerSchemeRequest`
  - `CreateScreenerSchemeVersionRequest`
  - `ScreenerSchemeListResponse`
- Service
  - `screener_scheme_service`
- Storage
  - 可先使用文件型或轻量 DB 存储，优先与当前项目风格一致
- API
  - `GET /screener/schemes`
  - `POST /screener/schemes`
  - `GET /screener/schemes/{scheme_id}`
  - `PATCH /screener/schemes/{scheme_id}`
  - `POST /screener/schemes/{scheme_id}/versions`
  - `GET /screener/schemes/{scheme_id}/versions`

### 配置内容

第一阶段方案版本至少包含：

- `universe_filter_config`
- `factor_selection_config`
- `factor_weight_config`
- `threshold_config`
- `quality_gate_config`
- `bucket_rule_config`

### 状态

当前未实现。

### 验收

- 可创建方案；
- 可保存多个版本；
- 可读取方案当前激活版本；
- 方案版本内容结构化返回；
- 每次方案配置变化都生成新版本。

## 7. 包 2：方案驱动的初筛运行接入

### 当前进度

已完成第一阶段：

- 已完成 `ScreenerWorkflowRunRequest` / `WorkflowRunResponse` 的 `scheme_id / scheme_version / scheme_name / scheme_snapshot_hash` 扩展
- 已完成 screener workflow run 启动时的 scheme 解析与 `ScreenerRunContextSnapshot` 落袋
- 已完成 workflow detail / runtime visibility 对 scheme 摘要字段的透传
- 已完成 `effective_scheme_config` 的有限消费：`factor_weight_config`、`threshold_config`、`quality_gate_config` 已可影响初筛评分、分桶和质量门控

下一阶段：

- 扩展更多可控但仍有限的 scheme 覆盖面，同时继续保持默认内置方案兼容
- 为方案级 runs / stats / feedback 聚合准备稳定查询字段
- 明确哪些 config 进入 v1 主链、哪些延后到更高自由度阶段

### 目标

让 `ScreenerPipeline` 不再只依赖固定内置规则，而能消费方案版本配置。

### 需要调整

- `ScreenerWorkflowRunRequest`
  - 增加 `scheme_id`
  - 增加 `scheme_version` 可选
- `run_screener_workflow` 输入构造
- `ScreenerPipeline.run_screener()`
  - 增加 `scheme_context`
- 评分逻辑
  - 从固定内置权重，扩展为“默认权重 + 方案覆盖”
- 质量门控逻辑
  - 从固定门控，扩展为“默认门控 + 方案覆盖”

### 设计要求

- 没有传方案时，仍能运行默认内置方案；
- 方案驱动必须是兼容式接入，而不是打断现有初筛主链；
- 第一阶段只允许方案改“组级权重”和“少量关键阈值”；
- 原子因子内部映射仍保持后端固定实现。

### 状态

当前未实现。

### 验收

- 同一批 universe，在不同方案下能产出不同结果；
- 未传方案时结果与当前默认逻辑基本兼容；
- 运行日志中能识别当前方案版本；
- workflow 详情中能返回方案摘要。

## 8. 包 3：批次、结果与因子快照的方案挂接

### 当前进度

已完成第一阶段：

- 已完成 `ScreenerBatchRecord` / `ScreenerSymbolResult` / `ScreenerRunResponse` 的 scheme 元数据扩展
- 已完成 scheme 元数据从 workflow run context 透传到 batch、result、factor snapshot 与 selection snapshot params hash
- 已完成针对 `batch_service`、`screener_factor_snapshot_daily`、`screener_selection_snapshot_daily`、`screener_workflow_cursor` 的回归测试

下一阶段：

- 让批次详情、结果详情与 scheme 版本对象形成更稳定的双向查询关系
- 为后续方案级 runs / stats / feedback 聚合准备索引与查询入口

### 目标

让每次初筛运行结果都能追溯到具体方案版本与方案快照。

### 需要调整

- `ScreenerBatchRecord`
  - 新增：
    - `scheme_id`
    - `scheme_version`
    - `scheme_name`
    - `scheme_snapshot_hash`
- `ScreenerSymbolResult`
  - 新增：
    - `scheme_id`
    - `scheme_version`
    - `scheme_snapshot_hash`
    - `selected_factor_groups`
    - `scoring_profile_name`
    - `quality_gate_profile_name`
- `ScreenerBatchService`
  - `create_running_batch()`
  - `finalize_batch()`
  - `_build_symbol_results()`
- `screener_factor_snapshot_daily`
  - 参数哈希中补充方案维度
- 新增运行时方案快照对象
  - `ScreenerRunContextSnapshot`

### 设计要求

- 结果保存时必须记录当时生效的配置快照，而不是仅记录 `scheme_id`；
- `params_hash` 与 `scheme_snapshot_hash` 必须能稳定计算；
- 后续结果读取与历史展示必须优先显示“当时实际运行配置”。

### 状态

当前结果保存已存在，但未挂接方案对象。

### 验收

- 批次详情可看到方案版本；
- 单只结果可看到方案元信息；
- 因子快照能识别与哪次方案运行相关；
- 方案变化后，新旧运行结果不会混淆。

## 9. 包 4：方案级复盘统计

### 目标

让用户能以“方案”为单位回看其后续效果，而不是只看单次批次结果。

### 需要新增

- Schema
  - `ScreenerSchemeStats`
  - `ScreenerSchemeRunSummary`
  - `ScreenerSchemeFeedbackSummary`
  - `ScreenerSchemeReviewStatsResponse`
- Service
  - `screener_scheme_review_service`
- API
  - `GET /screener/schemes/{scheme_id}/stats`
  - `GET /screener/schemes/{scheme_id}/runs`
  - `GET /screener/schemes/{scheme_id}/feedback`

### 第一阶段统计项

- 运行次数
- 总候选数
- 各 bucket 数量
- 进入研究数
- 生成 decision snapshot 数
- 产生 trade 数
- 产生 review 数
- `success / partial_success / failure / no_trade` 分布

### 第二阶段预留统计项

- 5/10/20 日候选后验表现
- bucket 转化率
- 不同行业下方案有效性
- 不同质量状态下方案有效性

### 状态

当前交易/复盘主线已存在，但缺少方案聚合层。

### 验收

- 可查看某方案的历史运行列表；
- 可统计某方案筛出的股票后续进入研究/交易/复盘的数量；
- 统计结果能区分不同版本；
- 可按时间窗口查看方案表现。

## 10. 包 5：前端初筛工作台重构

### 目标

把现有初筛前端从“结果列表中心”重构为“方案中心”。

### 目标页面主线

1. 方案区
2. 运行区
3. 结果区
4. 复盘区

### 需要调整

- `frontend/src/components/screener-workspace.tsx`
- `frontend/src/lib/api.ts`
- `frontend/src/types/api.ts`
- 如果需要，可拆分：
  - `screener-scheme-panel.tsx`
  - `screener-run-panel.tsx`
  - `screener-result-panel.tsx`
  - `screener-review-panel.tsx`

### 第一阶段前端能力

- 查看方案列表；
- 切换方案；
- 展示方案摘要；
- 发起方案运行；
- 展示方案版本；
- 在结果详情里展示方案信息；
- 展示方案历史运行与基础反馈统计。

### 前端限制

第一阶段不做：

- 前端原子因子自由编辑器；
- 全量阈值表单；
- 可视化规则 DSL；
- 复杂拖拽式策略编排器。

### 状态

当前前端已有初筛工作台，但方案中心未实现。

### 验收

- 用户能直观看到“当前结果属于哪套方案”；
- 用户能在不进入后端接口文档的情况下切换方案与运行；
- 结果页不再只有 `rule_version`，而是有完整方案上下文；
- 方案历史与复盘入口清晰可见。

## 11. 包 6：测试、文档与迁移收口

### 目标

确保方案系统不是只在前端“看起来能用”，而是后端对象、版本、结果、复盘都稳定可测。

## 12. 2026-04-21 Progress Update

### 包 4 当前状态

包 4 第一阶段后端已完成，已落地内容：

- 新增方案级聚合 schema：
  - `ScreenerSchemeRunSummary`
  - `ScreenerSchemeStats`
  - `ScreenerSchemeFeedbackSummary`
  - `ScreenerSchemeReviewStatsResponse`
- 新增只读聚合服务：
  - `backend/app/services/screener_service/scheme_review_service.py`
- 新增只读接口：
  - `GET /screener/schemes/{scheme_id}/runs`
  - `GET /screener/schemes/{scheme_id}/stats`
  - `GET /screener/schemes/{scheme_id}/feedback`
- 已补齐测试：
  - `backend/tests/test_screener_scheme_review_service.py`
  - `backend/tests/test_screener_scheme_api.py` 中方案级 runs/stats/feedback 路由测试

### 包 4 当前统计口径

当前第一阶段采用“方案批次结果符号集合 + 本地 journal 记录”的轻量归因方式：

- runs：按 `ScreenerBatchRecord.scheme_id` 过滤批次并汇总单批次结果；
- stats：聚合方案批次的运行数、候选数、bucket 分布，以及本地 `decision_snapshot / trade / review` 的去重统计；
- feedback：汇总 `strategy_alignment`、`did_follow_plan`、`outcome_label`、`lesson_tags` 等反馈信号；
- 当前不引入新的存储表，也不修改 trade/review 主链外键结构。

### 包 4 后续收紧点

包 4 第二阶段再处理：

- 更严格的方案到 journal 显式归因；
- 时间窗和版本窗口的精细化过滤；
- 5/10/20 日后验与 bucket 转化类统计。

### 下一步

下一步进入包 5：前端初筛工作台方案中心化改造。

### 需要新增测试

#### 后端

- 方案 schema 校验
- 方案版本创建
- 方案哈希稳定性
- 方案驱动下的初筛运行
- 批次与结果方案挂接
- 方案级统计聚合
- 版本变更隔离

#### 前端

- 方案切换与运行态
- 方案摘要展示
- 方案版本展示
- 方案统计展示

### 需要补充文档

- 更新 README 中“初筛主入口”描述
- 更新 `docs/current_phase.md`
- 在使用手册中补充“方案初筛”的操作说明

### 数据迁移策略

历史批次没有方案信息时，可采用：

- 显示为 `default_builtin_scheme`
- 版本标记为 `legacy_v1`

禁止因为历史数据不完整而中断读取。

### 验收

- 单测覆盖主要对象和服务；
- 旧批次可读；
- 新批次具备完整方案元信息；
- 文档与代码一致。

## 12. 推荐落地节奏

### 阶段 1：先稳后动

优先完成：

- 包 1
- 包 2
- 包 3

原因：

- 没有方案对象与运行挂接，前端重构会失去基础；
- 没有结果方案绑定，后续复盘就只是口号。

### 阶段 2：形成闭环

继续完成：

- 包 4
- 包 5

原因：

- 方案系统必须和后续反馈链闭环；
- 前端只有在后端闭环存在时，才能真正做“方案中心”。

### 阶段 3：收口与扩展

最后完成：

- 包 6

并预留：

- 高级调参
- 方案对比
- 参数变更效果分析

## 13. 当前建议的实现优先级

如果要马上进入开发，建议优先级如下：

1. 后端方案对象与版本对象
2. 运行时方案快照接入 screener workflow
3. 批次与结果对象挂接方案元信息
4. 方案级复盘聚合接口
5. 前端方案区重构
6. 前端结果与复盘区重构
7. 测试与迁移收口

## 14. 当前阶段验收结论

截至目前，项目已经具备建设“因子优先初筛方案系统”的基础，但尚未具备方案级对象、版本、挂接与复盘能力。

因此当前最正确的下一步不是继续扩展更多因子，而是先把：

- 方案对象
- 方案版本
- 运行结果绑定
- 方案复盘

这四件事工程化。

## 15. 下一步建议

建议下一步直接进入“包 1：方案对象与版本对象”的技术细化设计。

推荐输出顺序：

1. 方案 schema 设计
2. 存储结构设计
3. API 设计
4. `ScreenerPipeline` 接入设计

只有完成这一步，后续前端重构才会真正稳定。
