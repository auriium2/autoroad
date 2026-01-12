import { useQuery, useInfiniteQuery } from '@tanstack/react-query';
import { fireroadApi } from '@/services/fireroad';
import { queryKeys } from '@/lib/queryKeys';

export interface CourseFilters {
  gir?: string;
  hass?: string;
  ci?: string;
  level?: string;
  units?: string;
  term?: string;
  sort?: string;
}

const COURSES_PER_PAGE = 30;

export function useSearchCourses(query: string, department?: string, filters?: CourseFilters) {
  const trimmedQuery = query.trim();

  return useInfiniteQuery({
    queryKey: queryKeys.courses.search(query, department, filters),
    queryFn: async ({ pageParam = 0 }) => {
      // Determine search type based on query
      // Use 'starts' for course IDs (e.g., "6.100" or just "6"), 'contains' for text search
      const looksLikeCourseId = trimmedQuery.includes('.') || /^\d+$/.test(trimmedQuery);
      const searchType = looksLikeCourseId ? 'starts' : 'contains';

      // Normalize department filter - treat 'all' as undefined
      const deptFilter = department === 'all' ? undefined : department;

      return await fireroadApi.searchCourses(trimmedQuery, {
        type: searchType,
        department: deptFilter,
        offset: pageParam,
        limit: COURSES_PER_PAGE,
        ...filters,
      });
    },
    initialPageParam: 0,
    getNextPageParam: (lastPage) => {
      if (lastPage?.has_more) {
        return lastPage.offset + lastPage.limit;
      }
      return undefined;
    },
    enabled: !!trimmedQuery,
    staleTime: 24 * 60 * 60 * 1000,
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
  });
}

export function useCourseDetails(courseId: string | null) {
  return useQuery({
    queryKey: courseId ? queryKeys.courses.details(courseId) : ['courses', 'details', null],
    queryFn: async () => {
      if (!courseId) return null;

      return await fireroadApi.getCourseDetails(courseId);
    },
    enabled: !!courseId,
    staleTime: 24 * 60 * 60 * 1000,
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
  });
}
