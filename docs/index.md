# Docs Index

本文件用于整理 `docs/` 目录，明确哪些文档当前有效、哪些文档属于长期参考、哪些文档仅作为历史记录保留。

原则：

- 当前有效文档必须少而明确；
- 历史文档可以保留，但不应继续充当当前实现依据；
- 代理执行任务前，应先读 `AGENTS.md`、`docs/project-constraints.md`、`docs/execution-baseline.md`，再根据本索引进入当前有效文档。

## 1. 当前有效入口

以下文档当前有效，且应作为实现、重构、补测、联调时的主要依据。

### 1.1 规则与基线

- `AGENTS.md`
- `docs/project-constraints.md`
- `docs/execution-baseline.md`

### 1.2 当前因子优先初筛主线

- `docs/factor-first-screener-design-v1.md`
- `docs/taskbook-factor-first-screener-v1.md`
- `docs/factor-first-screener-implementation-spec-v1.md`
- `docs/factor-first-screener-api-storage-spec-v1.md`
- `docs/factor-first-screener-frontend-spec-v1.md`

## 2. 长期参考文档

以下文档描述长期方向、架构目标和因子体系全景，适合作为设计背景，但不直接替代当前有效需求与技术规格。

- `docs/architecture.md`
- `docs/roadmap.md`
- `docs/a_share_factor_prd_v1.md`
- `docs/a_share_architecture_design_spec_v1.md`
- `docs/a_share_factor_dictionary_v1.md`

## 3. 使用与运维文档

以下文档用于本地运行、排障、数据说明和日常使用，不承担当前需求与任务基线职责。

- `docs/provider-notes.md`
- `docs/manuals/quickstart.md`
- `docs/manuals/daily-usage.md`
- `docs/manuals/troubleshooting.md`
- `docs/manuals/data-cleaning.md`
- `docs/manuals/data-and-limitations.md`

## 4. 历史参考文档

以下文档保留作为历史阶段记录、专项阶段说明或旧任务拆解，不再作为当前实现依据。除非是在追溯历史决策或核对旧实现来源，否则不应优先阅读。

- `docs/current_phase.md`
- `docs/taskbook-v2.1.md`
- `docs/taskbook-v2.2.md`
- `docs/taskbook-screener-factors-v1.1.md`
- `docs/lineage-package-v1.md`
- `docs/screener-runtime-fix-v1.md`
- `docs/初筛因子体系设计文档_v1.1.md`
- `docs/初筛因子体系设计文档_v1md`

说明：

- 这些文档可以继续保留；
- 但如果其中内容与 `docs/execution-baseline.md` 或当前有效设计文档冲突，以当前有效文档为准；
- 后续若文档继续增多，应优先把“当前有效”保持在一个很小的集合内，而不是继续堆叠并列版本。

## 5. 维护规则

新增文档时必须明确归属：

- 当前有效
- 长期参考
- 使用与运维
- 历史参考

如果一个新文档被纳入“当前有效”，则必须同步更新：

- `docs/execution-baseline.md`
- 本索引

如果一个旧文档失效，则应：

- 从 `docs/execution-baseline.md` 的当前有效清单中移除；
- 在本索引中标记为历史参考或长期参考。
