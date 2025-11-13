/**
 * Prerequisite System - CourseRoad Compatible
 * 
 * Parses and evaluates prerequisites in CourseRoad's array format:
 * [count, item1, item2, ...]
 * 
 * Examples:
 * - [0, "18.01", "18.02"] = "18.01 AND 18.02" (0 means all)
 * - [1, "6.100A", "6.100B"] = "6.100A OR 6.100B" (need 1 of them)
 * - [2, "A", "B", "C", "D"] = "2 of: A, B, C, D"
 * - [0, [1, "18.01", "18.02"], "18.03"] = "(18.01 OR 18.02) AND 18.03"
 */

// ============================================================================
// Type Definitions
// ============================================================================

/**
 * CourseRoad prerequisite format:
 * - First element: number (count of items needed, 0 = all)
 * - Remaining elements: course IDs (strings), nested arrays, or objects
 */
export type PrereqArray = [number, ...PrereqItem[]];

export type PrereqItem = 
  | string                    // Simple course ID
  | PrereqArray              // Nested requirement
  | PrereqObject;            // Complex course with metadata

export interface PrereqObject {
  id: string;                // Course ID
  coreq?: number;           // 1 if corequisite (can take concurrently)
  range?: number;           // 1 if this is a range matcher
  matchRegex?: RegExp | string;      // Pattern to match course IDs
  excludeRegex?: RegExp | string;    // Pattern to exclude course IDs
  desc?: string;            // Additional description
}

export interface EvaluationResult {
  satisfied: boolean;
  unsatisfiedReasons: string[];
  matchedCourses: string[];
}

// ============================================================================
// Prerequisite Evaluator
// ============================================================================

export class PrerequisiteEvaluator {
  private usedCourses: Set<string>;

  constructor(
    private availableCourses: string[],
    private options: {
      allowReuseAcrossRequirements?: boolean; // Default: false (CourseRoad style)
    } = {}
  ) {
    this.usedCourses = new Set();
  }

  /**
   * Evaluate a prerequisite array
   */
  evaluate(prereq: PrereqArray): EvaluationResult {
    if (!Array.isArray(prereq) || prereq.length === 0) {
      throw new Error('Invalid prerequisite array');
    }

    let count = prereq[0];
    const items = prereq.slice(1) as PrereqItem[];

    // Handle the 0 shortcut: 0 means "all of the following"
    if (count === 0) {
      count = items.length;
    }

    const results: EvaluationResult[] = [];
    const unsatisfiedReasons: string[] = [];
    let satisfiedCount = 0;

    // Evaluate each item
    for (const item of items) {
      const result = this.evaluateItem(item);
      results.push(result);

      if (result.satisfied) {
        satisfiedCount++;
      } else {
        unsatisfiedReasons.push(...result.unsatisfiedReasons);
      }

      // Early exit if we've satisfied enough requirements
      if (satisfiedCount >= count) {
        return {
          satisfied: true,
          unsatisfiedReasons: [],
          matchedCourses: results.flatMap(r => r.matchedCourses),
        };
      }
    }

    // Check if we satisfied the requirement
    const satisfied = satisfiedCount >= count;

    if (satisfied) {
      return {
        satisfied: true,
        unsatisfiedReasons: [],
        matchedCourses: results.flatMap(r => r.matchedCourses),
      };
    }

    // Build error message
    const needed = count - satisfiedCount;
    return {
      satisfied: false,
      unsatisfiedReasons: [
        `Need ${count} of ${items.length}: ${unsatisfiedReasons.join(', ')}`
      ],
      matchedCourses: results.flatMap(r => r.matchedCourses),
    };
  }

  private evaluateItem(item: PrereqItem): EvaluationResult {
    // Nested array - recursively evaluate
    if (Array.isArray(item)) {
      return this.evaluate(item as PrereqArray);
    }

    // String - simple course ID
    if (typeof item === 'string') {
      return this.evaluateCourse(item);
    }

    // Object - complex requirement
    if (typeof item === 'object') {
      const obj = item as PrereqObject;
      
      // Range matcher
      if (obj.range) {
        return this.evaluateRange(obj);
      }

      // Regular course with metadata
      return this.evaluateCourse(obj.id, obj.coreq === 1);
    }

    throw new Error(`Unknown prerequisite item type: ${typeof item}`);
  }

  private evaluateCourse(courseId: string, coreq: boolean = false): EvaluationResult {
    const canUse = this.options.allowReuseAcrossRequirements || 
                   !this.usedCourses.has(courseId);
    const hasCourse = this.availableCourses.includes(courseId);

    if (hasCourse && canUse) {
      this.usedCourses.add(courseId);
      return {
        satisfied: true,
        unsatisfiedReasons: [],
        matchedCourses: [courseId],
      };
    }

    const reason = coreq ? `[${courseId}]` : courseId;
    return {
      satisfied: false,
      unsatisfiedReasons: [reason],
      matchedCourses: [],
    };
  }

