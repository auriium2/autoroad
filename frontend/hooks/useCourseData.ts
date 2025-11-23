import { useQuery } from '@tanstack/react-query';
import { fireroadApi } from '@/services/fireroad';

const USE_FIREROAD = true; // Toggle to switch between fake data and real API

/**
 * Hook to search for courses with infinite scroll
 * For Fireroad API: searches or lists by department
 * For fake data: filters local array
 */
export function useSearchCourses(query: string, department?: string) {
  return useQuery({
    queryKey: ['courses', 'search', query, department],
    queryFn: async () => {
      if (USE_FIREROAD) {
        // Use Fireroad API with pagination
        if (query.trim() && query !== '*') {
          // Search by query - use 'starts' for better department matching
          const searchType = query.includes('.') ? 'starts' : 'contains';
          const response = await fireroadApi.searchCourses(query, {
            type: searchType,
            department: department,
            offset: 0,
            limit: 1000, // Get a large batch since we'll cache it
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
          // This will match courses across all departments (e.g., x.0, x.1, x.2, etc.)
          const response = await fireroadApi.searchCourses('.0', {
            type: 'contains',
            department: undefined,
            offset: 0,
            limit: 2000,
          });
          return response.courses;
        } else {
          // Return empty for no query and no wildcard
          return [];
        }
      } else {
        // Use fake local data
        const FAKE_COURSES = [
          { subject_id: "6.1200", title: "Mathematics for Computer Science", total_units: 12, offered_fall: true, offered_spring: true },
          { subject_id: "6.120A", title: "Discrete Mathematics and Proof for Computer Science", total_units: 6, offered_fall: true, offered_spring: false },
          { subject_id: "6.1010", title: "Fundamentals of Programming", total_units: 12, offered_fall: true, offered_spring: true },
          { subject_id: "6.1020", title: "Software Construction", total_units: 12, offered_spring: true },
          { subject_id: "6.1800", title: "Computer Systems Engineering", total_units: 12, offered_fall: true },
          { subject_id: "6.3700", title: "Introduction to Probability", total_units: 12, offered_fall: true, offered_spring: true },
          { subject_id: "18.01", title: "Single Variable Calculus", total_units: 12, offered_fall: true, offered_spring: true },
          { subject_id: "18.02", title: "Multivariable Calculus", total_units: 12, offered_fall: true, offered_spring: true },
          { subject_id: "18.03", title: "Differential Equations", total_units: 12, offered_spring: true },
        ];

        await new Promise(resolve => setTimeout(resolve, 300)); // Simulate network delay

        return FAKE_COURSES.filter(course => {
          const matchesQuery = query === '' ||
            course.subject_id.toLowerCase().includes(query.toLowerCase()) ||
            course.title.toLowerCase().includes(query.toLowerCase());
          const matchesDepartment = !department || department === 'all' || course.subject_id.startsWith(department + '.');
          return matchesQuery && matchesDepartment;
        });
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
