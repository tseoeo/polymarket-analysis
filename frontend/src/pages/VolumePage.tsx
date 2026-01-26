import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { EmptyState } from '@/components/ui/EmptyState';
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
        <h1 className="text-2xl font-semibold text-gray-900 mb-2">
          Volume Analysis
        </h1>
        <p className="text-gray-600 max-w-2xl">
          Monitor volume spikes, identify high-activity markets, and track volume trends.
          Unusual volume often precedes significant price movements.
        </p>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="flex gap-4">
          <button
            onClick={() => setActiveTab('spikes')}
            className={`pb-3 px-1 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'spikes'
                ? 'border-gray-900 text-gray-900'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            Volume Spikes
          </button>
          <button
            onClick={() => setActiveTab('leaders')}
            className={`pb-3 px-1 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'leaders'
                ? 'border-gray-900 text-gray-900'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            Volume Leaders
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
            <div className="text-red-600 py-4">Failed to load volume spikes</div>
          )}

          {spikes && spikes.length === 0 && (
            <EmptyState
              title="No volume spikes"
              description="No unusual volume activity detected at this time."
            />
          )}

          {spikes && spikes.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {spikes.map((spike) => (
                <Card key={spike.id} className="p-4">
                  <div className="flex items-start justify-between mb-3">
                    <Badge color="yellow">Volume Spike</Badge>
                    <span className={`text-lg font-semibold ${
                      spike.volume_ratio >= 5 ? 'text-red-600' :
                      spike.volume_ratio >= 3 ? 'text-orange-600' :
                      'text-yellow-600'
                    }`}>
                      {spike.volume_ratio.toFixed(1)}x
                    </span>
                  </div>
                  <h3 className="font-medium text-gray-900 mb-2 text-sm">
                    {spike.title}
                  </h3>
                  <div className="space-y-1 text-sm text-gray-600">
                    <div className="flex justify-between">
                      <span>Current Volume:</span>
                      <span className="font-mono">${spike.current_volume.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Avg Volume:</span>
                      <span className="font-mono">${spike.average_volume.toLocaleString()}</span>
                    </div>
                  </div>
                  <div className="mt-3 pt-3 border-t border-gray-100 flex justify-between items-center">
                    <Link
                      to={`/markets/${spike.market_id}`}
                      className="text-xs text-blue-600 hover:underline"
                    >
                      View Market
                    </Link>
                    <span className="text-xs text-gray-400">
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
            <div className="text-red-600 py-4">Failed to load volume leaders</div>
          )}

          {leaders && leaders.length === 0 && (
            <EmptyState
              title="No volume data"
              description="No trading volume recorded in the last 24 hours."
            />
          )}

          {leaders && leaders.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="text-left text-xs text-gray-500 uppercase border-b border-gray-200">
                    <th className="pb-3 font-medium">Rank</th>
                    <th className="pb-3 font-medium">Market</th>
                    <th className="pb-3 font-medium text-right">24h Volume</th>
                    <th className="pb-3 font-medium text-right">Trades</th>
                    <th className="pb-3 font-medium text-right">Avg Trade</th>
                  </tr>
                </thead>
                <tbody>
                  {leaders.map((leader, i) => (
                    <tr key={`${leader.market_id}-${leader.token_id}`} className="border-b border-gray-100">
                      <td className="py-4 text-gray-500 font-medium">#{i + 1}</td>
                      <td className="py-4">
                        <Link
                          to={`/markets/${leader.market_id}`}
                          className="text-blue-600 hover:underline font-mono text-sm"
                        >
                          {leader.market_id.slice(0, 16)}...
                        </Link>
                      </td>
                      <td className="py-4 text-right font-mono">
                        ${leader.volume_24h.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                      </td>
                      <td className="py-4 text-right font-mono">
                        {leader.trade_count_24h.toLocaleString()}
                      </td>
                      <td className="py-4 text-right font-mono text-gray-600">
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
