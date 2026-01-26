import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { EmptyState } from '@/components/ui/EmptyState';
import { useArbitrageOpportunities, useRelationshipGroups } from '@/hooks/useArbitrage';

const TYPE_LABELS: Record<string, { label: string; color: string }> = {
  mutually_exclusive: { label: 'Mutual Exclusion', color: 'purple' },
  conditional: { label: 'Conditional', color: 'blue' },
  time_sequence: { label: 'Time Inversion', color: 'orange' },
  subset: { label: 'Subset Mispricing', color: 'teal' },
};

export function ArbitragePage() {
  const [activeTab, setActiveTab] = useState<'opportunities' | 'groups'>('opportunities');
  const [typeFilter, setTypeFilter] = useState('');

  const {
    data: opportunities,
    isLoading: loadingOpps,
    error: errorOpps,
  } = useArbitrageOpportunities({
    type: typeFilter || undefined,
    is_active: true,
  });

  const {
    data: groupsData,
    isLoading: loadingGroups,
  } = useRelationshipGroups();

  return (
    <div className="page-container">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-gray-900 mb-2">
          Cross-Market Arbitrage
        </h1>
        <p className="text-gray-600 max-w-2xl">
          Detect pricing anomalies across related markets. Cross-market arbitrage opportunities
          arise when markets with logical relationships are mispriced relative to each other.
        </p>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="flex gap-4">
          <button
            onClick={() => setActiveTab('opportunities')}
            className={`pb-3 px-1 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'opportunities'
                ? 'border-gray-900 text-gray-900'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            Opportunities
          </button>
          <button
            onClick={() => setActiveTab('groups')}
            className={`pb-3 px-1 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'groups'
                ? 'border-gray-900 text-gray-900'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            Relationship Groups
          </button>
        </nav>
      </div>

      {activeTab === 'opportunities' && (
        <>
          {/* Type Filter */}
          <div className="flex gap-2 mb-6 flex-wrap">
            <button
              onClick={() => setTypeFilter('')}
              className={`px-3 py-1 text-sm rounded-full border transition-colors ${
                !typeFilter
                  ? 'bg-gray-900 text-white border-gray-900'
                  : 'bg-white text-gray-600 border-gray-300 hover:border-gray-400'
              }`}
            >
              All Types
            </button>
            {Object.entries(TYPE_LABELS).map(([type, { label }]) => (
              <button
                key={type}
                onClick={() => setTypeFilter(type)}
                className={`px-3 py-1 text-sm rounded-full border transition-colors ${
                  typeFilter === type
                    ? 'bg-gray-900 text-white border-gray-900'
                    : 'bg-white text-gray-600 border-gray-300 hover:border-gray-400'
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Opportunities List */}
          {loadingOpps && (
            <div className="flex justify-center py-12">
              <LoadingSpinner />
            </div>
          )}

          {errorOpps && (
            <div className="text-red-600 py-4">
              Failed to load opportunities
            </div>
          )}

          {opportunities && opportunities.opportunities.length === 0 && (
            <EmptyState
              title="No arbitrage opportunities"
              description="No cross-market pricing anomalies detected at this time."
            />
          )}

          {opportunities && opportunities.opportunities.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {opportunities.opportunities.map((opp) => {
                const typeInfo = TYPE_LABELS[opp.type || ''] || { label: 'Unknown', color: 'gray' };
                return (
                  <Card key={opp.id} className="p-4">
                    <div className="flex items-start justify-between mb-3">
                      <Badge color={typeInfo.color as any}>{typeInfo.label}</Badge>
                      {opp.profit_estimate && (
                        <span className="text-lg font-semibold text-emerald-600">
                          +{(opp.profit_estimate * 100).toFixed(1)}%
                        </span>
                      )}
                    </div>
                    <h3 className="font-medium text-gray-900 mb-2">{opp.title}</h3>
                    {opp.description && (
                      <p className="text-sm text-gray-600 mb-3">{opp.description}</p>
                    )}
                    {opp.strategy && (
                      <p className="text-xs text-gray-500">
                        <span className="font-medium">Strategy:</span> {opp.strategy.replace(/_/g, ' ')}
                      </p>
                    )}
                    {opp.market_ids && opp.market_ids.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-gray-100 flex gap-2 flex-wrap">
                        {opp.market_ids.map((id) => (
                          <Link
                            key={id}
                            to={`/markets/${id}`}
                            className="text-xs text-blue-600 hover:underline"
                          >
                            {id.slice(0, 12)}...
                          </Link>
                        ))}
                      </div>
                    )}
                  </Card>
                );
              })}
            </div>
          )}
        </>
      )}

      {activeTab === 'groups' && (
        <>
          {loadingGroups && (
            <div className="flex justify-center py-12">
              <LoadingSpinner />
            </div>
          )}

          {groupsData && groupsData.groups.length === 0 && (
            <EmptyState
              title="No relationship groups"
              description="No market relationship groups have been defined."
            />
          )}

          {groupsData && groupsData.groups.length > 0 && (
            <div className="space-y-4">
              {groupsData.groups.map((group) => {
                const typeInfo = TYPE_LABELS[group.relationship_type] || { label: 'Unknown', color: 'gray' };
                return (
                  <Card key={group.group_id} className="p-4">
                    <div className="flex items-center gap-3 mb-2">
                      <Badge color={typeInfo.color as any}>{typeInfo.label}</Badge>
                      <span className="text-sm text-gray-500">
                        {group.market_ids.length} markets
                      </span>
                      <span className="text-xs text-gray-400">
                        Confidence: {(group.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                    <h3 className="font-medium text-gray-900 mb-2">{group.group_id}</h3>
                    {group.notes && (
                      <p className="text-sm text-gray-600 mb-3">{group.notes}</p>
                    )}
                    <div className="flex gap-2 flex-wrap">
                      {group.market_ids.map((id) => (
                        <Link
                          key={id}
                          to={`/markets/${id}`}
                          className="text-xs px-2 py-1 bg-gray-100 rounded text-gray-600 hover:bg-gray-200"
                        >
                          {id.slice(0, 16)}...
                        </Link>
                      ))}
                    </div>
                  </Card>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}
