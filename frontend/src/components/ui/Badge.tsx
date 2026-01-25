import { cn } from '@/lib/utils';

type BadgeVariant = 'default' | 'severity' | 'status' | 'type';

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  color?: string;
  className?: string;
}

const severityColors: Record<string, string> = {
  critical: 'bg-red-50 text-red-700 border-red-200',
  high: 'bg-orange-50 text-orange-700 border-orange-200',
  medium: 'bg-yellow-50 text-yellow-700 border-yellow-200',
  low: 'bg-blue-50 text-blue-700 border-blue-200',
  info: 'bg-gray-50 text-gray-600 border-gray-200',
};

const statusColors: Record<string, string> = {
  healthy: 'bg-green-50 text-green-700 border-green-200',
  degraded: 'bg-yellow-50 text-yellow-700 border-yellow-200',
  unhealthy: 'bg-red-50 text-red-700 border-red-200',
  success: 'bg-green-50 text-green-700 border-green-200',
  running: 'bg-blue-50 text-blue-700 border-blue-200',
  failed: 'bg-red-50 text-red-700 border-red-200',
};

const typeColors: Record<string, string> = {
  volume_spike: 'bg-purple-50 text-purple-700 border-purple-200',
  spread_anomaly: 'bg-indigo-50 text-indigo-700 border-indigo-200',
  market_maker_withdrawal: 'bg-pink-50 text-pink-700 border-pink-200',
  arbitrage_opportunity: 'bg-emerald-50 text-emerald-700 border-emerald-200',
};

export function Badge({ children, variant = 'default', color, className }: BadgeProps) {
  let colorClass = 'bg-gray-100 text-gray-700 border-gray-200';

  if (color) {
    if (variant === 'severity') {
      colorClass = severityColors[color] || colorClass;
    } else if (variant === 'status') {
      colorClass = statusColors[color] || colorClass;
    } else if (variant === 'type') {
      colorClass = typeColors[color] || colorClass;
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
