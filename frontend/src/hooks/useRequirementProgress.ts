/**
 * Hook for fetching requirement progress with individual caching per requirement
 */

import { useQueries } from '@tanstack/react-query';
import { fireroadApi, type RequirementTree } from '@/services/fireroad';
import { queryKeys } from '@/lib/queryKeys';
import { useGraphStore } from '@/stores/roadStore';
import { useOptimizationStore } from '@/stores/optimizationStore';

interface RequirementProgressResult {
  data: Record<string, RequirementTree>;
  isLoading: boolean;
}

export function useRequirementProgressBatch(requirementKeys: string[]): RequirementProgressResult {
  const markers = useGraphStore((state) => state.markers);
  const optimizerNodes = useGraphStore((state) => state.optimizerNodes);
  const isOptimizing = useGraphStore((state) => state.isOptimizing);
  const requirementSources = useOptimizationStore((state) => state.requirementSources);

  // Build course IDs list
  const courseIdSet = new Set([
    ...markers.map(m => m.courseId),
    ...optimizerNodes.map(n => n.courseId)
  ]);
  const courseIds = Array.from(courseIdSet).sort();
  const courseIdsKey = courseIds.join(',');

  // Create individual queries for each requirement
  const queries = useQueries({
    queries: requirementKeys.map(key => {
      const source = (requirementSources[key] || 'canonical') as 'canonical' | 'beta';
      return {
        queryKey: queryKeys.requirements.progress(key, courseIdsKey, source),
        queryFn: () => fireroadApi.getRequirementProgress(key, courseIds, source),
        staleTime: 10 * 60 * 1000, // 10 minutes
        enabled: !isOptimizing,
      };
    }),
  });

  // Combine results into a map
  const data: Record<string, RequirementTree> = {};
  for (let i = 0; i < requirementKeys.length; i++) {
    const query = queries[i];
    if (query.data) {
      data[requirementKeys[i]] = query.data;
    }
  }

  const isLoading = queries.some(q => q.isLoading);

  return {
    data,
    isLoading,
  };
}
