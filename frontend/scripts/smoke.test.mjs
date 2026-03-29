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
    "Loading workspace bundle",
    "stock workspace should expose loading state text",
  );
  assertContains(
    source,
    "runtime_mode_effective",
    "stock workspace should surface effective runtime mode",
  );
  assertContains(
    source,
    "Fallback applied",
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

process.stdout.write("Smoke tests completed.\n");
