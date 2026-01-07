/**
 * Caching Utilities
 * Client-side prerequisite cache and course prefetching
 */

import QuickLRU from 'quick-lru';
import { QueryClient } from "@tanstack/react-query";
import { fireroadApi, type RequirementTree, type RequirementNode } from "@/services/fireroad";
import { queryKeys } from "@/lib/queryKeys";
import { parseFireroad, type PrereqNode } from './prerequisites';

// ============================================================================
// Client-Side Prerequisite Cache
// ============================================================================

const prereqTreeCache = new QuickLRU<string, PrereqNode>({ maxSize: 500 });

export function getCachedPrereqTree(prereqString: string): PrereqNode {
  if (!prereqString || prereqString.trim() === '') {
    return { type: 'group', threshold: 0, items: [] };
  }

  const cached = prereqTreeCache.get(prereqString);
  if (cached) {
    return cached;
  }

  const parsed = parseFireroad(prereqString);
  prereqTreeCache.set(prereqString, parsed);
  
  return parsed;
}

export function clearPrereqCache(): void {
  prereqTreeCache.clear();
}

export function getPrereqCacheStats() {
  return {
    size: prereqTreeCache.size,
    maxSize: 500,
  };
}

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
  
  await Promise.all(
    uniqueCourseIds.map(courseId =>
      queryClient.prefetchQuery({
        queryKey: queryKeys.courses.details(courseId),
        queryFn: () => fireroadApi.getCourseDetails(courseId),
        staleTime: 24 * 60 * 60 * 1000,
      }).catch(() => {
        // Silently ignore prefetch failures
      })
    )
  );
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
