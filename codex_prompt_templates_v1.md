# Codex 常用任务提示词模板包

## 文档目标

本文件用于沉淀一套适合当前项目的 **Codex 提示词模板**，帮助你在 Windows + Codex App 环境下，更稳定地推进项目开发。

原则：

- 任务边界清楚
- 先计划再实现
- 尽量让 Codex 一次只完成一个明确子任务
- 强制遵守项目文档与目录边界

---

# 一、通用任务模板

适用于大多数中等复杂度开发任务。

```text
先阅读：
- AGENTS.md
- docs/architecture.md
- docs/roadmap.md
- docs/current-phase.md

先输出计划：
1. 这次要改哪些文件
2. 新增哪些 schema / service / route / tests
3. 本轮明确不做什么
4. 如何验证

确认计划后再开始实现。

实现要求：
- 严格控制范围
- 先 schema，再 service，再 route，再 tests，再 README
- 不修改无关文件
- 不引入不必要的新依赖
- 保持实现简单、typed、可测试、可解释
- 严格遵守 AGENTS.md
```

---

# 二、后端 API 新功能模板

适用于新增单个 API 或一组紧密相关 API。

```text
先阅读：
- AGENTS.md
- docs/architecture.md
- docs/current-phase.md

现在实现一个新的后端能力。

请先输出计划：
1. 需要新增哪些 schema
2. 需要新增哪些 service
3. 需要新增哪些 route
4. 需要新增哪些 tests
5. README 需要补什么

然后再实现。

要求：
- 路由层只做入参和出参，不写复杂业务逻辑
- 业务逻辑放在 service 层
- 外部数据访问必须走 provider 层
- 返回 typed Pydantic schema
- 不直接返回 dataframe 或 provider 原始 dict
- 测试不要依赖实时外网
```

---

# 三、provider / 数据接入模板

适用于 AKShare、CNINFO、BaoStock 等 provider 扩展或修复。

```text
先阅读：
- AGENTS.md
- docs/architecture.md
- docs/current-phase.md
- docs/provider-notes.md（如果存在）

现在只处理 provider / data service 相关工作。

请先输出计划：
1. 涉及哪些 provider 文件
2. 是否需要补 normalize
3. 是否需要补 schema
4. 错误处理如何做
5. 如何做无外网测试

实现要求：
- 所有外部数据访问必须集中在 provider 层
- provider 异常不能直接泄漏到 API
- symbol/date/字段标准化必须集中处理
- 不要在 route 或 research 层散落 provider 逻辑
- 可以允许 graceful failure
- 测试优先 mock provider，不依赖实时外网
```

---

# 四、研究/策略模块模板

适用于 research_report、strategy_plan 等规则化聚合任务。

```text
先阅读：
- AGENTS.md
- docs/architecture.md
- docs/current-phase.md
- docs/a_share_factor_dictionary_v1.md（如果相关）

现在只实现 research / strategy 相关能力。

先输出计划：
1. 输入来源有哪些
2. 新增哪些中间结果 schema
3. 聚合逻辑放在哪些 service
4. 评分逻辑如何保持可解释
5. 测试如何覆盖

实现要求：
- 第一版使用规则和模板化输出
- 不调用 LLM
- 不写成长文
- 输出必须结构化
- 逻辑必须可解释、可测试
- 不要把 research / strategy 逻辑写进 route
```

---

# 五、选股器模板

适用于 screener、deep screener 等功能。

```text
先阅读：
- AGENTS.md
- docs/architecture.md
- docs/roadmap.md
- docs/current-phase.md

现在只处理 screener 相关工作。

先输出计划：
1. 是初筛还是深筛
2. 输入来源有哪些
3. schema 怎么定义
4. pipeline 怎么组织
5. 个股失败如何局部容错
6. 如何测试

实现要求：
- 全市场阶段必须轻量
- 深筛阶段只复用已有 research/strategy，不新增 provider
- 个股失败不能让全局扫描崩掉
- 输出必须适合后续前端接入
- 测试不要依赖实时外网
```

