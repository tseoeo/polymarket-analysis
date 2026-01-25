import { cn } from '@/lib/utils';

type StatusType = 'healthy' | 'degraded' | 'unhealthy' | 'success' | 'running' | 'failed' | 'default';

interface StatusDotProps {
  status: StatusType | string;
  pulse?: boolean;
  className?: string;
}

const statusColors: Record<string, string> = {
  healthy: 'bg-green-500',
  success: 'bg-green-500',
  degraded: 'bg-yellow-500',
  running: 'bg-blue-500',
  unhealthy: 'bg-red-500',
  failed: 'bg-red-500',
  default: 'bg-gray-400',
};

export function StatusDot({ status, pulse = false, className }: StatusDotProps) {
  const colorClass = statusColors[status] || statusColors.default;

  return (
    <span className={cn('relative flex h-2.5 w-2.5', className)}>
      {pulse && (
        <span
          className={cn(
            'absolute inline-flex h-full w-full rounded-full opacity-75 animate-ping',
            colorClass
          )}
        />
      )}
      <span className={cn('relative inline-flex rounded-full h-2.5 w-2.5', colorClass)} />
    </span>
  );
}
