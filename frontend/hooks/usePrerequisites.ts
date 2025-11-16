/**
 * React hooks for fetching and evaluating prerequisites using TanStack Query
 */

import * as React from 'react';
import { useQuery } from '@tanstack/react-query';
import { fireroadApi } from '@/services/fireroad';
import { parseFireroad, extractCourseIds, evaluatePrerequisites } from '@/lib/prerequisites';
import type { CourseNode } from '@/types';

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
    staleTime: 10 * 60 * 1000, // Prerequisites don't change often - cache for 10 minutes
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
    staleTime: 5 * 60 * 1000,
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
 * Hook to compute prerequisite edges for a graph of courses
 */
export function usePrerequisiteEdges(nodes: CourseNode[]) {
  // Create a stable key from the sorted course IDs and their node uuids
  // Using useMemo to prevent recreating the key on every render
  const courseKey = React.useMemo(
    () => nodes.map(n => `${n.courseId}:${n.uuid}`).sort().join(','),
    [nodes]
  );
  
  return useQuery({
    queryKey: ['prerequisites', 'edges', courseKey],
    queryFn: async () => {
      console.log('[Performance] Fetching prerequisite edges for', nodes.length, 'nodes');
      const startTime = performance.now();
      const edges: Array<{ fromUuid: string; toUuid: string }> = [];

      // Build a map of courseId -> node for quick lookup
      const courseToNode = new Map<string, CourseNode>();
      for (const node of nodes) {
        courseToNode.set(node.courseId, node);
      }

      // Fetch all prerequisites in parallel instead of sequentially
      const prereqPromises = nodes.map(node => 
        fetchPrerequisitesForCourse(node.courseId).then(prereqs => ({ node, prereqs }))
      );
      
      const results = await Promise.all(prereqPromises);

      // Build edges from results
      for (const { node, prereqs } of results) {
        for (const prereqCourseId of prereqs) {
          const prereqNode = courseToNode.get(prereqCourseId);

          // Only create edge if both courses are in the graph
          if (prereqNode) {
            edges.push({
              fromUuid: prereqNode.uuid,
              toUuid: node.uuid,
            });
          }
        }
      }

      const endTime = performance.now();
      console.log(`[Performance] Fetched ${edges.length} edges in ${(endTime - startTime).toFixed(2)}ms`);
      return edges;
    },
    enabled: nodes.length > 0,
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Hook to compute missing prerequisites for all nodes in a graph
 * Returns a map of uuid -> missing prerequisite course IDs
 */
export function useMissingPrerequisites(nodes: CourseNode[]) {
  const courseKey = React.useMemo(
    () => nodes.map(n => `${n.courseId}:${n.uuid}:${n.section}:${n.nodeStatus || ''}`).sort().join(','),
    [nodes]
  );

  return useQuery({
    queryKey: ['prerequisites', 'missing', courseKey],
    queryFn: async () => {
      console.log('[Performance] Computing missing prerequisites for', nodes.length, 'nodes');
      const startTime = performance.now();
      const uuid2missingPrereqs = new Map<string, string[]>();

      // Fetch all prerequisite strings in parallel
      const prereqPromises = nodes.map(async (node) => {
        if (node.nodeStatus === 'solo' || node.nodeStatus === 'banish') {
          return { node, prereqString: '' };
        }

        try {
          const courseDetails = await fireroadApi.getCourseDetails(node.courseId);
          return { node, prereqString: courseDetails.prerequisites || '' };
        } catch (error) {
          console.warn(`Failed to fetch prerequisites for ${node.courseId}:`, error);
          return { node, prereqString: '' };
        }
      });

      const results = await Promise.all(prereqPromises);

      // Evaluate prerequisites for each node
      for (const { node, prereqString } of results) {
        if (!prereqString) {
          uuid2missingPrereqs.set(node.uuid, []);
          continue;
        }

        try {
          const prereqTree = parseFireroad(prereqString);
          
          // Get courses taken before this node's section (excluding banished)
          const takenCourses = nodes
            .filter(n => n.section < node.section && n.nodeStatus !== 'banish')
            .map(n => n.courseId);

          const result = evaluatePrerequisites(prereqTree, takenCourses);

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
    enabled: nodes.length > 0,
    staleTime: 5 * 60 * 1000,
  });
}
