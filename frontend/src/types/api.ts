export type ResearchAction = "BUY" | "WATCH" | "AVOID";
export type StrategyType = "pullback" | "breakout" | "wait" | "no_trade";
export type ScreenerListType = "BUY_CANDIDATE" | "WATCHLIST" | "AVOID";
export type DataRefreshTaskStatus = "idle" | "running" | "completed" | "failed";

export type PriceRange = {
  low: number;
  high: number;
};

export type ScreenerCandidate = {
  symbol: string;
  name: string;
  list_type: ScreenerListType;
  rank: number;
  screener_score: number;
  trend_state: "up" | "neutral" | "down";
  trend_score: number;
  latest_close: number;
  support_level: number | null;
  resistance_level: number | null;
  short_reason: string;
};

export type ScreenerRunResponse = {
  as_of_date: string;
  total_symbols: number;
  scanned_symbols: number;
  buy_candidates: ScreenerCandidate[];
  watch_candidates: ScreenerCandidate[];
  avoid_candidates: ScreenerCandidate[];
};

export type DeepScreenerCandidate = {
  symbol: string;
  name: string;
  base_list_type: ScreenerListType;
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
