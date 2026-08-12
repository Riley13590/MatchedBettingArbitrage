export interface HealthResponse {
  status: string;
  mode: string;
  time_utc: string;
}

export interface Venue {
  code: string;
  name: string;
  data_allowed: boolean;
  execution_allowed: boolean;
  geo_status: string;
  terms_status: string;
  checked_at: string;
  evidence_url: string | null;
}

export interface EventSummary {
  id: string;
  sport: string;
  competition: string;
  start_time: string;
  home_participant: string | null;
  away_participant: string | null;
  status: string;
  match_confidence: number | null;
  needs_review: boolean;
}

export interface ApiUsage {
  provider: string;
  credits_used_this_month: number;
  credits_by_sport: Record<string, number>;
  remaining_credits_reported: number | null;
  soft_monthly_budget: number;
  hard_monthly_budget: number;
  over_soft_budget: boolean;
  over_hard_budget: boolean;
}

export interface Opportunity {
  id: string;
  strategy: string;
  status: string;
  event_id: string | null;
  market_id: string | null;
  detected_at: string;
  expires_at: string | null;
  sport: string | null;
  competition: string | null;
  market_family: string | null;
  venues: string | null;
  time_to_start_bucket: string | null;
  expected_profit: string | null;
  expected_roi: string | null;
  worst_case_profit: string | null;
  quote_age_ms_at_detection: string | null;
  executable_stake_gbp: string | null;
  executable_edge_gbp: string | null;
  lifetime_ms: string | null;
  verification_outcome: string | null;
}
