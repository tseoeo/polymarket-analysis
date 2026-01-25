import { useState } from 'react';
import { AlertList } from '@/components/alerts/AlertList';
import { AlertFilters } from '@/components/alerts/AlertFilters';
import { Pagination } from '@/components/ui/Pagination';
import { InfoBox } from '@/components/ui/Tooltip';
import { useAlerts } from '@/hooks';
import { alertExplanations } from '@/lib/explanations';

const ITEMS_PER_PAGE = 12;

export function AlertsPage() {
  const [type, setType] = useState('');
  const [severity, setSeverity] = useState('');
  const [isActive, setIsActive] = useState('true');
  const [offset, setOffset] = useState(0);

  const { data, isLoading, error } = useAlerts({
    alert_type: type || undefined,
    severity: severity || undefined,
    is_active: isActive === '' ? undefined : isActive === 'true',
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

  // Get explanation for selected type filter
  const selectedTypeExplanation = type ? alertExplanations[type] : null;

  return (
    <div className="page-container">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-gray-900 mb-2">
          Trading Opportunities
        </h1>
        <p className="text-gray-600 max-w-2xl">
          Each alert below represents a detected market anomaly that may indicate a trading opportunity.
          Click any card to see detailed analysis and suggested actions.
        </p>
      </div>

      {/* Filters */}
      <div className="flex items-start justify-between gap-4 mb-6 flex-wrap">
        <AlertFilters
          type={type}
          severity={severity}
          isActive={isActive}
          onTypeChange={(v) => handleFilterChange(setType, v)}
          onSeverityChange={(v) => handleFilterChange(setSeverity, v)}
          onIsActiveChange={(v) => handleFilterChange(setIsActive, v)}
        />
        {data && (
          <p className="text-sm text-gray-500">
            {data.total} {data.total === 1 ? 'opportunity' : 'opportunities'} found
          </p>
        )}
      </div>

      {/* Type explanation when filtered */}
      {selectedTypeExplanation && (
        <InfoBox variant="info" className="mb-6">
          <p className="font-medium">{selectedTypeExplanation.icon} {selectedTypeExplanation.title}</p>
          <p className="mt-1">{selectedTypeExplanation.whatItMeans}</p>
          <p className="mt-2 text-emerald-700">
            <strong>Opportunity:</strong> {selectedTypeExplanation.opportunity}
          </p>
        </InfoBox>
      )}

      {/* Legend for new users */}
      {!type && !severity && isActive === 'true' && offset === 0 && (
        <div className="mb-6 p-4 bg-gray-50 rounded-lg border border-gray-200">
          <p className="text-sm font-medium text-gray-700 mb-2">Understanding Alert Types:</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs text-gray-600">
            <div><span className="font-medium">📈 Volume Spike:</span> Unusual trading activity</div>
            <div><span className="font-medium">↔️ Wide Spread:</span> Large bid-ask gap</div>
            <div><span className="font-medium">🚰 Liquidity Drop:</span> Market makers exiting</div>
            <div><span className="font-medium">💰 Arbitrage:</span> Risk-free profit opportunity</div>
          </div>
        </div>
      )}

      {/* Alert List */}
      <AlertList
        alerts={data?.alerts}
        isLoading={isLoading}
        error={error}
      />

      {/* Pagination */}
      {data && data.total > ITEMS_PER_PAGE && (
        <div className="mt-6">
          <Pagination
            total={data.total}
            limit={data.limit}
            offset={offset}
            onPageChange={setOffset}
          />
        </div>
      )}
    </div>
  );
}
