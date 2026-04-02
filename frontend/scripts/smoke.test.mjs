import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const frontendRoot = process.cwd();

function read(filePath) {
  return readFileSync(join(frontendRoot, filePath), "utf8");
}

function assertContains(source, needle, message) {
  assert.ok(source.includes(needle), message);
}

function runCheck(name, fn) {
  fn();
  process.stdout.write(`PASS ${name}\n`);
}

runCheck("单票页挂载工作台组件", () => {
  const source = read("src/app/stocks/[symbol]/page.tsx");
  assertContains(source, "StockWorkspace", "单票页应导入 StockWorkspace");
  assertContains(source, "<StockWorkspace symbol={decodedSymbol} />", "单票页应渲染工作台");
});

runCheck("单票工作台接入保存判断与记录交易动作", () => {
  const source = read("src/components/stock-workspace.tsx");
  assertContains(source, "createDecisionSnapshot", "应调用保存判断接口");
  assertContains(source, "createTradeFromCurrentDecision", "应调用记录交易接口");
  assertContains(source, "与原判断不一致", "应展示交易冲突提示");
  assertContains(source, "预测快照（辅助）", "单票页应展示预测快照卡片");
  assertContains(source, "predictive_snapshot", "单票页应消费 workspace-bundle 预测字段");
  assertContains(source, "getModelEvaluation", "单票页应加载模型评估建议");
  assertContains(source, "模型版本建议", "单票页应展示模型版本建议");
  assertContains(source, "预测分解释", "单票页应展示预测分解释");
});

runCheck("交易页已升级为可用页面并显示中文交易标签", () => {
  const source = read("src/app/trades/page.tsx");
  assertContains(source, "createTradeFromCurrentDecision", "交易页应支持创建交易记录");
  assertContains(source, "listTrades", "交易页应加载交易记录列表");
  assertContains(source, "快速记录交易", "交易页应提供快速记录入口");
  assertContains(source, "高级参数（原因类型、对齐策略、人工覆盖、备注）", "交易页应提供高级参数折叠区");
  assertContains(source, "动作与原因类型提示", "交易页应提示动作与原因类型匹配关系");
  assertContains(source, "覆盖原因模板", "交易页应提供人工覆盖原因模板");
  assertContains(source, "预测模型版本", "交易页快照摘要应展示预测模型版本");
  assertContains(source, "formatTradeSide", "交易页应使用中文动作映射");
  assertContains(source, "formatStrategyAlignment", "交易页应使用中文对齐映射");
});

runCheck("复盘页已升级为可用页面并支持保存修改", () => {
  const source = read("src/app/reviews/page.tsx");
  assertContains(source, "createReviewFromTrade", "复盘页应支持从交易生成草稿");
  assertContains(source, "updateReview", "复盘页应支持更新复盘记录");
  assertContains(source, "待复盘交易", "复盘页应优先展示待复盘任务");
  assertContains(source, "复盘对照视图", "复盘页应展示判断-执行-结果对照视图");
  assertContains(source, "偏差诊断摘要", "复盘页应展示偏差诊断摘要卡");
  assertContains(source, "建议下一步", "复盘页应展示可执行的后续建议");
  assertContains(source, "原判断快照", "复盘页应展示原判断快照摘要");
  assertContains(source, "预测置信度", "复盘页原判断快照应展示预测置信度");
  assertContains(source, "执行路径", "复盘页应展示执行路径摘要");
  assertContains(source, "保存复盘修改", "复盘页应保留保存按钮");
  assertContains(source, "formatReviewOutcome", "复盘页应使用中文结果标签");
});

runCheck("前端格式化层提供交易与复盘中文字典", () => {
  const source = read("src/lib/format.ts");
  assertContains(source, "formatTradeSide", "应包含交易动作中文映射");
  assertContains(source, "formatTradeReasonType", "应包含交易原因中文映射");
  assertContains(source, "formatStrategyAlignment", "应包含策略对齐中文映射");
  assertContains(source, "formatReviewOutcome", "应包含复盘结果中文映射");
  assertContains(source, "formatDidFollowPlan", "应包含执行一致性中文映射");
});

runCheck("选股工作台保持结果优先与高级操作折叠", () => {
  const source = read("src/components/screener-workspace.tsx");
  assertContains(source, "当前展示窗口", "选股页应优先展示当前窗口结果");
  assertContains(source, "运行初筛（快速入口）", "选股页应提供快速初筛入口");
  assertContains(source, "分桶分布概览（当前窗口）", "选股页应展示分桶分布概览");
  assertContains(source, "高级操作（游标管理与深筛工作流）", "高级操作应下沉到折叠区");
  assertContains(source, "runScreenerWorkflow", "选股页应保留初筛 workflow 调用");
  assertContains(source, "runDeepReviewWorkflow", "选股页应保留深筛 workflow 调用");
  assertContains(source, "预测分", "选股结果表应展示预测分列");
  assertContains(source, "predictive_model_version", "选股详情应展示预测模型版本");
  assertContains(source, "getModelEvaluation", "选股详情应支持加载模型评估建议");
  assertContains(source, "预测分解释", "选股详情应展示预测分解释");
  assertContains(source, "模型版本建议", "选股详情应展示模型版本建议");
});

runCheck("工作流运行摘要展示模型版本建议与变化提醒", () => {
  const source = read("src/components/workflow-run-summary.tsx");
  assertContains(source, "模型版本建议", "工作流摘要应展示模型版本建议");
  assertContains(source, "版本建议变化提醒", "工作流摘要应展示版本变化提醒");
  assertContains(source, "formatModelRecommendation", "工作流摘要应使用模型建议格式化");
});

process.stdout.write("Smoke tests completed.\n");
