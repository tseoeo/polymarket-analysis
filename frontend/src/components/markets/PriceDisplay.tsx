import { cn } from '@/lib/utils';

interface PriceDisplayProps {
  yesPrice: number | null;
  noPrice: number | null;
  size?: 'sm' | 'md' | 'lg';
}

const sizeStyles = {
  sm: 'text-sm',
  md: 'text-base',
  lg: 'text-lg font-medium',
};

export function PriceDisplay({ yesPrice, noPrice, size = 'md' }: PriceDisplayProps) {
  const formatPrice = (price: number | null) => {
    if (price === null) return '-';
    return `${(price * 100).toFixed(0)}%`;
  };

  return (
    <div className={cn('flex items-center gap-4', sizeStyles[size])}>
      <div className="flex items-center gap-1.5">
        <span className="text-gray-500 dark:text-gray-400">Yes</span>
        <span className="text-green-600 dark:text-green-400 font-medium">{formatPrice(yesPrice)}</span>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="text-gray-500 dark:text-gray-400">No</span>
        <span className="text-red-600 dark:text-red-400 font-medium">{formatPrice(noPrice)}</span>
      </div>
    </div>
  );
}
