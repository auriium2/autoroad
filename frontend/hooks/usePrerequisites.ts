/**
 * React hooks for fetching and evaluating prerequisites using TanStack Query
 */

import * as React from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { fireroadApi } from '@/services/fireroad';
import { parseFireroad, extractCourseIds, evaluatePrerequisites } from '@/lib/prerequisites';
import type { CourseNode } from '@/types';

interface CourseDetailsWithPrereqs {
  node: CourseNode;
  prereqCourseIds: string[];
  tags: string[];
  prereqString: string;
}

/**
 * Fetch prerequisites for a single course (non-hook version for internal use)
 */
async function fetchPrerequisitesForCourse(courseId: string): Promise<string[]> {
  try {
    const courseDetails = await fireroadApi.getCourseDetails(courseId);
    const prereqString = courseDetails.prerequisites || '';

    if (!prereqString) {
      return [];
    }

    const prereqTree = parseFireroad(prereqString);
    return extractCourseIds(prereqTree);
  } catch (error) {
    console.warn(`Failed to fetch prerequisites for ${courseId}:`, error);
    return [];
  }
}

/**
 * Hook to get prerequisite course IDs for a course
 */
export function usePrerequisiteCourseIds(courseId: string) {
  return useQuery({
    queryKey: ['prerequisites', 'courseIds', courseId],
    queryFn: async () => {
      return await fetchPrerequisitesForCourse(courseId);
    },
    staleTime: 60 * 60 * 1000, // Prerequisites don't change often - cache for 1 hour
    retry: 2,
  });
}

/**
 * Hook to check if a course's prerequisites are satisfied
 */
export function useCheckCoursePlacement(
  courseId: string,
  section: number,
  allNodes: CourseNode[]
) {
  return useQuery({
    queryKey: ['prerequisites', 'check', courseId, section, allNodes.map(n => n.courseId).sort()],
    queryFn: async () => {
      try {
        const courseDetails = await fireroadApi.getCourseDetails(courseId);
        const prereqString = courseDetails.prerequisites || '';

        if (!prereqString) {
          return { satisfied: true, missing: [] };
        }

        const prereqTree = parseFireroad(prereqString);

        const takenCourses = allNodes
          .filter(n => n.section < section)
          .map(n => n.courseId);

        const result = evaluatePrerequisites(prereqTree, takenCourses);

        return {
          satisfied: result.satisfied,
          missing: result.unsatisfiedReasons,
        };
      } catch (error) {
        console.warn(`Failed to check course placement for ${courseId}:`, error);
        return { satisfied: true, missing: [] };
      }
    },
    enabled: !!courseId,
    staleTime: 60 * 60 * 1000,
  });
}

/**
 * Hook to get the raw prerequisite string for a course
 */
export function usePrerequisiteString(courseId: string | null) {
  return useQuery({
    queryKey: ['prerequisites', 'string', courseId],
    queryFn: async () => {
      if (!courseId) return '';

      try {
        const courseDetails = await fireroadApi.getCourseDetails(courseId);
        return courseDetails.prerequisites || '';
      } catch (error) {
        console.warn(`Failed to fetch prerequisite string for ${courseId}:`, error);
        return '';
      }
    },
    enabled: !!courseId,
    staleTime: 10 * 60 * 1000,
  });
}

/**
 * Shared hook to fetch course details with prerequisites for all nodes
 * This prevents duplicate fetches between usePrerequisiteEdges and useMissingPrerequisites
 */
