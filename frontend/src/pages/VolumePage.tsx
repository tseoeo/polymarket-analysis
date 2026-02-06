import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { EmptyState } from '@/components/ui/EmptyState';
import { InfoBox } from '@/components/ui/Tooltip';
import { useVolumeSpikes, useVolumeLeaders } from '@/hooks/useVolume';

export function VolumePage() {
  const [activeTab, setActiveTab] = useState<'spikes' | 'leaders'>('spikes');

  const {
    data: spikes,
    isLoading: loadingSpikes,
    error: spikesError,
  } = useVolumeSpikes(true, 20);

  const {
    data: leaders,
    isLoading: loadingLeaders,
    error: leadersError,
  } = useVolumeLeaders(10);

  return (
    <div className="page-container">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-50 mb-2">
          Trading Activity Monitor
        </h1>
        <p className="text-gray-600 dark:text-gray-300 max-w-2xl">
          Track which markets are seeing unusual trading activity. When trading volume suddenly
          spikes well above normal, it often means someone knows something — a news event, a leak,
          or informed traders taking positions before a price move.
        </p>
      </div>

      {/* Intro Explainer */}
      <InfoBox variant="info" className="mb-6">
        <strong>What is volume?</strong> Volume is simply the total dollar amount of trades
        happening in a market. Think of it like foot traffic in a store — if a normally quiet shop
        suddenly has a crowd, something interesting is probably happening. The <strong>volume
        ratio</strong> (e.g., &quot;5.2x&quot;) tells you how much higher current activity is compared to normal.
      </InfoBox>

      {/* Tabs */}
      <div className="border-b border-gray-200 dark:border-gray-700 mb-6">
        <nav className="flex gap-4">
          <button
            onClick={() => setActiveTab('spikes')}
            className={`pb-3 px-1 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'spikes'
                ? 'border-gray-900 dark:border-gray-100 text-gray-900 dark:text-gray-50'
                : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
            }`}
          >
            Unusual Activity
          </button>
          <button
            onClick={() => setActiveTab('leaders')}
            className={`pb-3 px-1 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'leaders'
                ? 'border-gray-900 dark:border-gray-100 text-gray-900 dark:text-gray-50'
                : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
            }`}
          >
            Most Active Markets
          </button>
        </nav>
      </div>

      {activeTab === 'spikes' && (
        <>
          {loadingSpikes && (
            <div className="flex justify-center py-12">
              <LoadingSpinner />
            </div>
          )}

          {spikesError && (
            <div className="text-red-600 dark:text-red-400 py-4">Failed to load volume spikes</div>
          )}

          {spikes && spikes.length === 0 && (
            <EmptyState
              title="No unusual activity"
              description="All markets are trading at normal levels right now. Check back later — spikes often happen around news events."
            />
          )}

          {spikes && spikes.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {spikes.map((spike) => (
                <Card key={spike.id} className="p-4">
                  <div className="flex items-start justify-between mb-3">
                    <Badge color="yellow">Activity Surge</Badge>
                    <span className={`text-lg font-semibold ${
                      spike.volume_ratio >= 5 ? 'text-red-600 dark:text-red-400' :
                      spike.volume_ratio >= 3 ? 'text-orange-600 dark:text-orange-400' :
                      'text-yellow-600 dark:text-yellow-400'
                    }`}>
                      {spike.volume_ratio.toFixed(1)}x normal
                    </span>
                  </div>
                  <h3 className="font-medium text-gray-900 dark:text-gray-50 mb-2 text-sm">
                    {spike.title}
                  </h3>
                  <div className="space-y-1 text-sm text-gray-600 dark:text-gray-300">
                    <div className="flex justify-between">
                      <span>Recent trading:</span>
                      <span className="font-mono">${spike.current_volume.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Normal level:</span>
                      <span className="font-mono">${spike.average_volume.toLocaleString()}</span>
                    </div>
                  </div>
                  <div className="mt-3 pt-3 border-t border-gray-100 dark:border-gray-800 flex justify-between items-center">
                    <Link
                      to={`/markets/${spike.market_id}`}
                      className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
                    >
                      View Market
                    </Link>
                    <span className="text-xs text-gray-400 dark:text-gray-500">
                      {new Date(spike.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </>
      )}

      {activeTab === 'leaders' && (
        <>
          {loadingLeaders && (
            <div className="flex justify-center py-12">
              <LoadingSpinner />
            </div>
          )}

          {leadersError && (
            <div className="text-red-600 dark:text-red-400 py-4">Failed to load volume leaders</div>
          )}

          {leaders && leaders.length === 0 && (
            <EmptyState
              title="No trading data"
              description="No trades recorded in the last 24 hours. This is unusual — the data collector may be offline."
            />
          )}

          {leaders && leaders.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="text-left text-xs text-gray-500 dark:text-gray-400 uppercase border-b border-gray-200 dark:border-gray-700">
                    <th className="pb-3 font-medium">Rank</th>
                    <th className="pb-3 font-medium">Market</th>
                    <th className="pb-3 font-medium text-right">24h Total Traded</th>
                    <th className="pb-3 font-medium text-right">Number of Trades</th>
                    <th className="pb-3 font-medium text-right">Avg Trade Size</th>
                  </tr>
                </thead>
                <tbody>
                  {leaders.map((leader, i) => (
                    <tr key={`${leader.market_id}-${leader.token_id}`} className="border-b border-gray-100 dark:border-gray-800">
                      <td className="py-4 text-gray-500 dark:text-gray-400 font-medium">#{i + 1}</td>
                      <td className="py-4">
                        <Link
                          to={`/markets/${leader.market_id}`}
                          className="text-blue-600 dark:text-blue-400 hover:underline font-mono text-sm"
                        >
                          {leader.market_id.slice(0, 16)}...
                        </Link>
                      </td>
                      <td className="py-4 text-right font-mono text-gray-900 dark:text-gray-50">
                        ${leader.volume_24h.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                      </td>
                      <td className="py-4 text-right font-mono text-gray-900 dark:text-gray-50">
                        {leader.trade_count_24h.toLocaleString()}
                      </td>
                      <td className="py-4 text-right font-mono text-gray-600 dark:text-gray-300">
                        ${leader.avg_trade_size.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
