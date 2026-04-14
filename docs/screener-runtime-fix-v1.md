# Screener Runtime Fix v1

## 背景

2026-04-14 晚间排查发现，选股工作台在运行初筛 workflow 时出现：

- 前端长时间无结果返回；
- 后端持续刷 `GET /workflows/runs/{run_id}`；
- 后端反复执行：
  - `prediction.features.build_done`
  - `prediction.labels.build_done`
- PowerShell 中反复出现 `login success! / logout success!`。

本专项文档用于记录这次修复的计划、落地结果和验收口径。

## 根因总结

### 1. 运行状态读接口带副作用

`GET /workflows/runs/{run_id}` 在构建 runtime visibility 时，会间接触发：

- `evaluation_service.get_model_evaluation()`
- `backtest_service`
- `label_service`
- `prediction_service`
- `dataset_service`

也就是说，前端轮询“读取运行状态”，实际上会触发特征/标签/评估链重算。

### 2. Label 构建逻辑与点时日线读取冲突

`LabelService.build_label_dataset()` 使用了按 `as_of_date` 截断的点时日线结果，却又要计算未来 5/10 日收益。

结果是：

- `label_version=... symbol_count=0`
- `warning_count` 很高

这不是偶发缺数据，而是 forward window 读取策略本身有问题。

### 3. 前端轮询存在重叠请求

`/screener` 页面当前采用固定间隔轮询，上一轮请求未返回时，下一轮请求仍可能继续发出。

在后端读接口本身很重的情况下，这会把同一个 `run_id` 打成请求风暴。

### 4. BaoStock stdout 放大了问题表象

`login success! / logout success!` 基本来自 BaoStock 库自身在 `login()/logout()` 时打印的 stdout。

真正的问题不是这两行日志本身，而是上面的重算链路让 BaoStock 被频繁调用。

## 修复计划

### 阶段 1：后端运行状态接口纯读取化

目标：

- `GET /workflows/runs/{run_id}` 不再触发评估、回测、特征、标签构建。

措施：

- `workflow_service` 的 runtime visibility 读取 recommendation 时只读缓存，不现场触发 `evaluation_service`。
- running 状态下直接跳过 model recommendation 解析。

### 阶段 2：修复 Label forward window

目标：

- label 构建时可正确读取未来窗口，不再用点时截断 bars 去算 future return。

措施：

- label 读取日线时，显式把 `end_date` 扩展到 `as_of_date + 20 days`。
- 继续保持 `allow_remote_sync=False`，避免在标签链上额外引入远端补数副作用。

### 阶段 3：前端轮询去重叠

目标：

- 同一页面对同一 `run_id` 不再产生重叠的 inflight 轮询请求。

措施：

- `useWorkflowPolling()` 增加 inflight guard。
- 上一轮未完成时，丢弃下一轮 interval tick。

## 已完成结果

### 已完成

- [x] 阶段 1：后端运行状态接口纯读取化
- [x] 阶段 2：修复 Label forward window
- [x] 阶段 3：前端轮询去重叠

## 代码落点

- `backend/app/services/workflow_runtime/workflow_service.py`
- `backend/app/services/label_service/label_service.py`
- `frontend/src/components/screener-workspace.tsx`
- `backend/tests/test_workflow_runtime_service.py`
- `backend/tests/test_point_in_time_policy.py`

## 验收标准

修复完成后，至少满足：

1. 轮询 `GET /workflows/runs/{run_id}` 不再触发 `prediction.features.build_done / prediction.labels.build_done`。
2. `labels-*.json` 构建不再普遍出现 `symbol_count=0 warning_count=400`。
3. 同一页面对同一 `run_id` 的请求数明显下降，不再出现同一秒十几次请求。
4. PowerShell 中的 `login/logout` 日志频率随之明显下降。

## 后续观察点

- 如果后续仍看到高频 `GET /workflows/runs/{run_id}`，需要继续检查是否有多页面/多标签页同时打开。
- 如果 label 仍然大量为空，需要继续检查本地 daily bars 覆盖范围是否满足 `as_of_date + 10` 的 forward window。
