import apiClient from './client';
import type { Market, MarketListResponse, MarketFilters, Alert } from '@/types';

export async function fetchMarkets(filters: MarketFilters = {}): Promise<MarketListResponse> {
  const params = new URLSearchParams();

  if (filters.active !== undefined) params.append('active', String(filters.active));
  if (filters.has_alerts !== undefined) params.append('has_alerts', String(filters.has_alerts));
  if (filters.limit) params.append('limit', String(filters.limit));
  if (filters.offset) params.append('offset', String(filters.offset));

  const response = await apiClient.get<MarketListResponse>('/markets', { params });
  return response.data;
}

export async function fetchMarket(id: string): Promise<Market> {
  const response = await apiClient.get<Market>(`/markets/${id}`);
  return response.data;
}

export async function fetchMarketAlerts(
  marketId: string,
  isActive?: boolean
): Promise<Alert[]> {
  const params = new URLSearchParams();
  if (isActive !== undefined) params.append('is_active', String(isActive));

  const response = await apiClient.get<Alert[]>(`/markets/${marketId}/alerts`, { params });
  return response.data;
}
