import { cn } from '@/lib/utils';

interface FilterOption {
  value: string;
  label: string;
}

const alertTypes: FilterOption[] = [
  { value: '', label: 'All Types' },
  { value: 'volume_spike', label: 'Volume Spike' },
  { value: 'spread_anomaly', label: 'Spread Anomaly' },
  { value: 'market_maker_withdrawal', label: 'MM Withdrawal' },
  { value: 'arbitrage_opportunity', label: 'Arbitrage' },
];

const severities: FilterOption[] = [
  { value: '', label: 'All Severities' },
  { value: 'critical', label: 'Critical' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
  { value: 'info', label: 'Info' },
];

const statusOptions: FilterOption[] = [
  { value: 'true', label: 'Active' },
  { value: 'false', label: 'Dismissed' },
  { value: '', label: 'All' },
];

interface AlertFiltersProps {
  type: string;
  severity: string;
  isActive: string;
  onTypeChange: (value: string) => void;
  onSeverityChange: (value: string) => void;
  onIsActiveChange: (value: string) => void;
}

export function AlertFilters({
  type,
  severity,
  isActive,
  onTypeChange,
  onSeverityChange,
  onIsActiveChange,
}: AlertFiltersProps) {
  const selectClass = cn(
    'px-3 py-2 text-sm bg-white border border-gray-200 rounded-md',
    'focus:outline-none focus:ring-2 focus:ring-gray-400 focus:ring-offset-1',
    'text-gray-700'
  );

  return (
    <div className="flex flex-wrap gap-3">
      <select
        value={type}
        onChange={(e) => onTypeChange(e.target.value)}
        className={selectClass}
      >
        {alertTypes.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>

      <select
        value={severity}
        onChange={(e) => onSeverityChange(e.target.value)}
        className={selectClass}
      >
        {severities.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>

      <select
        value={isActive}
        onChange={(e) => onIsActiveChange(e.target.value)}
        className={selectClass}
      >
        {statusOptions.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}
