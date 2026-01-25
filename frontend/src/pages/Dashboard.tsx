import { Link } from 'react-router-dom';
import { Card, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { InfoBox } from '@/components/ui/Tooltip';
import { SystemStatus } from '@/components/system/SystemStatus';
import { AlertCard } from '@/components/alerts/AlertCard';
import { LoadingState } from '@/components/ui/LoadingSpinner';
import { EmptyState } from '@/components/ui/EmptyState';
import { useAlerts, useSystemStatus } from '@/hooks';
import { Bell, ArrowRight, TrendingUp, Zap, Search, DollarSign } from 'lucide-react';

export function Dashboard() {
  const { data: alertsData, isLoading: alertsLoading } = useAlerts({
    is_active: true,
    limit: 6,
  });

  const { data: systemStatus } = useSystemStatus();
  const activeAlerts = systemStatus?.counts?.alerts_active || 0;

  return (
    <div className="page-container">
      {/* Welcome Section */}
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-gray-900 mb-2">
          Polymarket Opportunity Scanner
        </h1>
        <p className="text-gray-600 max-w-2xl">
          This dashboard monitors prediction markets in real-time and alerts you to
          potential trading opportunities based on unusual market activity.
        </p>
      </div>

      {/* Quick Guide */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <QuickGuideCard
          icon={<TrendingUp className="w-5 h-5 text-purple-600" />}
          title="Volume Spikes"
          description="Sudden trading surges often signal informed traders acting on news"
        />
        <QuickGuideCard
          icon={<Zap className="w-5 h-5 text-amber-600" />}
          title="Wide Spreads"
          description="Large bid-ask gaps offer entry points and signal uncertainty"
        />
        <QuickGuideCard
          icon={<Search className="w-5 h-5 text-pink-600" />}
          title="Liquidity Drops"
          description="When market makers exit, big moves often follow"
        />
        <QuickGuideCard
          icon={<DollarSign className="w-5 h-5 text-emerald-600" />}
          title="Arbitrage"
          description="Price misalignments between related markets = risk-free profit"
        />
      </div>

      {/* Active Opportunities Summary */}
      {activeAlerts > 0 ? (
        <InfoBox variant="tip" className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <span className="font-semibold">{activeAlerts} active opportunities</span> detected across monitored markets.
              Review them below or visit the Alerts page for filtering options.
            </div>
            <Link to="/alerts">
              <Button variant="primary" size="sm">
                View All <ArrowRight className="w-4 h-4 ml-1" />
              </Button>
            </Link>
          </div>
        </InfoBox>
      ) : (
        <InfoBox variant="info" className="mb-8">
          <span className="font-semibold">No active opportunities right now.</span> The scanner is monitoring
          {systemStatus?.counts?.markets_active ? ` ${systemStatus.counts.markets_active.toLocaleString()} markets` : ' markets'} for anomalies.
          Check back soon or explore individual markets.
        </InfoBox>
      )}

      {/* Recent Opportunities */}
      <section className="mb-8">
        <Card padding="none">
          <div className="p-4 border-b border-gray-100 flex items-center justify-between">
            <div>
              <CardTitle>Recent Opportunities</CardTitle>
              <p className="text-sm text-gray-500 mt-1">
                Latest alerts from our analysis engine - each represents a potential edge
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
              <LoadingState message="Scanning for opportunities..." />
            ) : !alertsData?.alerts.length ? (
              <EmptyState
                icon={<Bell className="w-6 h-6 text-gray-400" />}
                title="No active opportunities"
                description="Markets are quiet. The scanner runs continuously and will surface opportunities as they appear."
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

      {/* How It Works */}
      <section className="mb-8">
        <Card>
          <CardTitle>How This Works</CardTitle>
          <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-6">
            <HowItWorksStep
              number={1}
              title="Continuous Monitoring"
              description="We collect trade data, order books, and market prices every few minutes from Polymarket."
            />
            <HowItWorksStep
              number={2}
              title="Pattern Detection"
              description="Our algorithms detect volume spikes, spread anomalies, liquidity changes, and cross-market arbitrage."
            />
            <HowItWorksStep
              number={3}
              title="Opportunity Alerts"
              description="When something unusual happens, we generate an alert explaining the opportunity and suggested action."
            />
          </div>
        </Card>
      </section>

      {/* System Status */}
      <section>
        <div className="mb-4">
          <h2 className="text-lg font-semibold text-gray-900">System Status</h2>
          <p className="text-sm text-gray-500">
            Data collection and analysis health - green means opportunities are being detected in real-time
          </p>
        </div>
        <SystemStatus />
      </section>
    </div>
  );
}

interface QuickGuideCardProps {
  icon: React.ReactNode;
  title: string;
  description: string;
}

function QuickGuideCard({ icon, title, description }: QuickGuideCardProps) {
  return (
    <Card className="flex items-start gap-3">
      <div className="p-2 bg-gray-100 rounded-lg">{icon}</div>
      <div>
        <h3 className="font-medium text-gray-900 text-sm">{title}</h3>
        <p className="text-xs text-gray-500 mt-0.5">{description}</p>
      </div>
    </Card>
  );
}

interface HowItWorksStepProps {
  number: number;
  title: string;
  description: string;
}

function HowItWorksStep({ number, title, description }: HowItWorksStepProps) {
  return (
    <div className="flex gap-3">
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gray-900 text-white flex items-center justify-center text-sm font-medium">
        {number}
      </div>
      <div>
        <h3 className="font-medium text-gray-900">{title}</h3>
        <p className="text-sm text-gray-500 mt-1">{description}</p>
      </div>
    </div>
  );
}
