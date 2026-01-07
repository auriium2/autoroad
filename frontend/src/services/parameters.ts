/**
 * Parameters API Client
 * Interface for searching and managing optimization parameters
 */

import type { SearchResults } from '@/types/models/optimizer';

export interface SearchParams {
  query?: string;
  limit?: number;
  excludeRequirements?: string[];
  excludeObjectives?: string[];
  excludeConstraints?: string[];
}

export const parametersApi = {
  async search(params: SearchParams = {}): Promise<SearchResults> {
    const searchParams = new URLSearchParams();
    
    if (params.query) {
      searchParams.append('q', params.query);
    }
    if (params.limit !== undefined) {
      searchParams.append('limit', params.limit.toString());
    }
    if (params.excludeRequirements?.length) {
      searchParams.append('exclude_requirements', params.excludeRequirements.join(','));
    }
    if (params.excludeObjectives?.length) {
      searchParams.append('exclude_objectives', params.excludeObjectives.join(','));
    }
    if (params.excludeConstraints?.length) {
      searchParams.append('exclude_constraints', params.excludeConstraints.join(','));
    }

    const url = `/api/parameters/search?${searchParams}`;
    const response = await fetch(url, {
      headers: {
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        errorData.error || `HTTP ${response.status}: ${response.statusText}`
      );
    }

    return await response.json();
  },
};
