import { useQuery } from '@tanstack/react-query';
import {
  fetchMMPresence,
  fetchMMPatterns,
  fetchMMPullbacks,
  fetchBestTradingHoursOverall,
} from '@/api/mm';

export const mmKeys = {
  all: ['mm'] as const,
  presence: (tokenId: string, hours: number) =>
    [...mmKeys.all, 'presence', tokenId, hours] as const,
  patterns: (tokenId: string, hours: number) =>
    [...mmKeys.all, 'patterns', tokenId, hours] as const,
  pullbacks: (isActive: boolean, limit: number) =>
    [...mmKeys.all, 'pullbacks', isActive, limit] as const,
  bestHours: (hours: number, limit: number) =>
    [...mmKeys.all, 'best-hours', hours, limit] as const,
};

export function useMMPresence(tokenId: string, hours: number = 24) {
  return useQuery({
    queryKey: mmKeys.presence(tokenId, hours),
    queryFn: () => fetchMMPresence(tokenId, hours),
    enabled: !!tokenId,
    staleTime: 60 * 1000,
  });
}

export function useMMPatterns(tokenId: string, hours: number = 168) {
  return useQuery({
    queryKey: mmKeys.patterns(tokenId, hours),
    queryFn: () => fetchMMPatterns(tokenId, hours),
    enabled: !!tokenId,
    staleTime: 5 * 60 * 1000,
  });
}

export function useMMPullbacks(isActive: boolean = true, limit: number = 20) {
  return useQuery({
    queryKey: mmKeys.pullbacks(isActive, limit),
    queryFn: () => fetchMMPullbacks(isActive, limit),
    staleTime: 30 * 1000,
  });
}

export function useBestTradingHoursOverall(hours: number = 168, limit: number = 24) {
  return useQuery({
    queryKey: mmKeys.bestHours(hours, limit),
    queryFn: () => fetchBestTradingHoursOverall(hours, limit),
    staleTime: 5 * 60 * 1000,
  });
}
