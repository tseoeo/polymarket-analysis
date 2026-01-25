import { useParams, useNavigate, Link } from 'react-router-dom';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { SeverityBadge, TypeBadge, Badge } from '@/components/ui/Badge';
import { LoadingState } from '@/components/ui/LoadingSpinner';
import { EmptyState } from '@/components/ui/EmptyState';
import { useAlert, useDismissAlert } from '@/hooks';
import { formatDate, formatRelativeTime } from '@/lib/utils';
import { ArrowLeft, Bell, CheckCircle, ExternalLink } from 'lucide-react';

export function AlertDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const alertId = Number(id);

  const { data: alert, isLoading, error } = useAlert(alertId);
  const dismissMutation = useDismissAlert();

  const handleDismiss = async () => {
    if (!alert) return;
    await dismissMutation.mutateAsync(alert.id);
  };

  if (isLoading) {
    return (
      <div className="page-container">
        <LoadingState message="Loading alert..." />
      </div>
    );
  }

  if (error || !alert) {
    return (
      <div className="page-container">
        <EmptyState
          icon={<Bell className="w-6 h-6 text-gray-400" />}
          title="Alert not found"
          description="The alert you're looking for doesn't exist or has been removed."
          action={
            <Button onClick={() => navigate('/alerts')}>Back to Alerts</Button>
          }
        />
      </div>
    );
  }

  return (
    <div className="page-container">
      {/* Back button */}
      <Link
        to="/alerts"
        className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 mb-4"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Alerts
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <TypeBadge type={alert.alert_type} />
            <SeverityBadge severity={alert.severity} />
            {!alert.is_active && (
              <Badge>
                <CheckCircle className="w-3 h-3 mr-1" />
                Dismissed
              </Badge>
            )}
          </div>
          <h1 className="text-2xl font-semibold text-gray-900">{alert.title}</h1>
          <p className="text-sm text-gray-500 mt-1">
            Created {formatRelativeTime(alert.created_at)}
          </p>
        </div>

        {alert.is_active && (
          <Button
            onClick={handleDismiss}
            loading={dismissMutation.isPending}
            variant="secondary"
          >
            <CheckCircle className="w-4 h-4 mr-1.5" />
            Dismiss
          </Button>
        )}
      </div>

      {/* Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main content */}
        <div className="lg:col-span-2 space-y-6">
          {alert.description && (
            <Card>
              <CardHeader>
                <CardTitle>Description</CardTitle>
              </CardHeader>
              <p className="text-gray-700 whitespace-pre-wrap">
                {alert.description}
              </p>
            </Card>
          )}

          {alert.data && Object.keys(alert.data).length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Details</CardTitle>
              </CardHeader>
              <div className="bg-gray-50 rounded-md p-4 overflow-x-auto">
                <pre className="text-sm text-gray-700">
                  {JSON.stringify(alert.data, null, 2)}
                </pre>
              </div>
            </Card>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Information</CardTitle>
            </CardHeader>
            <dl className="space-y-3">
              <InfoItem label="Alert ID" value={`#${alert.id}`} />
              <InfoItem label="Created" value={formatDate(alert.created_at)} />
              {alert.dismissed_at && (
                <InfoItem
                  label="Dismissed"
                  value={formatDate(alert.dismissed_at)}
                />
              )}
              {alert.expires_at && (
                <InfoItem label="Expires" value={formatDate(alert.expires_at)} />
              )}
            </dl>
          </Card>

          {alert.market_id && (
            <Card>
              <CardHeader>
                <CardTitle>Related Market</CardTitle>
              </CardHeader>
              <Link
                to={`/markets/${alert.market_id}`}
                className="inline-flex items-center gap-1 text-sm text-blue-600 hover:text-blue-700"
              >
                View market
                <ExternalLink className="w-3.5 h-3.5" />
              </Link>
              <p className="text-xs text-gray-500 mt-1 font-mono break-all">
                {alert.market_id}
              </p>
            </Card>
          )}

          {alert.related_market_ids && alert.related_market_ids.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Related Markets</CardTitle>
              </CardHeader>
              <ul className="space-y-2">
                {alert.related_market_ids.map((marketId) => (
                  <li key={marketId}>
                    <Link
                      to={`/markets/${marketId}`}
                      className="text-sm text-blue-600 hover:text-blue-700 font-mono break-all"
                    >
                      {marketId}
                    </Link>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

interface InfoItemProps {
  label: string;
  value: string;
}

function InfoItem({ label, value }: InfoItemProps) {
  return (
    <div>
      <dt className="text-xs text-gray-500">{label}</dt>
      <dd className="text-sm text-gray-900 mt-0.5">{value}</dd>
    </div>
  );
}
