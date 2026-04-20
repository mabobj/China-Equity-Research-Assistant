# 因子优先初筛 API 与存储规格 v1

## 1. 文档目标

本文件定义第一阶段方案化初筛所需的：

- API 契约
- 存储结构
- 版本规则
- 哈希规则
- 迁移与兼容策略

它的作用是减少后端实现时的自由裁量空间，让 route、service、storage 和前端消费口径保持一致。

## 2. API 范围

第一阶段 API 分为四组：

1. 方案管理
2. 方案版本管理
3. 方案驱动运行
4. 方案历史与反馈统计

## 3. 方案管理 API

### 3.1 `GET /screener/schemes`

用途：

- 列出当前可用方案

返回要点：

- 轻量列表，不返回完整版本配置
- 包含当前激活版本摘要

每项最少字段：

- `scheme_id`
- `name`
- `description`
- `status`
- `current_version`
- `is_builtin`
- `is_default`
- `updated_at`

### 3.2 `POST /screener/schemes`

用途：

- 创建方案主对象

请求最少字段：

- `name`
- `description`
- `is_default` 可选

约束：

- 创建主对象不等于创建版本
- 首个版本应通过独立版本接口创建

### 3.3 `GET /screener/schemes/{scheme_id}`

用途：

- 查看单个方案详情

返回要点：

- 方案主对象
- 当前版本摘要
- 可选返回最近版本列表摘要

### 3.4 `PATCH /screener/schemes/{scheme_id}`

用途：

- 修改方案主对象元信息

允许修改：

- `name`
- `description`
- `status`
- `is_default`

不允许修改：

- 历史版本内容

## 4. 方案版本 API

### 4.1 `GET /screener/schemes/{scheme_id}/versions`

用途：

- 查看某方案的版本列表

每项最少字段：

- `scheme_version`
- `version_label`
- `created_at`
- `change_note`
- `snapshot_hash`

### 4.2 `POST /screener/schemes/{scheme_id}/versions`

用途：

- 创建新的方案版本

请求必须包含：

- `version_label`
- `change_note`
- `config`

`config` 最少包含：

- `universe_filter_config`
- `factor_selection_config`
- `factor_weight_config`
- `threshold_config`
- `quality_gate_config`
- `bucket_rule_config`

约束：

- 任何配置变更都必须创建新版本
- 不允许原地覆盖旧版本

### 4.3 `GET /screener/schemes/{scheme_id}/versions/{scheme_version}`

用途：

- 读取某个版本的完整配置

返回要点：

- 完整 `config`
- `snapshot_hash`
- `change_note`

## 5. 运行相关 API

### 5.1 复用现有 `POST /workflows/screener/run`

新增请求字段：

- `scheme_id` 可选
- `scheme_version` 可选

解析规则：

- 都不传：运行默认 builtin scheme
- 只传 `scheme_id`：运行该方案当前版本
- 两者都传：运行指定版本

返回中应新增：

- `scheme_id`
- `scheme_version`
- `scheme_name`
- `scheme_snapshot_hash`

### 5.2 `GET /workflows/runs/{run_id}`

返回中应新增方案摘要：

- `scheme_id`
- `scheme_version`
- `scheme_name`
- `scheme_snapshot_hash`

## 6. 方案统计 API

### 6.1 `GET /screener/schemes/{scheme_id}/runs`

用途：

- 查看某方案历史运行列表

每项最少字段：

- `run_id`
- `batch_id`
- `scheme_version`
- `trade_date`
- `started_at`
- `status`
- `candidate_count`
- `top_bucket_summary`

### 6.2 `GET /screener/schemes/{scheme_id}/stats`

用途：

- 查看某方案基础统计摘要

最少字段：

- `total_runs`
- `total_candidates`
- `bucket_counts`
- `entered_research_count`
- `decision_snapshot_count`
- `trade_count`
- `review_count`

### 6.3 `GET /screener/schemes/{scheme_id}/feedback`

用途：

- 查看某方案反馈聚合

最少字段：

- `review_outcome_distribution`
- `trade_conversion_rate`
- `research_conversion_rate`
- `version_breakdown`

## 7. 存储结构

第一阶段建议继续沿用现有本地持久化风格，优先简单稳定。

建议目录：

- `data/screener_schemes/{scheme_id}.json`
- `data/screener_scheme_versions/{scheme_id}/{scheme_version}.json`
- `data/screener_run_contexts/{run_id}.json`
- `data/screener_scheme_links/{run_id}.json`

## 8. 文件内容规范

### 8.1 `screener_schemes`

保存主对象元信息：

- `scheme_id`
- `name`
- `description`
- `status`
- `current_version`
- `is_builtin`
- `is_default`
- `created_at`
- `updated_at`

### 8.2 `screener_scheme_versions`

保存完整版本内容：

- `scheme_id`
- `scheme_version`
- `version_label`
- `change_note`
- `created_at`
- `snapshot_hash`
- `config`

### 8.3 `screener_run_contexts`

保存运行时冻结快照：

- `run_id`
- `scheme_id`
- `scheme_version`
- `scheme_snapshot_hash`
- `effective_scheme_config`
- `runtime_params`
- `trade_date`

### 8.4 `screener_scheme_links`

保存结果关联信息：

- `run_id`
- `batch_id`
- `symbols`
- 每个 symbol 的关联字段：
  - `scheme_id`
  - `scheme_version`
  - `selection_bucket`
  - `selection_score`
  - `decision_snapshot_id`
  - `trade_id`
  - `review_id`

## 9. 版本规则

### 9.1 版本递增

建议使用单方案内递增整数版本：

- `v1`
- `v2`
- `v3`

禁止使用“覆盖旧版本内容但不升版”的方式。

### 9.2 哪些修改必须升版

以下任意一项变化都必须升版：

- 因子集合变化
- 权重变化
- 阈值变化
- 质量门控变化
- 分桶规则变化
- universe filter 变化

### 9.3 哪些修改不必升版

以下只改主对象，不必新建版本：

- 方案名称
- 方案描述
- 状态切换

## 10. 哈希规则

### 10.1 `snapshot_hash`

必须基于版本配置稳定生成。

建议输入：

- 标准化后的 `config`
- 排序后的字段
- 固定 JSON 序列化规则

禁止把时间戳之类运行时字段混进版本哈希。

### 10.2 `scheme_snapshot_hash`

运行时快照哈希应至少包含：

- `scheme_id`
- `scheme_version`
- `snapshot_hash`
- `runtime_params` 中会影响结果的字段

这样才能区分“同一版本，不同运行上下文”。

## 11. 迁移策略

### 11.1 历史批次

历史批次没有方案字段时：

- 前端显示为 `default_builtin_scheme`
- 版本显示为 `legacy_v1`

### 11.2 历史结果

允许只补显示元信息，不强行回填完整运行时快照。

### 11.3 新旧共存

第一阶段允许：

- 旧入口继续跑
- 新方案入口逐步接管

但新产生的数据必须完整写入方案元信息。

## 12. 验收口径

以下条件满足后，API 与存储层才算完成：

1. 能创建方案与多版本
2. 能从 workflow run 显式看到方案版本
3. 能在 batch / result 看到方案元信息
4. 能读取运行时方案快照
5. 能按方案读取历史 runs
6. 能按方案读取基础 stats / feedback
7. 旧批次不会因为缺少方案字段而报错
