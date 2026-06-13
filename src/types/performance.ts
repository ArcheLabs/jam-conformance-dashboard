export interface LaneLatency {
  min: number | null;
  p50: number | null;
  p75: number | null;
  p90: number | null;
  p99: number | null;
  max: number | null;
  mean: number | null;
  std_dev: number | null;
}

export interface NormalizedLane {
  preset: string;
  status: string;
  error: string | null;
  team_id: string;
  team_h160: string;
  target: string;
  suite_id: string;
  client_name_raw: string;
  client_name: string;
  team_name: string;
  language: string;
  language_color: string;
  client_version: string;
  jam_version: string;
  steps: number;
  imported: number;
  import_ratio: number;
  latency: LaneLatency;
}

export interface NormalizedEvaluation {
  attestation_hash: string;
  suite_id: string;
  team_id: string;
  team_h160: string;
  target: string;
  lanes: NormalizedLane[];
}

export interface LeaderboardLaneEntry {
  p50: number | null;
  p90: number | null;
  p99: number | null;
  imported: number;
  import_ratio: number;
}

export interface LeaderboardEntry {
  rank: number;
  team_id: string;
  team_name: string;
  client_name: string;
  client_version: string;
  jam_version: string;
  language: string;
  language_color: string;
  latest_attestation: string;
  completed_count: number;
  total_lanes: number;
  score: number | null;
  metrics: {
    geo_p50: number | null;
    geo_p90: number | null;
    geo_p99: number | null;
    total_imported: number;
  };
  lanes: Record<string, LeaderboardLaneEntry>;
  error_lanes: Array<{ preset: string; error: string }>;
}

export interface LeaderboardData {
  generated_at: string;
  methodology_version: number;
  lanes: string[];
  scoring: {
    description: string;
    lane_weights: Record<string, number>;
    aggregation: string;
  };
  teams: LeaderboardEntry[];
  complete_teams: LeaderboardEntry[];
  partial_teams: LeaderboardEntry[];
  failed_teams: LeaderboardEntry[];
}