function useCourseDetailsWithPrereqs(nodes: CourseNode[]) {
  const queryClient = useQueryClient();
  
  const courseKey = React.useMemo(
    () => nodes.map(n => `${n.courseId}:${n.uuid}`).sort().join(','),
    [nodes]
  );

  return useQuery({
    queryKey: ['courseDetails', 'batch', courseKey],
    queryFn: async () => {
      const prereqPromises = nodes.map(async (node) => {
        try {
          const courseDetails = await queryClient.fetchQuery({
            queryKey: ['courseDetails', node.courseId],
            queryFn: () => fireroadApi.getCourseDetails(node.courseId),
            staleTime: 60 * 60 * 1000,
          });
          const prereqString = courseDetails.prerequisites || '';
          
          let prereqCourseIds: string[] = [];
          if (prereqString) {
            try {
              const prereqTree = parseFireroad(prereqString);
              prereqCourseIds = extractCourseIds(prereqTree);
            } catch {
              // Ignore parse errors
            }
          }
          
          const tags: string[] = [];
          if (courseDetails.gir_attribute) {
            tags.push(`GIR:${courseDetails.gir_attribute}`);
          }
          if (courseDetails.hass_attribute) {
            tags.push(`HASS:${courseDetails.hass_attribute}`);
          }
          
          return { node, prereqCourseIds, tags, prereqString };
        } catch (error) {
          console.warn(`Failed to fetch course details for ${node.courseId}:`, error);
          return { node, prereqCourseIds: [], tags: [], prereqString: '' };
        }
      });

      return await Promise.all(prereqPromises);
    },
    staleTime: 60 * 60 * 1000,
    enabled: nodes.length > 0,
  });
}

/**
 * Hook to compute prerequisite edges for a graph of courses
 */
export function usePrerequisiteEdges(nodes: CourseNode[]) {
  const courseDetailsQuery = useCourseDetailsWithPrereqs(nodes);
  
  const courseKey = React.useMemo(
    () => nodes.map(n => `${n.courseId}:${n.uuid}`).sort().join(','),
    [nodes]
  );

  return useQuery({
    queryKey: ['prerequisites', 'edges', courseKey],
    queryFn: async () => {
      if (!courseDetailsQuery.data) {
        return { edges: [], tag2courses: new Map() };
      }

      console.log('[Performance] Computing prerequisite edges for', nodes.length, 'nodes');
      const startTime = performance.now();
      const edges: Array<{ fromUuid: string; toUuid: string }> = [];

      // Build a map of courseId -> node for quick lookup
      const courseToNode = new Map<string, CourseNode>();
      for (const node of nodes) {
        courseToNode.set(node.courseId, node);
      }

      // Use the shared fetched data
      const results = courseDetailsQuery.data;

      // Build tag -> courses map
      const tag2courses = new Map<string, CourseNode[]>();
      for (const { node, tags } of results) {
        for (const tag of tags) {
          if (!tag2courses.has(tag)) {
            tag2courses.set(tag, []);
          }
          tag2courses.get(tag)!.push(node);
        }
      }

      // Build edges from results - only draw edges to courses that actually satisfy the prerequisites
      for (const { node, prereqString } of results) {
        // Skip if no prerequisites
        if (!prereqString) continue;

        try {
          const prereqTree = parseFireroad(prereqString);
          
          // Get courses taken before this node
          const takenCourseIds = results
            .filter(r => r.node.section < node.section)
            .map(r => r.node.courseId);

          // Build tags map for taken courses
          const takenCourseTags = new Map<string, string[]>();
          for (const { node: n, tags } of results) {
            if (n.section < node.section) {
              takenCourseTags.set(n.courseId, tags);
            }
          }

          // Evaluate prerequisites to find which courses actually satisfy them
          const result = evaluatePrerequisites(prereqTree, takenCourseIds, true, true, takenCourseTags);

          // Only draw edges to the courses that were matched
          for (const matchedCourseId of result.matchedCourses) {
            const prereqNode = courseToNode.get(matchedCourseId);
            if (prereqNode && prereqNode.section < node.section) {
              edges.push({
                fromUuid: prereqNode.uuid,
                toUuid: node.uuid,
              });
            }
          }
        } catch (error) {
          console.warn(`Failed to evaluate prerequisites for edges for ${node.courseId}:`, error);
        }
      }

      const endTime = performance.now();
      console.log(`[Performance] Computed ${edges.length} edges in ${(endTime - startTime).toFixed(2)}ms`);
      return { edges, tag2courses };
    },
    enabled: nodes.length > 0 && courseDetailsQuery.isSuccess,
    staleTime: 60 * 60 * 1000,
  });
}

