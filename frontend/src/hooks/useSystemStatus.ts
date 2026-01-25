import { useQuery } from '@tanstack/react-query';
import { fetchSystemStatus } from '@/api/system';

export const systemKeys = {
  all: ['system'] as const,
  status: (includeCounts: boolean) => [...systemKeys.all, 'status', includeCounts] as const,
};

export function useSystemStatus(includeCounts = true) {
  return useQuery({
    queryKey: systemKeys.status(includeCounts),
    queryFn: () => fetchSystemStatus(includeCounts),
    staleTime: 30 * 1000, // 30 seconds
    refetchInterval: 60 * 1000, // Auto-refresh every minute
  });
}
