import { useParams, useNavigate, Link } from 'react-router-dom';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { SeverityBadge, TypeBadge, Badge } from '@/components/ui/Badge';
import { InfoBox } from '@/components/ui/Tooltip';
import { LoadingState } from '@/components/ui/LoadingSpinner';
import { EmptyState } from '@/components/ui/EmptyState';
import { useAlert, useDismissAlert } from '@/hooks';
import { formatDate, formatRelativeTime } from '@/lib/utils';
import { getAlertExplanation, severityExplanations } from '@/lib/explanations';
import { ArrowLeft, Bell, CheckCircle, ExternalLink, Lightbulb, AlertTriangle } from 'lucide-react';

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
        <LoadingState message="Loading opportunity details..." />
      </div>
    );
  }

  if (error || !alert) {
    return (
      <div className="page-container">
        <EmptyState
          icon={<Bell className="w-6 h-6 text-gray-400" />}
          title="Opportunity not found"
          description="This alert may have expired or been removed."
          action={
            <Button onClick={() => navigate('/alerts')}>Back to Opportunities</Button>
          }
        />
      </div>
    );
  }

  const explanation = getAlertExplanation(alert.alert_type);
  const severityExplanation = severityExplanations[alert.severity] || '';

  return (
    <div className="page-container">
      {/* Back button */}
      <Link
        to="/alerts"
        className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 mb-4"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Opportunities
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="text-2xl">{explanation.icon}</span>
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
            Detected {formatRelativeTime(alert.created_at)} · {severityExplanation}
          </p>
        </div>

        {alert.is_active && (
          <Button
            onClick={handleDismiss}
            loading={dismissMutation.isPending}
            variant="secondary"
          >
            <CheckCircle className="w-4 h-4 mr-1.5" />
            Mark as Reviewed
          </Button>
        )}
      </div>

      {/* Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main content */}
        <div className="lg:col-span-2 space-y-6">
          {/* What This Means */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-amber-500" />
                What This Means
              </CardTitle>
            </CardHeader>
            <p className="text-gray-700">
              {explanation.whatItMeans}
            </p>
          </Card>

          {/* The Opportunity */}
          <InfoBox variant="tip">
            <p className="font-medium mb-1">The Opportunity</p>
            {explanation.opportunity}
          </InfoBox>

          {/* Suggested Action */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Lightbulb className="w-5 h-5 text-yellow-500" />
                Suggested Action
              </CardTitle>
            </CardHeader>
            <p className="text-gray-700">
              {explanation.action}
            </p>
          </Card>

          {/* Alert Details */}
          {alert.description && (
            <Card>
              <CardHeader>
                <CardTitle>Details</CardTitle>
              </CardHeader>
              <p className="text-gray-700 whitespace-pre-wrap">
                {alert.description}
              </p>
            </Card>
          )}

          {/* Raw Data */}
          {alert.data && Object.keys(alert.data).length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Technical Data</CardTitle>
              </CardHeader>
              <p className="text-sm text-gray-500 mb-3">
                Raw data from our analysis - useful for advanced traders
              </p>
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
          {/* Quick Info */}
          <Card>
            <CardHeader>
              <CardTitle>Quick Info</CardTitle>
            </CardHeader>
            <dl className="space-y-3">
              <InfoItem label="Alert ID" value={`#${alert.id}`} />
              <InfoItem label="Detected" value={formatDate(alert.created_at)} />
              <InfoItem
                label="Status"
                value={alert.is_active ? 'Active - Not yet reviewed' : 'Reviewed'}
              />
              {alert.dismissed_at && (
                <InfoItem
                  label="Reviewed on"
                  value={formatDate(alert.dismissed_at)}
                />
              )}
              {alert.expires_at && (
                <InfoItem label="Expires" value={formatDate(alert.expires_at)} />
              )}
            </dl>
          </Card>

          {/* Related Market */}
          {alert.market_id && (
            <Card>
              <CardHeader>
                <CardTitle>Related Market</CardTitle>
              </CardHeader>
              <p className="text-sm text-gray-600 mb-3">
                This opportunity was detected in the following market:
              </p>
              <Link
                to={`/markets/${alert.market_id}`}
                className="inline-flex items-center gap-1 text-sm text-blue-600 hover:text-blue-700 font-medium"
              >
                View Market Details
                <ExternalLink className="w-3.5 h-3.5" />
              </Link>
              <p className="text-xs text-gray-400 mt-2 font-mono break-all">
                ID: {alert.market_id}
              </p>
            </Card>
          )}

          {/* Related Markets (for arbitrage) */}
          {alert.related_market_ids && alert.related_market_ids.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Markets Involved</CardTitle>
              </CardHeader>
              <p className="text-sm text-gray-600 mb-3">
                This arbitrage opportunity spans multiple markets:
              </p>
              <ul className="space-y-2">
                {alert.related_market_ids.map((marketId, index) => (
                  <li key={marketId}>
                    <Link
                      to={`/markets/${marketId}`}
                      className="text-sm text-blue-600 hover:text-blue-700"
                    >
                      Market {index + 1}
                    </Link>
                    <p className="text-xs text-gray-400 font-mono truncate">
                      {marketId}
                    </p>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {/* Disclaimer */}
          <Card className="bg-gray-50 border-gray-200">
            <p className="text-xs text-gray-500">
              <strong>Disclaimer:</strong> This is not financial advice.
              Alerts are generated algorithmically and may contain false positives.
              Always do your own research before trading.
            </p>
          </Card>
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
