import { Link } from 'react-router-dom';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { EmptyState } from '@/components/ui/EmptyState';
import { useDailyBriefing } from '@/hooks/useBriefing';
import { Clock, TrendingUp, AlertCircle, Lightbulb, ChevronRight, Shield } from 'lucide-react';
import type { Opportunity } from '@/api/briefing';

function SafetyScoreBadge({ score }: { score: number }) {
  const colorClass = score >= 70
    ? 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950 dark:text-emerald-400 dark:border-emerald-800'
    : score >= 50
    ? 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950 dark:text-amber-400 dark:border-amber-800'
    : 'bg-red-50 text-red-700 border-red-200 dark:bg-red-950 dark:text-red-400 dark:border-red-800';
  return (
    <div className="flex items-center gap-2">
      <Shield className="w-4 h-4 text-gray-500 dark:text-gray-400" />
      <span className={`inline-flex items-center px-3 py-1 text-sm font-semibold rounded border ${colorClass}`}>
        {score}
      </span>
    </div>
  );
}

function MetricBar({ value, max, label }: { value: number; max: number; label: string }) {
  const pct = Math.min((value / max) * 100, 100);
  const isGood = pct > 50;
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400">
        <span>{label}</span>
        <span>{value.toFixed(0)}</span>
      </div>
      <div className="h-1.5 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${isGood ? 'bg-emerald-500' : 'bg-amber-500'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function FreshnessBadge({ minutes }: { minutes: number | null }) {
  if (minutes === null) return <Badge color="gray">No data</Badge>;
  if (minutes < 15) return <Badge color="green">Updated {minutes.toFixed(0)}m ago</Badge>;
  if (minutes < 30) return <Badge color="yellow">Updated {minutes.toFixed(0)}m ago</Badge>;
  return <Badge color="red">Stale ({minutes.toFixed(0)}m)</Badge>;
}

function OpportunityCard({ opportunity }: { opportunity: Opportunity }) {
  const { metrics, scores } = opportunity;

  return (
    <Card className="p-5 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <FreshnessBadge minutes={metrics.freshness_minutes} />
            {opportunity.category && (
              <span className="text-xs text-gray-400 dark:text-gray-500">{opportunity.category}</span>
            )}
          </div>
          <h3 className="font-medium text-gray-900 dark:text-gray-50 line-clamp-2">
            {opportunity.market_question}
          </h3>
        </div>
        <div className="ml-4 flex-shrink-0">
          <SafetyScoreBadge score={opportunity.safety_score} />
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-2 gap-4 mb-4">
        <MetricBar
          value={metrics.total_depth}
          max={5000}
          label="Depth ($)"
        />
        <MetricBar
          value={scores.spread}
          max={20}
          label="Spread Score"
        />
      </div>

      {/* Spread & Depth Details */}
      <div className="flex gap-4 text-sm text-gray-600 dark:text-gray-300 mb-4">
        <div>
          <span className="text-gray-400 dark:text-gray-500">Spread:</span>{' '}
          {metrics.spread_pct !== null ? `${(metrics.spread_pct * 100).toFixed(2)}%` : 'N/A'}
        </div>
        <div>
          <span className="text-gray-400 dark:text-gray-500">Signals:</span>{' '}
          {metrics.signal_count}
        </div>
      </div>

      {/* Why Safe / What Could Go Wrong */}
      <div className="space-y-2 mb-4">
        <div className="flex items-start gap-2">
          <TrendingUp className="w-4 h-4 text-emerald-500 mt-0.5 flex-shrink-0" />
          <p className="text-sm text-gray-600 dark:text-gray-300">{opportunity.why_safe}</p>
        </div>
        <div className="flex items-start gap-2">
          <AlertCircle className="w-4 h-4 text-amber-500 mt-0.5 flex-shrink-0" />
          <p className="text-sm text-gray-500 dark:text-gray-400">{opportunity.what_could_go_wrong}</p>
        </div>
      </div>

      {/* Action */}
      <Link
        to={`/opportunity/${opportunity.market_id}`}
        className="flex items-center justify-center gap-2 w-full py-2 px-4 bg-gray-900 dark:bg-gray-100 text-white dark:text-gray-900 rounded-md text-sm font-medium hover:bg-gray-800 dark:hover:bg-gray-200 transition-colors"
      >
        View Details
        <ChevronRight className="w-4 h-4" />
      </Link>
    </Card>
  );
}

