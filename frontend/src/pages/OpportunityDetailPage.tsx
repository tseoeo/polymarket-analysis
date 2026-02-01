import { useParams, Link } from 'react-router-dom';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { useOpportunityDetail, useAddToWatchlist } from '@/hooks/useBriefing';
import {
  Shield,
  ArrowLeft,
  BookOpen,
  CheckCircle,
  XCircle,
  AlertCircle,
  Plus,
  ExternalLink,
  Clock,
  DollarSign,
  Zap,
  Eye,
  Pause,
  Target,
} from 'lucide-react';
import type { ChecklistItem as ChecklistItemType, Scores, Metrics, Explanation } from '@/api/briefing';
import { useState } from 'react';

function HowToMonetizePill({ status, reason }: { status: string; reason: string }) {
  const config = {
    act_now: { icon: <Zap className="w-3 h-3" />, label: 'Act Now', className: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-300' },
    watch: { icon: <Eye className="w-3 h-3" />, label: 'Watch', className: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300' },
    wait: { icon: <Pause className="w-3 h-3" />, label: 'Wait', className: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300' },
  }[status] || { icon: null, label: status, className: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300' };

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${config.className}`} title={reason}>
      {config.icon}
      {config.label}
    </span>
  );
}

function SafetyScoreRing({ score, size = 'lg' }: { score: number; size?: 'sm' | 'lg' }) {
  const color = score >= 70 ? 'text-emerald-500' : score >= 50 ? 'text-amber-500' : 'text-red-500';
  const bgColor = score >= 70 ? 'bg-emerald-50 dark:bg-emerald-950' : score >= 50 ? 'bg-amber-50 dark:bg-amber-950' : 'bg-red-50 dark:bg-red-950';
  const dimensions = size === 'lg' ? 'w-24 h-24' : 'w-16 h-16';
  const textSize = size === 'lg' ? 'text-3xl' : 'text-xl';

  return (
    <div className={`${dimensions} ${bgColor} rounded-full flex flex-col items-center justify-center`}>
      <span className={`${textSize} font-bold ${color}`}>{score}</span>
      <span className="text-xs text-gray-500 dark:text-gray-400">/ 100</span>
    </div>
  );
}

function ScoreBreakdown({ scores }: { scores: Scores }) {
  const items = [
    { label: 'Freshness', value: scores.freshness, max: 30, description: 'Data recency' },
    { label: 'Liquidity', value: scores.liquidity, max: 30, description: 'Order book depth' },
    { label: 'Spread', value: scores.spread, max: 20, description: 'Bid-ask gap' },
    { label: 'Alignment', value: scores.alignment, max: 20, description: 'Signal confirmation' },
  ];

  return (
    <div className="space-y-3">
      {items.map((item) => (
        <div key={item.label}>
          <div className="flex justify-between text-sm mb-1">
            <span className="text-gray-600 dark:text-gray-300">{item.label}</span>
            <span className="font-medium text-gray-900 dark:text-gray-50">{item.value}/{item.max}</span>
          </div>
          <div className="h-2 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-gray-800 dark:bg-gray-200 rounded-full transition-all"
              style={{ width: `${(item.value / item.max) * 100}%` }}
            />
          </div>
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">{item.description}</p>
        </div>
      ))}
    </div>
  );
}

function MetricsPanel({ metrics }: { metrics: Metrics }) {
  return (
    <div className="grid grid-cols-2 gap-4">
      <div>
        <span className="text-sm text-gray-500 dark:text-gray-400">Spread</span>
        <p className="font-medium text-gray-900 dark:text-gray-50">
          {metrics.spread_pct !== null ? `${(metrics.spread_pct * 100).toFixed(2)}%` : 'N/A'}
        </p>
      </div>
      <div>
        <span className="text-sm text-gray-500 dark:text-gray-400">Total Depth</span>
        <p className="font-medium text-gray-900 dark:text-gray-50">${metrics.total_depth.toFixed(0)}</p>
      </div>
      <div>
        <span className="text-sm text-gray-500 dark:text-gray-400">Bid Depth (1%)</span>
        <p className="font-medium text-gray-900 dark:text-gray-50">${metrics.bid_depth_1pct.toFixed(0)}</p>
      </div>
      <div>
        <span className="text-sm text-gray-500 dark:text-gray-400">Ask Depth (1%)</span>
        <p className="font-medium text-gray-900 dark:text-gray-50">${metrics.ask_depth_1pct.toFixed(0)}</p>
      </div>
      <div>
        <span className="text-sm text-gray-500 dark:text-gray-400">Best Bid</span>
        <p className="font-medium text-gray-900 dark:text-gray-50">
          {metrics.best_bid !== null ? `$${metrics.best_bid.toFixed(3)}` : 'N/A'}
        </p>
      </div>
      <div>
        <span className="text-sm text-gray-500 dark:text-gray-400">Best Ask</span>
        <p className="font-medium text-gray-900 dark:text-gray-50">
          {metrics.best_ask !== null ? `$${metrics.best_ask.toFixed(3)}` : 'N/A'}
        </p>
      </div>
      <div className="col-span-2">
        <span className="text-sm text-gray-500 dark:text-gray-400">Active Signals</span>
        <div className="flex gap-2 mt-1 flex-wrap">
          {metrics.active_signals.length > 0 ? (
            metrics.active_signals.map((signal) => (
              <span
                key={signal}
                className="inline-flex items-center px-2 py-0.5 text-xs font-medium rounded border bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950 dark:text-blue-400 dark:border-blue-800"
              >
                {signal.replace(/_/g, ' ')}
              </span>
            ))
          ) : (
            <span className="text-gray-400 dark:text-gray-500 text-sm">None</span>
          )}
        </div>
      </div>
    </div>
  );
}

function ChecklistItem({ item, onToggle }: { item: ChecklistItemType; onToggle?: () => void }) {
  const isUserConfirm = item.passed === null;
  const [confirmed, setConfirmed] = useState(false);

  const handleClick = () => {
    if (isUserConfirm) {
      setConfirmed(!confirmed);
      onToggle?.();
    }
  };

  const icon = isUserConfirm ? (
    confirmed ? (
      <CheckCircle className="w-5 h-5 text-emerald-500" />
    ) : (
      <AlertCircle className="w-5 h-5 text-gray-400 dark:text-gray-500" />
    )
  ) : item.passed ? (
    <CheckCircle className="w-5 h-5 text-emerald-500" />
  ) : (
    <XCircle className="w-5 h-5 text-red-500" />
  );

  return (
    <div
      onClick={handleClick}
      className={`flex items-start gap-3 p-3 rounded-lg border transition-colors ${
        isUserConfirm
          ? 'cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 border-dashed'
          : ''
      } ${
        isUserConfirm && confirmed
          ? 'bg-emerald-50 border-emerald-200 dark:bg-emerald-950 dark:border-emerald-800'
          : 'border-gray-200 dark:border-gray-700'
      }`}
    >
      {icon}
      <div className="flex-1">
        <p className={`font-medium ${isUserConfirm && !confirmed ? 'text-gray-500 dark:text-gray-400' : 'text-gray-900 dark:text-gray-50'}`}>
          {item.label}
        </p>
        <p className="text-sm text-gray-500 dark:text-gray-400">{item.detail}</p>
      </div>
    </div>
  );
}

export function OpportunityDetailPage() {
  const { marketId } = useParams<{ marketId: string }>();
  const { data, isLoading, error } = useOpportunityDetail(marketId || '');
  const addToWatchlist = useAddToWatchlist();
  const [isAdded, setIsAdded] = useState(false);

  const handleAddToWatchlist = async () => {
    if (!marketId) return;
    try {
      await addToWatchlist.mutateAsync({ market_id: marketId });
      setIsAdded(true);
    } catch (err) {
      console.error('Failed to add to watchlist:', err);
    }
  };

  if (isLoading) {
    return (
      <div className="page-container flex justify-center py-12">
        <LoadingSpinner />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="page-container">
        <div className="text-red-600 dark:text-red-400 py-4">
          Failed to load opportunity details.
        </div>
        <Link to="/briefing" className="text-blue-600 dark:text-blue-400 hover:underline">
          Back to Daily Briefing
        </Link>
      </div>
    );
  }

  return (
    <div className="page-container">
      {/* Back Link */}
      <Link
        to="/briefing"
        className="inline-flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 mb-6"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Daily Briefing
      </Link>

      {/* Header */}
      <div className="flex items-start gap-6 mb-8">
        <SafetyScoreRing score={data.safety_score} />
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            {data.category && (
              <Badge color="gray">{data.category}</Badge>
            )}
            {data.last_updated && (
              <span className="text-xs text-gray-400 dark:text-gray-500 flex items-center gap-1">
                <Clock className="w-3 h-3" />
                Updated {new Date(data.last_updated).toLocaleTimeString()}
              </span>
            )}
          </div>
          <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-50 mb-4">
            {data.market_question}
          </h1>
          <div className="flex gap-3">
            <Button
              onClick={handleAddToWatchlist}
              disabled={isAdded || addToWatchlist.isPending}
              variant={isAdded ? 'secondary' : 'primary'}
            >
              {isAdded ? (
                <>
                  <CheckCircle className="w-4 h-4 mr-2" />
                  Added to Watchlist
                </>
              ) : (
                <>
                  <Plus className="w-4 h-4 mr-2" />
                  Add to Watchlist
                </>
              )}
            </Button>
            <a
              href={`https://polymarket.com/event/${data.market_id}`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center px-3 py-2 text-sm font-medium rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
            >
              Open on Polymarket
              <ExternalLink className="w-4 h-4 ml-2" />
            </a>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content - 2 cols */}
        <div className="lg:col-span-2 space-y-6">
          {/* How to Monetize */}
          {data.explanation && (
            <Card className="p-6">
              <div className="flex items-center gap-2 mb-4">
                <Target className="w-5 h-5 text-purple-600 dark:text-purple-400" />
                <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-50">How to Monetize</h2>
                <HowToMonetizePill status={data.explanation.best_time_to_act.status} reason={data.explanation.best_time_to_act.reason} />
              </div>
              <div className="space-y-4">
                <div>
                  <h3 className="font-medium text-gray-700 dark:text-gray-200 mb-1">Opportunity</h3>
                  <p className="text-gray-600 dark:text-gray-300">{data.explanation.opportunity}</p>
                </div>
                <div>
                  <h3 className="font-medium text-gray-700 dark:text-gray-200 mb-1">Action</h3>
                  <p className="text-gray-600 dark:text-gray-300">{data.explanation.action}</p>
                </div>
                <div className="bg-gray-50 dark:bg-gray-800 p-4 rounded-lg">
                  <h3 className="font-medium text-gray-700 dark:text-gray-200 mb-2 flex items-center gap-2">
                    <DollarSign className="w-4 h-4" />
                    Profit per €1
                  </h3>
                  <div className="grid grid-cols-2 gap-4 mb-2">
                    <div>
                      <span className="text-sm text-gray-500 dark:text-gray-400">Conservative</span>
                      <p className="text-lg font-semibold text-gray-900 dark:text-gray-50">
                        {data.explanation.profit_per_eur.conservative !== null
                          ? `€${(data.explanation.profit_per_eur.conservative * 100).toFixed(1)}¢`
                          : 'N/A'}
                      </p>
                    </div>
                    <div>
                      <span className="text-sm text-gray-500 dark:text-gray-400">Optimistic</span>
                      <p className="text-lg font-semibold text-emerald-600 dark:text-emerald-400">
                        {data.explanation.profit_per_eur.optimistic !== null
                          ? `€${(data.explanation.profit_per_eur.optimistic * 100).toFixed(1)}¢`
                          : 'N/A'}
                      </p>
                    </div>
                  </div>
                  <p className="text-xs text-gray-500 dark:text-gray-400">{data.explanation.profit_per_eur.note}</p>
                  <p className="text-xs text-gray-400 dark:text-gray-500 mt-1 italic">{data.explanation.profit_math}</p>
                </div>
                {data.explanation.risks.length > 0 && (
                  <div>
                    <h3 className="font-medium text-gray-700 dark:text-gray-200 mb-2">Key Risks</h3>
                    <ul className="space-y-1">
                      {data.explanation.risks.map((risk, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm text-gray-600 dark:text-gray-300">
                          <AlertCircle className="w-4 h-4 text-amber-500 mt-0.5 flex-shrink-0" />
                          {risk}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                <p className="text-xs text-gray-400 dark:text-gray-500">{data.explanation.best_time_to_act.reason}</p>
              </div>
            </Card>
          )}

          {/* Teach Me Panel */}
          <Card className="p-6">
            <div className="flex items-center gap-2 mb-4">
              <BookOpen className="w-5 h-5 text-blue-600 dark:text-blue-400" />
              <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-50">Teach Me</h2>
            </div>
            <div className="space-y-4">
              <div>
                <h3 className="font-medium text-gray-700 dark:text-gray-200 mb-1">What this signal means</h3>
                <p className="text-gray-600 dark:text-gray-300">{data.teach_me.what_signal_means}</p>
              </div>
              <div>
                <h3 className="font-medium text-gray-700 dark:text-gray-200 mb-1">Why it can be safe</h3>
                <p className="text-gray-600 dark:text-gray-300">{data.teach_me.why_safe}</p>
              </div>
              <div>
                <h3 className="font-medium text-gray-700 dark:text-gray-200 mb-1">What would invalidate it</h3>
                <p className="text-gray-600 dark:text-gray-300">{data.teach_me.what_invalidates}</p>
              </div>
              <div className="bg-amber-50 dark:bg-amber-950 p-4 rounded-lg border border-amber-100 dark:border-amber-800">
                <h3 className="font-medium text-amber-800 dark:text-amber-300 mb-1">Risk with 100 EUR</h3>
                <p className="text-amber-700 dark:text-amber-400">{data.teach_me.risk_with_100_eur}</p>
              </div>
            </div>
          </Card>

          {/* Go/No-Go Checklist */}
          <Card className="p-6">
            <div className="flex items-center gap-2 mb-4">
              <Shield className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
              <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-50">Go / No-Go Checklist</h2>
            </div>
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
              All items should be checked before considering a trade.
            </p>
            <div className="space-y-3">
              {data.checklist.map((item, index) => (
                <ChecklistItem key={index} item={item} />
              ))}
            </div>
          </Card>
        </div>

        {/* Sidebar - 1 col */}
        <div className="space-y-6">
          {/* Score Breakdown */}
          <Card className="p-5">
            <h3 className="font-semibold text-gray-900 dark:text-gray-50 mb-4">Score Breakdown</h3>
            <ScoreBreakdown scores={data.scores} />
          </Card>

          {/* Raw Metrics */}
          <Card className="p-5">
            <h3 className="font-semibold text-gray-900 dark:text-gray-50 mb-4">Raw Metrics</h3>
            <MetricsPanel metrics={data.metrics} />
          </Card>

          {/* Why Safe / Risk */}
          <Card className="p-5">
            <h3 className="font-semibold text-gray-900 dark:text-gray-50 mb-4">Summary</h3>
            <div className="space-y-4">
              <div>
                <p className="text-sm font-medium text-emerald-700 dark:text-emerald-400 mb-1">Why Safe</p>
                <p className="text-sm text-gray-600 dark:text-gray-300">{data.why_safe}</p>
              </div>
              <div>
                <p className="text-sm font-medium text-amber-700 dark:text-amber-400 mb-1">What Could Go Wrong</p>
                <p className="text-sm text-gray-600 dark:text-gray-300">{data.what_could_go_wrong}</p>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
