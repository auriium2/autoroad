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

interface PrereqCourse {
  type: 'course';
  courseId: string;
  wasPruned?: boolean;
}

interface PrereqGroup {
  type: 'group';
  threshold: number;  // number of items required (0 = all, 1 = any one, 2 = any two, etc.)
  items: PrereqNode[];
  wasPruned?: boolean;
}

type PrereqNode = PrereqCourse | PrereqGroup;

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

  if (trimmed.startsWith('GIR:')) {
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
  // - GIR requirements: GIR:XXXX
  // - Course IDs: dept.number (both can have letters/numbers)
  // - Operators: , /
  // - Parentheses: ( )
  const pattern = /''[^']*''|"[^"]*"|GIR:[A-Z0-9]+|[A-Z0-9]+\.[A-Z0-9]+|[(),/]/gi;

  const tokens = prereqStr.match(pattern) || [];
  return tokens.map(t => t.trim()).filter(t => t.length > 0);
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

  // Remove consecutive operators
  const cleaned: string[] = [];
  if (filtered.length > 0) {
    cleaned.push(filtered[0]);
    for (let i = 1; i < filtered.length; i++) {
      if ([',', '/'].includes(filtered[i]) && [',', '/'].includes(cleaned[cleaned.length - 1])) {
        continue;
      }
      cleaned.push(filtered[i]);
    }
  }

  return cleaned;
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
  private usedCourses: Set<string>;

  constructor(
    availableCourses: string[],
    allowReuseAcrossRequirements: boolean = false
  ) {
    this.availableCourses = new Set(availableCourses);
    this.allowReuseAcrossRequirements = allowReuseAcrossRequirements;
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
    const allUnsatisfiedReasons: string[] = [];

    for (const item of group.items) {
      const result = this.evaluate(item);

      allMatchedCourses.push(...result.matchedCourses);

      if (result.satisfied) {
        satisfiedCount++;
      } else {
        allUnsatisfiedReasons.push(...result.unsatisfiedReasons);
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

    return {
      satisfied: false,
      unsatisfiedReasons: allUnsatisfiedReasons,
      matchedCourses: allMatchedCourses
    };
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
  allowReuse: boolean = true
): EvaluationResult {
  const evaluator = new PrerequisiteEvaluator(availableCourses, allowReuse);
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
