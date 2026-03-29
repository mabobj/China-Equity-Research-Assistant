"use client";

import { useEffect, useState } from "react";

import { getDbTables, runDbQuery } from "@/lib/api";
import type { DbQueryResponse, DbTablesResponse } from "@/types/api";

import { SectionCard } from "./section-card";
import { StatusBlock } from "./status-block";

const DEFAULT_SQL = "SELECT * FROM daily_bars ORDER BY trade_date DESC LIMIT 20";

export function DbConsole() {
  const [tables, setTables] = useState<DbTablesResponse | null>(null);
  const [tablesLoading, setTablesLoading] = useState(false);
  const [tablesError, setTablesError] = useState<string | null>(null);

  const [sql, setSql] = useState(DEFAULT_SQL);
  const [limit, setLimit] = useState("200");
  const [queryLoading, setQueryLoading] = useState(false);
  const [queryError, setQueryError] = useState<string | null>(null);
  const [queryResult, setQueryResult] = useState<DbQueryResponse | null>(null);

  useEffect(() => {
    void loadTables();
  }, []);

  async function loadTables() {
    setTablesLoading(true);
    setTablesError(null);
    try {
      const response = await getDbTables();
      setTables(response);
    } catch (error) {
      setTablesError(getErrorMessage(error));
    } finally {
      setTablesLoading(false);
    }
  }

  async function handleQuerySubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setQueryLoading(true);
    setQueryError(null);

    try {
      const response = await runDbQuery(sql, parseLimit(limit));
      setQueryResult(response);
    } catch (error) {
      setQueryError(getErrorMessage(error));
    } finally {
      setQueryLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <SectionCard
        title="数据库表清单"
        description="用于排查本地 DuckDB 表现状与数据规模。"
        actions={
          <button
            type="button"
            onClick={() => void loadTables()}
            className="min-h-10 rounded-2xl border border-slate-300 px-4 text-sm font-semibold text-slate-700 transition hover:border-slate-400 hover:bg-slate-50"
          >
            刷新表清单
          </button>
        }
      >
        {tablesLoading ? (
          <StatusBlock title="正在加载" description="正在获取数据库表清单。" />
        ) : null}
        {tablesError ? (
          <StatusBlock title="加载失败" description={tablesError} tone="error" />
        ) : null}
        {!tablesLoading && !tablesError && tables ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {tables.tables.map((table) => (
              <div
                key={table.table_name}
                className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3"
              >
                <p className="text-sm font-semibold text-slate-900">{table.table_name}</p>
                <p className="mt-1 text-xs text-slate-600">行数：{table.row_count}</p>
              </div>
            ))}
          </div>
        ) : null}
      </SectionCard>

      <SectionCard
        title="只读 SQL 查询"
        description="支持 SELECT / WITH / PRAGMA / DESCRIBE / SHOW / EXPLAIN。默认最多返回 2000 行。"
      >
        <form className="space-y-4" onSubmit={handleQuerySubmit}>
          <label className="space-y-2 block">
            <span className="text-sm font-medium text-slate-700">SQL</span>
            <textarea
              value={sql}
              onChange={(event) => setSql(event.target.value)}
              rows={6}
              className="w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 font-mono text-sm text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
            />
          </label>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <label className="space-y-2">
              <span className="text-sm font-medium text-slate-700">返回上限（limit）</span>
              <input
                value={limit}
                onChange={(event) => setLimit(event.target.value)}
                inputMode="numeric"
                className="min-h-11 w-40 rounded-2xl border border-slate-300 bg-white px-4 text-sm text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
              />
            </label>
            <button
              type="submit"
              disabled={queryLoading}
              className="min-h-11 rounded-2xl bg-slate-900 px-5 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
            >
              {queryLoading ? "查询中..." : "执行查询"}
            </button>
          </div>
        </form>

        <div className="mt-5 space-y-4">
          {queryError ? (
            <StatusBlock title="查询失败" description={queryError} tone="error" />
          ) : null}
          {queryResult ? <QueryResultTable result={queryResult} /> : null}
        </div>
      </SectionCard>
    </div>
  );
}

function QueryResultTable({ result }: { result: DbQueryResponse }) {
  if (result.columns.length === 0) {
    return <StatusBlock title="无结果集" description="当前 SQL 没有返回可展示列。" />;
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-700">返回行数：{result.row_count}</p>
      <div className="overflow-x-auto rounded-2xl border border-slate-200">
        <table className="min-w-full border-collapse text-sm">
          <thead className="bg-slate-100">
            <tr>
              {result.columns.map((column) => (
                <th
                  key={column}
                  className="whitespace-nowrap border-b border-slate-200 px-3 py-2 text-left font-semibold text-slate-700"
                >
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {result.rows.map((row, rowIndex) => (
              <tr key={rowIndex} className="odd:bg-white even:bg-slate-50">
                {row.map((value, colIndex) => (
                  <td
                    key={`${rowIndex}-${colIndex}`}
                    className="whitespace-nowrap border-b border-slate-100 px-3 py-2 text-slate-800"
                  >
                    {formatCellValue(value)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function parseLimit(value: string): number {
  const parsed = Number.parseInt(value.trim(), 10);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return 200;
  }
  return Math.min(parsed, 2000);
}

function formatCellValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "NULL";
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "发生未知错误，请稍后重试。";
}
