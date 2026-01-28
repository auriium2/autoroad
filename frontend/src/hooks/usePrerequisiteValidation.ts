/**
 * React hook for server-side prerequisite validation
 * 
 * This hook sends course placements to the backend for validation,
 * which returns missing prerequisites, edges for arrows, and course tags.
 */

import { useQuery } from '@tanstack/react-query';
import { fireroadApi, type CoursePlacement, type PrereqEdge } from '@/services/fireroad';
import { queryKeys } from '@/lib/queryKeys';
import type { CourseNode } from '@/types';

interface PrerequisiteValidationResult {
  missing: Map<string, string[]>;
  edges: Array<{ fromUuid: string; toUuid: string }>;
  tags: Map<string, string[]>;
  isLoading: boolean;
}

export function usePrerequisiteValidation(nodes: CourseNode[]): PrerequisiteValidationResult {
  // Convert nodes to placements for the API
  const placements: CoursePlacement[] = nodes.map(node => ({
    courseId: node.courseId,
    section: node.section,
    status: node.nodeStatus,
  }));

  // Create a stable key for the query
  const placementsKey = nodes
    .map(n => `${n.courseId}:${n.section}:${n.nodeStatus || ''}`)
    .sort()
    .join(',');

  // Build courseId -> uuid map for edge conversion
  const courseId2uuid = new Map<string, string>();
  for (const node of nodes) {
    courseId2uuid.set(node.courseId, node.uuid);
  }

  const { data, isLoading } = useQuery({
    queryKey: queryKeys.prerequisites.validate(placementsKey),
    queryFn: () => fireroadApi.validatePrerequisites(placements),
    staleTime: 24 * 60 * 60 * 1000, // 24 hours - prerequisites are static
    enabled: nodes.length > 0,
  });

  if (!data || isLoading) {
    return {
      missing: new Map(),
      edges: [],
      tags: new Map(),
      isLoading,
    };
  }

  // Convert missing from Record to Map, keyed by uuid
  const missing = new Map<string, string[]>();
  for (const node of nodes) {
    const missingPrereqs = data.missing[node.courseId] || [];
    missing.set(node.uuid, missingPrereqs);
  }

  // Convert edges from courseId-based to uuid-based
  const edges: Array<{ fromUuid: string; toUuid: string }> = [];
  for (const edge of data.edges) {
    const fromUuid = courseId2uuid.get(edge.fromCourseId);
    const toUuid = courseId2uuid.get(edge.toCourseId);
    if (fromUuid && toUuid) {
      edges.push({ fromUuid, toUuid });
    }
  }

  // Convert tags from Record to Map
  const tags = new Map<string, string[]>();
  for (const [courseId, tagList] of Object.entries(data.tags)) {
    tags.set(courseId, tagList);
  }

  return {
    missing,
    edges,
    tags,
    isLoading,
  };
}
