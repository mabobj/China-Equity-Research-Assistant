# 稳定性审计 v1

审计日期：2026-03-26

审计目标：

1. 看当前结构是否清晰
2. 看当前健壮性是否足以支撑日常使用
3. 给出明确的后续问题清单

本次审计遵循当前阶段约束：

- 不引入新的核心业务能力
- 不做大规模重构
- 只记录问题与建议

## A. 结构审视

## 1. route 层是否足够薄

结论：

- 大体上是薄的
- `workflows.py`、`stocks.py`、`screener.py` 基本只做参数接收、依赖注入和响应返回
- 当前没有明显把复杂研究逻辑写进 route 的问题

观察到的点：

- `research.py` 和 `strategy.py` 仍保留旧入口
- `stocks/{symbol}/review-report`、`stocks/{symbol}/debate-review` 属于较新的 v2 主链路
- 路由层虽然不厚，但用户视角上的“主入口”存在双轨并行

影响：

- 前端和文档如果不主动收敛，很容易让人误以为 `research` 与 `review-report` 是同义接口

## 2. service 层是否边界清晰

结论：

- 主边界基本清晰
- `factor_service`、`review_service`、`debate_service`、`llm_debate_service`、`strategy_planner` 职责总体可分

观察到的点：

- `review_service` 和 `research_manager` 并存，容易让人误解“哪个才是单票研究主入口”
- `debate_service` 与 `llm_debate_service` 的关系是清晰的，但需要持续靠文档解释
- 单票与 workflow 都会复用同一批 service，这本身是对的，但也会引入重复调用和重复日志

## 3. workflow_runtime 是否只负责编排

结论：

- 是的，当前基本保持了“薄编排层”的边界
- 节点定义、执行器、上下文、artifact store 的分层也比较清楚

观察到的点：

- 当前 workflow 节点内部仍通过已有 service 自动补齐前置输入
- 这让 `start_from` 可用，但也意味着某些“从中间节点启动”的运行仍会触发额外服务调用

这不是设计错误，但需要明确：

- workflow runtime 不是纯函数式 DAG 引擎
- 它依赖下游 service 的补齐能力

## 4. 是否存在双向依赖或职责混乱

结论：

- 暂未发现明显双向 import 依赖
- 但存在“概念层面的命名重叠”

最容易混淆的地方：

- `research` vs `review`
- `reviews` 页面 / `review_service` / `review-report`
- `debate_service` vs `llm_debate_service`
- `workflow run record` vs 未来的 `reviews` 复盘记录

## 5. 哪些模块命名或职责容易引起误解

重点关注：

1. `research_manager`
   - 从名字上像“单票研究主入口”
   - 但当前前端主链路更适合使用 `review-report v2`
2. `/reviews`
   - 这个路由名容易让人以为“复盘记录已经存在”
   - 实际上当前只是占位
3. `debate-review`
   - 名称准确，但用户容易误把它理解成“自由文本智能总结”
   - 实际上它是固定 schema 的角色化裁决

## B. 健壮性审视

## 1. provider fallback 是否一致

结论：

- 总体设计方向是对的
- provider registry 与 capability-based 方式有利于降级

仍然存在的现实问题：

- 并不是所有 provider 降级都会在最终页面上明确显示“这次用了哪个 fallback”
- 部分模块失败时，用户更容易只看到“空结果”，而不是“为什么空”

建议：

- 后续逐步提升“结果中可见的来源与回退说明”

## 2. rule-based / llm fallback 是否一致

结论：

- 当前已经有清晰的一致性框架
- `runtime_mode` 能明确区分 `rule_based` 与 `llm`
- 火山方舟 provider 适配也已经独立拆层

仍需关注：

- 端到端的 fallback 仍比较依赖日志判断
- 前端虽然能展示 `runtime_mode`，但不会自动解释“为什么回退”

## 3. workflow 节点失败时是否有足够摘要

结论：

- 基本足够
- `run_id`、`step summaries`、`final_output_summary` 已经落地

不足之处：

