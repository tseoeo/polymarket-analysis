import { AlertCard } from './AlertCard';
import { EmptyState } from '@/components/ui/EmptyState';
import { LoadingState } from '@/components/ui/LoadingSpinner';
import { Bell } from 'lucide-react';
import type { Alert } from '@/types';

interface AlertListProps {
  alerts: Alert[] | undefined;
  isLoading: boolean;
  error: Error | null;
}

export function AlertList({ alerts, isLoading, error }: AlertListProps) {
  if (isLoading) {
    return <LoadingState message="Loading alerts..." />;
  }

  if (error) {
    return (
      <EmptyState
        icon={<Bell className="w-6 h-6 text-red-400" />}
        title="Failed to load alerts"
        description={error.message}
      />
    );
  }

  if (!alerts || alerts.length === 0) {
    return (
      <EmptyState
        icon={<Bell className="w-6 h-6 text-gray-400" />}
        title="No alerts found"
        description="Try adjusting your filters or check back later."
      />
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {alerts.map((alert) => (
        <AlertCard key={alert.id} alert={alert} />
      ))}
    </div>
  );
}
