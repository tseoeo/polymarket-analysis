import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Card } from '@/components/ui/Card';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { Tooltip, InfoBox } from '@/components/ui/Tooltip';
import { glossary } from '@/lib/explanations';
import {
  useOrderbook,
  useSlippage,
  useSpreadPatterns,
  useBestTradingHours,
} from '@/hooks/useOrderbook';

export function OrderBookPage() {
  const [searchParams] = useSearchParams();
  const [tokenId, setTokenId] = useState(searchParams.get('token') || '');
  const [tradeSize, setTradeSize] = useState(1000);
  const [tradeSide, setTradeSide] = useState<'buy' | 'sell'>('buy');

  const {
    data: orderbook,
    isLoading: loadingOrderbook,
    error: orderbookError,
  } = useOrderbook(tokenId);

  const {
    data: slippage,
    isLoading: loadingSlippage,
  } = useSlippage(tokenId, tradeSize, tradeSide);

  const {
    data: patterns,
    isLoading: loadingPatterns,
  } = useSpreadPatterns(tokenId, 24);

  const {
    data: bestHours,
    isLoading: loadingBestHours,
  } = useBestTradingHours(tokenId, 168, 5);

  const inputClass = 'w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-900 dark:focus:ring-gray-400 focus:border-transparent';

  const spreadHint = (spreadPct: number | null | undefined) => {
    if (spreadPct == null) return null;
    const pct = spreadPct * 100;
    if (pct < 2) return <span className="text-emerald-600 dark:text-emerald-400 text-xs mt-1 block">&#10003; Tight — cheap to trade</span>;
    if (pct < 5) return <span className="text-yellow-600 dark:text-yellow-400 text-xs mt-1 block">~ Moderate</span>;
    return <span className="text-red-600 dark:text-red-400 text-xs mt-1 block">&#9888; Wide — expensive to trade</span>;
  };

  const imbalanceHint = (imbalance: number | null | undefined) => {
    if (imbalance == null) return null;
    if (imbalance > 0.1) return <span className="text-xs text-gray-500 dark:text-gray-400 mt-1 block">More buyers than sellers</span>;
    if (imbalance < -0.1) return <span className="text-xs text-gray-500 dark:text-gray-400 mt-1 block">More sellers than buyers</span>;
    return <span className="text-xs text-gray-500 dark:text-gray-400 mt-1 block">Roughly balanced</span>;
  };

  return (
    <div className="page-container">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-50 mb-2">
          Liquidity & Pricing Analysis
        </h1>
        <p className="text-gray-600 dark:text-gray-300 max-w-2xl">
          See how much it actually costs to trade in a market. This page shows you the buy/sell prices,
          how much your trade size would affect the price, and which hours of the day give you the best deal.
        </p>
      </div>

      {/* Intro Explainer */}
      <InfoBox variant="info" className="mb-6">
        <strong>How to read this page:</strong> Every prediction market has an "order book" — a list of all
        pending buy and sell orders. The <strong>spread</strong> (gap between buy and sell prices) tells you
        the cost of trading. The <strong>depth</strong> tells you how much money is available. Together, they
        determine whether a market is cheap or expensive to trade in.
      </InfoBox>

      {/* Token Input */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-2">
          Token ID <Tooltip content={glossary.token_id} />
        </label>
        <input
          type="text"
          value={tokenId}
          onChange={(e) => setTokenId(e.target.value)}
          placeholder="Enter token ID to analyze..."
          className={`${inputClass} max-w-md`}
        />
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
          Paste a token ID from Polymarket or from one of the market detail pages in this app.
        </p>
      </div>

      {tokenId && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Current Buy & Sell Prices */}
          <Card className="p-4">
            <h2 className="font-semibold text-gray-900 dark:text-gray-50 mb-4">Current Buy & Sell Prices</h2>
            {loadingOrderbook && <LoadingSpinner />}
            {orderbookError && (
              <p className="text-red-600 dark:text-red-400 text-sm">Failed to load orderbook</p>
            )}
            {orderbook && (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs text-gray-500 dark:text-gray-400 uppercase">
                      Best Buy Price <Tooltip content={glossary.best_bid} />
                    </p>
                    <p className="text-lg font-mono text-emerald-600 dark:text-emerald-400">
                      ${orderbook.best_bid?.toFixed(4) || '-'}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 dark:text-gray-400 uppercase">
                      Best Sell Price <Tooltip content={glossary.best_ask} />
                    </p>
                    <p className="text-lg font-mono text-red-600 dark:text-red-400">
                      ${orderbook.best_ask?.toFixed(4) || '-'}
                    </p>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs text-gray-500 dark:text-gray-400 uppercase">
                      Spread (trading cost) <Tooltip content={glossary.spread} />
                    </p>
                    <p className="text-lg font-mono text-gray-900 dark:text-gray-50">
                      {orderbook.spread_pct ? (orderbook.spread_pct * 100).toFixed(2) : '-'}%
                    </p>
                    {spreadHint(orderbook.spread_pct)}
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 dark:text-gray-400 uppercase">
                      Buy/Sell Pressure <Tooltip content={glossary.imbalance} />
                    </p>
                    <p className={`text-lg font-mono ${
                      (orderbook.imbalance || 0) > 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'
                    }`}>
                      {orderbook.imbalance?.toFixed(3) || '-'}
                    </p>
                    {imbalanceHint(orderbook.imbalance)}
                  </div>
                </div>
                {orderbook.depth && (
                  <div className="pt-4 border-t border-gray-100 dark:border-gray-800">
                    <p className="text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
                      Available Liquidity <Tooltip content={glossary.depth} />
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">
                      Money available at each price distance — buy orders (green) / sell orders (red)
                    </p>
                    {Object.entries(orderbook.depth).map(([level, data]) => (
                      <div key={level} className="flex justify-between text-sm py-1">
                        <span className="text-gray-600 dark:text-gray-300">Within {level} of price:</span>
                        <span>
                          <span className="text-emerald-600 dark:text-emerald-400">${data.bid_depth.toFixed(0)}</span>
                          {' / '}
                          <span className="text-red-600 dark:text-red-400">${data.ask_depth.toFixed(0)}</span>
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </Card>

          {/* Price Impact Calculator */}
          <Card className="p-4">
            <h2 className="font-semibold text-gray-900 dark:text-gray-50 mb-4">Price Impact Calculator</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-gray-600 dark:text-gray-300 mb-1">How much do you want to trade? ($)</label>
                <input
                  type="number"
                  value={tradeSize}
                  onChange={(e) => setTradeSize(Number(e.target.value))}
                  className={inputClass}
                />
              </div>
              <div>
                <label className="block text-sm text-gray-600 dark:text-gray-300 mb-1">Are you buying or selling?</label>
                <select
                  value={tradeSide}
                  onChange={(e) => setTradeSide(e.target.value as 'buy' | 'sell')}
                  className={inputClass}
                >
                  <option value="buy">Buying (going long)</option>
                  <option value="sell">Selling (going short)</option>
                </select>
              </div>
              {loadingSlippage && <LoadingSpinner />}
              {slippage && !slippage.error && (
                <div className="pt-4 border-t border-gray-100 dark:border-gray-800 space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-600 dark:text-gray-300">Best available price:</span>
                    <span className="font-mono">${slippage.best_price?.toFixed(4)}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-600 dark:text-gray-300">
                      Price you'd actually get: <Tooltip content={glossary.expected_price} />
                    </span>
                    <span className="font-mono">${slippage.expected_price?.toFixed(4)}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-600 dark:text-gray-300">
                      Price impact: <Tooltip content={glossary.slippage} />
                    </span>
                    <span className={`font-mono ${
                      (slippage.slippage_pct || 0) > 0.01 ? 'text-red-600 dark:text-red-400' : 'text-gray-900 dark:text-gray-50'
                    }`}>
                      {slippage.slippage_pct ? (slippage.slippage_pct * 100).toFixed(3) : 0}%
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-600 dark:text-gray-300">
                      Price levels needed: <Tooltip content={glossary.levels_consumed} />
                    </span>
                    <span className="font-mono">{slippage.levels_consumed}</span>
                  </div>
                  {(slippage.slippage_pct || 0) > 0.02 && (
                    <div className="mt-2 p-2 bg-amber-50 dark:bg-amber-950 rounded text-xs text-amber-800 dark:text-amber-300">
                      &#9888; High price impact. Consider splitting into smaller trades or waiting for more liquidity.
                    </div>
                  )}
                </div>
              )}
              {slippage?.error && (
                <p className="text-sm text-red-600 dark:text-red-400">{slippage.error}</p>
              )}
            </div>
          </Card>

          {/* Best Times to Trade */}
          <Card className="p-4">
            <h2 className="font-semibold text-gray-900 dark:text-gray-50 mb-4">Best Times to Trade</h2>
            {loadingBestHours && <LoadingSpinner />}
            {bestHours && bestHours.length > 0 && (
              <div className="space-y-2">
                {bestHours.map((hour, i) => (
                  <div
                    key={hour.hour}
                    className="flex items-center justify-between p-2 bg-gray-50 dark:bg-gray-800 rounded"
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-xs font-medium text-gray-500 dark:text-gray-400">#{i + 1}</span>
                      <span className="font-mono text-gray-900 dark:text-gray-50">
                        {String(hour.hour).padStart(2, '0')}:00 UTC
                      </span>
                    </div>
                    <div className="flex items-center gap-4 text-sm">
                      <span className="text-gray-600 dark:text-gray-300">
                        {(hour.avg_spread_pct * 100).toFixed(2)}% spread
                      </span>
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                        hour.recommendation === 'excellent' ? 'bg-emerald-100 dark:bg-emerald-900 text-emerald-700 dark:text-emerald-300' :
                        hour.recommendation === 'good' ? 'bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300' :
                        hour.recommendation === 'fair' ? 'bg-yellow-100 dark:bg-yellow-900 text-yellow-700 dark:text-yellow-300' :
                        'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300'
                      }`}>
                        {hour.recommendation}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
            {bestHours && bestHours.length === 0 && (
              <p className="text-sm text-gray-500 dark:text-gray-400">No data available</p>
            )}
          </Card>

          {/* Trading Cost Patterns (24h) */}
          <Card className="p-4">
            <h2 className="font-semibold text-gray-900 dark:text-gray-50 mb-4">Trading Cost Patterns (24h)</h2>
            {loadingPatterns && <LoadingSpinner />}
            {patterns && (
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <p className="text-gray-500 dark:text-gray-400">
                      Cheapest Hour <Tooltip content={glossary.best_hour} />
                    </p>
                    <p className="font-mono text-gray-900 dark:text-gray-50">
                      {String(patterns.best_hour).padStart(2, '0')}:00
                      <span className="text-emerald-600 dark:text-emerald-400 ml-2">
                        {(patterns.best_hour_spread * 100).toFixed(2)}%
                      </span>
                    </p>
                  </div>
                  <div>
                    <p className="text-gray-500 dark:text-gray-400">
                      Most Expensive Hour <Tooltip content={glossary.worst_hour} />
                    </p>
                    <p className="font-mono text-gray-900 dark:text-gray-50">
                      {String(patterns.worst_hour).padStart(2, '0')}:00
                      <span className="text-red-600 dark:text-red-400 ml-2">
                        {(patterns.worst_hour_spread * 100).toFixed(2)}%
                      </span>
                    </p>
                  </div>
                </div>
                <div>
                  <p className="text-gray-500 dark:text-gray-400 text-sm">Average Trading Cost</p>
                  <p className="font-mono text-gray-900 dark:text-gray-50">
                    {(patterns.overall_avg_spread * 100).toFixed(2)}%
                  </p>
                </div>
                <p className="text-xs text-gray-400 dark:text-gray-500">
                  Based on {patterns.snapshot_count} data points <Tooltip content={glossary.snapshot} />
                </p>
              </div>
            )}
          </Card>
        </div>
      )}

      {!tokenId && (
        <div className="text-center py-12 text-gray-500 dark:text-gray-400">
          Enter a token ID above to analyze its order book
        </div>
      )}
    </div>
  );
}
