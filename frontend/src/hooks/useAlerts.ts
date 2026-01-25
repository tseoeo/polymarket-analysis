import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchAlerts, fetchAlert, dismissAlert } from '@/api/alerts';
import type { AlertFilters } from '@/types';

// Query keys factory for consistent cache management
export const alertKeys = {
  all: ['alerts'] as const,
  lists: () => [...alertKeys.all, 'list'] as const,
  list: (filters: AlertFilters) => [...alertKeys.lists(), filters] as const,
  details: () => [...alertKeys.all, 'detail'] as const,
  detail: (id: number) => [...alertKeys.details(), id] as const,
};

export function useAlerts(filters: AlertFilters = {}) {
  return useQuery({
    queryKey: alertKeys.list(filters),
    queryFn: () => fetchAlerts(filters),
    staleTime: 30 * 1000, // 30 seconds
  });
}

export function useAlert(id: number) {
  return useQuery({
    queryKey: alertKeys.detail(id),
    queryFn: () => fetchAlert(id),
    enabled: !!id,
  });
}

export function useDismissAlert() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => dismissAlert(id),
    onSuccess: () => {
      // Invalidate all alert queries to refresh lists and details
      queryClient.invalidateQueries({ queryKey: alertKeys.all });
    },
  });
}
