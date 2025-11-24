import { useQuery } from '@tanstack/react-query';
import { fireroadApi } from '@/services/fireroad';
import { queryKeys } from '@/lib/queryKeys';

export interface CourseFilters {
  gir?: string;
  hass?: string;
  ci?: string;
  level?: string;
  units?: string;
  term?: string;
}

export function useSearchCourses(query: string, department?: string, filters?: CourseFilters) {
  return useQuery({
    queryKey: queryKeys.courses.search(query, department, filters),
    queryFn: async () => {
      const trimmedQuery = query.trim();
      
      if (!trimmedQuery) {
        return [];
      }

      // Determine search type based on query
      // Use 'starts' for course IDs (e.g., "6.100"), 'contains' for text search
      const searchType = trimmedQuery.includes('.') ? 'starts' : 'contains';
      
      // Normalize department filter - treat 'all' as undefined
      const deptFilter = department === 'all' ? undefined : department;

      const response = await fireroadApi.searchCourses(trimmedQuery, {
        type: searchType,
        department: deptFilter,
        offset: 0,
        limit: 2000,
        ...filters,
      });

      // Sort to prioritize exact department matches when searching with course numbers
      if (trimmedQuery.includes('.')) {
        const queryDept = trimmedQuery.split('.')[0];
        return response.courses.sort((a, b) => {
          const aDept = a.subject_id.split('.')[0];
          const bDept = b.subject_id.split('.')[0];

          const aExact = aDept === queryDept;
          const bExact = bDept === queryDept;

          if (aExact && !bExact) return -1;
          if (!aExact && bExact) return 1;

          return a.subject_id.localeCompare(b.subject_id);
        });
      }

      return response.courses;
    },
    enabled: true,
    staleTime: 24 * 60 * 60 * 1000,
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
  });
}

/**
 * Hook to get detailed course information
 * Useful for hover tooltips or modals
 */
export function useCourseDetails(courseId: string | null) {
  return useQuery({
    queryKey: courseId ? queryKeys.courses.details(courseId) : ['courses', 'details', null],
    queryFn: async () => {
      if (!courseId) return null;

      return await fireroadApi.getCourseDetails(courseId);
    },
    enabled: !!courseId, // Only fetch when courseId is provided
    staleTime: 24 * 60 * 60 * 1000, // Course details are static - cache for 24 hours
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
  });
}
