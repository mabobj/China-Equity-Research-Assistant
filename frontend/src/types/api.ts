export type ResearchAction = "BUY" | "WATCH" | "AVOID";
export type StrategyType = "pullback" | "breakout" | "wait" | "no_trade";
export type LegacyScreenerListType = "BUY_CANDIDATE" | "WATCHLIST" | "AVOID";
export type ScreenerListType =
  | "READY_TO_BUY"
  | "WATCH_PULLBACK"
  | "WATCH_BREAKOUT"
  | "RESEARCH_ONLY"
  | "AVOID";
export type DataRefreshTaskStatus = "idle" | "running" | "completed" | "failed";
export type WorkflowRunStatus = "running" | "completed" | "failed";
export type WorkflowStepStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "skipped";
export type DecisionBriefActionNow =
  | "BUY_NOW"
  | "WAIT_PULLBACK"
  | "WAIT_BREAKOUT"
  | "RESEARCH_ONLY"
  | "AVOID";
export type DecisionConvictionLevel = "low" | "medium" | "high";
export type DataQualityStatus = "ok" | "warning" | "degraded" | "failed";

export type PriceRange = {
  low: number;
  high: number;
};

export type StockProfile = {
  symbol: string;
  code: string;
  exchange: "SH" | "SZ";
  name: string;
  industry: string | null;
  list_date: string | null;
  status: string | null;
  total_market_cap: number | null;
  circulating_market_cap: number | null;
  source: string;
};

export type FactorSignalGroup = {
  group_name: string;
  score: number | null;
  top_positive_signals: string[];
  top_negative_signals: string[];
};

export type FactorSnapshot = {
  symbol: string;
  as_of_date: string;
  freshness_mode?: string | null;
  source_mode?: string | null;
  raw_factors: Record<string, number | null>;
  normalized_factors: Record<string, number | null>;
  factor_group_scores: FactorSignalGroup[];
  alpha_score: {
    total_score: number;
  };
  trigger_score: {
    total_score: number;
    trigger_state: "pullback" | "breakout" | "neutral" | "avoid";
  };
  risk_score: {
    total_score: number;
  };
};

export type FactorProfileView = {
  strongest_factor_groups: string[];
  weakest_factor_groups: string[];
  alpha_score: number;
  trigger_score: number;
  risk_score: number;
  concise_summary: string;
};

export type TechnicalView = {
  trend_state: "up" | "neutral" | "down";
  trigger_state:
    | "near_support"
    | "near_breakout"
    | "neutral"
    | "overstretched"
    | "invalid";
  latest_close: number | null;
  support_level: number | null;
  resistance_level: number | null;
  key_levels: string[];
  tactical_read: string;
  invalidation_hint: string;
};

export type FundamentalView = {
  quality_read: string | null;
  growth_read: string | null;
  leverage_read: string | null;
  data_completeness_note: string;
  key_financial_flags: string[];
};

export type EventView = {
  recent_catalysts: string[];
  recent_risks: string[];
  event_temperature: "hot" | "warm" | "neutral" | "cool";
  concise_summary: string;
};

export type SentimentView = {
  sentiment_bias: "bullish" | "neutral" | "cautious" | "bearish";
  crowding_hint: string;
  momentum_context: string;
  concise_summary: string;
};

export type ReviewCase = {
  stance: "bull" | "bear";
  summary: string;
  reasons: string[];
};

export type FinalJudgement = {
  action: ResearchAction;
  summary: string;
  key_points: string[];
};

export type StrategySummary = {
  action: ResearchAction;
  strategy_type: StrategyType;
  entry_window: string;
  ideal_entry_range: PriceRange | null;
  stop_loss_price: number | null;
  take_profit_range: PriceRange | null;
  review_timeframe: string;
  concise_summary: string;
};

export type StockReviewReport = {
  symbol: string;
  name: string;
  as_of_date: string;
  factor_profile: FactorProfileView;
  technical_view: TechnicalView;
  fundamental_view: FundamentalView;
  event_view: EventView;
  sentiment_view: SentimentView;
  bull_case: ReviewCase;
  bear_case: ReviewCase;
  key_disagreements: string[];
  final_judgement: FinalJudgement;
  strategy_summary: StrategySummary;
  confidence: number;
};

