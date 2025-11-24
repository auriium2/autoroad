import { QueryClient } from "@tanstack/react-query";
import { fireroadApi, type RequirementTree, type RequirementNode } from "@/services/fireroad";
import { queryKeys } from "@/lib/queryKeys";

function isActualCourse(courseId: string): boolean {
  // Filter out generic requirement placeholders
  if (courseId.startsWith('GIR:')) return false;
  if (courseId.startsWith('HASS')) return false;
  if (courseId.startsWith('CI-')) return false;
  if (courseId === 'REST') return false;
  
  // Actual courses should have a department number and course number (e.g., "6.100A", "18.01")
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
        staleTime: 24 * 60 * 60 * 1000, // Course details are static - cache for 24 hours
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
        // This is a course requirement - extract course ID
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
