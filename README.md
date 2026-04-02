# A 股研究助手

面向中国大陆 A 股市场的单用户研究与决策工作台。当前强调“稳定、可解释、可追溯”，不做自动实盘交易。

## 当前能力

- 单票工作台（`/stocks/[symbol]`）
- 选股与深筛工作流（`/screener`）
- 结构化研究输出：`review-report v2`、`debate-review`、`strategy plan`、`decision brief`
- workflow 运行记录与轮询查看
- 初筛批次台账与结果回看（17:00 展示窗口口径）
- 数据清洗层（bars / financial_summary / announcements）
- 交易与复盘最小闭环（`decision snapshot -> trade -> review`）

## 主入口

- 单票主入口：`GET /stocks/{symbol}/workspace-bundle`
- 选股主入口：`POST /workflows/screener/run` + `GET /workflows/runs/{run_id}`
- 深筛主入口：`POST /workflows/deep-review/run` + `GET /workflows/runs/{run_id}`

兼容保留但非前端主路径：
- `GET /screener/run`
- `GET /screener/deep-run`

## 交易与复盘闭环（v0.1）

后端新增接口：
- `POST /decision-snapshots`
- `GET /decision-snapshots/{snapshot_id}`
- `GET /decision-snapshots?symbol=...&limit=...`
- `POST /trades`
- `GET /trades`
- `GET /trades/{trade_id}`
- `PATCH /trades/{trade_id}`
- `POST /trades/from-current-decision`
- `POST /reviews`
- `GET /reviews`
- `GET /reviews/{review_id}`
- `PATCH /reviews/{review_id}`
- `POST /reviews/from-trade/{trade_id}`

前端入口：
- `/stocks/[symbol]`：保存本次判断、记录交易
- `/trades`：快速记录交易（高级参数折叠）、按股票过滤、查看关联快照摘要
- `/trades`：支持动作-原因类型智能匹配提示与人工覆盖原因模板，减少录入冲突
- `/reviews`：待复盘交易优先、一键生成复盘草稿，并在“原判断快照 / 执行路径 / 复盘结论 / 偏差诊断摘要”对照视图中完成复盘

持久化：
- SQLite：`data/trade_review.sqlite3`
- 表：`decision_snapshots`、`trade_records`、`review_records`

规则要点：
- `SKIP` 允许 `price/quantity/amount` 为空
- 复盘草稿默认自动计算 `holding_days/MFE/MAE`（行情不足时返回受控 warning）
- 决策快照记录 `runtime_mode_requested/effective` 与数据质量摘要
- 决策快照同步记录预测元数据（`predictive_score/predictive_confidence/model_version/feature_version/label_version`），用于后续复盘对照

## 交易一致性校验口径（2026-04）

为避免“同一只股票出现两套冲突结论”导致执行混乱，当前系统对交易一致性采用以下统一口径：

- 方向基线（用于 `strategy_alignment` 推断）按优先级确定：
  1. `decision_brief.action_now`（映射为 `BUY/WATCH/AVOID`）
  2. `review_report.final_judgement.action`
  3. `research.action`
- 若交易动作与方向基线冲突：
  - 系统默认判为 `not_aligned`
  - 若仍需手动指定 `aligned/partially_aligned`，必须提供 `alignment_override_reason`
- `reason_type` 与 `side` 必须匹配（如 `watch_only` 仅用于 `SKIP`，`stop_loss/take_profit` 仅用于 `SELL/REDUCE`）
- 复盘 `did_follow_plan` 会与交易对齐状态联动校正，避免“交易不一致但复盘写 yes”的语义冲突

## 数据清洗层（v0.1）

统一链路：
`provider/local raw -> cleaning contracts -> market_data_service -> data products -> API`

已落地对象：
- bars 清洗
- financial_summary 清洗
- announcements 清洗（索引层）

质量字段统一口径：
- `quality_status`: `ok | warning | degraded | failed`
- `cleaning_warnings`
- `missing_fields`（适用时）
- `provider_used` / `fallback_applied` / `fallback_reason`

## 本地启动

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
Set-Location frontend
npm install
Set-Location ..
```

启动后端：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_backend.ps1
```

启动前端：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_frontend.ps1
```

默认地址：
- 后端健康检查：[http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- 后端文档：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- 前端页面：[http://127.0.0.1:3000](http://127.0.0.1:3000)

## 测试命令

后端关键回归：

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest backend/tests/test_stocks_api.py backend/tests/test_workflow_api.py backend/tests/test_trade_review_store.py backend/tests/test_trade_review_api.py -q
# 预测/回测/workflow 关键回归
python -m pytest backend/tests/test_prediction_pipeline_services.py backend/tests/test_prediction_api.py backend/tests/test_workflow_runtime_service.py -q
```

前端检查：

```powershell
Set-Location frontend
npm.cmd run type-check
npm.cmd run lint
npm.cmd run test:smoke
```

## 文档导航

- [项目任务书 v2.1（产品化增强版）](docs/taskbook-v2.1.md)
  - 说明：v2.1 任务书交付包共 6 个；文档中的 1~10 为章节编号。
