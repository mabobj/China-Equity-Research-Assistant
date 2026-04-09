# Data 清洗层说明

这份文档说明当前项目里的 data 清洗层是什么、已经覆盖到哪里、以及它和长期因子主线之间的关系。

## 1. Data 清洗层是什么

data 清洗层不是“拿到 dataframe 以后顺手洗一下”，而是：

**把多个 provider 的原始结果，统一转换成项目内部可长期复用的标准对象，并显式暴露质量状态。**

它解决五件事：

- 标识统一
- 字段统一
- 类型与单位统一
- 业务合理性校验
- 质量状态可见化

## 2. 当前已落地对象

当前已经正式落地三类核心清洗对象：

- `bars`
- `financial_summary`
- `announcements`

## 3. 当前统一模式

统一链路是：

`provider/local raw -> cleaner -> contract object -> local snapshot/data product -> API -> downstream`

这意味着 data 模块已经不再只是“接了几个源”，而是已经开始成为内部标准层。

## 4. 三类对象的当前语义

### 4.1 `bars`

重点不是字段多，而是：

- 价格和成交量口径一致
- 同日同票唯一
- 可稳定服务 `technical / screener`

### 4.2 `financial_summary`

重点不是报表全，而是：

- 报告期清楚
- 字段口径一致
- 缺失显式化
- 不误导研究层把低质量摘要当高质量数据

### 4.3 `announcements`

重点不是理解正文，而是：

- 标题正常
- 日期准确
- 类型粗分类可用
- 去重稳定
- 可被研究层安全消费

## 5. 统一质量状态

当前三层统一使用：

- `ok`
- `warning`
- `degraded`
- `failed`

配套字段包括：

- `cleaning_warnings`
- `missing_fields`
- `coerced_fields`
- `provider_used`
- `fallback_applied`
- `fallback_reason`
- `source_mode`
- `freshness_mode`

## 6. 当前下游消费情况

### 对 `technical`

- `bars` 更稳定
- 成交量口径统一
- 技术快照减少脏输入

### 对 `research`

- `financial_summary` 不再把缺字段误判为高质量
- `announcements` 已能稳定作为事件输入
- `quality_status` 已影响 `confidence` 与 `confidence_reasons`

### 对 `screener`

- 技术输入更稳定
- 公告索引与财务质量已可被质量门控消费
- `bars_quality=failed` 会走失败占位，不再混入高优先级候选

## 7. 清洗层的边界

以下内容仍然不属于 cleaning 层：

- 技术指标计算
- LLM 摘要生成
- 策略打分逻辑
- 复杂事件推理
- 自动交易判断

cleaning 层的职责始终是：

**让数据可靠，而不是让模型更聪明。**

## 8. 从长期方向看，还要补什么

当前清洗层已经够支撑现有工作台，但距离长期因子主线仍有几项必须继续补的内容：

1. 进一步加强点时一致性
2. 把更多长期需要的数据域做成标准对象
3. 把复权、公司行为、交易状态继续纳入统一口径
4. 让数据血缘和重建能力更强

## 9. 当前结论

到当前阶段，可以把项目的 data 模块定义为：

**A 股研究、预测与决策系统的数据输入标准层。**

这是后续因子发现、验证、组合与监控系统的基础，而不是附属工具。
