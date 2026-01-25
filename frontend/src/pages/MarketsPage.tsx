import { useState } from 'react';
import { MarketCard } from '@/components/markets/MarketCard';
import { Pagination } from '@/components/ui/Pagination';
import { LoadingState } from '@/components/ui/LoadingSpinner';
import { EmptyState } from '@/components/ui/EmptyState';
import { useMarkets } from '@/hooks';
import { cn } from '@/lib/utils';
import { BarChart3 } from 'lucide-react';

const ITEMS_PER_PAGE = 12;

interface FilterOption {
  value: string;
  label: string;
}

const activeOptions: FilterOption[] = [
  { value: 'true', label: 'Active' },
  { value: 'false', label: 'Closed' },
  { value: '', label: 'All' },
];

const alertOptions: FilterOption[] = [
  { value: '', label: 'All Markets' },
  { value: 'true', label: 'With Alerts' },
  { value: 'false', label: 'No Alerts' },
];

export function MarketsPage() {
  const [active, setActive] = useState('true');
  const [hasAlerts, setHasAlerts] = useState('');
  const [offset, setOffset] = useState(0);

  const { data, isLoading, error } = useMarkets({
    active: active === '' ? undefined : active === 'true',
    has_alerts: hasAlerts === '' ? undefined : hasAlerts === 'true',
    limit: ITEMS_PER_PAGE,
    offset,
  });

  const handleFilterChange = (
    setter: (value: string) => void,
    value: string
  ) => {
    setter(value);
    setOffset(0);
  };

  const selectClass = cn(
    'px-3 py-2 text-sm bg-white border border-gray-200 rounded-md',
    'focus:outline-none focus:ring-2 focus:ring-gray-400 focus:ring-offset-1',
    'text-gray-700'
  );

  return (
    <div className="page-container">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">Markets</h1>
        <div className="flex gap-3">
          <select
            value={active}
            onChange={(e) => handleFilterChange(setActive, e.target.value)}
            className={selectClass}
          >
            {activeOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>

          <select
            value={hasAlerts}
            onChange={(e) => handleFilterChange(setHasAlerts, e.target.value)}
            className={selectClass}
          >
            {alertOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {isLoading ? (
        <LoadingState message="Loading markets..." />
      ) : error ? (
        <EmptyState
          icon={<BarChart3 className="w-6 h-6 text-red-400" />}
          title="Failed to load markets"
          description={error.message}
        />
      ) : !data?.markets.length ? (
        <EmptyState
          icon={<BarChart3 className="w-6 h-6 text-gray-400" />}
          title="No markets found"
          description="Try adjusting your filters."
        />
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {data.markets.map((market) => (
              <MarketCard key={market.id} market={market} />
            ))}
          </div>

          {data.total > ITEMS_PER_PAGE && (
            <div className="mt-6">
              <Pagination
                total={data.total}
                limit={data.limit}
                offset={offset}
                onPageChange={setOffset}
              />
            </div>
          )}
        </>
      )}
    </div>
  );
}