- [系统架构](docs/architecture.md)
- [路线图](docs/roadmap.md)
- [稳定性审计 v1](docs/audits/stability-review-v1.md)
- [快速开始](docs/manuals/quickstart.md)
- [日常使用说明](docs/manuals/daily-usage.md)
- [数据源与边界](docs/manuals/data-and-limitations.md)
- [Data 清洗层说明](docs/manuals/data-cleaning.md)
- [故障排查](docs/manuals/troubleshooting.md)
## 预测底座骨架（v2.1 包 5 第一步）

本轮已新增最小可用的预测主线骨架，目标是先打通“数据集/预测/回测/评估”的 typed 契约，不改变现有单票、选股、交易、复盘主链路。

新增接口：
- `GET /datasets/features/{dataset_version}`：查询特征数据集版本与字段清单（支持 `latest`）。
- `GET /predictions/{symbol}`：获取单票预测快照（骨架分数）。
- `POST /predictions/cross-section/run`：运行截面预测并返回候选列表（骨架版）。
- `POST /backtests/screener/run`：运行选股回测（骨架版）。
- `POST /backtests/strategy/run`：运行单票策略回测（骨架版）。
- `GET /evaluations/models/{model_version}`：获取模型评估摘要（骨架版）。

当前阶段说明：
- 以上能力用于联调与契约验证，不代表真实实盘建议。
- 后续会在包 5 的后续阶段接入 point-in-time 特征、真实标签与 walk-forward 回测流水线。

## 预测底座增强（v2.1 包 5 第二步）

本轮已将“骨架契约”升级为“最小真实数据链路”：

- `dataset_service` 支持按交易日构建并落盘特征数据集（本地 JSON 台账）。
- `label_service` 支持基于未来 5/10 交易日收益构建标签数据集。
- `prediction_service` 优先消费真实特征记录计算 baseline 分数；未命中时才回退哈希分数。
- `backtest_service` 优先消费预测候选与真实标签，输出可解释指标（`top_k_avg_return/win_rate/max_drawdown`）。

新增数据集接口：

- `POST /datasets/features/build`
- `GET /datasets/labels/{label_version}`
- `POST /datasets/labels/build`

说明：

- 当前仍为最小可用预测链路，适合联调、流程验证与后续迭代。
- 不变更现有单票、选股、交易、复盘主链路。

预测结果接线状态（兼容增强）：

- `workspace-bundle` 可返回 `predictive_snapshot`（可选字段）。
- `screener` 候选与批次结果可返回：
  - `predictive_score`
  - `predictive_confidence`
  - `predictive_model_version`
- `deep-review` 候选可透传同一组预测字段，用于深筛优先级解释与对照。
- 前端最小展示已接线：
  - `/stocks/[symbol]` 展示“预测快照（辅助）”卡片；
  - `/screener` 结果表展示“预测分”，详情展示预测置信度与模型版本。

回测能力补充：

- `backtests` 已支持简化 walk-forward 切片聚合评估（指标中包含 `slice_count`）。

## 预测评估深化（v2.1 包5第三步，已完成）

本轮已将模型评估从“哈希占位指标”升级为“真实回测引用指标”：

- `/evaluations/models/{model_version}` 现在会引用真实回测结果，输出：
  - `backtest_references`（评估引用的回测摘要）
  - `metrics`（包含 `screener_win_rate`、`screener_top_k_avg_return`、`quality_score` 等）
  - `comparison`（当请求版本不是默认模型时，自动给出与默认基线模型的同窗差异）
- 指标兼容保留旧键位：
  - `precision_at_20`
  - `hit_rate_5d`
  - `excess_return_10d`
- 继续保持边界：
  - 当前评估用于研究与版本对比，不作为自动交易执行信号
  - 不包含交易成本、滑点、组合级归因

## 预测接入收尾（v2.1 包6第二阶段，已完成）

本轮完成“预测字段解释一致性 + 评估结果到版本建议最小联动”：

- 后端 `/evaluations/models/{model_version}` 新增 `recommendation` 字段，包含：
  - `recommendation`（`promote_candidate / keep_baseline / observe`）
  - `recommended_model_version`
  - `reason`
  - `supporting_metrics`
  - `guardrails`
- 单票页 `/stocks/[symbol]` 的“预测快照（辅助）”新增：
  - 预测分解释、置信度等级
  - 模型版本建议卡片（来自 evaluation）
- 选股页 `/screener` 的候选详情新增：
  - 预测分解释、置信度等级
  - 模型版本建议（按候选 `predictive_model_version` 懒加载）

说明：
- 版本建议仅用于研究与版本筛选，不作为自动交易执行信号。

## 预测接入收尾（v2.1 包6第三阶段，已完成）

本轮完成 workflow 运行详情的模型版本建议可见性：

- `GET /workflows/runs/{run_id}` 增加可选字段：
  - `model_recommendation`
  - `version_recommendation_alert`
- `workflow-run-summary` 前端面板可直接展示：
  - 当前 run 的模型版本建议
  - 建议版本与默认版本不一致时的变化提醒

说明：
- 变化提醒只做人工提示，不会自动切换默认模型版本。
- 该能力用于版本治理与运行解释，不作为自动交易执行入口。
