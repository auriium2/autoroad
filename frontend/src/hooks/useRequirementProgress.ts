/**
 * Hook for fetching requirement progress in batch
 */

import { useQuery } from '@tanstack/react-query';
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

  const requirements = requirementKeys.map(key => ({
    key,
    source: (requirementSources[key] || 'canonical') as 'canonical' | 'beta',
  }));

  // Create stable key for requirements (includes source info)
  const requirementsKey = requirements
    .map(r => `${r.key}:${r.source}`)
    .sort()
    .join(',');

  const { data, isLoading } = useQuery({
    queryKey: queryKeys.requirements.batchProgress(requirementsKey, courseIdsKey),
    queryFn: () => fireroadApi.getRequirementProgressBatch(requirements, courseIds),
    staleTime: 10 * 60 * 1000, // 10 minutes
    enabled: requirementKeys.length > 0 && !isOptimizing,
  });

  return {
    data: data || {},
    isLoading,
  };
}
