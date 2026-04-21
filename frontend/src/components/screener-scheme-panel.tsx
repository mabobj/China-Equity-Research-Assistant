"use client";

import { formatDateTime, formatLabel, formatUnknownValue } from "@/lib/format";
import type {
  ScreenerSchemeDetailResponse,
  ScreenerSchemeListResponse,
} from "@/types/api";

import { SectionCard } from "./section-card";
import { ScreenerMetric, ScreenerStringPanel } from "./screener-shared";
import { StatusBlock } from "./status-block";

export function ScreenerSchemePanel({
  schemes,
  selectedSchemeId,
  schemeDetail,
  loading,
  error,
  onSelectScheme,
}: {
  schemes: ScreenerSchemeListResponse | null;
  selectedSchemeId: string | null;
  schemeDetail: ScreenerSchemeDetailResponse | null;
  loading: boolean;
  error: string | null;
  onSelectScheme: (schemeId: string) => void;
}) {
  const version = schemeDetail?.current_version_detail ?? null;
  const enabledGroups = Array.isArray(
    version?.config.factor_selection_config.enabled_groups,
  )
    ? version.config.factor_selection_config.enabled_groups.map((item) => String(item))
    : [];

  return (
    <SectionCard
      title="方案"
      description="先确认当前使用的是哪套初筛方案，再决定是否发起运行。后续的结果与反馈都会围绕这个方案展开。"
    >
      <div className="space-y-4">
        {loading ? (
          <StatusBlock
            title="加载中"
            description="正在读取方案列表与当前方案详情..."
          />
        ) : null}
        {error ? <StatusBlock title="方案加载失败" description={error} tone="error" /> : null}
        {schemes && schemes.items.length === 0 && !loading && !error ? (
          <StatusBlock
            title="暂无可用方案"
            description="当前还没有可供运行的初筛方案。需要先在后端准备好方案定义，再回到这里选择并运行。"
          />
        ) : null}

        {schemes && schemes.items.length > 0 ? (
          <>
            <label className="space-y-2">
              <span className="text-sm font-medium text-slate-700">当前方案</span>
              <select
                value={selectedSchemeId ?? ""}
                onChange={(event) => onSelectScheme(event.target.value)}
                className="min-h-11 w-full rounded-2xl border border-slate-300 bg-white px-4 text-sm text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
              >
                {schemes.items.map((item) => (
                  <option key={item.scheme_id} value={item.scheme_id}>
                    {item.name}
                    {item.is_default ? "（默认）" : ""}
                  </option>
                ))}
              </select>
            </label>

            {schemeDetail ? (
              <div className="space-y-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-900">
                  方案是本次初筛的配置快照。这里定义因子分组、权重、阈值和质量门控；切换方案不会改写历史批次，历史结果会继续挂在各自运行时使用的方案版本下。
                </div>

                <div className="flex flex-col gap-2">
                  <h3 className="text-lg font-semibold text-slate-950">
                    {schemeDetail.scheme.name}
                  </h3>
                  <p className="text-sm leading-6 text-slate-700">
                    {schemeDetail.scheme.description ?? "当前方案暂未填写说明。"}
                  </p>
                </div>

                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  <ScreenerMetric
                    label="方案状态"
                    value={formatLabel(schemeDetail.scheme.status)}
                  />
                  <ScreenerMetric
                    label="当前版本"
                    value={version?.version_label ?? schemeDetail.scheme.current_version ?? "-"}
                  />
                  <ScreenerMetric
                    label="版本号"
                    value={version?.scheme_version ?? "-"}
                  />
                  <ScreenerMetric
                    label="最近更新"
                    value={formatDateTime(schemeDetail.scheme.updated_at)}
                  />
                </div>

                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                  <ScreenerMetric
                    label="启用因子组"
                    value={enabledGroups.length ? enabledGroups.join(" / ") : "-"}
                  />
                  <ScreenerMetric
                    label="阈值摘要"
                    value={formatConfigSummary(version?.config.threshold_config ?? {})}
                  />
                  <ScreenerMetric
                    label="质量门控摘要"
                    value={formatConfigSummary(version?.config.quality_gate_config ?? {})}
                  />
                </div>

                <div className="grid gap-4 xl:grid-cols-2">
                  <ScreenerStringPanel
                    title="最近版本摘要"
                    items={schemeDetail.recent_versions.map((item) => {
                      const note = item.change_note ? ` - ${item.change_note}` : "";
                      return `${item.version_label} (${item.scheme_version})${note}`;
                    })}
                  />
                  <ScreenerStringPanel
                    title="权重配置"
                    items={toKeyValueItems(version?.config.factor_weight_config ?? {})}
                  />
                </div>
              </div>
            ) : null}
          </>
        ) : null}
      </div>
    </SectionCard>
  );
}

function formatConfigSummary(config: Record<string, unknown>): string {
  const entries = Object.entries(config);
  if (entries.length === 0) {
    return "-";
  }
  return entries
    .slice(0, 3)
    .map(([key, value]) => `${key}=${formatUnknownValue(value)}`)
    .join(" / ");
}

function toKeyValueItems(config: Record<string, unknown>): string[] {
  const entries = Object.entries(config);
  if (entries.length === 0) {
    return [];
  }
  return entries.map(([key, value]) => `${key}: ${formatUnknownValue(value)}`);
}
