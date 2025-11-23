import { useQuery } from '@tanstack/react-query';
import { fireroadApi } from '@/services/fireroad';

export interface CourseFilters {
  gir?: string;
  hass?: string;
  ci?: string;
  level?: string;
  units?: string;
  term?: string;
}

/**
 * Hook to search for courses with server-side filtering
 */
export function useSearchCourses(query: string, department?: string, filters?: CourseFilters) {
  return useQuery({
    queryKey: ['courses', 'search', query, department, filters],
    queryFn: async () => {
      // Search by query - use 'starts' for better department matching
      if (query.trim() && query !== '*') {
        const searchType = query.includes('.') ? 'starts' : 'contains';
        const response = await fireroadApi.searchCourses(query, {
          type: searchType,
          department: department,
          offset: 0,
          limit: 1000, // Get a large batch since we'll cache it
          ...filters, // Pass filters to API
        });

        // Sort results to prioritize exact department matches
        const sorted = response.courses.sort((a, b) => {
          const aDept = a.subject_id.split('.')[0];
          const bDept = b.subject_id.split('.')[0];
          const queryDept = query.split('.')[0];

          // Exact department match comes first
          const aExact = aDept === queryDept;
          const bExact = bDept === queryDept;

          if (aExact && !bExact) return -1;
          if (!aExact && bExact) return 1;

          // Then sort alphabetically by subject_id
          return a.subject_id.localeCompare(b.subject_id);
        });

        return sorted;
      } else if (query === '*' && department && department !== 'all') {
        // Wildcard with specific department - list by department
        const response = await fireroadApi.getCoursesByDepartment(department, 0, 1000);
        return response.courses;
      } else if (query === '*' && department === 'all') {
        // Wildcard with all departments - search for a common number pattern
        const response = await fireroadApi.searchCourses('.', {
          type: 'contains',
          department: undefined,
          offset: 0,
          limit: 2000,
          ...filters, // Pass filters to API
        });
        return response.courses;
      } else {
        // Return empty for no query and no wildcard
        return [];
      }
    },
    enabled: true,
    staleTime: 5 * 60 * 1000, // Consider data fresh for 5 minutes
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
    queryKey: ['courses', 'details', courseId],
    queryFn: async () => {
      if (!courseId) return null;

      return await fireroadApi.getCourseDetails(courseId);
    },
    enabled: !!courseId, // Only fetch when courseId is provided
    staleTime: 10 * 60 * 1000, // Course details change rarely, cache for 10 minutes
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
  });
}