/**
 * Hook to compute missing prerequisites for all nodes in a graph
 * Returns a map of uuid -> missing prerequisite course IDs
 */
export function useMissingPrerequisites(nodes: CourseNode[]) {
  const courseDetailsQuery = useCourseDetailsWithPrereqs(nodes);
  
  const courseKey = React.useMemo(
    () => nodes.map(n => `${n.courseId}:${n.uuid}:${n.section}:${n.nodeStatus || ''}`).sort().join(','),
    [nodes]
  );

  return useQuery({
    queryKey: ['prerequisites', 'missing', courseKey],
    queryFn: async () => {
      if (!courseDetailsQuery.data) {
        return new Map<string, string[]>();
      }

      console.log('[Performance] Computing missing prerequisites for', nodes.length, 'nodes');
      const startTime = performance.now();
      const uuid2missingPrereqs = new Map<string, string[]>();

      // Use the shared fetched data
      const results = courseDetailsQuery.data.map(({ node, prereqString, tags }) => {
        // Skip prerequisite checking for Must Take (-2), ASEs (-1), and override nodes
        const skipPrereqCheck = node.section === -2 || node.section === -1 || node.nodeStatus === 'override';
        
        return {
          node,
          prereqString: skipPrereqCheck ? '' : prereqString,
          tags
        };
      });

      // Build course tags map
      const courseId2tags = new Map<string, string[]>();
      for (const { node, tags } of results) {
        courseId2tags.set(node.courseId, tags);
      }

      // Pre-compute courses taken before each section for O(1) lookup
      const minSection = Math.min(...nodes.map(n => n.section));
      const maxSection = Math.max(...nodes.map(n => n.section));
      const coursesBySection = new Map<number, string[]>();
      
      for (const { node } of results) {
        // For each course, add it to all sections that come AFTER it
        // This way, when we look up section N, we get all courses from sections < N
        for (let section = minSection; section <= maxSection; section++) {
          // If this section comes after the course's section, the course is "taken before" it
          if (section > node.section) {
            if (!coursesBySection.has(section)) {
              coursesBySection.set(section, []);
            }
            coursesBySection.get(section)!.push(node.courseId);
          }
        }
      }

      // Evaluate prerequisites for each node
      for (const { node, prereqString } of results) {
        if (!prereqString) {
          uuid2missingPrereqs.set(node.uuid, []);
          continue;
        }

        try {
          const prereqTree = parseFireroad(prereqString);

          // Get courses taken before this node's section (O(1) lookup)
          // This includes special semesters: -2 (Must Take), -1 (ASE)
          const takenCourses = coursesBySection.get(node.section) || [];

          const result = evaluatePrerequisites(prereqTree, takenCourses, true, true, courseId2tags);

          if (!result.satisfied) {
            // Store unique missing course IDs
            uuid2missingPrereqs.set(node.uuid, Array.from(new Set(result.unsatisfiedReasons)));
          } else {
            uuid2missingPrereqs.set(node.uuid, []);
          }
        } catch (error) {
          console.warn(`Failed to evaluate prerequisites for ${node.courseId}:`, error);
          uuid2missingPrereqs.set(node.uuid, []);
        }
      }

      const endTime = performance.now();
      console.log(`[Performance] Computed missing prerequisites in ${(endTime - startTime).toFixed(2)}ms`);
      return uuid2missingPrereqs;
    },
    enabled: nodes.length > 0 && courseDetailsQuery.isSuccess,
    staleTime: 60 * 60 * 1000,
  });
}
