import { cn } from '@/lib/utils';

type BadgeVariant = 'default' | 'severity' | 'status' | 'type';

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  color?: string;
  className?: string;
}

const severityColors: Record<string, string> = {
  critical: 'bg-red-50 text-red-700 border-red-200 dark:bg-red-950 dark:text-red-400 dark:border-red-800',
  high: 'bg-orange-50 text-orange-700 border-orange-200 dark:bg-orange-950 dark:text-orange-400 dark:border-orange-800',
  medium: 'bg-yellow-50 text-yellow-700 border-yellow-200 dark:bg-yellow-950 dark:text-yellow-400 dark:border-yellow-800',
  low: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950 dark:text-blue-400 dark:border-blue-800',
  info: 'bg-gray-50 text-gray-600 border-gray-200 dark:bg-gray-800 dark:text-gray-400 dark:border-gray-600',
};

const statusColors: Record<string, string> = {
  healthy: 'bg-green-50 text-green-700 border-green-200 dark:bg-green-950 dark:text-green-400 dark:border-green-800',
  degraded: 'bg-yellow-50 text-yellow-700 border-yellow-200 dark:bg-yellow-950 dark:text-yellow-400 dark:border-yellow-800',
  unhealthy: 'bg-red-50 text-red-700 border-red-200 dark:bg-red-950 dark:text-red-400 dark:border-red-800',
  success: 'bg-green-50 text-green-700 border-green-200 dark:bg-green-950 dark:text-green-400 dark:border-green-800',
  running: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950 dark:text-blue-400 dark:border-blue-800',
  failed: 'bg-red-50 text-red-700 border-red-200 dark:bg-red-950 dark:text-red-400 dark:border-red-800',
};

const typeColors: Record<string, string> = {
  volume_spike: 'bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-950 dark:text-purple-400 dark:border-purple-800',
  spread_alert: 'bg-indigo-50 text-indigo-700 border-indigo-200 dark:bg-indigo-950 dark:text-indigo-400 dark:border-indigo-800',
  mm_pullback: 'bg-pink-50 text-pink-700 border-pink-200 dark:bg-pink-950 dark:text-pink-400 dark:border-pink-800',
  arbitrage: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950 dark:text-emerald-400 dark:border-emerald-800',
};

export function Badge({ children, variant = 'default', color, className }: BadgeProps) {
  let colorClass = 'bg-gray-100 text-gray-700 border-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:border-gray-600';

  if (color) {
    if (variant === 'severity') {
      colorClass = severityColors[color] || colorClass;
    } else if (variant === 'status') {
      colorClass = statusColors[color] || colorClass;
    } else if (variant === 'type') {
      colorClass = typeColors[color] || colorClass;
    } else {
      // Default variant with direct color name
      const directColors: Record<string, string> = {
        green: 'bg-green-50 text-green-700 border-green-200 dark:bg-green-950 dark:text-green-400 dark:border-green-800',
        yellow: 'bg-yellow-50 text-yellow-700 border-yellow-200 dark:bg-yellow-950 dark:text-yellow-400 dark:border-yellow-800',
        red: 'bg-red-50 text-red-700 border-red-200 dark:bg-red-950 dark:text-red-400 dark:border-red-800',
        gray: 'bg-gray-100 text-gray-700 border-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:border-gray-600',
      };
      colorClass = directColors[color] || colorClass;
    }
  }

  return (
    <span
      className={cn(
        'inline-flex items-center px-2 py-0.5 text-xs font-medium rounded border',
        colorClass,
        className
      )}
    >
      {children}
    </span>
  );
}

// Convenience components for common badge types
export function SeverityBadge({ severity }: { severity: string }) {
  return (
    <Badge variant="severity" color={severity}>
      {severity}
    </Badge>
  );
}

export function StatusBadge({ status }: { status: string }) {
  return (
    <Badge variant="status" color={status}>
      {status}
    </Badge>
  );
}

export function TypeBadge({ type }: { type: string }) {
  const label = type
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');

  return (
    <Badge variant="type" color={type}>
      {label}
    </Badge>
  );
}
