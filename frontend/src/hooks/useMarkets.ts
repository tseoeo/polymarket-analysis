import { useQuery } from '@tanstack/react-query';
import { fetchMarkets, fetchMarket, fetchMarketAlerts } from '@/api/markets';
import type { MarketFilters } from '@/types';

// Query keys factory for consistent cache management
export const marketKeys = {
  all: ['markets'] as const,
  lists: () => [...marketKeys.all, 'list'] as const,
  list: (filters: MarketFilters) => [...marketKeys.lists(), filters] as const,
  details: () => [...marketKeys.all, 'detail'] as const,
  detail: (id: string) => [...marketKeys.details(), id] as const,
  alerts: (id: string, isActive?: boolean) =>
    [...marketKeys.detail(id), 'alerts', isActive] as const,
};

export function useMarkets(filters: MarketFilters = {}) {
  return useQuery({
    queryKey: marketKeys.list(filters),
    queryFn: () => fetchMarkets(filters),
    staleTime: 60 * 1000, // 1 minute
  });
}

export function useMarket(id: string) {
  return useQuery({
    queryKey: marketKeys.detail(id),
    queryFn: () => fetchMarket(id),
    enabled: !!id,
  });
}

export function useMarketAlerts(marketId: string, isActive?: boolean) {
  return useQuery({
    queryKey: marketKeys.alerts(marketId, isActive),
    queryFn: () => fetchMarketAlerts(marketId, isActive),
    enabled: !!marketId,
  });
}
