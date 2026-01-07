/**
 * Prerequisite parsing and evaluation
 * Based on the tested Python implementation in backend/courses/prerequisites
 *
 * This module contains PURE functions only - no API calls, no caching.
 * For API-based prerequisite fetching, use hooks/usePrerequisites.ts
 *
 * Fireroad prerequisite format:
 * - Operators: "," (AND), "/" (OR)
 * - Grouping: parentheses for precedence
 * - Course IDs: "6.100A", "18.01", "GIR:CAL1"
 *
 * Examples:
 * - Single course: "6.100A"
 * - AND: "6.100A,6.1200"
 * - OR: "18.05/18.06"
 * - Complex: "(6.100A,6.1200)/(6.100L,6.1200)"
 */

// ============================================================================
// Types
// ============================================================================

export interface PrereqCourse {
  type: 'course';
  courseId: string;
  wasPruned?: boolean;
}

export interface PrereqGroup {
  type: 'group';
  threshold: number;  // number of items required (0 = all, 1 = any one, 2 = any two, etc.)
  items: PrereqNode[];
  wasPruned?: boolean;
}

export type PrereqNode = PrereqCourse | PrereqGroup;

interface EvaluationResult {
  satisfied: boolean;
  unsatisfiedReasons: string[];
  matchedCourses: string[];
}

// ============================================================================
// Parser
// ============================================================================

function isValidCourseId(s: string): boolean {
  const trimmed = s.trim();

  if (trimmed.startsWith('GIR:') || trimmed.startsWith('HASS:')) {
    return true;
  }

  // Standard course format: <department>.<number>
  // Department can be letters or numbers (e.g., 18, 6, MAS)
  // Number can have letters (e.g., 100A, C06)
  return /^[A-Z0-9]+\.[A-Z0-9]+$/i.test(trimmed);
}

