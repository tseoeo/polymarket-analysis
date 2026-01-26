import apiClient from './client';

export interface ArbitrageOpportunity {
  id: number;
  type: string | null;
  title: string;
  description: string | null;
  profit_estimate: number | null;
  market_ids: string[] | null;
  strategy: string | null;
  created_at: string;
  is_active: boolean;
}

export interface ArbitrageListResponse {
  opportunities: ArbitrageOpportunity[];
  total: number;
}

export interface RelationshipGroup {
  group_id: string;
  relationship_type: string;
  market_ids: string[];
  notes: string | null;
  confidence: number;
}

export interface Relationship {
  id: number;
  relationship_type: string;
  parent_market_id: string;
  child_market_id: string;
  group_id: string | null;
  notes: string | null;
  confidence: number;
  created_at: string;
}

export interface ArbitrageFilters {
  type?: string;
  is_active?: boolean;
  limit?: number;
  offset?: number;
}

export async function fetchArbitrageOpportunities(
  filters: ArbitrageFilters = {}
): Promise<ArbitrageListResponse> {
  const params = new URLSearchParams();

  if (filters.type) params.append('type', filters.type);
  if (filters.is_active !== undefined) params.append('is_active', String(filters.is_active));
  if (filters.limit) params.append('limit', String(filters.limit));
  if (filters.offset) params.append('offset', String(filters.offset));

  const response = await apiClient.get<ArbitrageListResponse>('/arbitrage/opportunities', { params });
  return response.data;
}

export async function fetchRelationshipGroups(): Promise<{ groups: RelationshipGroup[] }> {
  const response = await apiClient.get<{ groups: RelationshipGroup[] }>('/arbitrage/groups');
  return response.data;
}

export async function fetchRelationshipGroup(groupId: string): Promise<{
  group_id: string;
  relationship_type: string;
  market_ids: string[];
  markets: Array<{ id: string; question: string; yes_price: number | null }>;
  relationships: Relationship[];
}> {
  const response = await apiClient.get(`/arbitrage/groups/${groupId}`);
  return response.data;
}

export async function fetchRelationships(type?: string): Promise<Relationship[]> {
  const params = new URLSearchParams();
  if (type) params.append('relationship_type', type);

  const response = await apiClient.get<Relationship[]>('/arbitrage/relationships', { params });
  return response.data;
}

export async function createRelationship(data: {
  relationship_type: string;
  parent_market_id: string;
  child_market_id: string;
  group_id?: string;
  notes?: string;
  confidence?: number;
}): Promise<Relationship> {
  const response = await apiClient.post<Relationship>('/arbitrage/relationships', data);
  return response.data;
}

export async function deleteRelationship(id: number): Promise<void> {
  await apiClient.delete(`/arbitrage/relationships/${id}`);
}
