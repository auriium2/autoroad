/**
 * Build RequirementTree from Fireroad requirement file format
 * Evaluates progress based on selected courses
 * 
 * Format specification from https://fireroad.mit.edu/requirements/
 * - Comments: %% symbol
 * - AND: comma (,)
 * - OR: slash (/)
 * - Thresholds: {>=x}, {>x}, {<=x}, {<x}, {>=xu} for units
 * - Variables: var_name, "Title" := statement
 * - Parentheses for grouping
 */

export interface RequirementNode {
  title?: string;
  'connection-type'?: 'all' | 'any';
  'threshold-desc'?: string;
  threshold?: {
    cutoff: number;
    criterion: string;
    type: string;
  };
  desc?: string;
  reqs?: RequirementNode[];
  req?: string;
  fulfilled?: boolean;
  progress?: number;
  max?: number;
  percent_fulfilled?: number;
  sat_courses?: string[];
  is_bypassed?: boolean;
}

export interface RequirementTree {
  'list-id': string;
  title: string;
  'medium-title'?: string;
  'short-title'?: string;
  'title-no-degree'?: string;
  desc?: string;
  reqs: RequirementNode[];
}

interface SelectedSubject {
  subject_id: string;
  title?: string;
  units?: number;
  semester?: number;
}

interface VariableDeclaration {
  name: string;
  title?: string;
  statement: string;
}

/**
 * Remove comments from a line (everything after %%)
 */
function stripComments(line: string): string {
  const commentIndex = line.indexOf('%%');
  if (commentIndex === -1) return line;
  return line.substring(0, commentIndex);
}

/**
 * Parse variable declarations from requirement file content
 * Returns map of variable name to statement and list of non-declaration lines
 */
