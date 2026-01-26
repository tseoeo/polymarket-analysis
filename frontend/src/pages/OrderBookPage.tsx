import { useState } from 'react';
import { Card } from '@/components/ui/Card';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import {
  useOrderbook,
  useSlippage,
  useSpreadPatterns,
  useBestTradingHours,
} from '@/hooks/useOrderbook';

export function OrderBookPage() {
  const [tokenId, setTokenId] = useState('');
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

  return (
    <div className="page-container">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-gray-900 mb-2">
          Order Book Analysis
        </h1>
        <p className="text-gray-600 max-w-2xl">
          Analyze order book depth, calculate slippage for trade sizes, and identify
          optimal trading hours based on spread patterns.
        </p>
      </div>

      {/* Token Input */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Token ID
        </label>
        <input
          type="text"
          value={tokenId}
          onChange={(e) => setTokenId(e.target.value)}
          placeholder="Enter token ID to analyze..."
          className="w-full max-w-md px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent"
        />
      </div>

      {tokenId && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Current Orderbook */}
          <Card className="p-4">
            <h2 className="font-semibold text-gray-900 mb-4">Current Order Book</h2>
            {loadingOrderbook && <LoadingSpinner />}
            {orderbookError && (
              <p className="text-red-600 text-sm">Failed to load orderbook</p>
            )}
            {orderbook && (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs text-gray-500 uppercase">Best Bid</p>
                    <p className="text-lg font-mono text-emerald-600">
                      ${orderbook.best_bid?.toFixed(4) || '-'}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 uppercase">Best Ask</p>
                    <p className="text-lg font-mono text-red-600">
                      ${orderbook.best_ask?.toFixed(4) || '-'}
                    </p>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs text-gray-500 uppercase">Spread</p>
                    <p className="text-lg font-mono">
                      {orderbook.spread_pct ? (orderbook.spread_pct * 100).toFixed(2) : '-'}%
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 uppercase">Imbalance</p>
                    <p className={`text-lg font-mono ${
                      (orderbook.imbalance || 0) > 0 ? 'text-emerald-600' : 'text-red-600'
                    }`}>
                      {orderbook.imbalance?.toFixed(3) || '-'}
                    </p>
                  </div>
                </div>
                {orderbook.depth && (
                  <div className="pt-4 border-t border-gray-100">
                    <p className="text-sm font-medium text-gray-700 mb-2">Depth</p>
                    {Object.entries(orderbook.depth).map(([level, data]) => (
                      <div key={level} className="flex justify-between text-sm py-1">
                        <span className="text-gray-600">At {level}:</span>
                        <span>
                          <span className="text-emerald-600">${data.bid_depth.toFixed(0)}</span>
                          {' / '}
                          <span className="text-red-600">${data.ask_depth.toFixed(0)}</span>
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </Card>

          {/* Slippage Calculator */}
          <Card className="p-4">
            <h2 className="font-semibold text-gray-900 mb-4">Slippage Calculator</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-gray-600 mb-1">Trade Size ($)</label>
                <input
                  type="number"
                  value={tradeSize}
                  onChange={(e) => setTradeSize(Number(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">Side</label>
                <select
                  value={tradeSide}
                  onChange={(e) => setTradeSide(e.target.value as 'buy' | 'sell')}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                >
                  <option value="buy">Buy</option>
                  <option value="sell">Sell</option>
                </select>
              </div>
              {loadingSlippage && <LoadingSpinner />}
              {slippage && !slippage.error && (
                <div className="pt-4 border-t border-gray-100 space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-600">Best Price:</span>
                    <span className="font-mono">${slippage.best_price?.toFixed(4)}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-600">Expected Price:</span>
                    <span className="font-mono">${slippage.expected_price?.toFixed(4)}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-600">Slippage:</span>
                    <span className={`font-mono ${
                      (slippage.slippage_pct || 0) > 0.01 ? 'text-red-600' : 'text-gray-900'
                    }`}>
                      {slippage.slippage_pct ? (slippage.slippage_pct * 100).toFixed(3) : 0}%
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-600">Levels Consumed:</span>
                    <span className="font-mono">{slippage.levels_consumed}</span>
                  </div>
                </div>
              )}
              {slippage?.error && (
                <p className="text-sm text-red-600">{slippage.error}</p>
              )}
            </div>
          </Card>

          {/* Best Trading Hours */}
          <Card className="p-4">
            <h2 className="font-semibold text-gray-900 mb-4">Best Trading Hours</h2>
            {loadingBestHours && <LoadingSpinner />}
            {bestHours && bestHours.length > 0 && (
              <div className="space-y-2">
                {bestHours.map((hour, i) => (
                  <div
                    key={hour.hour}
                    className="flex items-center justify-between p-2 bg-gray-50 rounded"
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-xs font-medium text-gray-500">#{i + 1}</span>
                      <span className="font-mono">
                        {String(hour.hour).padStart(2, '0')}:00 UTC
                      </span>
                    </div>
                    <div className="flex items-center gap-4 text-sm">
                      <span className="text-gray-600">
                        {(hour.avg_spread_pct * 100).toFixed(2)}% spread
                      </span>
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                        hour.recommendation === 'excellent' ? 'bg-emerald-100 text-emerald-700' :
                        hour.recommendation === 'good' ? 'bg-blue-100 text-blue-700' :
                        hour.recommendation === 'fair' ? 'bg-yellow-100 text-yellow-700' :
                        'bg-gray-100 text-gray-700'
                      }`}>
                        {hour.recommendation}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
            {bestHours && bestHours.length === 0 && (
              <p className="text-sm text-gray-500">No data available</p>
            )}
          </Card>

          {/* Spread Patterns */}
          <Card className="p-4">
            <h2 className="font-semibold text-gray-900 mb-4">Spread Patterns (24h)</h2>
            {loadingPatterns && <LoadingSpinner />}
            {patterns && (
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <p className="text-gray-500">Best Hour</p>
                    <p className="font-mono">
                      {String(patterns.best_hour).padStart(2, '0')}:00
                      <span className="text-emerald-600 ml-2">
                        {(patterns.best_hour_spread * 100).toFixed(2)}%
                      </span>
                    </p>
                  </div>
                  <div>
                    <p className="text-gray-500">Worst Hour</p>
                    <p className="font-mono">
                      {String(patterns.worst_hour).padStart(2, '0')}:00
                      <span className="text-red-600 ml-2">
                        {(patterns.worst_hour_spread * 100).toFixed(2)}%
                      </span>
                    </p>
                  </div>
                </div>
                <div>
                  <p className="text-gray-500 text-sm">Overall Average</p>
                  <p className="font-mono">
                    {(patterns.overall_avg_spread * 100).toFixed(2)}%
                  </p>
                </div>
                <p className="text-xs text-gray-400">
                  Based on {patterns.snapshot_count} snapshots
                </p>
              </div>
            )}
          </Card>
        </div>
      )}

      {!tokenId && (
        <div className="text-center py-12 text-gray-500">
          Enter a token ID above to analyze its order book
        </div>
      )}
    </div>
  );
}
