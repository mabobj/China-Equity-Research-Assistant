# 因子优先初筛实现规格 v1

## 1. 文档定位

本文件用于把 [factor-first-screener-design-v1.md](D:/dev/project/codex/China-Equity-Research-Assistant/docs/factor-first-screener-design-v1.md) 和 [taskbook-factor-first-screener-v1.md](D:/dev/project/codex/China-Equity-Research-Assistant/docs/taskbook-factor-first-screener-v1.md) 落到可以直接编码的实现规格。

目标是让 Codex 能在较少临场判断的前提下，连续推进：

- 后端对象建模
- service 接入
- route 暴露
- 存储落地
- 前端接线
- 测试与迁移

## 2. 本阶段实现边界

本阶段要做：

- 建立 `ScreenerScheme` 与 `ScreenerSchemeVersion`
- 建立运行时 `ScreenerRunContextSnapshot`
- 让 screener workflow 能显式绑定方案版本
- 让 batch / result / factor snapshot 带上方案元信息
- 提供方案级历史运行与基础复盘聚合
- 为前端“方案中心 -> 运行 -> 结果 -> 复盘”主线提供稳定后端契约

本阶段不做：

- 自由 DSL
- 任意原子因子编辑器
- 自动调参
- 因子实验平台
- 复杂可视化策略编排

## 3. 目标实现顺序

连续开发必须按以下顺序推进：

1. Schema
2. Storage
3. Service
4. Route
5. Pipeline integration
6. Frontend integration
7. Tests
8. Docs sync

禁止前端先行定义一套后端尚不存在的方案对象。

## 4. 核心对象

### 4.1 ScreenerScheme

职责：

- 表示一套可复用的初筛方案主对象；
- 承载方案名称、状态和当前默认版本信息；
- 不直接承载完整运行配置。

建议字段：

- `scheme_id`
- `name`
- `description`
- `status`
- `created_at`
- `updated_at`
- `current_version`
- `is_builtin`
- `is_default`

状态约束：

- `draft`
- `active`
- `archived`

### 4.2 ScreenerSchemeVersion

职责：

- 表示某套方案在某时刻冻结的完整版本；
- 承载完整配置快照；
- 作为运行时的可追溯依据。

建议字段：

- `scheme_id`
- `scheme_version`
- `version_label`
- `created_at`
- `created_by`
- `change_note`
- `snapshot_hash`
- `config`

`config` 内必须包含：

- `universe_filter_config`
- `factor_selection_config`
- `factor_weight_config`
- `threshold_config`
- `quality_gate_config`
- `bucket_rule_config`

### 4.3 ScreenerRunContextSnapshot

职责：

- 冻结某次 workflow run 实际执行时使用的方案上下文；
- 解决“方案版本后来变了，历史结果无法解释”的问题。

建议字段：

- `run_id`
- `scheme_id`
- `scheme_version`
- `scheme_name`
- `scheme_snapshot_hash`
- `trade_date`
- `started_at`
- `finished_at`
- `workflow_name`
- `runtime_params`
- `effective_scheme_config`

### 4.4 SchemeResultLink

职责：

- 把方案运行结果与后续研究、交易、复盘链路挂接起来；
- 支撑方案级反馈统计。

建议字段：

- `run_id`
- `batch_id`
- `symbol`
- `scheme_id`
- `scheme_version`
- `scheme_snapshot_hash`
- `selection_bucket`
- `selection_rank`
- `selection_score`
- `factor_snapshot_dataset_version`
- `decision_snapshot_id`
- `trade_id`
- `review_id`

## 5. 模块落点

### 5.1 Schema 层

建议新增：

- `backend/app/schemas/screener_scheme.py`
- `backend/app/schemas/screener_scheme_stats.py`

现有 `screener.py` 中与运行请求强耦合的字段可保留，但新的方案对象不要继续堆进旧 schema 文件。

### 5.2 Service 层

建议新增：

- `backend/app/services/screener_service/scheme_service.py`
- `backend/app/services/screener_service/scheme_review_service.py`
- `backend/app/services/screener_service/scheme_hashing.py`

建议调整：

- `pipeline.py`
- `batch_service.py`
- `workflow_runtime` 相关接线

### 5.3 Storage 层

建议新增独立存储目录，风格与现有本地文件型持久化保持一致。

建议目录：

- `data/screener_schemes/`
- `data/screener_scheme_versions/`
- `data/screener_run_contexts/`
- `data/screener_scheme_links/`

如果现有项目已有更统一的数据目录规范，应保持同风格，不要并行造第二种落盘模式。

### 5.4 API 层

建议新增独立 route 文件：

- `backend/app/api/routes/screener_schemes.py`

不要继续把方案管理、运行、复盘统计全部塞到旧 `screener.py` 里。

## 6. 与现有流程的接入点

### 6.1 与 screener workflow 接入

运行入口保持现有 workflow 形态，但请求参数新增：

- `scheme_id`
- `scheme_version` 可选

接入规则：

- 如果未传方案，则走默认 builtin scheme
- 如果传 `scheme_id` 未传 `scheme_version`，则取该方案 `current_version`
- workflow 启动前就必须解析出完整方案配置并生成 `ScreenerRunContextSnapshot`

### 6.2 与 ScreenerPipeline 接入

`ScreenerPipeline` 不直接读取方案主对象，而只消费一份已经解析完成的 `scheme_context`。

`scheme_context` 至少包含：

- 启用的因子组
- 权重配置
- 阈值配置
- 质量门控配置
- 分桶配置

这样可以避免 pipeline 直接承担版本选择与存储读取职责。

### 6.3 与 batch / result 接入

`ScreenerBatchRecord` 和 `ScreenerSymbolResult` 在保存阶段必须附带：

- `scheme_id`
- `scheme_version`
- `scheme_snapshot_hash`

否则后续方案级复盘无法成立。

### 6.4 与 trade / review 接入

第一阶段不要求直接改动交易和复盘主表结构；优先通过 `SchemeResultLink` 做关联聚合。

如果后续要把方案信息进一步写入 `decision snapshot`，必须另立变更设计，不在本阶段强制推进。

## 7. 兼容与迁移规则

### 7.1 旧 workflow 兼容

旧 workflow 必须继续可用。

兼容策略：

- 默认自动挂到 `default_builtin_scheme`
- 历史结果可显示为：
  - `scheme_id = default_builtin_scheme`
  - `scheme_version = legacy_v1`

### 7.2 旧结果兼容

禁止因为旧批次缺少方案字段而中断读取。

历史结果读取时：

- 缺字段允许回填默认显示值
- 但不能伪造不存在的完整方案快照

## 8. 实施完成标准

具备以下条件，才算可以进入稳定前端开发：

1. 方案对象和版本对象可保存、可读取、可列出
2. workflow run 能绑定方案版本
3. batch / result 能带方案元信息
4. 有单独的运行时方案快照对象
5. 有方案级历史运行接口
6. 有基础方案级统计接口
7. 主链测试覆盖以上对象与流程

## 9. 对 Codex 的直接编码指引

后续如果要直接进入编码，优先顺序必须是：

1. 先实现 `screener_scheme` schema
2. 再实现 scheme storage / service
3. 再接 workflow run request
4. 再接 batch / result metadata
5. 再补 stats service
6. 最后再进入前端重构

如果缺少上述前置对象，不应先实现复杂前端交互。
