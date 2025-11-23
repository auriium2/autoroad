/**
 * LRU Cache for parsed prerequisite trees
 * Prevents re-parsing the same prerequisite strings repeatedly
 */

import QuickLRU from 'quick-lru';
import { parseFireroad } from './prerequisites';
import type { PrereqNode } from './prerequisites';

// Global LRU cache for parsed prerequisite trees
// maxSize: 500 courses should be more than enough for any student's schedule
const prereqTreeCache = new QuickLRU<string, PrereqNode>({ maxSize: 500 });

/**
 * Get parsed prerequisite tree with caching
 * Uses LRU cache to avoid re-parsing the same prerequisite strings
 */
export function getCachedPrereqTree(prereqString: string): PrereqNode {
  if (!prereqString || prereqString.trim() === '') {
    return { type: 'group', threshold: 0, items: [] };
  }

  // Check cache first
  const cached = prereqTreeCache.get(prereqString);
  if (cached) {
    return cached;
  }

  // Parse and cache
  const parsed = parseFireroad(prereqString);
  prereqTreeCache.set(prereqString, parsed);
  
  return parsed;
}

/**
 * Clear the prerequisite tree cache
 * Useful for testing or if course catalog updates
 */
export function clearPrereqCache(): void {
  prereqTreeCache.clear();
}

/**
 * Get cache statistics for debugging
 */
export function getPrereqCacheStats() {
  return {
    size: prereqTreeCache.size,
    maxSize: 500,
  };
}