export type DebatePoint = {
  title: string;
  detail: string;
};

export type AnalystView = {
  role:
    | "technical_analyst"
    | "fundamental_analyst"
    | "event_analyst"
    | "sentiment_analyst";
  summary: string;
  action_bias: "supportive" | "neutral" | "cautious" | "negative";
  positive_points: DebatePoint[];
  caution_points: DebatePoint[];
  key_levels: string[];
};

export type DebateReviewReport = {
  symbol: string;
  name: string;
  as_of_date: string;
  analyst_views: {
    technical: AnalystView;
    fundamental: AnalystView;
    event: AnalystView;
    sentiment: AnalystView;
  };
  bull_case: {
    summary: string;
    reasons: DebatePoint[];
  };
  bear_case: {
    summary: string;
    reasons: DebatePoint[];
  };
  key_disagreements: string[];
  chief_judgement: {
    final_action: ResearchAction;
    summary: string;
    decisive_points: string[];
    key_disagreements: string[];
  };
  risk_review: {
    risk_level: "low" | "medium" | "high";
    summary: string;
    execution_reminders: string[];
  };
  final_action: ResearchAction;
  strategy_summary: StrategySummary;
  confidence: number;
  runtime_mode: "rule_based" | "llm";
  provider_used: string | null;
  provider_candidates: string[];
  fallback_applied: boolean;
  fallback_reason: string | null;
  runtime_mode_requested: "rule_based" | "llm" | null;
  runtime_mode_effective: "rule_based" | "llm" | null;
  warning_messages: string[];
};

export type DebateReviewProgress = {
  symbol: string;
  request_id: string | null;
  status: "idle" | "running" | "completed" | "failed" | "fallback";
  stage:
    | "idle"
    | "rule_based"
    | "building_inputs"
    | "running_roles"
    | "finalizing"
    | "completed"
    | "failed"
    | "fallback_rule_based";
  runtime_mode: "rule_based" | "llm" | null;
  current_step: string | null;
  completed_steps: number;
  total_steps: number;
  message: string;
  started_at: string | null;
  updated_at: string | null;
  finished_at: string | null;
  error_message: string | null;
  recent_steps: string[];
};

export type TriggerSnapshot = {
  symbol: string;
  as_of_datetime: string;
  daily_trend_state: "up" | "neutral" | "down";
  daily_support_level: number | null;
  daily_resistance_level: number | null;
  latest_intraday_price: number;
  distance_to_support_pct: number | null;
  distance_to_resistance_pct: number | null;
  trigger_state:
    | "near_support"
    | "near_breakout"
    | "neutral"
    | "overstretched"
    | "invalid";
  trigger_note: string;
};

export type ScreenerCandidate = {
  symbol: string;
  name: string;
  list_type: LegacyScreenerListType;
  v2_list_type: ScreenerListType;
  rank: number;
  screener_score: number;
  alpha_score: number;
  trigger_score: number;
  risk_score: number;
  trend_state: "up" | "neutral" | "down";
  trend_score: number;
  latest_close: number;
  support_level: number | null;
  resistance_level: number | null;
  top_positive_factors: string[];
  top_negative_factors: string[];
  risk_notes: string[];
  short_reason: string;
  calculated_at: string | null;
  rule_version: string | null;
  rule_summary: string | null;
  headline_verdict: string | null;
  action_now: DecisionBriefActionNow | null;
  evidence_hints: string[];
  bars_quality?: DataQualityStatus | null;
  financial_quality?: DataQualityStatus | null;
  announcement_quality?: DataQualityStatus | null;
  quality_penalty_applied?: boolean;
  quality_note?: string | null;
  fail_reason?: string | null;
};

