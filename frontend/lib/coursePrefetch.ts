import { QueryClient } from "@tanstack/react-query";
import { fireroadApi } from "@/services/fireroad";
import type { RequirementTree, RequirementNode } from "@/services/optimizer";

export async function prefetchCourses(
  queryClient: QueryClient,
  courseIds: string[]
): Promise<void> {
  const uniqueCourseIds = Array.from(new Set(courseIds));
  
  await Promise.all(
    uniqueCourseIds.map(courseId =>
      queryClient.prefetchQuery({
        queryKey: ['courseDetails', courseId],
        queryFn: () => fireroadApi.getCourseDetails(courseId),
        staleTime: 60 * 60 * 1000, // 1 hour
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
    const { optimizerApi } = await import('@/services/optimizer');
    const requirement = await optimizerApi.getRequirementProgress(requirementKey, []);
    
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
