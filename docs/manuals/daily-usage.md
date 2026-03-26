# 日常使用说明

这份文档面向已经能跑通项目、准备开始日常使用的人。

## 1. 如何做单票分析

推荐入口：

- 首页输入股票代码
- 或直接打开 `/stocks/[symbol]`

### 单票页的推荐阅读顺序

1. 股票基础信息
   - 看名称、交易所、行业、上市日期、数据源
2. Factor Snapshot 摘要
   - 先看 `alpha / trigger / risk`
   - 再看偏强因子组和偏弱因子组
3. Review Report v2
   - 看 `final_judgement`
   - 看技术、基本面、事件、情绪四个视角的摘要
4. Debate Review
   - 看当前是 `rule_based` 还是 `llm`
   - 看首席裁决、四类分析员观点和执行提醒
5. Strategy Plan
   - 看动作、入场区间、止损、止盈和持有规则
6. Trigger Snapshot
   - 用来判断当前触发位置是否接近预期

### 页面上的常用操作

- `切换股票`
- `刷新当前股票分析`
- `debate-review 使用 LLM`

其中：

- 如果只是看稳定结果，优先用 `rule_based`
- 如果你需要更强的解释性综合判断，再打开 LLM

## 2. 如何跑选股

推荐入口：

- `/screener`

### 推荐顺序

1. 先看是否需要 `数据补全`
2. 运行 `规则初筛`
3. 按 v2 分桶看候选
4. 再运行 `深筛`

### 当前主展示分桶

- `READY_TO_BUY`
- `WATCH_PULLBACK`
- `WATCH_BREAKOUT`
- `RESEARCH_ONLY`
- `AVOID`

说明：

- 页面主展示字段是 `v2_list_type`
- 旧字段 `list_type` 只保留兼容说明

### 看到候选后怎么做

每个候选项都支持点击进入单票页。

推荐做法：

1. 先在选股页缩小范围
2. 对重点候选点击进入单票页
3. 在单票页继续看 review / debate / strategy

## 3. 如何看 debate-review

`debate-review` 不是自由聊天结果，而是受控的角色化裁决输出。

建议重点关注：

1. `runtime_mode`
   - `rule_based`
   - `llm`
2. `final_action`
3. `chief_judgement.summary`
4. 四类分析员的谨慎点
5. `risk_review.execution_reminders`

### 什么时候看 rule-based 版

适合：

- 要稳定结果
- 要排查 schema 和 provider 问题
- 当前 LLM 不可用

### 什么时候看 LLM 版

适合：

- 想看多角色综合表达是否更顺手
- 想辅助阅读 review-service 的结构化结果

不适合：

- 把 LLM 输出当成唯一决策来源
- 用自由文本替代规则与分数

## 4. 如何跑 workflow

当前有两个 workflow。

### 单票 workflow

入口：

- 单票页里的 `单票 Workflow`

名称：

- `single_stock_full_review`

支持参数：

- `symbol`
- `start_from`
- `stop_after`
- `use_llm`

### 深筛 workflow

入口：

- 选股页里的 `Deep Review Workflow`

名称：

- `deep_candidate_review`

支持参数：

- `max_symbols`
- `top_n`
- `deep_top_k`
- `start_from`
- `stop_after`
- `use_llm`

## 5. 如何理解 `start_from` / `stop_after`

### `start_from`

表示从哪个节点开始正式执行。

例如：

- 在单票 workflow 里选择 `DebateReviewBuild`
- 这表示前面的节点不会被记为“本次已执行完成”
- 但内部 service 仍可能自动补齐必要输入

### `stop_after`

表示执行到哪个节点后停止。

例如：

- 在 deep review workflow 里选择 `CandidateReviewBuild`
- 这表示后面的 debate / strategy 节点不会继续执行

## 6. 如何查看 workflow 运行记录

你有三种方式。

### A. 页面内直接查看

workflow 执行完成后，页面会直接展示：

- `run_id`
- 步骤摘要
- 最终输出摘要

### B. 按 `run_id` 回查

单票页和选股页都支持输入 `run_id` 回查记录。

### C. 直接看本地 artifacts

运行记录文件在：

```text
data/workflow_runs/{run_id}.json
```

如果你需要排查某次 workflow 是否中途失败，优先看这个文件和后端日志。

## 7. 当前规则版与 LLM 版的区别

### 规则版

特点：

- 更稳定
- 更容易复现
- 没有外部 LLM 依赖
- 适合作为兜底基线

### LLM 版

特点：

- 解释性通常更自然
- 更适合多视角摘要整合
- 依赖 provider、网络、超时和 schema 校验
- 失败时会自动回退到规则版

### 实际建议

日常建议：

1. 先确保规则版链路可用
2. 再把 LLM 当作增强层，而不是基础依赖

## 8. 什么时候应该看日志

如果出现下面这些情况，直接看日志比盯着页面更快：

- 页面只显示“加载失败”
- debate-review 明明设置了 `use_llm=true` 却返回规则版
- workflow 某个节点失败
- provider 结果为空或明显异常

日志默认位置：

```text
logs/backend-debug.log
```

## 9. DecisionBrief 的推荐用法

`DecisionBrief` 是当前系统新的主输出层，适合当作单票分析和候选跟踪的第一阅读入口。

推荐顺序：

1. 先看 `DecisionBrief`
   - 看一句话结论 `headline_verdict`
   - 看当前动作 `action_now`
   - 看 `what_to_do_next`
   - 看 `next_review_window`
2. 再看证据层
   - `why_it_made_the_list`
   - `why_not_all_in`
   - `key_evidence`
   - `key_risks`
   - `price_levels_to_watch`
3. 最后再看详细模块
   - `factor snapshot`
   - `review-report v2`
   - `debate-review`
   - `strategy plan`
   - `trigger snapshot`

这意味着：

- 单票页先给出结论和动作，再下沉详细模块
- 选股页先给出候选的一句话判断和动作建议，再进入单票页深看
- `review / debate / strategy / factor` 仍然保留，但它们现在主要承担“依据层”角色