export type ScreenerRunResponse = {
  as_of_date: string;
  freshness_mode?: string | null;
  source_mode?: string | null;
  total_symbols: number;
  scanned_symbols: number;
  buy_candidates: ScreenerCandidate[];
  watch_candidates: ScreenerCandidate[];
  avoid_candidates: ScreenerCandidate[];
  ready_to_buy_candidates: ScreenerCandidate[];
  watch_pullback_candidates: ScreenerCandidate[];
  watch_breakout_candidates: ScreenerCandidate[];
  research_only_candidates: ScreenerCandidate[];
};

export type ScreenerBatchStatus = "running" | "completed" | "failed";

export type ScreenerBatchRecord = {
  batch_id: string;
  trade_date: string;
  run_id: string;
  status: ScreenerBatchStatus;
  started_at: string;
  finished_at: string | null;
  universe_size: number;
  scanned_size: number;
  rule_version: string;
  batch_size: number | null;
  max_symbols: number | null;
  top_n: number | null;
  workflow_name: string;
  warning_messages: string[];
  failure_reason: string | null;
};

export type ScreenerSymbolResult = {
  batch_id: string;
  symbol: string;
  name: string;
  list_type: ScreenerListType;
  screener_score: number;
  trend_state: "up" | "neutral" | "down";
  trend_score: number;
  latest_close: number;
  support_level: number | null;
  resistance_level: number | null;
  short_reason: string;
  calculated_at: string;
  rule_version: string;
  rule_summary: string;
  action_now: DecisionBriefActionNow | null;
  headline_verdict: string | null;
  evidence_hints: string[];
  fail_reason: string | null;
  bars_quality?: DataQualityStatus | null;
  financial_quality?: DataQualityStatus | null;
  announcement_quality?: DataQualityStatus | null;
  quality_penalty_applied?: boolean;
  quality_note?: string | null;
};

export type ScreenerLatestBatchResponse = {
  window_start: string;
  window_end: string;
  batch: ScreenerBatchRecord | null;
  results: ScreenerSymbolResult[];
  total_results: number;
};

export type ScreenerBatchDetailResponse = {
  batch: ScreenerBatchRecord;
};

export type ScreenerBatchResultsResponse = {
  batch: ScreenerBatchRecord;
  results: ScreenerSymbolResult[];
};

export type ScreenerSymbolResultResponse = {
  batch: ScreenerBatchRecord;
  result: ScreenerSymbolResult;
};

export type ScreenerCursorResetResponse = {
  reset_at: string;
  message: string;
};

export type DeepScreenerCandidate = {
  symbol: string;
  name: string;
  base_list_type: LegacyScreenerListType;
  base_rank: number;
  base_screener_score: number;
  research_action: ResearchAction;
  research_overall_score: number;
  research_confidence: number;
  strategy_action: ResearchAction;
  strategy_type: StrategyType;
  ideal_entry_range: PriceRange | null;
  stop_loss_price: number | null;
  take_profit_range: PriceRange | null;
  review_timeframe: string;
  thesis: string;
  short_reason: string;
  priority_score: number;
};

export type DeepScreenerRunResponse = {
  as_of_date: string;
  total_symbols: number;
  scanned_symbols: number;
  selected_for_deep_review: number;
  deep_candidates: DeepScreenerCandidate[];
};

export type ResearchReport = {
  symbol: string;
  name: string;
  as_of_date: string;
  technical_score: number;
  fundamental_score: number;
  event_score: number;
  risk_score: number;
  overall_score: number;
  action: ResearchAction;
  confidence: number;
  thesis: string;
  key_reasons: string[];
  risks: string[];
  triggers: string[];
  invalidations: string[];
  data_quality_summary?: {
    bars_quality: DataQualityStatus;
    financial_quality: DataQualityStatus;
    announcement_quality: DataQualityStatus;
    technical_modifier: number;
    fundamental_modifier: number;
    event_modifier: number;
    overall_quality_modifier: number;
  } | null;
  confidence_reasons?: string[];
};

export type StrategyPlan = {
  symbol: string;
  name: string;
  as_of_date: string;
  action: ResearchAction;
  strategy_type: StrategyType;
  entry_window: string;
  ideal_entry_range: PriceRange | null;
  entry_triggers: string[];
  avoid_if: string[];
  initial_position_hint: "small" | "medium" | null;
  stop_loss_price: number | null;
  stop_loss_rule: string;
  take_profit_range: PriceRange | null;
  take_profit_rule: string;
  hold_rule: string;
  sell_rule: string;
  review_timeframe: string;
  confidence: number;
};

