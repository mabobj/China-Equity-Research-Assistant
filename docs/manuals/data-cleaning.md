# Data 模块清洗层总结文档 v0.1

当前项目的 data 清洗层可以正式定义为三类核心输入对象的标准化层：

- `bars`
- `financial_summary`
- `announcements`

其中 `announcements` 已完成从 `provider/local raw -> 清洗 -> 结构化响应 -> research 消费` 的闭环验证。

## 1. 目标

data 清洗层不是“顺手洗一下数据”，而是把多个 provider 的原始结果统一为项目内部长期可复用对象，并显式暴露质量状态。

清洗层解决 5 件事：
- 标识统一
- 字段统一
- 类型与单位统一
- 业务合理性校验
- 质量状态可见化

## 2. 当前范围

### 2.1 `bars` 清洗层

统一字段：
- `symbol`
- `trade_date`
- `open/high/low/close`
- `volume`
- `amount`
- `source`

补充质量字段：
- `quality_status`
- `cleaning_warnings`
- `dropped_rows`
- `dropped_duplicate_rows`

已接入链路：
- `market_data_service.get_daily_bars`
- `technical snapshot`
- `screener`

### 2.2 `financial_summary` 清洗层

统一字段：
- `report_period`
- `report_type`
- `revenue`
- `revenue_yoy`
- `net_profit`
- `net_profit_yoy`
- `roe`
- `gross_margin`
- `debt_ratio`
- `eps`
- `bps`

补充质量字段：
- `quality_status`
- `missing_fields`
- `cleaning_warnings`

已接入链路：
- `market_data_service.get_stock_financial_summary`
- `financial_summary_daily`
- `research`

### 2.3 `announcements` 清洗层

统一字段：
- `title`
- `publish_date`
- `announcement_type`
- `source`
- `url`

补充质量字段：
- `quality_status`
- `cleaning_warnings`
- `dropped_rows`
- `dropped_duplicate_rows`
- `dedupe_key`

已接入链路：
- `market_data_service.get_stock_announcements`
- `research` 的事件输入

## 3. 统一设计原则

### 3.1 provider 只负责“取”

provider 层只负责：
- 请求第三方源
- 返回原始结果

provider 层不负责：
- 业务规则判断
- 质量分级
- 下游字段拼装

### 3.2 cleaner 负责“洗”

cleaning 层负责：
- `symbol/date` 规范化
- 字段映射
- 类型与单位归一
- 规则校验
- 质量分级
- warning 聚合

### 3.3 contract 负责“定义内部对象”

contracts 层负责项目内部标准对象定义，不允许下游直接消费 provider 原始字段名。

### 3.4 API 只返回清洗后对象

对外接口不直接暴露 provider 原始字段，而是返回统一 schema。

## 4. 质量状态定义

三层统一使用：
- `ok`
- `warning`
- `degraded`
- `failed`

含义：
- `ok`：核心字段齐全，结构可直接消费
- `warning`：少量缺失或轻微纠偏，整体可用
- `degraded`：核心字段缺失较多或不确定性较高，只能谨慎消费
- `failed`：无法形成可用对象

配套字段：
- `cleaning_warnings`
- `missing_fields`
- `coerced_fields`
- `provider_used`
- `fallback_applied`
- `fallback_reason`
- `source_mode`
- `freshness_mode`

## 5. 三类对象的项目内语义

### 5.1 `bars`

技术分析和选股的基础输入。重点是：
- 口径一致
- 单位一致
- 同日同票唯一
- 稳定支撑 `technical/screener`

### 5.2 `financial_summary`

基本面判断的基础输入。重点是：
- 报告期清晰
- 财务字段口径一致
- 缺失显式化
- 不误导 research 把低质量摘要当高质量数据

### 5.3 `announcements`

事件输入基础层。重点是：
- 标题可读
- 日期准确
- 粗分类可用
- 去重稳定
- 可被 `event_score/research` 安全消费

## 6. 当前主链路

当前 data 层统一模式：

`provider/local raw -> cleaner -> contract object -> local snapshot/data product -> API -> research/screener/technical`

这意味着 data 模块已经从“多源接入”升级为“内部标准层”。

## 7. 当前已完成价值

对 technical：
- `bars` 更稳定
- `volume` 口径统一
- technical snapshot 减少脏数据输入

对 screener：
- 技术输入更稳定
- 公告标题与分类可复用
- 评分与短理由可解释性增强
- 质量门控已接入分桶逻辑（如 `bars_quality=failed` 走失败占位，不参与高优先级候选）

对 research：
- 财务缺字段不再误判为高质量
- 事件输入可稳定消费公告索引
- `thesis/key_reasons/triggers` 证据链更清晰
- `quality_status` 已影响 `confidence` 与 `confidence_reasons`，实现“质量影响置信度、而非直接当利空”

## 8. 当前边界（必须坚持）

以下能力不应放入 cleaning 层：
- 技术指标计算
- LLM 摘要生成
- 策略打分逻辑
- 复杂事件推理
- 自动交易判断

cleaning 层职责始终是：

**让数据可靠，而不是让模型更聪明。**

## 9. 后续建议

### 9.1 已落地能力（质量消费）

当前已落地：
- `research` 会消费 `bars/financial/announcements` 质量状态，并修正 `confidence`
- `screener` 会消费三路质量状态，执行降权、分桶上限与失败占位
- 关键响应会暴露 `quality_status/cleaning_warnings/fallback` 相关字段供前端解释

### 9.2 下一步建议（不改清洗层边界）

建议继续完善：
- 在更多页面显式展示“质量影响说明”，降低用户误读
- 持续收敛 provider 失败时的提示文案，统一“无数据”与“降级”差异表达

### 9.3 持续维护本规范文档

本文件作为清洗层规范基线，后续新增对象时按同一结构补充：
- 对象契约
- 质量状态定义
- 字段口径约定
- 接入点
- 下游消费建议

## 10. 当前结论

到当前阶段，可以将本项目 data 模块定义为：

**A 股研究系统的数据输入标准层**

关键三块已完成：
- 量价输入标准化
- 财务摘要标准化
- 公告索引标准化

足以支撑后续更稳定推进：
- `review`
- `debate`
- `decision brief`
- `screener`
- `workflow`
