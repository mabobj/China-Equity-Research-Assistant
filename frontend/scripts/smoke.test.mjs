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
});

runCheck("交易页已升级为可用页面并显示中文交易标签", () => {
  const source = read("src/app/trades/page.tsx");
  assertContains(source, "createTradeFromCurrentDecision", "交易页应支持创建交易记录");
  assertContains(source, "listTrades", "交易页应加载交易记录列表");
  assertContains(source, "formatTradeSide", "交易页应使用中文动作映射");
  assertContains(source, "formatStrategyAlignment", "交易页应使用中文对齐映射");
});

runCheck("复盘页已升级为可用页面并支持保存修改", () => {
  const source = read("src/app/reviews/page.tsx");
  assertContains(source, "createReviewFromTrade", "复盘页应支持从交易生成草稿");
  assertContains(source, "updateReview", "复盘页应支持更新复盘记录");
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

process.stdout.write("Smoke tests completed.\n");