export type DecisionBriefEvidence = {
  title: string;
  detail: string;
  source_module:
    | "stock_profile"
    | "factor_snapshot"
    | "review_report"
    | "debate_review"
    | "strategy_plan"
    | "trigger_snapshot";
  evidence_refs: EvidenceRef[];
};

export type DecisionPriceLevel = {
  label: string;
  value_text: string;
  note: string | null;
};

export type DecisionSourceModule = {
  module_name:
    | "stock_profile"
    | "factor_snapshot"
    | "review_report"
    | "debate_review"
    | "strategy_plan"
    | "trigger_snapshot";
  as_of: string | null;
  note: string | null;
};

export type DecisionBrief = {
  symbol: string;
  name: string;
  as_of_date: string;
  freshness_mode?: string | null;
  source_mode?: string | null;
  headline_verdict: string;
  action_now: DecisionBriefActionNow;
  conviction_level: DecisionConvictionLevel;
  why_it_made_the_list: string[];
  why_not_all_in: string[];
  key_evidence: DecisionBriefEvidence[];
  key_risks: DecisionBriefEvidence[];
  price_levels_to_watch: DecisionPriceLevel[];
  what_to_do_next: string[];
  next_review_window: string;
  source_modules: DecisionSourceModule[];
  evidence_manifest_refs: EvidenceRef[];
};

export type EvidenceRef = {
  dataset:
    | "daily_bars_daily"
    | "announcements_daily"
    | "financial_summary_daily"
    | "factor_snapshot_daily"
    | "review_report_daily"
    | "debate_review_daily"
    | "strategy_plan_daily"
    | "decision_brief_daily"
    | "screener_snapshot_daily";
  provider: string;
  symbol: string;
  as_of_date: string;
  field_path: string;
  raw_value: string | number | boolean | null;
  derived_value: string | number | boolean | null;
  used_by:
    | "decision_brief"
    | "workspace_bundle"
    | "screener_candidate"
    | "review_report"
    | "strategy_plan";
  note: string | null;
};

export type EvidenceBundle = {
  bundle_name: string;
  used_by:
    | "decision_brief"
    | "workspace_bundle"
    | "screener_candidate"
    | "review_report"
    | "strategy_plan";
  refs: EvidenceRef[];
};

export type EvidenceManifest = {
  symbol: string;
  as_of_date: string;
  bundles: EvidenceBundle[];
};

export type WorkspaceModuleStatus = {
  module_name: string;
  status: "success" | "error" | "skipped";
  message: string | null;
  provider_used: string | null;
  provider_candidates: string[];
  fallback_applied: boolean;
  fallback_reason: string | null;
  warning_messages: string[];
};

export type WorkspaceFreshnessItem = {
  item_name: string;
  as_of_date: string | null;
  freshness_mode: string | null;
  source_mode: string | null;
};

export type FreshnessSummary = {
  default_as_of_date: string | null;
  items: WorkspaceFreshnessItem[];
};

export type WorkspaceBundleResponse = {
  symbol: string;
  use_llm: boolean;
  profile: StockProfile | null;
  factor_snapshot: FactorSnapshot | null;
  review_report: StockReviewReport | null;
  debate_review: DebateReviewReport | null;
  strategy_plan: StrategyPlan | null;
  trigger_snapshot: TriggerSnapshot | null;
  decision_brief: DecisionBrief | null;
  module_status_summary: WorkspaceModuleStatus[];
  evidence_manifest: EvidenceManifest | null;
  freshness_summary: FreshnessSummary;
  debate_progress: DebateReviewProgress | null;
  provider_used: string | null;
  provider_candidates: string[];
  fallback_applied: boolean;
  fallback_reason: string | null;
  runtime_mode_requested: string | null;
  runtime_mode_effective: string | null;
  warning_messages: string[];
};