- 对深筛 workflow 来说，个别 symbol 的失败已能记录，但前端没有把“失败 symbol 列表”做特别突出展示
- 对单票 workflow 来说，错误摘要够用，但如果失败来自下游 provider，用户仍需要回到日志继续排查

## 4. 前端错误状态是否统一

结论：

- 比之前明显更统一了
- 首页、单票页、选股页、workflow 面板都已经有 loading / error / empty state

仍然存在的点：

- 当前错误状态仍以模块内块状提示为主，没有统一的系统级错误模型
- 没有前端端到端测试来防止页面回归

## 5. 哪些地方还缺系统级场景测试

当前最缺的是：

1. “单票页全模块并行加载”的集成测试
2. “LLM 失败自动回退规则版”的端到端测试
3. “workflow 从中间节点启动”的接口级集成测试
4. “深筛 workflow 个别 symbol 失败但整体继续”的端到端测试
5. “前端代理超时配置”是否覆盖 workflow 的前后端联动测试

## 6. 哪些地方仍依赖手工判断

主要有：

1. LLM 是否值得开启
2. provider 空结果到底是“市场无数据”还是“provider 不可用”
3. 深筛结果为空时，是筛选太严还是上游数据不足
4. `research` 与 `review-report` 哪个更适合作为用户主入口

## C. 改进清单

## P0：必须尽快修

### 1. 统一对外主链路口径

问题：

- 当前 `research/{symbol}` 与 `stocks/{symbol}/review-report` 并存
- 对新用户来说，哪个是主链路并不天然清楚

建议：

- 明确文档和前端主入口以 `review-report v2 + debate-review + strategy plan` 为主
- 对旧接口做保留但弱化展示

### 2. 增加关键场景的系统级测试

问题：

- 当前单元测试与接口测试已不少，但对“前端工作台 + 后端组合链路”的场景覆盖仍不足

建议：

- 优先补关键 API 集成测试和少量页面级 smoke test

## P1：建议下一阶段修

### 1. 收敛命名与用户词汇

问题：

- `review`、`research`、`reviews`、`workflow record` 这几组概念很容易混淆

建议：

- 在路由、前端文案和文档里逐步统一术语

### 2. 减少 workflow 与直接页面加载的重复调用

问题：

- 当前单票工作台和 workflow 都会分别触发下游 service
- 某些链路会重复读取相同数据，导致日志冗长和响应偏慢

建议：

- 下一阶段评估是否可以在不破坏边界的前提下复用更多中间结果

### 3. 提升 fallback 可见性

问题：

- 当前很多 fallback 只在日志中清晰
- 页面层面能看见“结果”，但不一定看见“为什么降级”

建议：

- 后续逐步把 fallback 来源、provider 来源和降级原因结构化暴露

### 4. 增补前端回归测试

问题：

- 前端现在已经从“演示态”变成“工作台态”
- 但还缺针对关键交互的自动回归保护

建议：

- 后续为 API 封装、workflow 展示和关键视图摘要补少量前端测试

## P2：后续可优化

### 1. workflow run record 的检索体验

问题：

- 当前 run record 已经持久化，但仍以 `run_id` 查询为主

建议：

- 后续再考虑提供按 workflow_name / 日期 / symbol 的轻量检索

### 2. 前端的信息密度自适应

问题：

- 当前页面优先保证结构清晰
- 但移动端和窄屏下的信息密度仍偏高

建议：

- 后续可做更细的移动端信息折叠

### 3. 旧版组件与占位组件清理

问题：

- 项目里还保留了一些当前页面不再直接使用的组件或旧路径

建议：

- 后续做一轮非功能性整理，避免“能跑但让人困惑”的遗留文件继续增加

## 总结

当前系统已经从“能力堆叠阶段”进入“可用性与稳态阶段”。

结构上最大的优点是：

- 分层总体清楚
- workflow runtime 边界明确
- 前后端都已经开始围绕“单票工作台 / 选股工作台”收敛

当前最大的风险不在于缺少更多能力，而在于：

- 用户入口概念仍需继续统一
- fallback 可见性仍需提升
- 系统级场景测试还不够多

因此，下一阶段最应该做的不是继续扩能力，而是继续收敛口径、补关键场景测试、压低使用时的认知成本。
