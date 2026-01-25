import { useState } from 'react';
import { AlertList } from '@/components/alerts/AlertList';
import { AlertFilters } from '@/components/alerts/AlertFilters';
import { Pagination } from '@/components/ui/Pagination';
import { useAlerts } from '@/hooks';

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

  // Reset pagination when filters change
  const handleFilterChange = (
    setter: (value: string) => void,
    value: string
  ) => {
    setter(value);
    setOffset(0);
  };

  return (
    <div className="page-container">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">Alerts</h1>
        <AlertFilters
          type={type}
          severity={severity}
          isActive={isActive}
          onTypeChange={(v) => handleFilterChange(setType, v)}
          onSeverityChange={(v) => handleFilterChange(setSeverity, v)}
          onIsActiveChange={(v) => handleFilterChange(setIsActive, v)}
        />
      </div>

      <AlertList
        alerts={data?.alerts}
        isLoading={isLoading}
        error={error}
      />

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