export type DataRefreshStatus = {
  status: DataRefreshTaskStatus;
  is_running: boolean;
  started_at: string | null;
  finished_at: string | null;
  universe_count: number;
  total_symbols: number;
  processed_symbols: number;
  succeeded_symbols: number;
  failed_symbols: number;
  profiles_updated: number;
  daily_bars_updated: number;
  financial_summaries_updated: number;
  announcements_updated: number;
  daily_bars_synced_rows: number;
  announcements_synced_items: number;
  profile_step_failures: number;
  daily_bar_step_failures: number;
  financial_step_failures: number;
  announcement_step_failures: number;
  universe_updated: boolean;
  max_symbols: number | null;
  current_symbol: string | null;
  current_stage: string | null;
  message: string;
  recent_warnings: string[];
  recent_errors: string[];
};

export type WorkflowStepSummary = {
  node_name: string;
  status: WorkflowStepStatus;
  started_at: string | null;
  finished_at: string | null;
  message: string | null;
  input_summary: Record<string, unknown>;
  output_summary: Record<string, unknown>;
  error_message: string | null;
};

export type WorkflowRunResponse = {
  run_id: string;
  workflow_name: string;
  status: WorkflowRunStatus;
  started_at: string;
  finished_at: string | null;
  input_summary: Record<string, unknown>;
  steps: WorkflowStepSummary[];
  final_output_summary: Record<string, unknown>;
  error_message: string | null;
  accepted: boolean;
  existing_run_id: string | null;
  message: string | null;
  provider_used: string | null;
  provider_candidates: string[];
  fallback_applied: boolean;
  fallback_reason: string | null;
  runtime_mode_requested: string | null;
  runtime_mode_effective: string | null;
  warning_messages: string[];
  failed_symbols: string[];
};

export type WorkflowRunDetailResponse = WorkflowRunResponse & {
  final_output: Record<string, unknown> | null;
};

export type TradeSide = "BUY" | "SELL" | "ADD" | "REDUCE" | "SKIP";
export type TradeReasonType =
  | "signal_entry"
  | "pullback_entry"
  | "breakout_entry"
  | "stop_loss"
  | "take_profit"
  | "time_exit"
  | "manual_override"
  | "watch_only"
  | "skip_due_to_quality"
  | "skip_due_to_risk";
export type StrategyAlignment =
  | "aligned"
  | "partially_aligned"
  | "not_aligned"
  | "unknown";
export type ReviewOutcomeLabel =
  | "success"
  | "partial_success"
  | "failure"
  | "invalidated"
  | "no_trade";
export type DidFollowPlan = "yes" | "partial" | "no";

export type DecisionSourceRef = {
  module_name: string;
  as_of_date: string | null;
  freshness_mode: string | null;
  source_mode: string | null;
  note: string | null;
};

export type DecisionSnapshot = {
  snapshot_id: string;
  symbol: string;
  as_of_date: string;
  action: string;
  confidence: number;
  technical_score: number;
  fundamental_score: number;
  event_score: number;
  overall_score: number;
  thesis: string;
  risks: string[];
  triggers: string[];
  invalidations: string[];
  data_quality_summary:
    | {
        bars_quality: DataQualityStatus;
        financial_quality: DataQualityStatus;
        announcement_quality: DataQualityStatus;
        technical_modifier: number;
        fundamental_modifier: number;
        event_modifier: number;
        overall_quality_modifier: number;
      }
    | null;
  confidence_reasons: string[];
  runtime_mode_requested: string | null;
  runtime_mode_effective: string | null;
  source_refs: DecisionSourceRef[];
  created_at: string;
};

export type DecisionSnapshotListResponse = {
  count: number;
  items: DecisionSnapshot[];
};

export type TradeRecord = {
  trade_id: string;
  symbol: string;
  side: TradeSide;
  trade_date: string;
  price: number | null;
  quantity: number | null;
  amount: number | null;
  reason_type: TradeReasonType;
  note: string | null;
  decision_snapshot_id: string | null;
  strategy_alignment: StrategyAlignment;
  created_at: string;
  updated_at: string;
  decision_snapshot: DecisionSnapshot | null;
};

