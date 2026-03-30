# 日常使用说明

这份文档面向已经跑通系统的日常使用场景，目标是“先看结论、再看证据、最后看细节”。

## 1. 单票分析怎么用

推荐入口：
- 首页输入股票代码
- 或直接访问 `/stocks/[symbol]`

推荐阅读顺序：
1. `DecisionBrief`（一句话结论 + 当前动作）
2. 证据层（看多证据 / 风险证据 / 来源提示）
3. 行动层（观察位、止损、复盘窗口）
4. 详细模块（factor / review / debate / strategy / trigger）

页面常用操作：
- 切换股票
- 刷新当前股票分析
- `debate-review 使用 LLM`

## 2. 如何看 workspace-bundle

单票页主链路已经切到：
- `GET /stocks/{symbol}/workspace-bundle`

它一次返回：
- `profile`
- `factor_snapshot`
- `review_report`
- `debate_review`
- `strategy_plan`
- `trigger_snapshot`
- `decision_brief`
- `module_status_summary`
- `evidence_manifest`
- `freshness_summary`

解释规则：
- 某个子模块失败时，bundle 仍可 `200` 返回。
- 看 `module_status_summary` 判断失败模块和原因摘要。

## 3. debate-review 怎么看

重点看：
1. `runtime_mode_requested` / `runtime_mode_effective`
2. `fallback_applied` / `fallback_reason`
3. `final_action`
4. `chief_judgement.summary`

建议：
- 日常先看规则版（稳定、可复现）。
- LLM 作为增强层，不作为唯一决策源。

## 4. 选股工作台（/screener）怎么跑

当前主链路是 workflow，不再用同步长请求当主路径。

推荐顺序：
1. 输入 `batch_size`（本批次计算股票数量）
2. 提交 `POST /workflows/screener/run`
3. 页面拿到 `run_id` 后轮询 `GET /workflows/runs/{run_id}`
4. 查看“运行状态 + 最新批次摘要 + 批次结果表”
5. 点击股票代码查看单股详情
6. 如需深筛，再运行 `deep_candidate_review`

关键行为：
- 同时只允许一个 `screener_run` 运行（互斥）。
- 每次只处理游标窗口内的 `batch_size` 支股票。
- 17:00 后首次触发会自动重置游标。
- 结果按展示窗口聚合，默认每只股票显示最新一条。

## 5. 如何查看批次与运行记录

workflow 记录：
- 页面里看 `run_id`、步骤摘要、最终摘要
- 后端查 `GET /workflows/runs/{run_id}`
- 本地看 `data/workflow_runs/{run_id}.json`

初筛批次结果：
- `GET /screener/latest-batch`
- `GET /screener/batches/{batch_id}`
- `GET /screener/batches/{batch_id}/results`
- `GET /screener/batches/{batch_id}/results/{symbol}`

## 6. 如何判断数据质量与可用性

财务摘要与公告列表已经接入清洗层，优先看这些字段：
- `quality_status`
- `cleaning_warnings`
- `provider_used`
- `source_mode`
- `freshness_mode`

财务额外关注：
- `report_type`
- `missing_fields`

公告额外关注：
- `dropped_rows`
- `dropped_duplicate_rows`
- `dedupe_key`
- `announcement_type`

## 7. freshness 怎么理解

默认策略：
- 使用最后一个已收盘交易日
- 本地同日快照优先复用
- 仅在缺失/过期或 `force_refresh=true` 时重算

重点字段：
- `as_of_date`
- `freshness_mode`
- `source_mode`

## 8. 规则版与 LLM 版的边界

规则版负责：
- 指标计算
- 规则筛选
- 风险边界和价格条件

LLM 版负责：
- 解释和归纳
- 多视角文字整合

不要把确定性计算交给 LLM。