  private evaluateRange(obj: PrereqObject): EvaluationResult {
    // Convert regex to actual RegExp if it's a string
    let matchPattern: RegExp;
    if (typeof obj.matchRegex === 'string') {
      matchPattern = new RegExp(obj.matchRegex);
    } else if (obj.matchRegex instanceof RegExp) {
      matchPattern = obj.matchRegex;
    } else {
      // Fallback: use the ID as a prefix pattern
      matchPattern = new RegExp(`^${obj.id.replace('.', '\\.')}`);
    }

    let excludePattern: RegExp | undefined;
    if (obj.excludeRegex) {
      if (typeof obj.excludeRegex === 'string') {
        excludePattern = new RegExp(obj.excludeRegex);
      } else {
        excludePattern = obj.excludeRegex;
      }
    }

    // Find matching courses
    const matchingCourses: string[] = [];
    for (const courseId of this.availableCourses) {
      // Check if already used
      const canUse = this.options.allowReuseAcrossRequirements || 
                     !this.usedCourses.has(courseId);
      if (!canUse) continue;

      // Check if matches pattern
      if (!matchPattern.test(courseId)) continue;

      // Check if excluded
      if (excludePattern && excludePattern.test(courseId)) continue;

      matchingCourses.push(courseId);
    }

    if (matchingCourses.length > 0) {
      // Mark the first matching course as used
      const selectedCourse = matchingCourses[0];
      this.usedCourses.add(selectedCourse);
      return {
        satisfied: true,
        unsatisfiedReasons: [],
        matchedCourses: [selectedCourse],
      };
    }

    return {
      satisfied: false,
      unsatisfiedReasons: [`${obj.id}${obj.desc || ''}`],
      matchedCourses: [],
    };
  }

  /**
   * Reset the used courses set (useful for re-evaluation)
   */
  reset(): void {
    this.usedCourses.clear();
  }
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Convert a prerequisite array to a human-readable string
 */
export function prereqToString(prereq: PrereqArray): string {
  if (!Array.isArray(prereq) || prereq.length === 0) {
    return '';
  }

  let count = prereq[0];
  const items = prereq.slice(1) as PrereqItem[];

  if (count === 0) {
    count = items.length;
  }

  const itemStrings = items.map(item => {
    if (Array.isArray(item)) {
      return `(${prereqToString(item as PrereqArray)})`;
    } else if (typeof item === 'string') {
      return item;
    } else if (typeof item === 'object') {
      const obj = item as PrereqObject;
      return obj.id + (obj.desc || '');
    }
    return String(item);
  });

  if (count === items.length) {
    return itemStrings.join(' AND ');
  } else if (count === 1) {
    return itemStrings.join(' OR ');
  } else {
    return `${count} of: [${itemStrings.join(', ')}]`;
  }
}

/**
 * Parse a simple string into a prerequisite array
 * This is a basic implementation - expand as needed
 */
export function parsePrereqString(str: string): PrereqArray {
  const cleaned = str.trim();

  // Handle parentheses
  const parenMatch = cleaned.match(/^\(([^)]+)\)(.*)$/);
  if (parenMatch) {
    const inner = parsePrereqString(parenMatch[1]);
    const rest = parenMatch[2].trim();
    if (rest.startsWith(' and ')) {
      const restParsed = parsePrereqString(rest.substring(5));
      return [0, inner, ...restParsed.slice(1)];
    } else if (rest.startsWith(' or ')) {
      const restParsed = parsePrereqString(rest.substring(4));
      return [1, inner, ...restParsed.slice(1)];
    }
    return inner;
  }

  // Handle AND
  if (cleaned.includes(' and ')) {
    const parts = cleaned.split(' and ').map(p => p.trim());
    return [0, ...parts];
  }

  // Handle OR
  if (cleaned.includes(' or ')) {
    const parts = cleaned.split(' or ').map(p => p.trim());
    return [1, ...parts];
  }

  // Single course
  return [0, cleaned];
}

// ============================================================================
// Example Usage
// ============================================================================

/*
// Example 1: "18.01 and 18.02"
const prereq1: PrereqArray = [0, "18.01", "18.02"];

// Example 2: "6.100A or 6.100B"
const prereq2: PrereqArray = [1, "6.100A", "6.100B"];

// Example 3: "(18.01 or 18.02) and 18.03"
const prereq3: PrereqArray = [0, [1, "18.01", "18.02"], "18.03"];

// Example 4: "2 of: 6.041, 6.042, 18.03, 18.06"
const prereq4: PrereqArray = [2, "6.041", "6.042", "18.03", "18.06"];

// Example 5: "Any 8.xxx course except 8.01-8.03"
const prereq5: PrereqArray = [1, {
  id: "8.03-999",
  range: 1,
  matchRegex: /^8\./,
  excludeRegex: /^8\.0[1-3]$/
}];

// Evaluate
const evaluator = new PrerequisiteEvaluator(['18.01', '18.03', '6.100A']);
console.log(prereqToString(prereq1), "→", evaluator.evaluate(prereq1));
evaluator.reset();
console.log(prereqToString(prereq2), "→", evaluator.evaluate(prereq2));
evaluator.reset();
console.log(prereqToString(prereq3), "→", evaluator.evaluate(prereq3));
*/
