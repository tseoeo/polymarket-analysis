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

/**
 * Plain-language glossary for every technical term used in the UI.
 * Used with the Tooltip component to explain jargon on hover.
 */
export const glossary: Record<string, string> = {
  // Order book terms
  best_bid: 'The highest price someone is currently willing to pay. Think of it as the best offer from buyers.',
  best_ask: 'The lowest price someone is currently willing to sell for. Think of it as the cheapest offer from sellers.',
  spread: 'The gap between the best buy price and best sell price. Smaller = cheaper to trade. Larger = more expensive or uncertain.',
  spread_pct: 'The spread shown as a percentage of the price. Under 2% is tight (good). Over 5% is wide (expensive to trade).',
  imbalance: 'Shows whether there are more buyers or sellers. Positive = more buy pressure. Negative = more sell pressure. Close to 0 = balanced.',
  depth: 'How much money is available at different price levels. More depth = you can trade larger amounts without moving the price.',
  depth_at_level: 'Money available within this distance from the current price. Left number (green) = buy orders. Right number (red) = sell orders.',
  slippage: 'How much worse your actual price will be compared to the displayed price, because your order is large enough to eat through multiple price levels.',
  levels_consumed: 'How many price levels your order would need to eat through. More levels = more slippage = worse price.',
  expected_price: 'The average price you\'d actually pay after accounting for slippage. This is more realistic than the \'best price\' for larger trades.',
  snapshot: 'A frozen picture of the order book at a moment in time. We take these regularly to track how liquidity changes.',
  snapshot_age: 'How old this data snapshot is. Fresher is better — anything over 15 minutes may not reflect current conditions.',
  token_id: 'A unique identifier for one side of a prediction market (e.g., the \'Yes\' side of \'Will X happen?\'). You can find this on Polymarket.',

  // Volume terms
  volume_ratio: 'How much higher current trading volume is compared to normal. 3x means three times the usual activity.',
  volume_24h: 'Total dollar amount of trades in the last 24 hours. Higher = more actively traded market.',
  trade_count: 'Number of individual trades that happened. More trades = more market participants are active.',
  avg_trade_size: 'Average dollar size per trade. Large average = bigger players. Small average = retail activity.',
  volume_spike: 'When trading volume suddenly jumps well above normal levels. Often happens when news breaks or insiders act.',
  volume_baseline: 'The \'normal\' level of trading activity, calculated from the last 7 days of data.',

  // Market maker terms
  market_maker: 'Professional traders who provide liquidity by always offering to buy and sell. They keep markets functional and tradeable.',
  mm_pullback: 'When market makers withdraw their orders, reducing available liquidity. Often a warning sign that they expect big price moves.',
  depth_drop: 'The percentage decrease in available liquidity. A 50% drop means half the money was pulled from the order book.',
  previous_depth: 'How much liquidity was available before the withdrawal happened.',
  current_depth: 'How much liquidity is available now, after the withdrawal.',
  presence_score: 'A 0-100 rating of how actively market makers are providing liquidity. Higher = more professional liquidity.',
  quality_score: 'A 0-100 rating of trading conditions at a given hour, based on how tight spreads are and how deep the order book is.',

  // Arbitrage terms
  arbitrage: 'A pricing mistake across related markets that lets you lock in a guaranteed profit regardless of the outcome.',
  mutually_exclusive: 'Markets where only one outcome can happen (e.g., \'Who will win?\' — only one candidate can win). If prices add up to more than 100%, there\'s a mispricing.',
  conditional: 'Markets where one outcome depends on another (e.g., \'Wins primary\' → \'Wins election\'). The first step can\'t be cheaper than the final result.',
  time_sequence: 'Markets with different deadlines for the same event. An earlier deadline should never cost more than a later one.',
  subset: 'Markets where one outcome is a specific version of another (e.g., \'Wins by 10+\' vs \'Wins at all\'). The specific one can\'t cost more than the general.',
  profit_estimate: 'The estimated profit percentage from the arbitrage, before fees. Check that this exceeds Polymarket\'s trading fees.',
  confidence: 'How confident the system is that these two markets are actually related. Higher = more reliable.',
  relationship_group: 'A set of markets that are logically connected (e.g., all candidates for the same race).',

  // Trading hours
  best_hour: 'The hour of the day when spreads are tightest and depth is deepest — meaning you\'ll get the best prices.',
  worst_hour: 'The hour when spreads are widest and liquidity is thinnest — trading here costs more.',
  trading_hours: 'Analysis of which hours of the day offer the best trading conditions, based on historical order book data.',

  // General
  active_market: 'A prediction market that is still open for trading and hasn\'t resolved yet.',
  resolved_market: 'A prediction market that has ended — the outcome is known and positions have been settled.',
  yes_price: 'The probability (shown as price) that the market thinks this outcome will happen. 75% = market thinks 75% likely.',
  no_price: 'The probability that this outcome WON\'T happen. Always equals 100% minus the Yes price.',
};
