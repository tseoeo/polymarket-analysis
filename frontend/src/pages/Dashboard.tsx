import { Link } from 'react-router-dom';
import { Card, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { SystemStatus } from '@/components/system/SystemStatus';
import { AlertCard } from '@/components/alerts/AlertCard';
import { LoadingState } from '@/components/ui/LoadingSpinner';
import { EmptyState } from '@/components/ui/EmptyState';
import { useAlerts } from '@/hooks';
import { Bell, ArrowRight } from 'lucide-react';

export function Dashboard() {
  // Fetch recent active alerts
  const { data: alertsData, isLoading: alertsLoading } = useAlerts({
    is_active: true,
    limit: 6,
  });

  return (
    <div className="page-container">
      <h1 className="page-title">Dashboard</h1>

      {/* System Status */}
      <section className="mb-8">
        <SystemStatus />
      </section>

      {/* Recent Alerts */}
      <section>
        <Card padding="none">
          <div className="p-4 border-b border-gray-100 flex items-center justify-between">
            <div>
              <CardTitle>Recent Alerts</CardTitle>
              <p className="text-sm text-gray-500 mt-1">
                Latest active alerts from analysis
              </p>
            </div>
            <Link to="/alerts">
              <Button variant="ghost" size="sm">
                View all
                <ArrowRight className="w-4 h-4 ml-1" />
              </Button>
            </Link>
          </div>

          <div className="p-4">
            {alertsLoading ? (
              <LoadingState message="Loading alerts..." />
            ) : !alertsData?.alerts.length ? (
              <EmptyState
                icon={<Bell className="w-6 h-6 text-gray-400" />}
                title="No active alerts"
                description="The system is running smoothly with no anomalies detected."
              />
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {alertsData.alerts.map((alert) => (
                  <AlertCard key={alert.id} alert={alert} />
                ))}
              </div>
            )}
          </div>
        </Card>
      </section>
    </div>
  );
}
