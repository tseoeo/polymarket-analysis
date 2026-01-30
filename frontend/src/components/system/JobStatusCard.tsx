import { Card } from '@/components/ui/Card';
import { StatusDot } from '@/components/ui/StatusDot';
import { StatusBadge } from '@/components/ui/Badge';
import { formatRelativeTime, formatNumber } from '@/lib/utils';
import type { JobStatus } from '@/types';

interface JobStatusCardProps {
  job: JobStatus;
}

function formatJobName(id: string): string {
  return id
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

export function JobStatusCard({ job }: JobStatusCardProps) {
  const status = job.last_status || 'pending';

  return (
    <Card padding="sm">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <StatusDot
            status={status}
            pulse={status === 'running'}
          />
          <div>
            <h4 className="text-sm font-medium text-gray-900 dark:text-gray-50">
              {formatJobName(job.id)}
            </h4>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              {job.last_run ? formatRelativeTime(job.last_run) : 'Never run'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {job.records_processed !== null && (
            <span className="text-xs text-gray-500 dark:text-gray-400">
              {formatNumber(job.records_processed)} processed
            </span>
          )}
          <StatusBadge status={status} />
        </div>
      </div>

      {job.error_message && (
        <p className="mt-2 text-xs text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950 rounded px-2 py-1">
          {job.error_message}
        </p>
      )}
    </Card>
  );
}