---

# 六、前端接入模板

适用于页面接 API、展示研究/策略/选股结果。

```text
先阅读：
- AGENTS.md
- docs/architecture.md
- docs/current-phase.md

现在只处理前端页面接入，不修改后端业务逻辑，除非确有必要并说明原因。

先输出计划：
1. 需要修改哪些页面
2. 需要新增哪些前端 types
3. 需要调用哪些 API
4. 空态、错误态、加载态怎么处理
5. 如何保证页面保持轻量

实现要求：
- 前端保持简单、清晰、可读
- 不引入复杂状态管理
- 优先展示结构化结果
- 不为视觉效果引入不必要复杂性
- 若后端 contract 不清晰，可先提出最小必要调整建议
```

---

# 七、测试补齐模板

适用于“功能已有，但测试不足”的场景。

```text
先阅读：
- AGENTS.md
- docs/current-phase.md

现在不要扩展功能，只补齐测试与必要的小修复。

先输出计划：
1. 哪些模块缺测试
2. 补哪些单元测试
3. 补哪些 API 测试
4. 是否需要 mock/stub
5. 是否需要修少量可测性问题

实现要求：
- 不改业务范围
- 不引入新功能
- 以单元测试和 API 测试为主
- 测试不要依赖实时外网
- 若需小修复，仅限于让现有功能更可测
```

---

# 八、文档同步模板

适用于代码完成后，让 Codex 补 README / docs。

```text
先阅读：
- AGENTS.md
- docs/architecture.md
- docs/roadmap.md
- docs/current-phase.md

现在只做文档同步，不改业务逻辑。

目标：
- 根据已经存在的代码更新 README 和相关 docs
- 补充新增 API、字段、运行方式、测试方式
- 确保文档与当前代码一致

要求：
- 不发明不存在的能力
- 不写与代码不一致的描述
- 保持文档简洁清晰
```

---

# 九、Bug 修复模板

适用于你已经发现具体问题，但不想让 Codex 顺手大改架构。

```text
先阅读：
- AGENTS.md
- docs/current-phase.md

现在只修复一个明确问题，不扩展功能。

问题描述：
[在这里写具体 bug]

先输出计划：
1. 可能涉及哪些文件
2. 根因猜测
3. 最小修复方案
4. 如何验证

要求：
- 只做最小修复
- 不顺手重构无关模块
- 如需重构，必须先说明原因
- 必须补回归测试
```

---

# 十、让 Codex 更稳的使用规则

## 1. 一次只给一个主要目标

不要这样：

- 同时接 provider
- 同时改前端
- 同时补文档
- 同时做策略与复盘

更好的做法是一次只给一个主目标。

## 2. 大任务先 plan

以下任务默认先 plan 再实现：

- 深筛选股器
- 交易记录与复盘
- 因子验证框架
- 前后端联调
- 新数据源接入

## 3. 明确写“不做什么”

这对 Codex 非常重要。

例如：

- 不做 LLM
- 不做前端
- 不做新 provider
- 不做定时任务

## 4. 强制验证方式

任务末尾最好加：

```text
完成后请说明：
1. 你运行了哪些测试
2. 哪些路径是 mock 验证
3. 哪些真实网络路径没有联调
```

这会让结果更可信。

## 5. 让 Codex 先列文件清单

对复杂任务，优先让它先说：

- 改哪些文件
- 新增哪些文件
- 不改哪些文件

这样你更容易控制范围。

---

# 十一、推荐的最小工作流

每次推进一个阶段时，建议你按这个顺序用 Codex：

1. 先发“计划模板”
2. 看计划是否越界
3. 再让它实现
4. 再让它补测试
5. 再让它同步 README/docs
6. 最后你把结果贴回 ChatGPT，让我帮你做产品/架构审查

这套流程最适合你现在的项目阶段。
