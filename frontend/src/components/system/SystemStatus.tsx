import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { StatusDot } from '@/components/ui/StatusDot';
import { JobStatusCard } from './JobStatusCard';
import { LoadingState } from '@/components/ui/LoadingSpinner';
import { formatRelativeTime, formatNumber } from '@/lib/utils';
import { useSystemStatus } from '@/hooks';
import { AlertCircle } from 'lucide-react';

export function SystemStatus() {
  const { data: status, isLoading, error } = useSystemStatus();

  if (isLoading) {
    return (
      <Card>
        <LoadingState message="Loading system status..." />
      </Card>
    );
  }

  if (error || !status) {
    return (
      <Card>
        <div className="flex items-center gap-3 text-gray-500">
          <AlertCircle className="w-5 h-5" />
          <span className="text-sm">Unable to load system status</span>
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Overall Status */}
      <Card>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <StatusDot status={status.status} pulse={status.status === 'degraded'} />
            <div>
              <h3 className="font-medium text-gray-900 capitalize">
                System {status.status}
              </h3>
              <p className="text-sm text-gray-500">
                Last updated {formatRelativeTime(status.timestamp)}
              </p>
            </div>
          </div>

          {status.counts && (
            <div className="flex gap-6 text-sm">
              <div className="text-center">
                <p className="font-semibold text-gray-900">
                  {formatNumber(status.counts.markets_active)}
                </p>
                <p className="text-gray-500">Markets</p>
              </div>
              <div className="text-center">
                <p className="font-semibold text-gray-900">
                  {formatNumber(status.counts.alerts_active)}
                </p>
                <p className="text-gray-500">Alerts</p>
              </div>
              <div className="text-center">
                <p className="font-semibold text-gray-900">
                  {formatNumber(status.counts.trades_24h)}
                </p>
                <p className="text-gray-500">Trades (24h)</p>
              </div>
            </div>
          )}
        </div>
      </Card>

      {/* Data Freshness */}
      <Card>
        <CardHeader>
          <CardTitle>Data Freshness</CardTitle>
        </CardHeader>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <FreshnessItem
            label="Last Trade"
            value={status.data_freshness.last_trade}
          />
          <FreshnessItem
            label="Last Orderbook"
            value={status.data_freshness.last_orderbook}
          />
          <FreshnessItem
            label="Last Analysis"
            value={status.data_freshness.last_analysis}
          />
          <FreshnessItem
            label="Last Market Sync"
            value={status.data_freshness.last_market_sync}
          />
        </div>
      </Card>

      {/* Job Status */}
      <Card padding="none">
        <div className="p-4 border-b border-gray-100">
          <CardTitle>Background Jobs</CardTitle>
          <p className="text-sm text-gray-500 mt-1">
            Scheduler is {status.scheduler.enabled ? 'enabled' : 'disabled'}
          </p>
        </div>
        <div className="divide-y divide-gray-100">
          {status.scheduler.jobs.map((job) => (
            <div key={job.id} className="p-3">
              <JobStatusCard job={job} />
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

interface FreshnessItemProps {
  label: string;
  value: string | null;
}

function FreshnessItem({ label, value }: FreshnessItemProps) {
  return (
    <div>
      <p className="text-sm text-gray-500">{label}</p>
      <p className="text-sm font-medium text-gray-900">
        {value ? formatRelativeTime(value) : 'Never'}
      </p>
    </div>
  );
}
