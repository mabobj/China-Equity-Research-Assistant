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
  assertContains(source, "保存本次判断", "应展示保存判断按钮");
  assertContains(source, "记录交易", "应展示记录交易按钮");
});

runCheck("交易页已从占位页升级为可用页面", () => {
  const source = read("src/app/trades/page.tsx");
  assertContains(source, "createTradeFromCurrentDecision", "交易页应支持创建交易记录");
  assertContains(source, "listTrades", "交易页应加载交易记录列表");
  assertContains(source, "交易记录列表", "交易页应展示列表区块");
});

runCheck("复盘页已从占位页升级为可用页面", () => {
  const source = read("src/app/reviews/page.tsx");
  assertContains(source, "createReviewFromTrade", "复盘页应支持从交易生成草稿");
  assertContains(source, "updateReview", "复盘页应支持更新复盘记录");
  assertContains(source, "复盘列表与详情", "复盘页应展示列表与详情区块");
});

runCheck("前端 API 层暴露交易/复盘闭环接口", () => {
  const source = read("src/lib/api.ts");
  assertContains(source, "createDecisionSnapshot", "应暴露决策快照创建方法");
  assertContains(source, "createTradeFromCurrentDecision", "应暴露从当前决策创建交易方法");
  assertContains(source, "createReviewFromTrade", "应暴露从交易生成复盘方法");
  assertContains(source, "/decision-snapshots", "应包含决策快照后端路径");
  assertContains(source, "/trades/from-current-decision", "应包含交易后端路径");
  assertContains(source, "/reviews/from-trade/", "应包含复盘后端路径");
});

process.stdout.write("Smoke tests completed.\n");
