import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchDailyBriefing,
  fetchOpportunityDetail,
  fetchWatchlist,
  addToWatchlist,
  updateWatchlistItem,
  markWatchlistViewed,
  removeFromWatchlist,
  type AddToWatchlistRequest,
  type UpdateWatchlistRequest,
} from '@/api/briefing';

// ============================================================================
// Query Keys
// ============================================================================

export const briefingKeys = {
  all: ['briefing'] as const,
  daily: () => [...briefingKeys.all, 'daily'] as const,
  dailyWithLimit: (limit: number) => [...briefingKeys.daily(), limit] as const,
  opportunity: (marketId: string) => [...briefingKeys.all, 'opportunity', marketId] as const,
};

export const watchlistKeys = {
  all: ['watchlist'] as const,
  list: () => [...watchlistKeys.all, 'list'] as const,
  item: (id: number) => [...watchlistKeys.all, 'item', id] as const,
};

// ============================================================================
// Briefing Hooks
// ============================================================================

export function useDailyBriefing(limit = 5) {
  return useQuery({
    queryKey: briefingKeys.dailyWithLimit(limit),
    queryFn: () => fetchDailyBriefing(limit),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

export function useOpportunityDetail(marketId: string) {
  return useQuery({
    queryKey: briefingKeys.opportunity(marketId),
    queryFn: () => fetchOpportunityDetail(marketId),
    enabled: !!marketId,
    staleTime: 60 * 1000, // 1 minute
  });
}

// ============================================================================
// Watchlist Hooks
// ============================================================================

export function useWatchlist() {
  return useQuery({
    queryKey: watchlistKeys.list(),
    queryFn: fetchWatchlist,
    staleTime: 30 * 1000, // 30 seconds
  });
}

export function useAddToWatchlist() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: AddToWatchlistRequest) => addToWatchlist(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: watchlistKeys.all });
    },
  });
}

export function useUpdateWatchlistItem() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ itemId, request }: { itemId: number; request: UpdateWatchlistRequest }) =>
      updateWatchlistItem(itemId, request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: watchlistKeys.all });
    },
  });
}

export function useMarkWatchlistViewed() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (itemId: number) => markWatchlistViewed(itemId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: watchlistKeys.all });
    },
  });
}

export function useRemoveFromWatchlist() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (itemId: number) => removeFromWatchlist(itemId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: watchlistKeys.all });
    },
  });
}
