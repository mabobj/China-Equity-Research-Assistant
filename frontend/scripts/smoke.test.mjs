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
  assertContains(
    source,
    "<StockWorkspace symbol={decodedSymbol} />",
    "单票页应渲染 StockWorkspace",
  );
});

runCheck("单票工作台以 workspace-bundle 为主数据源", () => {
  const source = read("src/components/stock-workspace.tsx");
  assertContains(source, "getWorkspaceBundle", "单票工作台应调用 getWorkspaceBundle");
  assertContains(source, "setStatus(\"loading\")", "单票工作台应进入 loading 状态");
  assertContains(source, "runtime_mode_effective", "应展示实际运行模式");
});

runCheck("选股工作台使用 workflow + 批次台账", () => {
  const source = read("src/components/screener-workspace.tsx");
  assertContains(source, "runScreenerWorkflow", "应发起初筛 workflow");
  assertContains(source, "getWorkflowRunDetail", "应轮询 workflow 运行详情");
  assertContains(source, "getLatestScreenerBatch", "应加载最新批次摘要");
  assertContains(source, "batch_size", "应使用 batch_size 发起初筛");
  assertContains(source, "当前展示窗口", "应展示时间窗口卡片");
  assertContains(source, "重置游标", "应提供游标重置入口");
  assertContains(source, "已有运行中的初筛任务", "应展示互斥运行提示");
});

runCheck("workflow 运行摘要组件展示状态与结果摘要", () => {
  const source = read("src/components/workflow-run-summary.tsx");
  assertContains(source, "run.status", "应读取 workflow 状态");
  assertContains(source, "final_output_summary", "应展示最终摘要");
  assertContains(source, "failed_symbols", "应展示局部失败摘要");
});

runCheck("前端 API 层暴露批次查询函数", () => {
  const source = read("src/lib/api.ts");
  assertContains(source, "getLatestScreenerBatch", "应提供最新批次接口");
  assertContains(source, "getScreenerBatchResults", "应提供批次结果接口");
  assertContains(source, "/screener/latest-batch", "应调用后端 latest-batch 路径");
});

runCheck("保留页明确标注未启用", () => {
  const reviewsSource = read("src/app/reviews/page.tsx");
  assertContains(reviewsSource, "复盘记录（预留）", "reviews 页应保留预留说明");
  assertContains(reviewsSource, "未启用", "reviews 页应明确未启用");

  const tradesSource = read("src/app/trades/page.tsx");
  assertContains(tradesSource, "交易记录（预留）", "trades 页应保留预留说明");
  assertContains(tradesSource, "未启用", "trades 页应明确未启用");
});

process.stdout.write("Smoke tests completed.\n");
