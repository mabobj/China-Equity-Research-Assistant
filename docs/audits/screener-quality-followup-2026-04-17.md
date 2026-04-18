# 初筛质量与展示对齐跟踪

日期：2026-04-17

## 1. 背景

在本轮初筛因子体系工程化之后，初筛结果页中个股详细卡片普遍出现：

- `财务质量 = warning`

同时，需要确认以下三个问题：

1. 初筛筛选逻辑是否已经改变
2. 个股展示信息是否需要同步调整
3. 财务质量显示为 `warning` 是否属于当前口径下的正常现象

## 2. 当前结论

### 2.1 初筛逻辑已经发生实质变化

当前 `ScreenerPipeline` 已默认接入：

- `ScreenerFactorService`
- `CrossSectionFactorService`
- `ScreenerFactorSnapshotDailyDataset`

因此主链路已不再只是旧版 `technical_snapshot / factor_snapshot` 的简单评分，而是：

1. 日线数据构建 `ScreenerFactorSnapshot`
2. 批量补充横截面与连续性因子
3. 基于 `score_screener_factor_snapshot()` 生成新的 alpha / trigger / risk / list_type
4. 叠加 `quality gate`
5. 将结果落袋到：
   - `screener_factor_snapshot_daily`
   - `screener_selection_snapshot_daily`

结论：本轮初筛不是“只调参数”，而是已经切入新的因子化初筛逻辑。

### 2.2 财务质量 `warning` 在当前规则下是正常现象

当前财务质量判断规则较保守：

- 只要存在 `missing_fields` 或 `warnings`，就可能返回 `warning`
- 例如：
  - `unknown_report_type`
  - 范围异常
  - provider 间不一致警告
  - 清洗阶段补充出的缺失字段

同时，初筛质量门控对 `financial_quality=warning` 的处理是：

- 不直接降级候选分桶
- 只通过组合权重参与轻微评分折损

只有在以下情况下才会触发更强动作：

- `financial_quality in {"degraded", "failed"}`

因此：

- 结果页里大量看到 `warning`，不等于系统异常
- 更接近“数据存在轻微不完美，但仍允许进入初筛候选”

### 2.3 当前展示口径与新逻辑存在轻度错位

当前初筛结果页详细卡片直接展示：

- `行情质量`
- `财务质量`
- `公告质量`
- `质量折损`

但没有把以下信息清楚表达出来：

1. `warning` 与 `degraded/failed` 的业务差异
2. 本次候选是否因为质量门控被降级
3. 当前分桶是原始因子结果，还是质量门控后的结果
4. `quality_note` 与 `quality_flags` 的结构化来由

此外，单票工作台当前并未直接消费：

- `selection_decision`
- `composite_score`
- `quality_note`
- `quality_penalty_applied`

因此用户在 `/screener` 看到的新初筛语义，进入 `/stocks/[symbol]` 后未必能看到对应解释。

## 3. 影响判断

## 3.1 对筛选结果的影响

本轮之后，初筛结果已经受到以下新逻辑影响：

- 原子因子
- 横截面因子
- 连续性因子
- 新的 `v2_list_type`
- 质量门控折损

这意味着候选排序、分桶、简述文案都可能与旧版不同。

## 3.2 对用户认知的影响

如果页面只展示 `财务质量=warning`，但不解释其含义，用户容易误判为：

- 财务数据有严重问题
- 初筛结果不可信
- 本轮因子调整把财务链路“调坏了”

实际上当前更准确的解释应是：

- `warning` 表示“存在轻度质量提示”
- 并不等于“不能看”或“不能进入候选”
- 是否真正影响候选优先级，要看 `quality_penalty_applied` 和 `quality_note`

## 4. 待优化项

### P1：补充质量状态语义说明

在初筛结果页明确说明：

- `ok`：数据完整且无明显警告
- `warning`：有轻微缺失/异常/口径提示，但仍可参与候选排序
- `degraded`：质量明显不足，候选应降级使用
- `failed`：该数据域不可用于当前候选判断

### P1：突出“是否真的影响了候选结果”

结果页应优先展示：

- 是否应用 `quality_penalty_applied`
- `quality_note`

而不是只把 `financial_quality` 当成单独标签裸展示。

### P1：区分“原始分桶”与“质量门控后分桶”

建议在结果详情中增加可解释字段，例如：

- 原始候选类型
- 门控后候选类型
- 原始评分
- 门控后评分

这样可以回答：

- 是因子逻辑把它筛到这个位置
- 还是质量门控把它从更高优先级降下来了

### P2：单票页与初筛语义对齐

建议后续让 `/stocks/[symbol]` 能消费或展示以下信息：

- 最近一次 `screener_factor_snapshot_daily`
- `selection_decision`
- `composite_score`
- `quality_note`

让单票页和初筛页在“为什么入选/为何被降级”上保持一致。

### P2：优化财务质量的展示文案

当前页面显示“财务质量：warning”过于技术化。

建议改成更接近用户理解的表达，例如：

- 财务质量：轻微警告
- 财务质量：可用但有提示

并支持展开查看具体 `warning_messages / missing_fields`。

### P2：评估是否需要重新校准财务质量阈值

如果生产使用中大量股票长期稳定落在 `warning`，后续应评估：

- 当前 `warning` 是否过宽
- 哪些 warning 是“结构性常态”，不应持续占用用户注意力
- 是否需要把“展示警告”与“门控警告”拆层

## 5. 当前建议

当前先不建议把“财务质量 warning 多”直接当作 bug 去修。

更合理的顺序是：

1. 先承认初筛逻辑已升级
2. 先把页面解释口径补齐
3. 再用实际样本统计判断财务质量阈值是否过严

## 6. 一句话结论

这轮之后，初筛逻辑已经变了；`财务质量=warning` 在当前规则下通常是正常现象；真正需要优先优化的不是立刻改筛选代码，而是把“质量状态、质量门控、候选分桶”之间的关系在页面上解释清楚。