function LearningTip({ tip }: { tip: string }) {
  return (
    <Card className="p-4 bg-blue-50 dark:bg-blue-950 border-blue-100 dark:border-blue-800">
      <div className="flex items-start gap-3">
        <Lightbulb className="w-5 h-5 text-blue-600 dark:text-blue-400 mt-0.5 flex-shrink-0" />
        <div>
          <h4 className="font-medium text-blue-900 dark:text-blue-200 mb-1">Learning Tip</h4>
          <p className="text-sm text-blue-800 dark:text-blue-300">{tip}</p>
        </div>
      </div>
    </Card>
  );
}

export function DailyBriefingPage() {
  const { data, isLoading, error } = useDailyBriefing(5);

  return (
    <div className="page-container">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-50 mb-2">
          Daily Briefing
        </h1>
        <p className="text-gray-600 dark:text-gray-300 max-w-2xl">
          Today's safest trading opportunities. Each card shows a safety score (0-100)
          based on data freshness, liquidity, spread, and signal alignment.
        </p>
        {data && (
          <p className="text-sm text-gray-400 dark:text-gray-500 mt-2 flex items-center gap-2">
            <Clock className="w-4 h-4" />
            Generated {new Date(data.generated_at).toLocaleTimeString()}
          </p>
        )}
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="flex justify-center py-12">
          <LoadingSpinner />
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="text-red-600 dark:text-red-400 py-4">
          Failed to load daily briefing. Please try again later.
        </div>
      )}

      {/* Empty State */}
      {data && data.opportunities.length === 0 && (
        <EmptyState
          title="No safe opportunities today"
          description="No markets currently pass all safety filters. Check back later or explore the markets page for learning."
        />
      )}

      {/* Content */}
      {data && data.opportunities.length > 0 && (
        <div className="space-y-6">
          {/* Learning Tip */}
          <LearningTip tip={data.learning_tip} />

          {/* Opportunity Count */}
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-medium text-gray-900 dark:text-gray-50">
              Top {data.opportunity_count} Safe Opportunities
            </h2>
            <Link
              to="/watchlist"
              className="text-sm text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300"
            >
              View Watchlist
            </Link>
          </div>

          {/* Opportunities Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {data.opportunities.map((opp) => (
              <OpportunityCard key={opp.market_id} opportunity={opp} />
            ))}
          </div>

          {/* Safety Score Legend */}
          <Card className="p-4 bg-gray-50 dark:bg-gray-800">
            <h4 className="font-medium text-gray-700 dark:text-gray-200 mb-3">Safety Score Breakdown</h4>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <span className="text-gray-500 dark:text-gray-400">Freshness</span>
                <p className="font-medium text-gray-900 dark:text-gray-50">0-30 pts</p>
                <p className="text-xs text-gray-400 dark:text-gray-500">&lt;15min = 30pts</p>
              </div>
              <div>
                <span className="text-gray-500 dark:text-gray-400">Liquidity</span>
                <p className="font-medium text-gray-900 dark:text-gray-50">0-30 pts</p>
                <p className="text-xs text-gray-400 dark:text-gray-500">&gt;$2000 = 30pts</p>
              </div>
              <div>
                <span className="text-gray-500 dark:text-gray-400">Spread</span>
                <p className="font-medium text-gray-900 dark:text-gray-50">0-20 pts</p>
                <p className="text-xs text-gray-400 dark:text-gray-500">&lt;3% = 20pts</p>
              </div>
              <div>
                <span className="text-gray-500 dark:text-gray-400">Signals</span>
                <p className="font-medium text-gray-900 dark:text-gray-50">0-20 pts</p>
                <p className="text-xs text-gray-400 dark:text-gray-500">2+ = 20pts</p>
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