export type TradeListResponse = {
  count: number;
  items: TradeRecord[];
};

export type ReviewRecord = {
  review_id: string;
  symbol: string;
  review_date: string;
  linked_trade_id: string | null;
  linked_decision_snapshot_id: string | null;
  outcome_label: ReviewOutcomeLabel;
  holding_days: number | null;
  max_favorable_excursion: number | null;
  max_adverse_excursion: number | null;
  exit_reason: string | null;
  did_follow_plan: DidFollowPlan;
  review_summary: string;
  lesson_tags: string[];
  warning_messages: string[];
  created_at: string;
  updated_at: string;
  linked_trade: TradeRecord | null;
  linked_decision_snapshot: DecisionSnapshot | null;
};

export type ReviewListResponse = {
  count: number;
  items: ReviewRecord[];
};

export type SingleStockWorkflowRunRequest = {
  symbol: string;
  start_from?: string;
  stop_after?: string;
  use_llm?: boolean;
};

export type DeepReviewWorkflowRunRequest = {
  max_symbols?: number;
  top_n?: number;
  deep_top_k?: number;
  force_refresh?: boolean;
  start_from?: string;
  stop_after?: string;
  use_llm?: boolean;
};

export type ScreenerWorkflowRunRequest = {
  batch_size?: number;
  max_symbols?: number;
  top_n?: number;
  force_refresh?: boolean;
  start_from?: string;
  stop_after?: string;
  use_llm?: boolean;
};

export type DbTableInfo = {
  table_name: string;
  row_count: number;
};

export type DbTablesResponse = {
  count: number;
  tables: DbTableInfo[];
};

export type DbQueryResponse = {
  columns: string[];
  rows: Array<Array<unknown>>;
  row_count: number;
};

export type CreateDecisionSnapshotRequest = {
  symbol?: string;
  use_llm?: boolean;
  payload?: {
    symbol: string;
    as_of_date: string;
    action: string;
    confidence: number;
    technical_score: number;
    fundamental_score: number;
    event_score: number;
    overall_score: number;
    thesis: string;
    risks?: string[];
    triggers?: string[];
    invalidations?: string[];
    data_quality_summary?: DecisionSnapshot["data_quality_summary"];
    confidence_reasons?: string[];
    runtime_mode_requested?: string;
    runtime_mode_effective?: string;
    source_refs?: DecisionSourceRef[];
  };
};

export type CreateTradeRequest = {
  symbol: string;
  side: TradeSide;
  trade_date: string;
  price?: number;
  quantity?: number;
  amount?: number;
  reason_type: TradeReasonType;
  note?: string;
  decision_snapshot_id?: string;
  strategy_alignment?: StrategyAlignment;
  auto_create_snapshot?: boolean;
  use_llm?: boolean;
};

export type UpdateTradeRequest = Partial<
  Omit<CreateTradeRequest, "symbol" | "auto_create_snapshot" | "use_llm">
>;

export type CreateTradeFromCurrentDecisionRequest = {
  symbol: string;
  use_llm?: boolean;
  side: TradeSide;
  trade_date?: string;
  price?: number;
  quantity?: number;
  amount?: number;
  reason_type: TradeReasonType;
  note?: string;
  strategy_alignment?: StrategyAlignment;
};

export type CreateReviewRequest = {
  symbol: string;
  review_date: string;
  linked_trade_id?: string;
  linked_decision_snapshot_id?: string;
  outcome_label: ReviewOutcomeLabel;
  holding_days?: number;
  max_favorable_excursion?: number;
  max_adverse_excursion?: number;
  exit_reason?: string;
  did_follow_plan?: DidFollowPlan;
  review_summary: string;
  lesson_tags?: string[];
  warning_messages?: string[];
};

export type CreateReviewFromTradeRequest = {
  review_date?: string;
  outcome_label?: ReviewOutcomeLabel;
  did_follow_plan?: DidFollowPlan;
  exit_reason?: string;
};

export type UpdateReviewRequest = Partial<
  Omit<CreateReviewRequest, "symbol" | "review_date" | "review_summary"> & {
    review_summary: string;
  }
>;