function tokenize(prereqStr: string): string[] {
  // Pattern to match:
  // - Quoted strings: ''text'' or "text"
  // - GIR/HASS requirements: GIR:XXXX, HASS:X (can include hyphens like HASS-A)
  // - Course IDs: dept.number (both can have letters/numbers)
  // - Text operators: AND, OR (case insensitive)
  // - Operators: , /
  // - Parentheses: ( )
  const pattern = /''[^']*''|"[^"]*"|(?:GIR|HASS):[A-Z0-9-]+|[A-Z0-9]+\.[A-Z0-9]+|\bAND\b|\bOR\b|[(),/]/gi;

  const tokens = prereqStr.match(pattern) || [];
  
  // Convert text operators to symbols
  const normalized: string[] = [];
  for (const t of tokens) {
    const trimmed = t.trim();
    if (!trimmed) continue;
    
    if (trimmed.toUpperCase() === 'AND') {
      normalized.push(',');
    } else if (trimmed.toUpperCase() === 'OR') {
      normalized.push('/');
    } else {
      normalized.push(trimmed);
    }
  }
  
  return normalized;
}

function filterJunkTokens(tokens: string[]): string[] {
  const filtered: string[] = [];

  for (const token of tokens) {
    if (token.startsWith("''") || token.startsWith('"')) {
      continue;
    }

    if (['(', ')', ',', '/'].includes(token)) {
      filtered.push(token);
    } else if (isValidCourseId(token)) {
      filtered.push(token);
    }
  }

  if (filtered.length === 0) {
    return [];
  }

  // Remove leading operators
  while (filtered.length > 0 && [',', '/'].includes(filtered[0])) {
    filtered.shift();
  }

  // Remove trailing operators
  while (filtered.length > 0 && [',', '/'].includes(filtered[filtered.length - 1])) {
    filtered.pop();
  }

  // Remove consecutive operators and operators after opening parens
  const cleaned: string[] = [];
  if (filtered.length > 0) {
    cleaned.push(filtered[0]);
    for (let i = 1; i < filtered.length; i++) {
      const current = filtered[i];
      const prev = cleaned[cleaned.length - 1];
      
      // Skip operators that follow other operators
      if ([',', '/'].includes(current) && [',', '/'].includes(prev)) {
        continue;
      }
      
      // Skip operators that directly follow opening parentheses
      if ([',', '/'].includes(current) && prev === '(') {
        continue;
      }
      
      // Skip operators that directly precede closing parentheses
      if ([',', '/'].includes(prev) && current === ')') {
        cleaned.pop(); // Remove the operator before the closing paren
      }
      
      cleaned.push(current);
    }
  }

  // Remove empty parentheses: ()
  const final: string[] = [];
  let i = 0;
  while (i < cleaned.length) {
    if (i < cleaned.length - 1 && cleaned[i] === '(' && cleaned[i + 1] === ')') {
      // Skip both ( and )
      i += 2;
      // Also remove preceding operator if exists
      if (final.length > 0 && [',', '/'].includes(final[final.length - 1])) {
        final.pop();
      }
    } else {
      final.push(cleaned[i]);
      i += 1;
    }
  }

  return final;
}

export function parseFireroad(prereqStr: string): PrereqNode {
  if (!prereqStr || prereqStr.trim() === '') {
    return { type: 'group', threshold: 0, items: [] };
  }

  let tokens = tokenize(prereqStr);
  tokens = filterJunkTokens(tokens);

  if (tokens.length === 0) {
    return { type: 'group', threshold: 0, items: [] };
  }

  let index = 0;

  const peek = (): string => {
    if (index < tokens.length) {
      return tokens[index];
    }
    return '';
  };

  const consume = (): string => {
    const token = peek();
    index++;
    return token;
  };

  const parseExpr = (): PrereqNode => {
    return parseOr();
  };

  const parseOr = (): PrereqNode => {
    const items: PrereqNode[] = [parseAnd()];

    while (peek() === '/') {
      consume();
      items.push(parseAnd());
    }

    if (items.length === 1) {
      return items[0];
    }

    return { type: 'group', threshold: 1, items };
  };

  const parseAnd = (): PrereqNode => {
    const items: PrereqNode[] = [parseTerm()];

    while (peek() === ',') {
      consume();
      items.push(parseTerm());
    }

    if (items.length === 1) {
      return items[0];
    }

    return { type: 'group', threshold: items.length, items };
  };

  const parseTerm = (): PrereqNode => {
    const token = peek();

    if (token === '(') {
      consume();
      const expr = parseExpr();
      if (peek() === ')') {
        consume();
      } else {
        throw new Error("Mismatched parentheses: expected ')'");
      }
      return expr;
    }

    if ([')', ',', '/'].includes(token)) {
      throw new Error(`Unexpected token: ${token}`);
    }

    const courseId = consume();
    if (!isValidCourseId(courseId)) {
      throw new Error(`Invalid course ID: ${courseId}`);
    }
    return { type: 'course', courseId };
  };

  return parseExpr();
}

export function prereqToString(prereq: PrereqNode): string {
  if (prereq.type === 'course') {
    return prereq.courseId;
  }

  if (!prereq.items || prereq.items.length === 0) {
    return '';
  }

  const itemStrings = prereq.items.map(item =>
    item.type === 'group' ? `(${prereqToString(item)})` : prereqToString(item)
  );

  if (prereq.threshold === prereq.items.length) {
    return itemStrings.join(' AND ');
  }
  if (prereq.threshold === 1) {
    return itemStrings.join(' OR ');
  }

  return `${prereq.threshold} of: [${itemStrings.join(', ')}]`;
}

// ============================================================================
// Evaluator
// ============================================================================

class PrerequisiteEvaluator {
  private availableCourses: Set<string>;
  private allowReuseAcrossRequirements: boolean;
  private minimal: boolean;
  private usedCourses: Set<string>;
  private courseTags: Map<string, string[]>; // courseId -> list of tags like ["GIR:CAL1", "HASS:A"]

  constructor(
    availableCourses: string[],
    allowReuseAcrossRequirements: boolean = false,
    minimal: boolean = true,
    courseTags: Map<string, string[]> = new Map()
  ) {
    this.availableCourses = new Set(availableCourses);
    this.allowReuseAcrossRequirements = allowReuseAcrossRequirements;
    this.minimal = minimal;
    this.courseTags = courseTags;
    this.usedCourses = new Set();
  }

  evaluate(prereq: PrereqNode): EvaluationResult {
    if (prereq.type === 'course') {
      return this.evaluateCourse(prereq);
    }

    if (prereq.type === 'group') {
      return this.evaluateGroup(prereq);
    }

    throw new Error(`Unknown prerequisite node type`);
  }

  private evaluateCourse(course: PrereqCourse): EvaluationResult {
    const courseId = course.courseId;

    // Check if this is a tag requirement (GIR:XXX or HASS:XXX)
    if (courseId.startsWith('GIR:') || courseId.startsWith('HASS:')) {
      // Find any available course that has this tag
      for (const availableCourse of this.availableCourses) {
        const tags = this.courseTags.get(availableCourse) || [];
        const canUse = this.allowReuseAcrossRequirements || !this.usedCourses.has(availableCourse);
        
        if (tags.includes(courseId) && canUse) {
          this.usedCourses.add(availableCourse);
          return {
            satisfied: true,
            matchedCourses: [availableCourse],
            unsatisfiedReasons: []
          };
        }
      }
      
      // No course with this tag found
      return {
        satisfied: false,
        unsatisfiedReasons: [courseId],
        matchedCourses: []
      };
    }

    // Regular course ID check
    const canUse = this.allowReuseAcrossRequirements || !this.usedCourses.has(courseId);

    if (this.availableCourses.has(courseId) && canUse) {
      this.usedCourses.add(courseId);
      return {
        satisfied: true,
        matchedCourses: [courseId],
        unsatisfiedReasons: []
      };
    }

    return {
      satisfied: false,
      unsatisfiedReasons: [courseId],
      matchedCourses: []
    };
  }

  private evaluateGroup(group: PrereqGroup): EvaluationResult {
    if (!group.items || group.items.length === 0) {
      return { satisfied: true, matchedCourses: [], unsatisfiedReasons: [] };
    }

    let satisfiedCount = 0;
    const allMatchedCourses: string[] = [];
    const itemResults: EvaluationResult[] = [];

    for (const item of group.items) {
      const result = this.evaluate(item);
      itemResults.push(result);

      allMatchedCourses.push(...result.matchedCourses);

      if (result.satisfied) {
        satisfiedCount++;
      }

      // Early exit if we've satisfied the threshold
      if (satisfiedCount >= group.threshold) {
        return {
          satisfied: true,
          matchedCourses: allMatchedCourses,
          unsatisfiedReasons: []
        };
      }
    }

    if (satisfiedCount >= group.threshold) {
      return {
        satisfied: true,
        matchedCourses: allMatchedCourses,
        unsatisfiedReasons: []
      };
    }

    // For unsatisfied groups, return unsatisfied reasons based on mode
    if (this.minimal) {
      // MINIMAL MODE: Return smallest set of missing prerequisites
      // For OR groups (threshold === 1), return the shortest unsatisfied option
      // For AND groups (threshold === items.length), return all unsatisfied items
      // For k-of-n groups, return the k options with fewest unsatisfied reasons
      
      if (group.threshold === 1) {
        // OR group: return the option with fewest missing prerequisites
        const unsatisfiedResults = itemResults.filter(r => !r.satisfied);
        if (unsatisfiedResults.length === 0) {
          return {
            satisfied: false,
            unsatisfiedReasons: [],
            matchedCourses: allMatchedCourses
          };
        }
        
        // Find the option with the fewest unsatisfied reasons
        const minimalOption = unsatisfiedResults.reduce((min, curr) => 
          curr.unsatisfiedReasons.length < min.unsatisfiedReasons.length ? curr : min
        );
        
        return {
          satisfied: false,
          unsatisfiedReasons: minimalOption.unsatisfiedReasons,
          matchedCourses: allMatchedCourses
        };
      } else if (group.threshold === group.items.length) {
        // AND group: return minimal set from each unsatisfied item
        // Each unsatisfied item already returns its minimal set
        const allUnsatisfiedReasons: string[] = [];
        for (const result of itemResults) {
          if (!result.satisfied) {
            allUnsatisfiedReasons.push(...result.unsatisfiedReasons);
          }
        }
        
        return {
          satisfied: false,
          unsatisfiedReasons: allUnsatisfiedReasons,
          matchedCourses: allMatchedCourses
        };
      } else {
        // k-of-n group: need to satisfy k items, find the k options with fewest missing
        const unsatisfiedResults = itemResults.filter(r => !r.satisfied);
        const needed = group.threshold - satisfiedCount;
        
        // Sort by number of unsatisfied reasons and take the k with fewest
        const sortedUnsatisfied = [...unsatisfiedResults].sort((a, b) => 
          a.unsatisfiedReasons.length - b.unsatisfiedReasons.length
        );
        
        const minimalOptions = sortedUnsatisfied.slice(0, needed);
        const allUnsatisfiedReasons: string[] = [];
        for (const result of minimalOptions) {
          allUnsatisfiedReasons.push(...result.unsatisfiedReasons);
        }
        
        return {
          satisfied: false,
          unsatisfiedReasons: allUnsatisfiedReasons,
          matchedCourses: allMatchedCourses
        };
      }
    } else {
      // COMPLETE MODE: Return all unsatisfied reasons from all branches
      const allUnsatisfiedReasons: string[] = [];
      for (const result of itemResults) {
        if (!result.satisfied) {
          allUnsatisfiedReasons.push(...result.unsatisfiedReasons);
        }
      }
      
      return {
        satisfied: false,
        unsatisfiedReasons: allUnsatisfiedReasons,
        matchedCourses: allMatchedCourses
      };
    }
  }

  reset(): void {
    this.usedCourses.clear();
  }
}

/**
 * Evaluate prerequisites against a list of available courses
 */
export function evaluatePrerequisites(
  prereqTree: PrereqNode,
  availableCourses: string[],
  allowReuse: boolean = true,
  minimal: boolean = true,
  courseTags: Map<string, string[]> = new Map()
): EvaluationResult {
  const evaluator = new PrerequisiteEvaluator(availableCourses, allowReuse, minimal, courseTags);
  return evaluator.evaluate(prereqTree);
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Extract all course IDs from a prerequisite tree
 */
export function extractCourseIds(prereqTree: PrereqNode | null): string[] {
  if (!prereqTree) return [];

  if (prereqTree.type === 'course') {
    return [prereqTree.courseId];
  }

  if (prereqTree.type === 'group') {
    return prereqTree.items.flatMap(child => extractCourseIds(child));
  }

  return [];
}
