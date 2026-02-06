import apiClient from './client';

export interface VolumeStats {
  token_id: string;
  period_days: number;
  total_volume: number;
  daily_avg: number;
  min_daily: number;
  max_daily: number;
  trend_pct: number;
  source: string;
}

export interface VolumeAcceleration {
  token_id: string;
  window_hours: number;
  recent_volume: number;
  recent_trade_count: number;
  previous_volume: number;
  previous_trade_count: number;
  volume_acceleration: number;
  trade_acceleration: number;
  signal: string;
}

export interface VolumePriceCorrelation {
  token_id: string;
  analysis_hours: number;
  data_points: number;
  correlation: number;
  price_change_pct: number;
  volume_trend_pct: number;
  total_volume: number;
  avg_hourly_volume: number;
  price_start: number;
  price_end: number;
  interpretation: string;
}

export interface VolumeHistoryData {
  period_start: string;
  period_end: string;
  volume: number;
  trade_count: number;
  avg_trade_size: number | null;
  price_open: number | null;
  price_close: number | null;
  price_high: number | null;
  price_low: number | null;
}

export interface VolumeHistory {
  token_id: string;
  period_type: string;
  data: VolumeHistoryData[];
}

export interface VolumeSpike {
  id: number;
  market_id: string;
  token_id: string;
  title: string;
  volume_ratio: number;
  current_volume: number;
  average_volume: number;
  created_at: string;
  is_active: boolean;
}

export interface VolumeLeader {
  market_id: string;
  token_id: string;
  volume_24h: number;
  trade_count_24h: number;
  avg_trade_size: number;
  question: string | null;
}

export async function fetchVolumeStats(tokenId: string): Promise<VolumeStats> {
  const response = await apiClient.get<VolumeStats>(`/volume/${tokenId}/stats`);
  return response.data;
}

export async function fetchVolumeAcceleration(
  tokenId: string,
  windowHours: number = 6
): Promise<VolumeAcceleration> {
  const response = await apiClient.get<VolumeAcceleration>(`/volume/${tokenId}/acceleration`, {
    params: { window_hours: windowHours },
  });
  return response.data;
}

export async function fetchVolumePriceCorrelation(
  tokenId: string,
  hours: number = 24
): Promise<VolumePriceCorrelation> {
  const response = await apiClient.get<VolumePriceCorrelation>(`/volume/${tokenId}/correlation`, {
    params: { hours },
  });
  return response.data;
}

export async function fetchVolumeHistory(
  tokenId: string,
  period: 'hour' | 'day' | 'week' = 'hour',
  limit: number = 24
): Promise<VolumeHistory> {
  const response = await apiClient.get<VolumeHistory>(`/volume/${tokenId}/history`, {
    params: { period, limit },
  });
  return response.data;
}

export async function fetchVolumeSpikes(
  isActive: boolean = true,
  limit: number = 20
): Promise<VolumeSpike[]> {
  const response = await apiClient.get<VolumeSpike[]>('/volume/spikes', {
    params: { is_active: isActive, limit },
  });
  return response.data;
}

export async function fetchVolumeLeaders(limit: number = 10): Promise<VolumeLeader[]> {
  const response = await apiClient.get<VolumeLeader[]>('/volume/leaders', {
    params: { limit },
  });
  return response.data;
}
