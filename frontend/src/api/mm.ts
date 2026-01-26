import apiClient from './client';

export interface MMPresence {
  token_id: string;
  presence_score: number;
  avg_spread_pct: number;
  avg_depth_1pct: number;
  spread_consistency: number;
  depth_consistency: number;
  snapshot_count: number;
  analysis_period_hours: number;
}

export interface MMPatterns {
  token_id: string;
  hourly_patterns: Record<number, {
    avg_spread_pct: number;
    avg_depth: number;
    snapshot_count: number;
  }>;
  best_mm_hours: number[];
  worst_mm_hours: number[];
}

export interface MMPullback {
  id: number;
  market_id: string;
  token_id: string;
  title: string;
  depth_drop_pct: number;
  previous_depth: number;
  current_depth: number;
  created_at: string;
  is_active: boolean;
}

export interface BestTradingHourOverall {
  hour: number;
  avg_spread_pct: number;
  avg_depth: number;
  market_count: number;
  quality_score: number;
}

export async function fetchMMPresence(
  tokenId: string,
  hours: number = 24
): Promise<MMPresence> {
  const response = await apiClient.get<MMPresence>(`/mm/${tokenId}/presence`, {
    params: { hours },
  });
  return response.data;
}

export async function fetchMMPatterns(
  tokenId: string,
  hours: number = 168
): Promise<MMPatterns> {
  const response = await apiClient.get<MMPatterns>(`/mm/${tokenId}/patterns`, {
    params: { hours },
  });
  return response.data;
}

export async function fetchMMPullbacks(
  isActive: boolean = true,
  limit: number = 20
): Promise<MMPullback[]> {
  const response = await apiClient.get<MMPullback[]>('/mm/pullbacks', {
    params: { is_active: isActive, limit },
  });
  return response.data;
}

export async function fetchBestTradingHoursOverall(
  hours: number = 168,
  limit: number = 24
): Promise<BestTradingHourOverall[]> {
  const response = await apiClient.get<BestTradingHourOverall[]>('/mm/best-hours', {
    params: { hours, limit },
  });
  return response.data;
}
