export interface JobStatus {
  id: string;
  last_run: string | null;
  last_status: 'running' | 'success' | 'failed' | null;
  run_id: string | null;
  records_processed: number | null;
  error_message: string | null;
}

export interface SchedulerStatus {
  enabled: boolean;
  jobs: JobStatus[];
}

export interface DataFreshness {
  last_trade: string | null;
  last_orderbook: string | null;
  last_analysis: string | null;
  last_market_sync: string | null;
}

export interface DataCounts {
  markets_active: number;
  trades_24h: number;
  orderbooks_24h: number;
  alerts_active: number;
}

export type SystemHealthStatus = 'healthy' | 'degraded' | 'unhealthy';

export interface SystemStatusResponse {
  status: SystemHealthStatus;
  timestamp: string;
  scheduler: SchedulerStatus;
  data_freshness: DataFreshness;
  counts: DataCounts | null;
}
