/**
 * Plain-language explanations for alert types and what they mean for traders.
 */

export interface AlertExplanation {
  title: string;
  whatItMeans: string;
  opportunity: string;
  action: string;
  icon: string;
}

export const alertExplanations: Record<string, AlertExplanation> = {
  volume_spike: {
    title: 'Volume Spike',
    whatItMeans: 'Trading activity suddenly increased 3x or more above normal levels.',
    opportunity: 'High volume often signals that informed traders are moving. The price may be about to shift significantly.',
    action: 'Check what news or events might be driving this. Consider whether the current price reflects the new information.',
    icon: '📈',
  },
  spread_alert: {
    title: 'Wide Spread',
    whatItMeans: 'The gap between buy and sell prices is unusually large (over 5%).',
    opportunity: 'Wide spreads mean you can potentially buy low and sell high within the same market. Also indicates uncertainty or low liquidity.',
    action: 'If you have strong conviction about the outcome, the wide spread offers better entry prices.',
    icon: '↔️',
  },
  mm_pullback: {
    title: 'Liquidity Drop',
    whatItMeans: 'Market makers have pulled significant liquidity (50%+ depth reduction).',
    opportunity: 'MMs often withdraw before major price moves. This could signal upcoming volatility or insider knowledge.',
    action: 'Be cautious with large orders. Watch for news. This often precedes significant price changes.',
    icon: '🚰',
  },
  arbitrage: {
    title: 'Arbitrage',
    whatItMeans: 'Prices across related markets are misaligned, creating a risk-free profit opportunity.',
    opportunity: 'You can lock in guaranteed profit by taking opposing positions in mispriced markets.',
    action: 'Act quickly - these opportunities usually close within minutes. Check the profit margin covers fees.',
    icon: '💰',
  },
};

export function getAlertExplanation(alertType: string): AlertExplanation {
  return alertExplanations[alertType] || {
    title: alertType,
    whatItMeans: 'An unusual pattern was detected in this market.',
    opportunity: 'This may indicate a trading opportunity worth investigating.',
    action: 'Review the market details and recent activity.',
    icon: '🔔',
  };
}

export const severityExplanations: Record<string, string> = {
  critical: 'Requires immediate attention - high confidence opportunity or risk',
  high: 'Significant opportunity - worth investigating soon',
  medium: 'Notable pattern - monitor for developments',
  low: 'Minor anomaly - informational',
  info: 'For your awareness - no action needed',
};

export const systemStatusExplanations = {
  healthy: 'All systems operating normally. Data is fresh and analysis is up to date.',
  degraded: 'Some systems are running slower than usual. Data may be slightly delayed.',
  unhealthy: 'System issues detected. Some data may be stale or missing.',
};

export const metricExplanations = {
  markets_active: 'Total prediction markets currently being monitored for opportunities.',
  alerts_active: 'Number of active trading opportunities or anomalies detected.',
  trades_24h: 'Total trades processed in the last 24 hours across all markets.',
  orderbooks_24h: 'Order book snapshots collected for liquidity analysis.',
  last_trade: 'When we last received trade data from Polymarket.',
  last_orderbook: 'When we last captured order book depth.',
  last_analysis: 'When we last ran our detection algorithms.',
};
