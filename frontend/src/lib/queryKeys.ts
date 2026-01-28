/**
 * Centralized query key factory to prevent cache duplication
 * Following TanStack Query best practices
 */

export const queryKeys = {
  // Course-related queries
  courses: {
    all: ['courses'] as const,
    details: (courseId: string) => ['courses', 'details', courseId] as const,
    batch: (courseIdsKey: string) => ['courses', 'batch', courseIdsKey] as const,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    search: (query: string, department?: string, filters?: any) => 
      ['courses', 'search', query, department, filters] as const,
  },

  // Prerequisite-related queries
  prerequisites: {
    all: ['prerequisites'] as const,
    courseIds: (courseId: string) => ['prerequisites', 'courseIds', courseId] as const,
    string: (courseId: string) => ['prerequisites', 'string', courseId] as const,
    check: (courseId: string, section: number, takenCourseIds: string[]) => 
      ['prerequisites', 'check', courseId, section, takenCourseIds.sort()] as const,
    edges: (courseKey: string) => ['prerequisites', 'edges', courseKey] as const,
    missing: (courseKey: string) => ['prerequisites', 'missing', courseKey] as const,
    validate: (placementsKey: string) => ['prerequisites', 'validate', placementsKey] as const,
  },

  // Requirements and optimization
  requirements: {
    all: ['requirements'] as const,
    list: () => ['requirements', 'list'] as const,
    progress: (requirementKey: string, courseIdsKey: string, source: 'canonical' | 'beta' = 'canonical') => 
      ['requirements', 'progress', requirementKey, courseIdsKey, source] as const,
  },

  objectives: {
    all: ['objectives'] as const,
    list: () => ['objectives', 'list'] as const,
  },

  constraints: {
    all: ['constraints'] as const,
    hard: () => ['constraints', 'hard'] as const,
  },

  // Health checks
  health: {
    all: ['health'] as const,
    backend: () => ['health', 'backend'] as const,
  },

  // Hydrant schedule data
  hydrant: {
    all: ['hydrant'] as const,
    schedule: (semester: string, courseIds: string[]) => 
      ['hydrant', 'schedule', semester, courseIds.sort().join(',')] as const,
  },
} as const;
