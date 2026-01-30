import { useParams, Link } from 'react-router-dom';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { PriceDisplay } from '@/components/markets/PriceDisplay';
import { AlertCard } from '@/components/alerts/AlertCard';
import { LoadingState } from '@/components/ui/LoadingSpinner';
import { EmptyState } from '@/components/ui/EmptyState';
import { useMarket, useMarketAlerts } from '@/hooks';
import { formatDate, formatCurrency } from '@/lib/utils';
import { ArrowLeft, BarChart3, Bell, ExternalLink } from 'lucide-react';

export function MarketDetailPage() {
  const { id } = useParams<{ id: string }>();
  const marketId = id || '';

  const { data: market, isLoading, error } = useMarket(marketId);
  const { data: alerts, isLoading: alertsLoading } = useMarketAlerts(marketId);

  if (isLoading) {
    return (
      <div className="page-container">
        <LoadingState message="Loading market..." />
      </div>
    );
  }

  if (error || !market) {
    return (
      <div className="page-container">
        <EmptyState
          icon={<BarChart3 className="w-6 h-6 text-gray-400 dark:text-gray-500" />}
          title="Market not found"
          description="The market you're looking for doesn't exist or has been removed."
        />
      </div>
    );
  }

  return (
    <div className="page-container">
      {/* Back button */}
      <Link
        to="/markets"
        className="inline-flex items-center gap-1 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 mb-4"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Markets
      </Link>

      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-2 mb-2">
          {market.active ? (
            <Badge color="success" variant="status">Active</Badge>
          ) : (
            <Badge>Closed</Badge>
          )}
          {market.active_alerts > 0 && (
            <Badge variant="severity" color="medium">
              <Bell className="w-3 h-3 mr-1" />
              {market.active_alerts} alerts
            </Badge>
          )}
        </div>
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-50">{market.question}</h1>
      </div>

      {/* Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Prices */}
          <Card>
            <CardHeader>
              <CardTitle>Current Prices</CardTitle>
            </CardHeader>
            <PriceDisplay
              yesPrice={market.yes_price}
              noPrice={market.no_price}
              size="lg"
            />
          </Card>

          {/* Description */}
          {market.description && (
            <Card>
              <CardHeader>
                <CardTitle>Description</CardTitle>
              </CardHeader>
              <p className="text-gray-700 dark:text-gray-200 whitespace-pre-wrap">
                {market.description}
              </p>
            </Card>
          )}

          {/* Alerts */}
          <Card padding="none">
            <div className="p-4 border-b border-gray-100 dark:border-gray-800">
              <CardTitle>Market Alerts</CardTitle>
            </div>
            <div className="p-4">
              {alertsLoading ? (
                <LoadingState message="Loading alerts..." />
              ) : !alerts?.length ? (
                <EmptyState
                  icon={<Bell className="w-6 h-6 text-gray-400 dark:text-gray-500" />}
                  title="No active alerts"
                  description="This market has no active alerts."
                />
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {alerts.map((alert) => (
                    <AlertCard key={alert.id} alert={alert} />
                  ))}
                </div>
              )}
            </div>
          </Card>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Market Stats</CardTitle>
            </CardHeader>
            <dl className="space-y-3">
              <StatItem label="Volume" value={formatCurrency(market.volume)} />
              <StatItem
                label="Liquidity"
                value={formatCurrency(market.liquidity)}
              />
              {market.end_date && (
                <StatItem label="End Date" value={formatDate(market.end_date)} />
              )}
            </dl>
          </Card>

          {market.outcomes && market.outcomes.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Outcomes</CardTitle>
              </CardHeader>
              <ul className="space-y-2">
                {market.outcomes.map((outcome, index) => (
                  <li
                    key={index}
                    className="text-sm text-gray-700 dark:text-gray-200 px-2 py-1 bg-gray-50 dark:bg-gray-800 rounded"
                  >
                    {outcome}
                  </li>
                ))}
              </ul>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle>Market ID</CardTitle>
            </CardHeader>
            <p className="text-xs text-gray-500 dark:text-gray-400 font-mono break-all">
              {market.id}
            </p>
            <a
              href={`https://polymarket.com/event/${market.id}`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-sm text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 mt-3"
            >
              View on Polymarket
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          </Card>
        </div>
      </div>
    </div>
  );
}

interface StatItemProps {
  label: string;
  value: string;
}

function StatItem({ label, value }: StatItemProps) {
  return (
    <div>
      <dt className="text-xs text-gray-500 dark:text-gray-400">{label}</dt>
      <dd className="text-sm font-medium text-gray-900 dark:text-gray-50 mt-0.5">{value}</dd>
    </div>
  );
}
