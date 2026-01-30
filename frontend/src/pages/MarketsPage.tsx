import { useState } from 'react';
import { MarketCard } from '@/components/markets/MarketCard';
import { Pagination } from '@/components/ui/Pagination';
import { LoadingState } from '@/components/ui/LoadingSpinner';
import { EmptyState } from '@/components/ui/EmptyState';
import { InfoBox } from '@/components/ui/Tooltip';
import { useMarkets } from '@/hooks';
import { cn } from '@/lib/utils';
import { BarChart3, Bell } from 'lucide-react';

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
  { value: 'true', label: 'With Opportunities' },
  { value: 'false', label: 'No Opportunities' },
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
    'px-3 py-2 text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-md',
    'focus:outline-none focus:ring-2 focus:ring-gray-400 focus:ring-offset-1 dark:focus:ring-offset-gray-900',
    'text-gray-700 dark:text-gray-200'
  );

  const marketsWithAlerts = data?.markets.filter(m => m.active_alerts > 0).length || 0;

  return (
    <div className="page-container">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-50 mb-2">
          Monitored Markets
        </h1>
        <p className="text-gray-600 dark:text-gray-300 max-w-2xl">
          Browse prediction markets being analyzed. Markets with a bell icon have active opportunities.
          Click any market to see current prices and related alerts.
        </p>
      </div>

      {/* Quick tip for finding opportunities */}
      {hasAlerts !== 'true' && marketsWithAlerts > 0 && (
        <InfoBox variant="tip" className="mb-6">
          <span className="font-medium">{marketsWithAlerts} markets</span> on this page have active opportunities.
          Use the "With Opportunities" filter to focus on markets where our scanner detected something interesting.
        </InfoBox>
      )}

      {/* Filters */}
      <div className="flex items-center justify-between gap-4 mb-6 flex-wrap">
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

        {data && (
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {data.total.toLocaleString()} markets
          </p>
        )}
      </div>

      {/* Understanding the cards */}
      {offset === 0 && !isLoading && data?.markets.length ? (
        <div className="mb-6 p-4 bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
          <p className="text-sm font-medium text-gray-700 dark:text-gray-200 mb-2">Reading Market Cards:</p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs text-gray-600 dark:text-gray-300">
            <div><span className="font-medium text-green-600 dark:text-green-400">Yes %</span> = Probability market resolves Yes</div>
            <div><span className="font-medium text-red-600 dark:text-red-400">No %</span> = Probability market resolves No</div>
            <div><span className="inline-flex items-center"><Bell className="w-3 h-3 mr-1 text-amber-500" />Number</span> = Active opportunities in this market</div>
          </div>
        </div>
      ) : null}

      {/* Markets Grid */}
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
          icon={<BarChart3 className="w-6 h-6 text-gray-400 dark:text-gray-500" />}
          title="No markets found"
          description={hasAlerts === 'true'
            ? "No markets with active opportunities. Try removing the filter or check back later."
            : "Try adjusting your filters."}
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