function parseVariables(content: string): { 
  variables: Map<string, VariableDeclaration>;
  statements: string[];
} {
  const variables = new Map<string, VariableDeclaration>();
  const statements: string[] = [];
  
  const lines = content.split('\n');
  
  for (const line of lines) {
    const clean = stripComments(line).trim();
    if (!clean) continue;
    
    // Check for variable declaration: var_name, "Title" := statement
    const varMatch = clean.match(/^([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:,\s*"([^"]+)")?\s*:=\s*(.+)$/);
    if (varMatch) {
      const [, name, title, statement] = varMatch;
      variables.set(name, { name, title, statement });
    } else {
      // Not a variable declaration, it's a statement to be evaluated
      statements.push(clean);
    }
  }
  
  return { variables, statements };
}

/**
 * Expand variable references in a statement
 */
function expandVariables(
  statement: string,
  variables: Map<string, VariableDeclaration>,
  visited: Set<string> = new Set()
): string {
  // Tokenize to find variable references (identifiers that aren't course IDs)
  // Course IDs typically have dots or start with numbers
  const tokens = tokenize(statement);
  let expanded = '';
  
  for (const token of tokens) {
    if (token.type === 'identifier' && variables.has(token.value)) {
      // Check for circular references
      if (visited.has(token.value)) {
        throw new Error(`Circular variable reference detected: ${token.value}`);
      }
      
      const varDecl = variables.get(token.value)!;
      const newVisited = new Set(visited);
      newVisited.add(token.value);
      
      // Recursively expand the variable's statement
      const expandedVar = expandVariables(varDecl.statement, variables, newVisited);
      expanded += `(${expandedVar})`;
    } else {
      expanded += token.value;
    }
  }
  
  return expanded;
}

interface Token {
  type: 'identifier' | 'course' | 'operator' | 'threshold' | 'paren' | 'string' | 'whitespace';
  value: string;
}

/**
 * Tokenize a requirement statement
 */
function tokenize(statement: string): Token[] {
  const tokens: Token[] = [];
  let i = 0;
  
  while (i < statement.length) {
    const char = statement[i];
    
    // Whitespace
    if (/\s/.test(char)) {
      let ws = char;
      i++;
      while (i < statement.length && /\s/.test(statement[i])) {
        ws += statement[i];
        i++;
      }
      tokens.push({ type: 'whitespace', value: ws });
      continue;
    }
    
    // Parentheses
    if (char === '(' || char === ')') {
      tokens.push({ type: 'paren', value: char });
      i++;
      continue;
    }
    
    // Operators
    if (char === ',' || char === '/') {
      tokens.push({ type: 'operator', value: char });
      i++;
      continue;
    }
    
    // Threshold: {>=3}, {>2u}, etc.
    if (char === '{') {
      let threshold = char;
      i++;
      while (i < statement.length && statement[i] !== '}') {
        threshold += statement[i];
        i++;
      }
      if (i < statement.length) {
        threshold += statement[i]; // closing }
        i++;
      }
      tokens.push({ type: 'threshold', value: threshold });
      continue;
    }
    
    // Quoted strings (for special requirements like ""text"")
    if (char === '"' && i + 1 < statement.length && statement[i + 1] === '"') {
      let str = '""';
      i += 2;
      while (i < statement.length) {
        if (statement[i] === '"' && i + 1 < statement.length && statement[i + 1] === '"') {
          str += '""';
          i += 2;
          break;
        }
        str += statement[i];
        i++;
      }
      tokens.push({ type: 'string', value: str });
      continue;
    }
    
    // Identifiers/Course IDs
    // Course IDs: may contain letters, numbers, dots, hyphens
    // Examples: 6.100A, 18.01, CMS.100, 3.985J
    // Identifiers: variable names like intro_music, all_econ
    if (/[a-zA-Z0-9_]/.test(char)) {
      let id = char;
      i++;
      while (i < statement.length && /[a-zA-Z0-9._-]/.test(statement[i])) {
        id += statement[i];
        i++;
      }
      
      // Determine if it's a course ID or identifier
      // Course IDs typically contain dots or start with numbers
      // Identifiers are variable names (all lowercase/underscores, or single letters for test courses)
      const isCourse = /\d/.test(id) && /[0-9.]/.test(id);
      tokens.push({ type: isCourse ? 'course' : 'identifier', value: id });
      continue;
    }
    
    // Unknown character, skip it
    i++;
  }
  
  return tokens;
}

/**
 * Parse threshold from token stream
 */
function parseThreshold(thresholdToken: string): {
  cutoff: number;
  criterion: string;
  type: string;
} | null {
  const match = thresholdToken.match(/^\{(>=|>|<=|<)(\d+)(u)?\}$/);
  if (!match) return null;
  
  const [, type, cutoffStr, unitsSuffix] = match;
  return {
    cutoff: parseInt(cutoffStr, 10),
    criterion: unitsSuffix ? 'units' : 'courses',
    type,
  };
}

/**
 * Parse a requirement statement into a RequirementNode
 * This uses a proper recursive descent parser
 */
function parseStatement(
  statement: string,
  selectedCourses: Set<string>,
  courseUnits: Map<string, number>
): RequirementNode {
  const tokens = tokenize(statement).filter(t => t.type !== 'whitespace');
  let pos = 0;
  
  function peek(): Token | null {
    return pos < tokens.length ? tokens[pos] : null;
  }
  
  function consume(): Token | null {
    return pos < tokens.length ? tokens[pos++] : null;
  }
  
  // Parse an expression with threshold support
  function parseExpression(): RequirementNode {
    // Check for leading threshold: {>=3}(...)
    let leadingThreshold: ReturnType<typeof parseThreshold> = null;
    if (peek()?.type === 'threshold') {
      const thresholdToken = consume()!;
      leadingThreshold = parseThreshold(thresholdToken.value);
    }
    
    // Parse the main term
    let node = parseTerm();
    
    // Check for trailing threshold: (...){>=3}
    if (peek()?.type === 'threshold') {
      const thresholdToken = consume()!;
      const threshold = parseThreshold(thresholdToken.value);
      if (threshold) {
        node = applyThreshold(node, threshold, selectedCourses, courseUnits);
      }
    } else if (leadingThreshold) {
      node = applyThreshold(node, leadingThreshold, selectedCourses, courseUnits);
    }
    
    return node;
  }
  
  // Parse a term (handles OR operations)
  function parseTerm(): RequirementNode {
    const parts: RequirementNode[] = [];
    parts.push(parseFactor());
    
    while (peek()?.type === 'operator' && peek()?.value === '/') {
      consume(); // consume '/'
      parts.push(parseFactor());
    }
    
    if (parts.length === 1) {
      return parts[0];
    }
    
    // OR group
    const fulfilled = parts.some(p => p.fulfilled);
    const satCourses = parts.filter(p => p.fulfilled).flatMap(p => p.sat_courses || []);
    
    return {
      'connection-type': 'any',
      reqs: parts,
      fulfilled,
      sat_courses: satCourses,
    };
  }
  
  // Parse a factor (handles AND operations)
  function parseFactor(): RequirementNode {
    const parts: RequirementNode[] = [];
    parts.push(parsePrimary());
    
    while (peek()?.type === 'operator' && peek()?.value === ',') {
      consume(); // consume ','
      parts.push(parsePrimary());
    }
    
    if (parts.length === 1) {
      return parts[0];
    }
    
    // AND group
    const fulfilled = parts.every(p => p.fulfilled);
    const satCourses = parts.filter(p => p.fulfilled).flatMap(p => p.sat_courses || []);
    
    return {
      'connection-type': 'all',
      reqs: parts,
      fulfilled,
      sat_courses: satCourses,
    };
  }
  
  // Parse a primary (course ID, special string, or parenthesized expression)
  function parsePrimary(): RequirementNode {
    const token = peek();
    
    if (!token) {
      throw new Error('Unexpected end of expression');
    }
    
    // Parenthesized expression
    if (token.type === 'paren' && token.value === '(') {
      consume(); // consume '('
      const node = parseExpression();
      const closeParen = consume();
      if (closeParen?.type !== 'paren' || closeParen.value !== ')') {
        throw new Error('Expected closing parenthesis');
      }
      return node;
    }
    
    // Special string: ""text""
    if (token.type === 'string') {
      consume();
      const text = token.value.slice(2, -2); // Remove "" markers
      return {
        req: text,
        fulfilled: false,
        sat_courses: [],
      };
    }
    
    // Course ID or identifier (treat as course if not a variable)
    if (token.type === 'course' || token.type === 'identifier') {
      consume();
      const courseId = token.value;
      const isFulfilled = selectedCourses.has(courseId);
      return {
        req: courseId,
        fulfilled: isFulfilled,
        sat_courses: isFulfilled ? [courseId] : [],
      };
    }
    
    throw new Error(`Unexpected token: ${token.type} = ${token.value}`);
  }
  
  return parseExpression();
}

/**
 * Apply threshold to a requirement node
 */
function applyThreshold(
  node: RequirementNode,
  threshold: { cutoff: number; criterion: string; type: string },
  selectedCourses: Set<string>,
  courseUnits: Map<string, number>
): RequirementNode {
  // Calculate progress based on threshold type
  let progress = 0;
  const satCourses: string[] = [];
  
  if (node.reqs) {
    // Count progress across all requirements (even partially fulfilled ones)
    // This allows thresholds like {>=1} to work with OR groups
    for (const req of node.reqs) {
      if (threshold.criterion === 'units') {
        // For units, count all satisfied courses
        if (req.sat_courses && req.sat_courses.length > 0) {
          for (const course of req.sat_courses) {
            progress += courseUnits.get(course) || 12;
          }
          satCourses.push(...req.sat_courses);
        }
      } else if (threshold.criterion === 'courses') {
        // For courses, count the number of satisfied courses
        if (req.sat_courses && req.sat_courses.length > 0) {
          progress += req.sat_courses.length;
          satCourses.push(...req.sat_courses);
        }
      }
    }
  }
  
  const max = threshold.cutoff;
  const fulfilled = threshold.type === '>=' 
    ? progress >= max 
    : threshold.type === '>' 
    ? progress > max 
    : threshold.type === '<=' 
    ? progress <= max 
    : progress < max;
  
  return {
    ...node,
    threshold: {
      cutoff: threshold.cutoff,
      criterion: threshold.criterion,
      type: threshold.type,
    },
    'threshold-desc': `${threshold.type}${threshold.cutoff}${threshold.criterion === 'units' ? 'u' : ''}`,
    progress,
    max,
    fulfilled,
    percent_fulfilled: max > 0 ? Math.min(100, (progress / max) * 100) : 0,
    sat_courses: satCourses,
  };
}

/**
 * Build RequirementTree from file content and selected courses
 */
export function buildRequirementTree(
  key: string,
  metadata: { title?: string; medium?: string; short?: string; title_no_degree?: string },
  description: string,
  content: string,
  selectedSubjects: SelectedSubject[]
): RequirementTree {
  // Build sets for quick lookup
  const selectedCourses = new Set(selectedSubjects.map(s => s.subject_id));
  const courseUnits = new Map(selectedSubjects.map(s => [s.subject_id, s.units || 12]));
  
  // Parse variables and statements
  const { variables, statements } = parseVariables(content);
  
  // If there are no standalone statements, use the last variable declaration
  // In Fireroad files, intermediate variables are helpers, final variable is the actual requirement
  const requirementsToEvaluate = statements.length > 0 
    ? statements 
    : Array.from(variables.values()).slice(-1).map(v => v.statement);
  
  // Expand variables in statements and parse
  const reqs: RequirementNode[] = requirementsToEvaluate.map(stmt => {
    const expanded = expandVariables(stmt, variables);
    return parseStatement(expanded, selectedCourses, courseUnits);
  });
  
  return {
    'list-id': key,
    title: metadata.title || metadata.medium || metadata.short || key,
    'medium-title': metadata.medium,
    'short-title': metadata.short,
    'title-no-degree': metadata.title_no_degree,
    desc: description,
    reqs,
  };
}
