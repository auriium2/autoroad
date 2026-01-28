/**
 * Caching Utilities
 * Course prefetching and requirement extraction
 */

import { QueryClient } from "@tanstack/react-query";
import { fireroadApi } from "@/services/fireroad";
import { optimizerApi } from "@/services/optimizer";
import { queryKeys } from "@/lib/queryKeys";

// ============================================================================
// Course Prefetching
// ============================================================================

function isActualCourse(courseId: string): boolean {
  if (courseId.startsWith('GIR:')) return false;
  if (courseId.startsWith('HASS')) return false;
  if (courseId.startsWith('CI-')) return false;
  if (courseId === 'REST') return false;
  
  // Match course IDs like "6.100A", "18.01", "21G.111", "WGS.101"
  return /^[\dA-Z]+\./.test(courseId);
}

export async function prefetchCourses(
  queryClient: QueryClient,
  courseIds: string[]
): Promise<void> {
  const uniqueCourseIds = Array.from(new Set(courseIds)).filter(isActualCourse);
  
  if (uniqueCourseIds.length === 0) return;
  
  try {
    // Backend has 200 course limit, so chunk if needed
    const CHUNK_SIZE = 200;
    for (let i = 0; i < uniqueCourseIds.length; i += CHUNK_SIZE) {
      const chunk = uniqueCourseIds.slice(i, i + CHUNK_SIZE);
      const courseId2details = await fireroadApi.getCourseDetailsBatch(chunk);
      
      for (const [courseId, details] of Object.entries(courseId2details)) {
        queryClient.setQueryData(queryKeys.courses.details(courseId), details);
      }
    }
  } catch {
  }
}

/**
 * Prefetch static configuration data (requirements list, objectives, constraints).
 * Call this on app mount to warm the cache.
 */
export function prefetchStaticData(queryClient: QueryClient): void {
  queryClient.prefetchQuery({
    queryKey: queryKeys.requirements.list(),
    queryFn: () => fireroadApi.getRequirementsList(),
    staleTime: 24 * 60 * 60 * 1000,
  });

  queryClient.prefetchQuery({
    queryKey: queryKeys.objectives.list(),
    queryFn: () => optimizerApi.getObjectives(),
    staleTime: 24 * 60 * 60 * 1000,
  });

  queryClient.prefetchQuery({
    queryKey: queryKeys.constraints.hard(),
    queryFn: () => optimizerApi.getHardConstraints(),
    staleTime: 24 * 60 * 60 * 1000,
  });
}


