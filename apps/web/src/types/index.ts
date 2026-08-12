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
}
