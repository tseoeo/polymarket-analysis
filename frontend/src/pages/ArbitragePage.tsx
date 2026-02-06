import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { EmptyState } from '@/components/ui/EmptyState';
import { Tooltip, InfoBox } from '@/components/ui/Tooltip';
import { glossary } from '@/lib/explanations';
import { useArbitrageOpportunities, useRelationshipGroups } from '@/hooks/useArbitrage';

const TYPE_LABELS: Record<string, { label: string; color: string; explanation: string }> = {
  mutually_exclusive: {
    label: 'Only-One-Can-Win',
    color: 'purple',
    explanation: 'Prices for competing outcomes add up to more (or less) than 100% — that\'s a math error you can profit from.',
  },
  conditional: {
    label: 'Depends-On',
    color: 'blue',
    explanation: 'A specific outcome is priced higher than the broader outcome it depends on — logically impossible.',
  },
  time_sequence: {
    label: 'Timeline Error',
    color: 'orange',
    explanation: 'An earlier deadline is priced higher than a later one for the same event — should be the other way around.',
  },
  subset: {
    label: 'Part vs Whole',
    color: 'teal',
    explanation: 'A specific version of an outcome costs more than the general version — makes no sense mathematically.',
  },
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
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-50 mb-2">
          Pricing Mistakes Across Markets
        </h1>
        <p className="text-gray-600 dark:text-gray-300 max-w-2xl">
          Sometimes related prediction markets have prices that contradict each other — creating
          opportunities where you can guarantee a profit no matter what happens. These mistakes
          get corrected fast, so timing matters.
        </p>
      </div>

      {/* Intro Explainer */}
      <InfoBox variant="tip" className="mb-6">
        <strong>How does this work?</strong> Imagine two markets: &quot;Will Team A win?&quot;
        at 60% and &quot;Will Team B win?&quot; at 50%. Since only one team can win, the prices
        should add up to around 100%. But 60% + 50% = 110% — that extra 10% is free money if you
        sell both sides. This page finds exactly these kinds of mathematical pricing errors.
      </InfoBox>

      {/* Tabs */}
      <div className="border-b border-gray-200 dark:border-gray-700 mb-6">
        <nav className="flex gap-4">
          <button
            onClick={() => setActiveTab('opportunities')}
            className={`pb-3 px-1 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'opportunities'
                ? 'border-gray-900 dark:border-gray-100 text-gray-900 dark:text-gray-50'
                : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
            }`}
          >
            Active Opportunities
          </button>
          <button
            onClick={() => setActiveTab('groups')}
            className={`pb-3 px-1 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'groups'
                ? 'border-gray-900 dark:border-gray-100 text-gray-900 dark:text-gray-50'
                : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
            }`}
          >
            Linked Markets
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
                  ? 'bg-gray-900 dark:bg-gray-100 text-white dark:text-gray-900 border-gray-900 dark:border-gray-100'
                  : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500'
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
                    ? 'bg-gray-900 dark:bg-gray-100 text-white dark:text-gray-900 border-gray-900 dark:border-gray-100'
                    : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500'
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
            <div className="text-red-600 dark:text-red-400 py-4">
              Failed to load opportunities
            </div>
          )}

          {opportunities && opportunities.opportunities.length === 0 && (
            <EmptyState
              title="No pricing mistakes found"
              description="All related markets are priced consistently right now. The scanner checks every 15 minutes and will alert you when it finds a discrepancy."
            />
          )}

          {opportunities && opportunities.opportunities.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {opportunities.opportunities.map((opp) => {
                const typeInfo = TYPE_LABELS[opp.type || ''] || { label: 'Unknown', color: 'gray', explanation: '' };
                return (
                  <Card key={opp.id} className="p-4">
                    <div className="flex items-start justify-between mb-3">
                      <div>
                        <Badge color={typeInfo.color as any}>{typeInfo.label}</Badge>
                        {typeInfo.explanation && (
                          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 max-w-xs">
                            {typeInfo.explanation}
                          </p>
                        )}
                      </div>
                      {opp.profit_estimate && (
                        <span className="text-lg font-semibold text-emerald-600 dark:text-emerald-400">
                          +{(opp.profit_estimate * 100).toFixed(1)}%
                        </span>
                      )}
                    </div>
                    <h3 className="font-medium text-gray-900 dark:text-gray-50 mb-2">{opp.title}</h3>
                    {opp.description && (
                      <p className="text-sm text-gray-600 dark:text-gray-300 mb-3">{opp.description}</p>
                    )}
                    {opp.strategy && (
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        <span className="font-medium">Strategy:</span> {opp.strategy.replace(/_/g, ' ')}
                      </p>
                    )}
                    {opp.market_ids && opp.market_ids.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-gray-100 dark:border-gray-800 flex gap-2 flex-wrap">
                        {opp.market_ids.map((id) => (
                          <Link
                            key={id}
                            to={`/markets/${id}`}
                            className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
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
              title="No linked markets"
              description="No market relationships have been set up yet. The system can auto-detect related markets, or you can link them manually through the API."
            />
          )}

          {groupsData && groupsData.groups.length > 0 && (
            <div className="space-y-4">
              {groupsData.groups.map((group) => {
                const typeInfo = TYPE_LABELS[group.relationship_type] || { label: 'Unknown', color: 'gray', explanation: '' };
                return (
                  <Card key={group.group_id} className="p-4">
                    <div className="flex items-center gap-3 mb-2">
                      <Badge color={typeInfo.color as any}>{typeInfo.label}</Badge>
                      <span className="text-sm text-gray-500 dark:text-gray-400">
                        {group.market_ids.length} markets
                      </span>
                      <span
                        className="text-xs text-gray-400 dark:text-gray-500"
                        title={glossary.confidence}
                      >
                        Confidence: {(group.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                    <h3 className="font-medium text-gray-900 dark:text-gray-50 mb-2">{group.group_id}</h3>
                    {group.notes && (
                      <p className="text-sm text-gray-600 dark:text-gray-300 mb-3">{group.notes}</p>
                    )}
                    <div className="flex gap-2 flex-wrap">
                      {group.market_ids.map((id) => (
                        <Link
                          key={id}
                          to={`/markets/${id}`}
                          className="text-xs px-2 py-1 bg-gray-100 dark:bg-gray-800 rounded text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700"
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
