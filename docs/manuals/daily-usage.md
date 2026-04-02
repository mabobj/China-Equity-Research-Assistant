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

判断口径说明（重要）：
- 页面会同时展示两层信息：
  - 方向基线（用于一致性校验）
  - 执行动作（时机层，来自 `decision_brief.action_now`）
- 当前一致性校验优先使用“方向基线”，并在页面显示来源（决策简报映射或 review-report 回退）。
- 若页面提示“结论口径不一致”，表示方向层与时机层表达角度不同，不等于系统报错。

说明：
- 单票页主数据来自 `workspace-bundle`
- 模块失败时页面会给出模块级失败提示，不会整页阻断

## 2. 选股工作台（`/screener`）

当前主流程是 workflow 提交 + 轮询，不再依赖同步长请求。

操作步骤：
1. 先看“当前展示窗口”与“最新批次摘要”，确认今天已有结果
2. 若需继续扫描，再输入 `batch_size` 并点击“运行初筛工作流”
3. 页面拿到 `run_id` 后自动轮询 `GET /workflows/runs/{run_id}`
4. 在结果表按列筛选，点击股票代码查看详情并跳转单票页
5. 如需更深分析，再展开“高级操作”运行 deep review workflow

结果查看：
- 表格主列：股票、分桶、评分、预测分、简述、计算时间、规则版本
- 详情区可看 quality 提示、evidence hints、预测置信度与模型版本
- 深筛候选卡片会同步展示预测分与预测模型版本，便于二次筛选时对照优先级。
- “分桶分布概览”可快速判断当前窗口里可买/观察/研究/回避的数量结构
- “重置游标”和“深筛参数”已下沉到“高级操作”，主路径不再默认展示

## 3. 保存判断与记录交易

入口一（单票页）：
- 点击“保存本次判断”创建 `decision_snapshot`
- 点击“记录交易”创建 `trade_record`（自动关联 snapshot）

入口二（交易页）：
- 在 `/trades` 填写最小字段创建交易记录
- 系统自动固化当前决策快照并绑定
- 高级区会提示“动作与原因类型”是否匹配，并提供“人工覆盖原因”模板按钮

动作约束：
- `SKIP` 允许不填价格和数量
- `BUY/SELL/ADD/REDUCE` 需要有效价格与数量
- `reason_type` 需要与动作匹配（如 `watch_only` 仅用于 `SKIP`）
- 若交易与方向基线冲突：
  - 默认记为 `not_aligned`
  - 若手动指定 `aligned/partially_aligned`，必须填写“人工覆盖原因（alignment_override_reason）”

## 4. 交易记录页（`/trades`）

可做事项：
- 快速记录交易（默认仅填股票、动作，必要时补价格/数量）
- 按 symbol 过滤
- 查看交易列表
- 查看关联决策快照摘要（thesis/triggers/invalidations）

建议重点看：
- 决策动作与置信度
- 预测分、预测置信度、预测模型版本
- 三路数据质量（bars/financial/announcements）
- 策略对齐状态（aligned/partially_aligned/not_aligned/unknown）
- 高级参数（原因类型、人工覆盖原因、LLM 上下文）已下沉到折叠区

## 5. 复盘页（`/reviews`）

可做事项：
- 从“待复盘交易”一键生成复盘草稿
- 编辑 outcome/did_follow_plan/review_summary/lesson_tags
- 查看“复盘对照视图”：原判断快照、执行路径、复盘结论同屏对照
- 查看“偏差诊断摘要”：系统自动归纳偏差等级、诊断要点与下一步建议
- 在“原判断快照”中查看当时的预测分与模型版本，避免事后只看主观结论

一致性提示：
- 当关联交易为 `not_aligned` 时，系统会对 `did_follow_plan=yes` 做自动纠偏并写入 warning。
- 复盘里看到 `did_follow_plan` 被调整，优先以“交易对齐状态 + warning_messages”理解原因。

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
## 预测底座（v2.1）日常使用

当前可用入口（最小可用版）：

1. 构建特征数据集  
接口：`POST /datasets/features/build`  
建议参数：`{ "max_symbols": 300 }`  
说明：按交易日构建 point-in-time 特征并落盘。

2. 构建标签数据集  
接口：`POST /datasets/labels/build`  
建议参数：`{ "max_symbols": 300 }`  
说明：基于未来 5/10 交易日收益构建标签。

3. 查看单票预测快照  
接口：`GET /predictions/{symbol}`  
说明：返回 baseline 预测分、置信度与版本信息。

4. 运行截面预测  
接口：`POST /predictions/cross-section/run`  
建议参数：`{ "max_symbols": 500, "top_k": 30 }`  
说明：输出预测候选列表，可作为选股辅助输入。

5. 运行回测与评估  
- 选股回测：`POST /backtests/screener/run`  
- 策略回测：`POST /backtests/strategy/run`  
- 模型评估：`GET /evaluations/models/{model_version}`

注意：
- 当前为最小可用预测链路，主要用于联调和流程验证。
- 单票页已展示“预测快照（辅助）”，选股页已展示“预测分/预测模型版本”。
- 预测结果不替代现有质量门控与研究解释链。
