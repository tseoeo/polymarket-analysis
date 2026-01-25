import { Link } from 'react-router-dom';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { PriceDisplay } from './PriceDisplay';
import { formatCurrency, formatRelativeTime } from '@/lib/utils';
import { Bell } from 'lucide-react';
import type { Market } from '@/types';

interface MarketCardProps {
  market: Market;
}

export function MarketCard({ market }: MarketCardProps) {
  return (
    <Link to={`/markets/${market.id}`}>
      <Card hover className="h-full">
        <div className="flex items-start justify-between gap-2 mb-3">
          <div className="flex items-center gap-2">
            {market.active ? (
              <Badge color="success" variant="status">Active</Badge>
            ) : (
              <Badge>Closed</Badge>
            )}
            {market.active_alerts > 0 && (
              <span className="inline-flex items-center gap-1 text-xs text-amber-600">
                <Bell className="w-3.5 h-3.5" />
                {market.active_alerts}
              </span>
            )}
          </div>
        </div>

        <h4 className="font-medium text-gray-900 mb-3 line-clamp-2">
          {market.question}
        </h4>

        <PriceDisplay
          yesPrice={market.yes_price}
          noPrice={market.no_price}
          size="sm"
        />

        <div className="flex items-center justify-between mt-4 pt-3 border-t border-gray-100 text-xs text-gray-500">
          <span>Vol: {formatCurrency(market.volume)}</span>
          {market.end_date && (
            <span>Ends {formatRelativeTime(market.end_date)}</span>
          )}
        </div>
      </Card>
    </Link>
  );
}
