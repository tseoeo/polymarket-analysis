import { useQuery } from '@tanstack/react-query';
import {
  fetchVolumeStats,
  fetchVolumeAcceleration,
  fetchVolumePriceCorrelation,
  fetchVolumeHistory,
  fetchVolumeSpikes,
  fetchVolumeLeaders,
} from '@/api/volume';

export const volumeKeys = {
  all: ['volume'] as const,
  stats: (tokenId: string) => [...volumeKeys.all, 'stats', tokenId] as const,
  acceleration: (tokenId: string, windowHours: number) =>
    [...volumeKeys.all, 'acceleration', tokenId, windowHours] as const,
  correlation: (tokenId: string, hours: number) =>
    [...volumeKeys.all, 'correlation', tokenId, hours] as const,
  history: (tokenId: string, period: string, limit: number) =>
    [...volumeKeys.all, 'history', tokenId, period, limit] as const,
  spikes: (isActive: boolean, limit: number) =>
    [...volumeKeys.all, 'spikes', isActive, limit] as const,
  leaders: (limit: number) => [...volumeKeys.all, 'leaders', limit] as const,
};

export function useVolumeStats(tokenId: string) {
  return useQuery({
    queryKey: volumeKeys.stats(tokenId),
    queryFn: () => fetchVolumeStats(tokenId),
    enabled: !!tokenId,
    staleTime: 60 * 1000,
  });
}

export function useVolumeAcceleration(tokenId: string, windowHours: number = 6) {
  return useQuery({
    queryKey: volumeKeys.acceleration(tokenId, windowHours),
    queryFn: () => fetchVolumeAcceleration(tokenId, windowHours),
    enabled: !!tokenId,
    staleTime: 60 * 1000,
  });
}

export function useVolumePriceCorrelation(tokenId: string, hours: number = 24) {
  return useQuery({
    queryKey: volumeKeys.correlation(tokenId, hours),
    queryFn: () => fetchVolumePriceCorrelation(tokenId, hours),
    enabled: !!tokenId,
    staleTime: 5 * 60 * 1000,
  });
}

export function useVolumeHistory(
  tokenId: string,
  period: 'hour' | 'day' | 'week' = 'hour',
  limit: number = 24
) {
  return useQuery({
    queryKey: volumeKeys.history(tokenId, period, limit),
    queryFn: () => fetchVolumeHistory(tokenId, period, limit),
    enabled: !!tokenId,
    staleTime: 60 * 1000,
  });
}

export function useVolumeSpikes(isActive: boolean = true, limit: number = 20) {
  return useQuery({
    queryKey: volumeKeys.spikes(isActive, limit),
    queryFn: () => fetchVolumeSpikes(isActive, limit),
    staleTime: 30 * 1000,
  });
}

export function useVolumeLeaders(limit: number = 10) {
  return useQuery({
    queryKey: volumeKeys.leaders(limit),
    queryFn: () => fetchVolumeLeaders(limit),
    staleTime: 60 * 1000,
  });
}
