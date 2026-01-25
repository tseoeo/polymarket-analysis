export interface Market {
  id: string;
  question: string;
  description: string | null;
  outcomes: string[] | null;
  volume: number | null;
  liquidity: number | null;
  active: boolean;
  end_date: string | null;
  yes_price: number | null;
  no_price: number | null;
  active_alerts: number;
}

export interface MarketListResponse {
  markets: Market[];
  total: number;
  limit: number;
  offset: number;
}

export interface MarketFilters {
  active?: boolean;
  has_alerts?: boolean;
  limit?: number;
  offset?: number;
}
