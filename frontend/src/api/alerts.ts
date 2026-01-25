import apiClient from './client';
import type { Alert, AlertListResponse, AlertFilters } from '@/types';

export async function fetchAlerts(filters: AlertFilters = {}): Promise<AlertListResponse> {
  const params = new URLSearchParams();

  if (filters.alert_type) params.append('alert_type', filters.alert_type);
  if (filters.severity) params.append('severity', filters.severity);
  if (filters.market_id) params.append('market_id', filters.market_id);
  if (filters.is_active !== undefined) params.append('is_active', String(filters.is_active));
  if (filters.limit) params.append('limit', String(filters.limit));
  if (filters.offset) params.append('offset', String(filters.offset));

  const response = await apiClient.get<AlertListResponse>('/alerts', { params });
  return response.data;
}

export async function fetchAlert(id: number): Promise<Alert> {
  const response = await apiClient.get<Alert>(`/alerts/${id}`);
  return response.data;
}

export async function dismissAlert(id: number): Promise<Alert> {
  const response = await apiClient.patch<Alert>(`/alerts/${id}/dismiss`);
  return response.data;
}
