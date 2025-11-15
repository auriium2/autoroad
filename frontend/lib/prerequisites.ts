/**
 * Prerequisite parsing and evaluation
 * Inspired by MIT Courseroad's approach
 * 
 * Prerequisites come in strings like:
 * - "6.1200" - simple prerequisite
 * - "6.1200 and 6.1010" - both required
 * - "6.1200 or 6.120a" - either required
 * - "6.1200 and (6.1010 or 6.120a)" - complex with parentheses
 */

import type { CourseNode } from '@/types';

/**
 * Parse a prerequisite string into a tree structure
 * This is a simplified version - real implementation would be more robust
 */
interface PrereqNode {
  type: 'course' | 'and' | 'or';
  value?: string; // course ID for type='course'
  children?: PrereqNode[];
}

/**
 * Simple prerequisite parser
 * Handles: "courseId", "X and Y", "X or Y", "(X or Y) and Z"
 */
function parsePrerequisites(prereqString: string): PrereqNode | null {
  if (!prereqString || prereqString.trim() === '') {
    return null;
  }

  // Remove extra whitespace
  const cleaned = prereqString.trim();

  // Check for AND (lower precedence)
  if (cleaned.includes(' and ')) {
    const parts = cleaned.split(' and ').map(p => p.trim());
    return {
      type: 'and',
      children: parts.map(p => parsePrerequisites(p)).filter(Boolean) as PrereqNode[],
    };
  }

  // Check for OR (higher precedence)
  if (cleaned.includes(' or ')) {
    const parts = cleaned.split(' or ').map(p => p.trim());
    return {
      type: 'or',
      children: parts.map(p => parsePrerequisites(p)).filter(Boolean) as PrereqNode[],
    };
  }

  // Handle parentheses (TODO: proper parsing)
  if (cleaned.startsWith('(') && cleaned.endsWith(')')) {
    return parsePrerequisites(cleaned.slice(1, -1));
  }

  // Base case: single course
  return {
    type: 'course',
    value: cleaned,
  };
}

/**
 * Check if prerequisites are satisfied
 * Returns true if the prereq tree is satisfied by the taken courses
 */
function checkPrerequisites(
  prereqTree: PrereqNode | null,
  takenCourses: Set<string>
): boolean {
  if (!prereqTree) return true;

  switch (prereqTree.type) {
    case 'course':
      return takenCourses.has(prereqTree.value || '');
    
    case 'and':
      return prereqTree.children?.every(child => 
        checkPrerequisites(child, takenCourses)
      ) ?? true;
    
    case 'or':
      return prereqTree.children?.some(child => 
        checkPrerequisites(child, takenCourses)
      ) ?? false;
    
    default:
      return false;
  }
}

/**
 * Extract all course IDs from a prerequisite tree
 * Used to create edges
 */
function extractCourseIds(prereqTree: PrereqNode | null): string[] {
  if (!prereqTree) return [];

  switch (prereqTree.type) {
    case 'course':
      return prereqTree.value ? [prereqTree.value] : [];
    
    case 'and':
    case 'or':
      return prereqTree.children?.flatMap(child => extractCourseIds(child)) ?? [];
    
    default:
      return [];
  }
}

// Lazy cache for prerequisites - only fetches what we need
const prerequisiteCache = new Map<string, string[]>();

/**
 * Get all prerequisite course IDs for a given course
 * Uses lazy caching - fetches from API on first access, then caches
 */
export async function getPrerequisites(courseId: string): Promise<string[]> {
  // Check cache first
  if (prerequisiteCache.has(courseId)) {
    return prerequisiteCache.get(courseId)!;
  }

  // TODO: Fetch from Fireroad API
  // For now, use hardcoded data matching our fake course data
  const prereqMap: Record<string, string> = {
    '6.1200': '6.100',
    '6.1010': '6.100 or 6.120a',
    '6.1020': '6.1010',
    '6.1030': '6.1200 and 6.1010',
    '6.1040': '6.1020',
    '6.1050': '6.1020 and 6.1030',
    '6.1060': '6.1050',
    '6.1070': '6.1010',
    '6.3700': '18.01',
    '18.02': '18.01',
    '18.03': '18.02',
    '6.1800': '6.1020',
  };

  const prereqString = prereqMap[courseId];
  if (!prereqString) {
    // Cache empty result
    prerequisiteCache.set(courseId, []);
    return [];
  }

  const prereqTree = parsePrerequisites(prereqString);
  const prerequisites = extractCourseIds(prereqTree);
  
  // Cache the result
  prerequisiteCache.set(courseId, prerequisites);
  return prerequisites;
}

/**
 * Clear the prerequisite cache (useful for testing or if data becomes stale)
 */
export function clearPrerequisiteCache(): void {
  prerequisiteCache.clear();
}

/**
 * Compute edges for a graph based on prerequisites
 * Returns array of {from_id, to_id} edges
 */
export async function computePrerequisiteEdges(
  nodes: CourseNode[]
): Promise<Array<{ from_id: string; to_id: string }>> {
  const edges: Array<{ from_id: string; to_id: string }> = [];
  
  // Build a map of courseId -> node for quick lookup
  const courseToNode = new Map<string, CourseNode>();
  for (const node of nodes) {
    courseToNode.set(node.courseId, node);
  }

  // For each node, find its prerequisites and create edges
  for (const node of nodes) {
    const prereqs = await getPrerequisites(node.courseId);
    
    for (const prereqCourseId of prereqs) {
      const prereqNode = courseToNode.get(prereqCourseId);
      
      // Only create edge if both courses are in the graph
      if (prereqNode) {
        edges.push({
          from_id: prereqNode.id,
          to_id: node.id,
        });
      }
    }
  }

  return edges;
}

/**
 * Check if a course's prerequisites are satisfied by courses taken in earlier semesters
 */
export async function checkCoursePlacement(
  courseId: string,
  section: number,
  allNodes: CourseNode[]
): Promise<{ satisfied: boolean; missing: string[] }> {
  const prereqs = await getPrerequisites(courseId);
  
  // Get courses taken in earlier semesters
  const takenCourses = new Set(
    allNodes
      .filter(n => n.section < section)
      .map(n => n.courseId)
  );

  const missing = prereqs.filter(p => !takenCourses.has(p));

  return {
    satisfied: missing.length === 0,
    missing,
  };
}
