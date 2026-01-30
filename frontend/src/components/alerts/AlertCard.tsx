import { Link } from 'react-router-dom';
import { Card } from '@/components/ui/Card';
import { SeverityBadge, TypeBadge } from '@/components/ui/Badge';
import { formatRelativeTime } from '@/lib/utils';
import { getAlertExplanation } from '@/lib/explanations';
import { ArrowRight } from 'lucide-react';
import type { Alert } from '@/types';

interface AlertCardProps {
  alert: Alert;
  showExplanation?: boolean;
}

export function AlertCard({ alert, showExplanation = true }: AlertCardProps) {
  const explanation = getAlertExplanation(alert.alert_type);

  return (
    <Link to={`/alerts/${alert.id}`}>
      <Card hover className="h-full flex flex-col">
        <div className="flex items-start justify-between gap-3 mb-2">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-lg" role="img" aria-label={explanation.title}>
              {explanation.icon}
            </span>
            <TypeBadge type={alert.alert_type} />
            <SeverityBadge severity={alert.severity} />
          </div>
          {!alert.is_active && (
            <span className="text-xs text-gray-400 dark:text-gray-500 whitespace-nowrap">Dismissed</span>
          )}
        </div>

        <h4 className="font-medium text-gray-900 dark:text-gray-50 mb-1 line-clamp-2">
          {alert.title}
        </h4>

        {showExplanation && (
          <p className="text-sm text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950 rounded px-2 py-1.5 mb-2">
            <span className="font-medium">Opportunity:</span> {explanation.opportunity}
          </p>
        )}

        {alert.description && (
          <p className="text-sm text-gray-500 dark:text-gray-400 line-clamp-2 mb-3 flex-grow">
            {alert.description}
          </p>
        )}

        <div className="flex items-center justify-between text-xs text-gray-400 dark:text-gray-500 mt-auto pt-2 border-t border-gray-100 dark:border-gray-800">
          <span>{formatRelativeTime(alert.created_at)}</span>
          <span className="flex items-center gap-1 text-blue-600 dark:text-blue-400">
            View details <ArrowRight className="w-3 h-3" />
          </span>
        </div>
      </Card>
    </Link>
  );
}
