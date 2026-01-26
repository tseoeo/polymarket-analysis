import { useQuery } from '@tanstack/react-query';
import {
  fetchOrderbook,
  calculateSlippage,
  fetchSpreadPatterns,
  fetchBestTradingHours,
  fetchOrderbookHistory,
} from '@/api/orderbook';

export const orderbookKeys = {
  all: ['orderbook'] as const,
  detail: (tokenId: string) => [...orderbookKeys.all, 'detail', tokenId] as const,
  slippage: (tokenId: string, size: number, side: string) =>
    [...orderbookKeys.all, 'slippage', tokenId, size, side] as const,
  patterns: (tokenId: string, hours: number) =>
    [...orderbookKeys.all, 'patterns', tokenId, hours] as const,
  bestHours: (tokenId: string, hours: number, topN: number) =>
    [...orderbookKeys.all, 'best-hours', tokenId, hours, topN] as const,
  history: (tokenId: string, hours: number) =>
    [...orderbookKeys.all, 'history', tokenId, hours] as const,
};

export function useOrderbook(tokenId: string) {
  return useQuery({
    queryKey: orderbookKeys.detail(tokenId),
    queryFn: () => fetchOrderbook(tokenId),
    enabled: !!tokenId,
    staleTime: 15 * 1000, // 15 seconds for orderbook
  });
}

export function useSlippage(tokenId: string, size: number, side: 'buy' | 'sell' = 'buy') {
  return useQuery({
    queryKey: orderbookKeys.slippage(tokenId, size, side),
    queryFn: () => calculateSlippage(tokenId, size, side),
    enabled: !!tokenId && size > 0,
    staleTime: 15 * 1000,
  });
}

export function useSpreadPatterns(tokenId: string, hours: number = 24) {
  return useQuery({
    queryKey: orderbookKeys.patterns(tokenId, hours),
    queryFn: () => fetchSpreadPatterns(tokenId, hours),
    enabled: !!tokenId,
    staleTime: 5 * 60 * 1000, // 5 minutes for patterns
  });
}

export function useBestTradingHours(tokenId: string, hours: number = 168, topN: number = 5) {
  return useQuery({
    queryKey: orderbookKeys.bestHours(tokenId, hours, topN),
    queryFn: () => fetchBestTradingHours(tokenId, hours, topN),
    enabled: !!tokenId,
    staleTime: 5 * 60 * 1000,
  });
}

export function useOrderbookHistory(tokenId: string, hours: number = 24) {
  return useQuery({
    queryKey: orderbookKeys.history(tokenId, hours),
    queryFn: () => fetchOrderbookHistory(tokenId, hours),
    enabled: !!tokenId,
    staleTime: 60 * 1000,
  });
}
