import apiClient from './client';
import type { SystemStatusResponse } from '@/types';

export async function fetchSystemStatus(includeCounts = true): Promise<SystemStatusResponse> {
  const response = await apiClient.get<SystemStatusResponse>('/system/status', {
    params: { include_counts: includeCounts },
  });
  return response.data;
}
