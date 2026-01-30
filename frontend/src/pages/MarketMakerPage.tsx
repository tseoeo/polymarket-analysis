import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { EmptyState } from '@/components/ui/EmptyState';
import { useMMPullbacks, useBestTradingHoursOverall } from '@/hooks/useMarketMaker';

export function MarketMakerPage() {
  const [activeTab, setActiveTab] = useState<'pullbacks' | 'hours'>('pullbacks');

  const {
    data: pullbacks,
    isLoading: loadingPullbacks,
    error: pullbacksError,
  } = useMMPullbacks(true, 20);

  const {
    data: bestHours,
    isLoading: loadingHours,
    error: hoursError,
  } = useBestTradingHoursOverall(168, 24);

  return (
    <div className="page-container">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-50 mb-2">
          Market Maker Analysis
        </h1>
        <p className="text-gray-600 dark:text-gray-300 max-w-2xl">
          Track market maker activity and liquidity patterns. MM pullbacks often signal
          upcoming volatility, while activity patterns help identify optimal trading windows.
        </p>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 dark:border-gray-700 mb-6">
        <nav className="flex gap-4">
          <button
            onClick={() => setActiveTab('pullbacks')}
            className={`pb-3 px-1 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'pullbacks'
                ? 'border-gray-900 dark:border-gray-100 text-gray-900 dark:text-gray-50'
                : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
            }`}
          >
            MM Pullbacks
          </button>
          <button
            onClick={() => setActiveTab('hours')}
            className={`pb-3 px-1 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'hours'
                ? 'border-gray-900 dark:border-gray-100 text-gray-900 dark:text-gray-50'
                : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
            }`}
          >
            Best Trading Hours
          </button>
        </nav>
      </div>

      {activeTab === 'pullbacks' && (
        <>
          {/* Info Box */}
          <div className="mb-6 p-4 bg-amber-50 dark:bg-amber-950 rounded-lg border border-amber-200 dark:border-amber-800">
            <p className="text-sm text-amber-800 dark:text-amber-300">
              <strong>What is an MM Pullback?</strong> When market makers withdraw liquidity,
              it often signals that they anticipate volatility or have information about upcoming news.
              This can create both risk and opportunity.
            </p>
          </div>

          {loadingPullbacks && (
            <div className="flex justify-center py-12">
              <LoadingSpinner />
            </div>
          )}

          {pullbacksError && (
            <div className="text-red-600 dark:text-red-400 py-4">Failed to load MM pullbacks</div>
          )}

          {pullbacks && pullbacks.length === 0 && (
            <EmptyState
              title="No MM pullbacks"
              description="No significant market maker liquidity withdrawals detected."
            />
          )}

          {pullbacks && pullbacks.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {pullbacks.map((pullback) => (
                <Card key={pullback.id} className="p-4">
                  <div className="flex items-start justify-between mb-3">
                    <Badge color="red">MM Pullback</Badge>
                    <span className="text-lg font-semibold text-red-600 dark:text-red-400">
                      -{(pullback.depth_drop_pct * 100).toFixed(0)}%
                    </span>
                  </div>
                  <h3 className="font-medium text-gray-900 dark:text-gray-50 mb-2 text-sm">
                    {pullback.title}
                  </h3>
                  <div className="space-y-1 text-sm text-gray-600 dark:text-gray-300">
                    <div className="flex justify-between">
                      <span>Previous Depth:</span>
                      <span className="font-mono">${pullback.previous_depth.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Current Depth:</span>
                      <span className="font-mono text-red-600 dark:text-red-400">
                        ${pullback.current_depth.toLocaleString()}
                      </span>
                    </div>
                  </div>
                  <div className="mt-3 pt-3 border-t border-gray-100 dark:border-gray-800 flex justify-between items-center">
                    <Link
                      to={`/markets/${pullback.market_id}`}
                      className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
                    >
                      View Market
                    </Link>
                    <span className="text-xs text-gray-400 dark:text-gray-500">
                      {new Date(pullback.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </>
      )}

      {activeTab === 'hours' && (
        <>
          {/* Info Box */}
          <div className="mb-6 p-4 bg-blue-50 dark:bg-blue-950 rounded-lg border border-blue-200 dark:border-blue-800">
            <p className="text-sm text-blue-800 dark:text-blue-300">
              <strong>Trading Hour Quality</strong> is calculated based on average spread tightness
              and order book depth across all markets. Higher quality scores indicate better
              liquidity conditions for trading.
            </p>
          </div>

          {loadingHours && (
            <div className="flex justify-center py-12">
              <LoadingSpinner />
            </div>
          )}

          {hoursError && (
            <div className="text-red-600 dark:text-red-400 py-4">Failed to load trading hours</div>
          )}

          {bestHours && bestHours.length === 0 && (
            <EmptyState
              title="No data"
              description="Insufficient order book data to analyze trading hours."
            />
          )}

          {bestHours && bestHours.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Hourly Grid */}
              <Card className="p-4 md:col-span-2">
                <h3 className="font-semibold text-gray-900 dark:text-gray-50 mb-4">24-Hour Quality Heatmap</h3>
                <div className="grid grid-cols-6 md:grid-cols-12 gap-1">
                  {Array.from({ length: 24 }, (_, i) => {
                    const hourData = bestHours.find((h) => h.hour === i);
                    const quality = hourData?.quality_score || 0;
                    const bgColor =
                      quality >= 0.7 ? 'bg-emerald-500' :
                      quality >= 0.5 ? 'bg-emerald-300 dark:bg-emerald-600' :
                      quality >= 0.3 ? 'bg-yellow-300 dark:bg-yellow-600' :
                      quality >= 0.1 ? 'bg-orange-300 dark:bg-orange-600' :
                      'bg-gray-200 dark:bg-gray-700';

                    return (
                      <div
                        key={i}
                        className={`${bgColor} rounded p-2 text-center text-xs transition-all hover:scale-105`}
                        title={`${String(i).padStart(2, '0')}:00 UTC - Quality: ${(quality * 100).toFixed(0)}%`}
                      >
                        <span className={quality >= 0.5 ? 'text-white' : 'text-gray-700 dark:text-gray-300'}>
                          {String(i).padStart(2, '0')}
                        </span>
                      </div>
                    );
                  })}
                </div>
                <div className="flex items-center gap-4 mt-4 text-xs text-gray-600 dark:text-gray-300">
                  <span>Quality:</span>
                  <div className="flex items-center gap-1">
                    <div className="w-4 h-4 bg-emerald-500 rounded" />
                    <span>Excellent</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <div className="w-4 h-4 bg-emerald-300 dark:bg-emerald-600 rounded" />
                    <span>Good</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <div className="w-4 h-4 bg-yellow-300 dark:bg-yellow-600 rounded" />
                    <span>Fair</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <div className="w-4 h-4 bg-orange-300 dark:bg-orange-600 rounded" />
                    <span>Poor</span>
                  </div>
                </div>
              </Card>

              {/* Top Hours List */}
              <Card className="p-4">
                <h3 className="font-semibold text-gray-900 dark:text-gray-50 mb-4">Top 5 Trading Hours</h3>
                <div className="space-y-2">
                  {bestHours.slice(0, 5).map((hour, i) => (
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
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-gray-600 dark:text-gray-300">
                          {(hour.quality_score * 100).toFixed(0)}%
                        </span>
                        <div
                          className="w-16 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden"
                        >
                          <div
                            className="h-full bg-emerald-500"
                            style={{ width: `${hour.quality_score * 100}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </Card>

              {/* Statistics */}
              <Card className="p-4">
                <h3 className="font-semibold text-gray-900 dark:text-gray-50 mb-4">Statistics</h3>
                <div className="space-y-3">
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-600 dark:text-gray-300">Avg Spread (best hour):</span>
                    <span className="font-mono text-gray-900 dark:text-gray-50">
                      {bestHours[0] ? (bestHours[0].avg_spread_pct * 100).toFixed(3) : '-'}%
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-600 dark:text-gray-300">Avg Spread (worst hour):</span>
                    <span className="font-mono text-gray-900 dark:text-gray-50">
                      {bestHours.length > 0
                        ? (bestHours[bestHours.length - 1].avg_spread_pct * 100).toFixed(3)
                        : '-'}%
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-600 dark:text-gray-300">Markets Analyzed:</span>
                    <span className="font-mono text-gray-900 dark:text-gray-50">
                      {bestHours[0]?.market_count || 0}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-600 dark:text-gray-300">Best Hour Depth:</span>
                    <span className="font-mono text-gray-900 dark:text-gray-50">
                      ${bestHours[0]?.avg_depth.toLocaleString(undefined, { maximumFractionDigits: 0 }) || '-'}
                    </span>
                  </div>
                </div>
              </Card>
            </div>
          )}
        </>
      )}
    </div>
  );
}
