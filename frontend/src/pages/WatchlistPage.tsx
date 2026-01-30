import { Link } from 'react-router-dom';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { EmptyState } from '@/components/ui/EmptyState';
import { useWatchlist, useRemoveFromWatchlist, useMarkWatchlistViewed } from '@/hooks/useBriefing';
import {
  Eye,
  Trash2,
  TrendingUp,
  TrendingDown,
  Bell,
  ChevronRight,
  Shield,
  Clock,
} from 'lucide-react';
import type { WatchlistItem } from '@/api/briefing';

function ScoreChange({ change }: { change: number | null }) {
  if (change === null) return null;
  if (change > 0) {
    return (
      <span className="flex items-center text-emerald-600 dark:text-emerald-400 text-sm">
        <TrendingUp className="w-4 h-4 mr-1" />
        +{change}
      </span>
    );
  }
  if (change < 0) {
    return (
      <span className="flex items-center text-red-600 dark:text-red-400 text-sm">
        <TrendingDown className="w-4 h-4 mr-1" />
        {change}
      </span>
    );
  }
  return <span className="text-gray-400 dark:text-gray-500 text-sm">No change</span>;
}

function WatchlistItemCard({
  item,
  onRemove,
  onMarkViewed,
}: {
  item: WatchlistItem;
  onRemove: () => void;
  onMarkViewed: () => void;
}) {
  const scoreColor =
    item.current_safety_score !== null
      ? item.current_safety_score >= 70
        ? 'green'
        : item.current_safety_score >= 50
        ? 'yellow'
        : 'red'
      : 'gray';

  return (
    <Card className="p-4">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="flex flex-col items-center">
            <Shield className="w-4 h-4 text-gray-400 dark:text-gray-500 mb-1" />
            <Badge color={scoreColor}>
              {item.current_safety_score ?? 'N/A'}
            </Badge>
          </div>
          <div>
            <Link
              to={`/opportunity/${item.market_id}`}
              className="font-medium text-gray-900 dark:text-gray-50 hover:text-blue-600 dark:hover:text-blue-400 line-clamp-2"
              onClick={onMarkViewed}
            >
              {item.market_question || item.market_id}
            </Link>
            {item.category && (
              <span className="text-xs text-gray-400 dark:text-gray-500">{item.category}</span>
            )}
          </div>
        </div>
        {item.new_alerts_count > 0 && (
          <span className="inline-flex items-center px-2 py-0.5 text-xs font-medium rounded border bg-red-50 text-red-700 border-red-200 dark:bg-red-950 dark:text-red-400 dark:border-red-800">
            <Bell className="w-3 h-3 mr-1" />
            {item.new_alerts_count} new
          </span>
        )}
      </div>

      {/* Metrics Row */}
      <div className="flex gap-4 text-sm text-gray-600 dark:text-gray-300 mb-3">
        <div>
          <span className="text-gray-400 dark:text-gray-500">Spread:</span>{' '}
          {item.spread_pct !== null ? `${(item.spread_pct * 100).toFixed(2)}%` : 'N/A'}
        </div>
        <div>
          <span className="text-gray-400 dark:text-gray-500">Depth:</span>{' '}
          {item.total_depth !== null ? `$${item.total_depth.toFixed(0)}` : 'N/A'}
        </div>
        <div className="flex items-center gap-1">
          <span className="text-gray-400 dark:text-gray-500">Change:</span>
          <ScoreChange change={item.score_change} />
        </div>
      </div>

      {/* Notes */}
      {item.notes && (
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-3 italic">"{item.notes}"</p>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between pt-3 border-t border-gray-100 dark:border-gray-800">
        <div className="flex items-center gap-4 text-xs text-gray-400 dark:text-gray-500">
          <span className="flex items-center gap-1">
            <Clock className="w-3 h-3" />
            Added {new Date(item.added_at).toLocaleDateString()}
          </span>
          {item.last_viewed_at && (
            <span>
              Last viewed {new Date(item.last_viewed_at).toLocaleDateString()}
            </span>
          )}
        </div>
        <div className="flex gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={onMarkViewed}
            title="Mark as viewed"
          >
            <Eye className="w-4 h-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={onRemove}
            title="Remove from watchlist"
          >
            <Trash2 className="w-4 h-4 text-red-500" />
          </Button>
          <Link to={`/opportunity/${item.market_id}`}>
            <Button variant="secondary" size="sm">
              Details
              <ChevronRight className="w-4 h-4 ml-1" />
            </Button>
          </Link>
        </div>
      </div>
    </Card>
  );
}

export function WatchlistPage() {
  const { data, isLoading, error } = useWatchlist();
  const removeFromWatchlist = useRemoveFromWatchlist();
  const markViewed = useMarkWatchlistViewed();

  const handleRemove = async (itemId: number) => {
    try {
      await removeFromWatchlist.mutateAsync(itemId);
    } catch (err) {
      console.error('Failed to remove from watchlist:', err);
    }
  };

  const handleMarkViewed = async (itemId: number) => {
    try {
      await markViewed.mutateAsync(itemId);
    } catch (err) {
      console.error('Failed to mark as viewed:', err);
    }
  };

  return (
    <div className="page-container">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-50 mb-2">
          Watchlist
        </h1>
        <p className="text-gray-600 dark:text-gray-300 max-w-2xl">
          Markets you're learning about. Track safety score changes and alerts without
          the pressure of trading. When you're ready, dive into the details.
        </p>
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
          Failed to load watchlist. Please try again later.
        </div>
      )}

      {/* Empty State */}
      {data && data.items.length === 0 && (
        <EmptyState
          title="Your watchlist is empty"
          description="Add markets from the Daily Briefing to track them here."
          action={
            <Link to="/briefing">
              <Button>
                Browse Daily Briefing
                <ChevronRight className="w-4 h-4 ml-2" />
              </Button>
            </Link>
          }
        />
      )}

      {/* Watchlist Items */}
      {data && data.items.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-500 dark:text-gray-400">
              {data.total_count} market{data.total_count !== 1 ? 's' : ''} tracked
            </span>
            <Link to="/briefing" className="text-sm text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300">
              Find more opportunities
            </Link>
          </div>

          {data.items.map((item) => (
            <WatchlistItemCard
              key={item.id}
              item={item}
              onRemove={() => handleRemove(item.id)}
              onMarkViewed={() => handleMarkViewed(item.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
