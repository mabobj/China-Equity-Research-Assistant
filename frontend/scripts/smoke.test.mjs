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

runCheck("stock page mounts stock workspace", () => {
  const source = read("src/app/stocks/[symbol]/page.tsx");
  assertContains(source, "StockWorkspace", "stock page should import StockWorkspace");
  assertContains(
    source,
    "<StockWorkspace symbol={decodedSymbol} />",
    "stock page should render StockWorkspace",
  );
  assertContains(
    source,
    "review-report v2（主研究产物）",
    "stock page should label review-report v2 as the primary artifact",
  );
  assertContains(
    source,
    "debate-review（结构化裁决）",
    "stock page should label debate-review as structured adjudication",
  );
});

runCheck("stock workspace uses workspace-bundle as primary data source", () => {
  const source = read("src/components/stock-workspace.tsx");
  assertContains(
    source,
    "getWorkspaceBundle",
    "stock workspace should call getWorkspaceBundle",
  );
  assertContains(
    source,
    "正在加载工作台聚合",
    "stock workspace should expose loading state text",
  );
  assertContains(
    source,
    "runtime_mode_effective",
    "stock workspace should surface effective runtime mode",
  );
  assertContains(
    source,
    "已触发降级",
    "stock workspace should show fallback status when present",
  );
});

runCheck("screener workspace triggers workflow run and polling", () => {
  const source = read("src/components/screener-workspace.tsx");
  assertContains(
    source,
    "runScreenerWorkflow",
    "screener workspace should start screener workflow",
  );
  assertContains(
    source,
    "getWorkflowRunDetail",
    "screener workspace should poll workflow detail",
  );
  assertContains(
    source,
    "WorkflowRunSummary",
    "screener workspace should render workflow run summary panel",
  );
  assertContains(
    source,
    "初筛工作流",
    "screener workspace should mention workflow run records",
  );
});

runCheck("workflow summary component renders status and final output summary", () => {
  const source = read("src/components/workflow-run-summary.tsx");
  assertContains(source, "run.status", "workflow summary should read run status");
  assertContains(
    source,
    "final_output_summary",
    "workflow summary should render final output summary",
  );
  assertContains(
    source,
    "failed_symbols",
    "workflow summary should render failed symbol summary",
  );
});

runCheck("reserved pages keep explicit not-enabled wording", () => {
  const reviewsSource = read("src/app/reviews/page.tsx");
  assertContains(reviewsSource, "复盘记录（预留）", "reviews page should stay reserved");
  assertContains(reviewsSource, "未启用", "reviews page should explicitly show not enabled");

  const tradesSource = read("src/app/trades/page.tsx");
  assertContains(tradesSource, "交易记录（预留）", "trades page should stay reserved");
  assertContains(tradesSource, "未启用", "trades page should explicitly show not enabled");
});

runCheck("home page keeps naming convergence hints", () => {
  const source = read("src/app/page.tsx");
  assertContains(
    source,
    "review-report v2",
    "home page should mention review-report v2 naming",
  );
  assertContains(
    source,
    "debate-review",
    "home page should mention debate-review naming",
  );
  assertContains(
    source,
    "工作流运行记录（workflow run record）",
    "home page should keep workflow run record wording",
  );
});

process.stdout.write("Smoke tests completed.\n");
