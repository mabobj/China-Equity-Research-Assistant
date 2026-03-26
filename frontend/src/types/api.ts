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
};

export type ScreenerRunResponse = {
  as_of_date: string;
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
};

export type WorkflowRunDetailResponse = WorkflowRunResponse & {
  final_output: Record<string, unknown> | null;
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
