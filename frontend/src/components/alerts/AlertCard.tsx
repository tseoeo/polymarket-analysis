import { Link } from 'react-router-dom';
import { Card } from '@/components/ui/Card';
import { SeverityBadge, TypeBadge } from '@/components/ui/Badge';
import { formatRelativeTime } from '@/lib/utils';
import type { Alert } from '@/types';

interface AlertCardProps {
  alert: Alert;
}

export function AlertCard({ alert }: AlertCardProps) {
  return (
    <Link to={`/alerts/${alert.id}`}>
      <Card hover className="h-full">
        <div className="flex items-start justify-between gap-3 mb-2">
          <div className="flex items-center gap-2 flex-wrap">
            <TypeBadge type={alert.alert_type} />
            <SeverityBadge severity={alert.severity} />
          </div>
          {!alert.is_active && (
            <span className="text-xs text-gray-400 whitespace-nowrap">Dismissed</span>
          )}
        </div>

        <h4 className="font-medium text-gray-900 mb-1 line-clamp-2">
          {alert.title}
        </h4>

        {alert.description && (
          <p className="text-sm text-gray-500 line-clamp-2 mb-3">
            {alert.description}
          </p>
        )}

        <div className="flex items-center justify-between text-xs text-gray-400">
          <span>{formatRelativeTime(alert.created_at)}</span>
          {alert.market_id && (
            <span className="truncate max-w-[120px]">
              {alert.market_id.slice(0, 8)}...
            </span>
          )}
        </div>
      </Card>
    </Link>
  );
}
