/**
 * Caching Utilities
 * Course prefetching and requirement extraction
 */

import { QueryClient } from "@tanstack/react-query";
import { fireroadApi, type RequirementTree, type RequirementNode } from "@/services/fireroad";
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
  
  return /^\d+\./.test(courseId);
}

export async function prefetchCourses(
  queryClient: QueryClient,
  courseIds: string[]
): Promise<void> {
  const uniqueCourseIds = Array.from(new Set(courseIds)).filter(isActualCourse);
  
  if (uniqueCourseIds.length === 0) return;
  
  try {
    const courseId2details = await fireroadApi.getCourseDetailsBatch(uniqueCourseIds);
    
    // Populate the individual query cache entries for each course
    for (const [courseId, details] of Object.entries(courseId2details)) {
      queryClient.setQueryData(queryKeys.courses.details(courseId), details);
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

export async function extractCoursesFromRequirement(
  requirementKey: string
): Promise<string[]> {
  try {
    const requirement = await fireroadApi.getRequirementProgress(requirementKey, []);
    
    const courseIds: string[] = [];
    
    function traverseRequirement(node: RequirementTree | RequirementNode) {
      if ('req' in node && node.req) {
        courseIds.push(node.req);
      }
      
      if ('reqs' in node && node.reqs && Array.isArray(node.reqs)) {
        node.reqs.forEach(traverseRequirement);
      }
    }
    
    traverseRequirement(requirement);
    
    return Array.from(new Set(courseIds));
  } catch (error) {
    console.error(`Failed to extract courses from requirement ${requirementKey}:`, error);
    return [];
  }
}
