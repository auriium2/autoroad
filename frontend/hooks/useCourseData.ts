import { useQuery, useInfiniteQuery } from '@tanstack/react-query';
import { fireroadApi, CourseDetails, FireroadCourse } from '@/services/fireroad';

const USE_FIREROAD = false; // Toggle to switch between fake data and real API

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
        // Use Fireroad API
        if (query.trim()) {
          // Search by query
          const results = await fireroadApi.searchCourses(query, {
            type: 'contains',
            full: false,
          });
          
          // Filter by department if specified
          if (department && department !== 'all') {
            return results.filter(course => course.subject_id.startsWith(department + '.'));
          }
          return results;
        } else if (department && department !== 'all') {
          // List by department
          return await fireroadApi.getCoursesByDepartment(department, false);
        } else {
          // Return empty for "all" with no query (too many courses)
          return [];
        }
      } else {
        // Use fake local data
        const FAKE_COURSES = [
          { subject_id: "6.1200", title: "Mathematics for Computer Science", total_units: 12, offered_fall: true, offered_spring: true },
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
      
      if (USE_FIREROAD) {
        // Use Fireroad API
        return await fireroadApi.getCourseDetails(courseId);
      } else {
        // Use fake local data
        const FAKE_COURSE_DETAILS: Record<string, CourseDetails> = {
          "18.01": {
            id: "18.01",
            name: "Single Variable Calculus",
            description: "Differentiation and integration of functions of one variable, with applications.",
            units: 12,
            prerequisites: "",
            corequisites: "",
            terms_offered: ["Fall", "Spring"],
            offered_fall: true,
            offered_spring: true,
            instructors: ["Prof. Adams"],
            gir_attribute: "REST",
          },
          "6.100": {
            id: "6.100",
            name: "Introduction to Computer Science Programming in Python",
            description: "Introduction to computer science and programming using Python.",
            units: 12,
            prerequisites: "",
            corequisites: "",
            terms_offered: ["Fall", "Spring"],
            offered_fall: true,
            offered_spring: true,
            instructors: ["Prof. Grimson"],
          },
          "6.1200": {
            id: "6.1200",
            name: "Mathematics for Computer Science",
            description: "Elementary discrete mathematics for science and engineering, with a focus on mathematical tools and proof techniques useful in computer science.",
            units: 12,
            prerequisites: "6.100",
            corequisites: "",
            terms_offered: ["Fall", "Spring"],
            offered_fall: true,
            offered_spring: true,
            instructors: ["Prof. Lehman", "Prof. Meyer"],
          },
          "6.120a": {
            id: "6.120a",
            name: "Discrete Mathematics and Proof for Computer Science",
            description: "Introduction to discrete mathematics and proof techniques with applications to computer science.",
            units: 6,
            prerequisites: "",
            corequisites: "",
            terms_offered: ["Fall"],
            offered_fall: true,
            offered_spring: false,
            instructors: ["Prof. Devadas"],
          },
          "6.1010": {
            id: "6.1010",
            name: "Fundamentals of Programming",
            description: "Introduction to programming in Python. Designed to help students develop skills in computational problem solving.",
            units: 12,
            prerequisites: "6.100 or 6.120a",
            corequisites: "",
            terms_offered: ["Fall", "Spring"],
            offered_fall: true,
            offered_spring: true,
            instructors: ["Prof. Williams"],
          },
          "6.1020": {
            id: "6.1020",
            name: "Software Construction",
            description: "Introduces fundamental principles and techniques of software development.",
            units: 12,
            prerequisites: "6.1010",
            corequisites: "",
            terms_offered: ["Spring"],
            offered_spring: true,
            instructors: ["Prof. Ernst"],
            communication_requirement: "CI-M",
          },
          "6.1030": {
            id: "6.1030",
            name: "Introduction to Algorithms",
            description: "Introduction to mathematical modeling of computational problems, as well as common algorithms and data structures.",
            units: 12,
            prerequisites: "6.1200 and 6.1010",
            corequisites: "",
            terms_offered: ["Fall", "Spring"],
            offered_fall: true,
            offered_spring: true,
            instructors: ["Prof. Leiserson"],
          },
          "6.1040": {
            id: "6.1040",
            name: "Software Design",
            description: "Learn to design software applications from scratch using modern design principles.",
            units: 12,
            prerequisites: "6.1020",
            corequisites: "",
            terms_offered: ["Fall", "Spring"],
            offered_fall: true,
            offered_spring: true,
            instructors: ["Prof. Jackson"],
          },
          "6.1050": {
            id: "6.1050",
            name: "Computer Systems Engineering",
            description: "Topics on the engineering of computer software and hardware systems.",
            units: 12,
            prerequisites: "6.1020 and 6.1030",
            corequisites: "",
            terms_offered: ["Fall"],
            offered_fall: true,
            instructors: ["Prof. Kaashoek"],
          },
          "6.1060": {
            id: "6.1060",
            name: "Performance Engineering of Software Systems",
            description: "Project-based introduction to building efficient, high-performance software systems.",
            units: 12,
            prerequisites: "6.1050",
            corequisites: "",
            terms_offered: ["Spring"],
            offered_spring: true,
            instructors: ["Prof. Leiserson"],
          },
          "6.1070": {
            id: "6.1070",
            name: "Introduction to Robotics",
            description: "Introduces students to the fundamentals of robotics.",
            units: 12,
            prerequisites: "6.1010",
            corequisites: "",
            terms_offered: ["Fall"],
            offered_fall: true,
            instructors: ["Prof. Roy"],
          },
          "6.3700": {
            id: "6.3700",
            name: "Introduction to Probability",
            description: "Introduction to probability theory and applications.",
            units: 12,
            prerequisites: "18.01",
            corequisites: "",
            terms_offered: ["Fall", "Spring"],
            offered_fall: true,
            offered_spring: true,
            instructors: ["Prof. Tsitsiklis"],
            gir_attribute: "REST",
          },
          "18.02": {
            id: "18.02",
            name: "Multivariable Calculus",
            description: "Calculus of several variables.",
            units: 12,
            prerequisites: "18.01",
            corequisites: "",
            terms_offered: ["Fall", "Spring"],
            offered_fall: true,
            offered_spring: true,
            instructors: ["Prof. Miller"],
            gir_attribute: "REST",
          },
          "18.03": {
            id: "18.03",
            name: "Differential Equations",
            description: "Study of ordinary differential equations.",
            units: 12,
            prerequisites: "18.02",
            corequisites: "",
            terms_offered: ["Fall", "Spring"],
            offered_fall: true,
            offered_spring: true,
            instructors: ["Prof. Haynes"],
            gir_attribute: "REST",
          },
          "6.1800": {
            id: "6.1800",
            name: "Computer Systems Engineering",
            description: "Topics on the engineering of computer software and hardware systems.",
            units: 12,
            prerequisites: "6.1020",
            corequisites: "",
            terms_offered: ["Fall"],
            offered_fall: true,
            instructors: ["Prof. Kaashoek"],
          },
        };
        
        await new Promise(resolve => setTimeout(resolve, 200)); // Simulate network delay
        
        return FAKE_COURSE_DETAILS[courseId] || null;
      }
    },
    enabled: !!courseId, // Only fetch when courseId is provided
    staleTime: 10 * 60 * 1000, // Course details change rarely, cache for 10 minutes
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
  });
}
