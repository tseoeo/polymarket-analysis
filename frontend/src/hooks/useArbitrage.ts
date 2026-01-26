import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchArbitrageOpportunities,
  fetchRelationshipGroups,
  fetchRelationshipGroup,
  fetchRelationships,
  createRelationship,
  deleteRelationship,
  type ArbitrageFilters,
} from '@/api/arbitrage';

export const arbitrageKeys = {
  all: ['arbitrage'] as const,
  opportunities: () => [...arbitrageKeys.all, 'opportunities'] as const,
  opportunitiesList: (filters: ArbitrageFilters) => [...arbitrageKeys.opportunities(), filters] as const,
  groups: () => [...arbitrageKeys.all, 'groups'] as const,
  group: (id: string) => [...arbitrageKeys.groups(), id] as const,
  relationships: () => [...arbitrageKeys.all, 'relationships'] as const,
  relationshipsList: (type?: string) => [...arbitrageKeys.relationships(), type] as const,
};

export function useArbitrageOpportunities(filters: ArbitrageFilters = {}) {
  return useQuery({
    queryKey: arbitrageKeys.opportunitiesList(filters),
    queryFn: () => fetchArbitrageOpportunities(filters),
    staleTime: 30 * 1000,
  });
}

export function useRelationshipGroups() {
  return useQuery({
    queryKey: arbitrageKeys.groups(),
    queryFn: fetchRelationshipGroups,
    staleTime: 60 * 1000,
  });
}

export function useRelationshipGroup(groupId: string) {
  return useQuery({
    queryKey: arbitrageKeys.group(groupId),
    queryFn: () => fetchRelationshipGroup(groupId),
    enabled: !!groupId,
  });
}

export function useRelationships(type?: string) {
  return useQuery({
    queryKey: arbitrageKeys.relationshipsList(type),
    queryFn: () => fetchRelationships(type),
    staleTime: 60 * 1000,
  });
}

export function useCreateRelationship() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createRelationship,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: arbitrageKeys.all });
    },
  });
}

export function useDeleteRelationship() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteRelationship,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: arbitrageKeys.all });
    },
  });
}
