# 日常使用说明

这份文档按“先结论、再证据、后细节”的顺序，覆盖单票、选股、交易记录、复盘四条主操作链。

## 1. 单票分析（`/stocks/[symbol]`）

建议顺序：
1. 先看 `DecisionBrief`（结论与行动）
2. 再看证据区（看多证据 / 风险证据 / 来源提示）
3. 再看详细模块（factor/review/debate/strategy/trigger）

常用操作：
- 切换股票代码
- 刷新当前股票分析
- 勾选“debate-review 使用 LLM”
- 点击“保存本次判断”
- 填写最小表单后点击“记录交易”

说明：
- 单票页主数据来自 `workspace-bundle`
- 模块失败时页面会给出模块级失败提示，不会整页阻断

## 2. 选股工作台（`/screener`）

当前主流程是 workflow 提交 + 轮询，不再依赖同步长请求。

操作步骤：
1. 输入 `batch_size`
2. 点击“运行初筛工作流”
3. 页面拿到 `run_id` 后自动轮询 `GET /workflows/runs/{run_id}`
4. 查看运行步骤、最新批次摘要、结果表格
5. 点击股票代码跳转单票页
6. 如需更深分析，再运行 deep review workflow

结果查看：
- 表格主列：股票、分桶、评分、简述、计算时间、规则版本
- 详情区可看 quality 提示与 evidence hints

## 3. 保存判断与记录交易

入口一（单票页）：
- 点击“保存本次判断”创建 `decision_snapshot`
- 点击“记录交易”创建 `trade_record`（自动关联 snapshot）

入口二（交易页）：
- 在 `/trades` 填写最小字段创建交易记录
- 系统自动固化当前决策快照并绑定

动作约束：
- `SKIP` 允许不填价格和数量
- `BUY/SELL/ADD/REDUCE` 需要有效价格与数量

## 4. 交易记录页（`/trades`）

可做事项：
- 新建交易记录
- 按 symbol 过滤
- 查看交易列表
- 查看关联决策快照摘要（thesis/triggers/invalidations）

建议重点看：
- 决策动作与置信度
- 三路数据质量（bars/financial/announcements）
- 策略对齐状态（aligned/partially_aligned/not_aligned/unknown）

## 5. 复盘页（`/reviews`）

可做事项：
- 从交易记录一键生成复盘草稿
- 编辑 outcome/did_follow_plan/review_summary/lesson_tags
- 查看关联交易和关联决策快照

自动计算项：
- `holding_days`
- `MFE`（最大有利波动）
- `MAE`（最大不利波动）

若行情窗口数据不足：
- 指标留空
- 返回受控 warning，不抛底层异常

## 6. 规则版与 LLM 版怎么选

规则版：
- 稳定、可复现，适合日常主路径

LLM 版：
- 适合补充解释与观点表达
- 失败时会自动回退 rule-based，并在响应字段中明确可见

建议：
- 先看 `runtime_mode_requested/runtime_mode_effective`
- 再看 `fallback_applied/fallback_reason/warning_messages`

## 7. 每天最小闭环建议

1. 在 `/screener` 跑一批初筛
2. 打开候选的单票页看 `DecisionBrief`
3. 对值得跟踪的标的先“保存本次判断”
4. 需要执行时“记录交易”
5. 次日或退出后在 `/reviews` 生成并补全复盘

这样可以持续积累“当时判断 -> 执行动作 -> 复盘结果”的可追溯数据。
