import apiClient from './client';

export interface OrderbookMetrics {
  token_id: string;
  timestamp: string;
  best_bid: number | null;
  best_ask: number | null;
  spread_pct: number | null;
  imbalance: number | null;
  depth: Record<string, { bid_depth: number; ask_depth: number }>;
}

export interface SlippageResult {
  token_id: string;
  side: string;
  trade_size: number;  // Requested trade size in dollars
  filled_dollars: number | null;  // Total dollars successfully filled
  unfilled_dollars: number | null;  // Dollars that couldn't be filled
  filled_shares: number | null;  // Total shares/contracts filled
  best_price: number | null;
  expected_price: number | null;  // Volume-weighted average price
  slippage_pct: number | null;
  levels_consumed: number | null;
  snapshot_age_seconds: number | null;
  error: string | null;
}

export interface SpreadPattern {
  token_id: string;
  analysis_period_hours: number;
  snapshot_count: number;
  hourly_spreads: Record<number, {
    avg_spread_pct: number;
    min_spread_pct: number;
    max_spread_pct: number;
    snapshot_count: number;
  }>;
  best_hour: number;
  best_hour_spread: number;
  worst_hour: number;
  worst_hour_spread: number;
  overall_avg_spread: number;
}

export interface BestTradingHour {
  hour: number;
  avg_spread_pct: number;
  min_spread_pct: number;
  snapshot_count: number;
  recommendation: string;
}

export interface HistoricalSnapshot {
  timestamp: string;
  best_bid: number | null;
  best_ask: number | null;
  spread_pct: number | null;
  mid_price: number | null;
  imbalance: number | null;
  bid_depth_1pct: number | null;
  ask_depth_1pct: number | null;
}

export async function fetchOrderbook(tokenId: string): Promise<OrderbookMetrics> {
  const response = await apiClient.get<OrderbookMetrics>(`/orderbook/${tokenId}`);
  return response.data;
}

export async function calculateSlippage(
  tokenId: string,
  size: number,
  side: 'buy' | 'sell' = 'buy'
): Promise<SlippageResult> {
  const response = await apiClient.get<SlippageResult>(`/orderbook/${tokenId}/slippage`, {
    params: { size, side },
  });
  return response.data;
}

export async function fetchSpreadPatterns(
  tokenId: string,
  hours: number = 24
): Promise<SpreadPattern> {
  const response = await apiClient.get<SpreadPattern>(`/orderbook/${tokenId}/patterns`, {
    params: { hours },
  });
  return response.data;
}

export async function fetchBestTradingHours(
  tokenId: string,
  hours: number = 168,
  topN: number = 5
): Promise<BestTradingHour[]> {
  const response = await apiClient.get<BestTradingHour[]>(`/orderbook/${tokenId}/best-hours`, {
    params: { hours, top_n: topN },
  });
  return response.data;
}

export async function fetchOrderbookHistory(
  tokenId: string,
  hours: number = 24
): Promise<HistoricalSnapshot[]> {
  const response = await apiClient.get<HistoricalSnapshot[]>(`/orderbook/${tokenId}/history`, {
    params: { hours },
  });
  return response.data;
}
