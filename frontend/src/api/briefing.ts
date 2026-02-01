import { apiClient } from './client';

// ============================================================================
// Types
// ============================================================================

export interface Metrics {
  freshness_minutes: number | null;
  spread_pct: number | null;
  total_depth: number;
  bid_depth_1pct: number;
  ask_depth_1pct: number;
  best_bid: number | null;
  best_ask: number | null;
  signal_count: number;
  active_signals: string[];
}

export interface Scores {
  freshness: number;
  liquidity: number;
  spread: number;
  alignment: number;
}

export interface Opportunity {
  market_id: string;
  market_question: string;
  category: string | null;
  outcomes: Record<string, unknown>[] | null;
  safety_score: number;
  scores: Scores;
  metrics: Metrics;
  why_safe: string;
  what_could_go_wrong: string;
  last_updated: string | null;
}

export interface DailyBriefingResponse {
  generated_at: string;
  opportunity_count: number;
  opportunities: Opportunity[];
  learning_tip: string;
  fallback_used: boolean;
  fallback_reason: string | null;
  learning_opportunities: Opportunity[];
}

export interface ChecklistItem {
  label: string;
  passed: boolean | null;
  detail: string;
}

export interface TeachMeContent {
  what_signal_means: string;
  why_safe: string;
  what_invalidates: string;
  risk_with_100_eur: string;
}

export interface OpportunityDetail extends Opportunity {
  teach_me: TeachMeContent;
  checklist: ChecklistItem[];
}

// ============================================================================
// Watchlist Types
// ============================================================================

export interface WatchlistItem {
  id: number;
  market_id: string;
  market_question: string | null;
  category: string | null;
  added_at: string;
  last_viewed_at: string | null;
  notes: string | null;
  current_safety_score: number | null;
  initial_safety_score: number | null;
  score_change: number | null;
  spread_pct: number | null;
  total_depth: number | null;
  freshness_minutes: number | null;
  new_alerts_count: number;
}

export interface WatchlistResponse {
  items: WatchlistItem[];
  total_count: number;
}

export interface AddToWatchlistRequest {
  market_id: string;
  notes?: string;
}

export interface UpdateWatchlistRequest {
  notes?: string;
}

// ============================================================================
// API Functions
// ============================================================================

export async function fetchDailyBriefing(limit = 5): Promise<DailyBriefingResponse> {
  const response = await apiClient.get<DailyBriefingResponse>('/briefing/daily', {
    params: { limit },
  });
  return response.data;
}

export async function fetchOpportunityDetail(marketId: string): Promise<OpportunityDetail> {
  const response = await apiClient.get<OpportunityDetail>(`/briefing/opportunity/${marketId}`);
  return response.data;
}

export async function fetchWatchlist(): Promise<WatchlistResponse> {
  const response = await apiClient.get<WatchlistResponse>('/watchlist');
  return response.data;
}

export async function addToWatchlist(request: AddToWatchlistRequest): Promise<WatchlistItem> {
  const response = await apiClient.post<WatchlistItem>('/watchlist', request);
  return response.data;
}

export async function updateWatchlistItem(
  itemId: number,
  request: UpdateWatchlistRequest
): Promise<WatchlistItem> {
  const response = await apiClient.patch<WatchlistItem>(`/watchlist/${itemId}`, request);
  return response.data;
}

export async function markWatchlistViewed(itemId: number): Promise<void> {
  await apiClient.post(`/watchlist/${itemId}/viewed`);
}

export async function removeFromWatchlist(itemId: number): Promise<void> {
  await apiClient.delete(`/watchlist/${itemId}`);
}
