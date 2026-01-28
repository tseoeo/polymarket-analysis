export interface Alert {
  id: number;
  alert_type: string;
  severity: AlertSeverity;
  title: string;
  description: string | null;
  market_id: string | null;
  related_market_ids: string[] | null;
  data: Record<string, unknown> | null;
  is_active: boolean;
  created_at: string;
  dismissed_at: string | null;
  expires_at: string | null;
}

export type AlertSeverity = 'critical' | 'high' | 'medium' | 'low' | 'info';

export type AlertType =
  | 'volume_spike'
  | 'spread_alert'
  | 'mm_pullback'
  | 'arbitrage';

export interface AlertListResponse {
  alerts: Alert[];
  total: number;
  limit: number;
  offset: number;
}

export interface AlertFilters {
  alert_type?: string;
  severity?: string;
  market_id?: string;
  is_active?: boolean;
  limit?: number;
  offset?: number;
}
