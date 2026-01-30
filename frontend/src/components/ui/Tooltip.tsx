import { useState } from 'react';
import { HelpCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface TooltipProps {
  content: string;
  children?: React.ReactNode;
  className?: string;
}

export function Tooltip({ content, children, className }: TooltipProps) {
  const [isVisible, setIsVisible] = useState(false);

  return (
    <span
      className={cn('relative inline-flex items-center', className)}
      onMouseEnter={() => setIsVisible(true)}
      onMouseLeave={() => setIsVisible(false)}
    >
      {children || <HelpCircle className="w-4 h-4 text-gray-400 dark:text-gray-500 cursor-help" />}
      {isVisible && (
        <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 text-xs text-white bg-gray-900 dark:bg-gray-100 dark:text-gray-900 rounded-lg shadow-lg whitespace-nowrap z-50 max-w-xs text-center">
          {content}
          <span className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-900 dark:border-t-gray-100" />
        </span>
      )}
    </span>
  );
}

interface InfoBoxProps {
  title?: string;
  children: React.ReactNode;
  variant?: 'info' | 'tip' | 'warning';
  className?: string;
}

const variantStyles = {
  info: 'bg-blue-50 border-blue-200 text-blue-800 dark:bg-blue-950 dark:border-blue-800 dark:text-blue-300',
  tip: 'bg-green-50 border-green-200 text-green-800 dark:bg-green-950 dark:border-green-800 dark:text-green-300',
  warning: 'bg-amber-50 border-amber-200 text-amber-800 dark:bg-amber-950 dark:border-amber-800 dark:text-amber-300',
};

export function InfoBox({ title, children, variant = 'info', className }: InfoBoxProps) {
  return (
    <div className={cn('rounded-lg border p-4', variantStyles[variant], className)}>
      {title && <p className="font-medium mb-1">{title}</p>}
      <div className="text-sm opacity-90">{children}</div>
    </div>
  );
}
