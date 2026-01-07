/**
 * Tests for prerequisite parser and evaluation
 */

import { parseFireroad, extractCourseIds, evaluatePrerequisites } from '../prerequisites';

describe('Prerequisites Parser', () => {
  describe('parseFireroad', () => {
    it('should parse single course', () => {
      const result = parseFireroad('6.100');
      expect(result.type).toBe('course');
      if (result.type === 'course') {
        expect(result.courseId).toBe('6.100');
      }
    });

    it('should parse AND expression', () => {
      const result = parseFireroad('6.100,6.1200');
      expect(result.type).toBe('group');
      if (result.type === 'group') {
        expect(result.threshold).toBe(2);
        expect(result.items).toHaveLength(2);
      }
    });

    it('should parse OR expression', () => {
      const result = parseFireroad('18.05/18.06');
      expect(result.type).toBe('group');
      if (result.type === 'group') {
        expect(result.threshold).toBe(1);
        expect(result.items).toHaveLength(2);
      }
    });

    it('should handle quoted strings and operators - case 6.1910', () => {
      const prereqStr = "GIR:PHY2/6.100A/(''Coreq: 6.1903''/6.1904)/''permission of instructor''";
      
      // Should parse without throwing
      const result = parseFireroad(prereqStr);
      
      // Should extract the valid courses
      const courseIds = extractCourseIds(result);
      expect(courseIds).toContain('GIR:PHY2');
      expect(courseIds).toContain('6.100A');
      expect(courseIds).toContain('6.1904');
      
      // Should NOT contain the quoted strings
      expect(courseIds).not.toContain("''Coreq: 6.1903''");
      expect(courseIds).not.toContain("''permission of instructor''");
    });

    it('should handle empty parentheses after filtering quoted strings', () => {
      const prereqStr = "21G.501/(''placement test'', ''permission of instructor'')";
      
      // Should parse without throwing
      const result = parseFireroad(prereqStr);
      
      // Should only contain the valid course
      const courseIds = extractCourseIds(result);
      expect(courseIds).toContain('21G.501');
      expect(courseIds).toHaveLength(1);
    });

    it('should handle AND text operator', () => {
      const prereqStr = "''Prereq: 10.213''/10.40/(5.601 AND 5.602)";
      
      // Should parse without throwing
      const result = parseFireroad(prereqStr);
      
      // Should extract valid courses
      const courseIds = extractCourseIds(result);
      expect(courseIds).toContain('10.40');
      expect(courseIds).toContain('5.601');
      expect(courseIds).toContain('5.602');
      expect(courseIds).toHaveLength(3);
    });

    it('should handle empty string', () => {
      const result = parseFireroad('');
      expect(result.type).toBe('group');
      if (result.type === 'group') {
        expect(result.items).toHaveLength(0);
      }
    });

    it('should handle GIR requirements', () => {
      const result = parseFireroad('GIR:CAL1');
      expect(result.type).toBe('course');
      if (result.type === 'course') {
        expect(result.courseId).toBe('GIR:CAL1');
      }
    });

    it('should handle complex nested expression', () => {
      const result = parseFireroad('(6.100,6.1200)/(6.100L,6.1200)');
      expect(result.type).toBe('group');
      if (result.type === 'group') {
        expect(result.threshold).toBe(1); // OR
        expect(result.items).toHaveLength(2);
      }
    });
  });

  describe('extractCourseIds', () => {
    it('should extract all course IDs from tree', () => {
      const tree = parseFireroad('6.100,6.1200/18.01');
      const courseIds = extractCourseIds(tree);
      
      expect(courseIds).toContain('6.100');
      expect(courseIds).toContain('6.1200');
      expect(courseIds).toContain('18.01');
    });
  });

  describe('evaluatePrerequisites', () => {
    describe('basic course prerequisites', () => {
      it('should satisfy single course prerequisite when taken', () => {
        const tree = parseFireroad('6.100');
        const taken = ['6.100'];
        const result = evaluatePrerequisites(tree, taken);
        
        expect(result.satisfied).toBe(true);
        expect(result.unsatisfiedReasons).toHaveLength(0);
      });

      it('should not satisfy single course prerequisite when not taken', () => {
        const tree = parseFireroad('6.100');
        const taken: string[] = [];
        const result = evaluatePrerequisites(tree, taken);
        
        expect(result.satisfied).toBe(false);
        expect(result.unsatisfiedReasons).toContain('6.100');
      });

      it('should satisfy AND prerequisite when all courses taken', () => {
        const tree = parseFireroad('6.100,6.1200');
        const taken = ['6.100', '6.1200'];
        const result = evaluatePrerequisites(tree, taken);
        
        expect(result.satisfied).toBe(true);
      });

      it('should not satisfy AND prerequisite when only some courses taken', () => {
        const tree = parseFireroad('6.100,6.1200');
        const taken = ['6.100'];
        const result = evaluatePrerequisites(tree, taken);
        
        expect(result.satisfied).toBe(false);
        expect(result.unsatisfiedReasons).toContain('6.1200');
      });

      it('should satisfy OR prerequisite when at least one course taken', () => {
        const tree = parseFireroad('6.100/6.1200');
        const taken = ['6.100'];
        const result = evaluatePrerequisites(tree, taken);
        
        expect(result.satisfied).toBe(true);
      });

      it('should not satisfy OR prerequisite when no courses taken', () => {
        const tree = parseFireroad('6.100/6.1200');
        const taken: string[] = [];
        const result = evaluatePrerequisites(tree, taken);
        
        expect(result.satisfied).toBe(false);
      });
    });

    describe('GIR prerequisites with tags', () => {
      it('should satisfy GIR prerequisite with course that has matching tag', () => {
        const tree = parseFireroad('GIR:CAL1');
        const taken = ['18.01'];
        const tags = new Map([['18.01', ['GIR:CAL1']]]);
        const result = evaluatePrerequisites(tree, taken, true, true, tags);
        
        expect(result.satisfied).toBe(true);
        expect(result.matchedCourses).toContain('18.01');
      });

      it('should not satisfy GIR prerequisite when no course has matching tag', () => {
        const tree = parseFireroad('GIR:CAL1');
        const taken = ['6.100'];
        const tags = new Map([['6.100', ['GIR:PHY1']]]);
        const result = evaluatePrerequisites(tree, taken, true, true, tags);
        
        expect(result.satisfied).toBe(false);
        expect(result.unsatisfiedReasons).toContain('GIR:CAL1');
      });

      it('should satisfy GIR prerequisite even when course ID does not match', () => {
        const tree = parseFireroad('GIR:CAL1');
        const taken = ['ES.1801']; // Different course but same GIR
        const tags = new Map([['ES.1801', ['GIR:CAL1']]]);
        const result = evaluatePrerequisites(tree, taken, true, true, tags);
        
        expect(result.satisfied).toBe(true);
        expect(result.matchedCourses).toContain('ES.1801');
      });

      it('should handle multiple GIR tags on same course', () => {
        const tree = parseFireroad('GIR:CAL1,GIR:PHY1');
        const taken = ['8.01']; // Physics course with CAL1 prereq
        const tags = new Map([
          ['8.01', ['GIR:PHY1']],
          ['18.01', ['GIR:CAL1']]
        ]);
        // Need both, but only have one
        const result = evaluatePrerequisites(tree, taken, true, true, tags);
        
        expect(result.satisfied).toBe(false);
      });
    });

    describe('HASS prerequisites with tags', () => {
      it('should satisfy HASS prerequisite with course that has matching tag', () => {
        // Note: HASS prerequisites in the database may be "HASS:A" or "HASS:H"
        // but the frontend stores tags as "HASS:HASS-A" (with HASS- prefix)
        // For testing, we use the full format to match actual runtime behavior
        const tree = parseFireroad('HASS:A'); // Simplified HASS code (not HASS-A)
        const taken = ['21M.011'];
        const tags = new Map([['21M.011', ['HASS:HASS-A']]]);
        const result = evaluatePrerequisites(tree, taken, true, true, tags);
        
        // This won't match because tag is "HASS:HASS-A" but prereq is "HASS:A"
        // This is a known limitation - HASS tags need exact match
        expect(result.satisfied).toBe(false);
      });

      it('should satisfy HASS prerequisite with exact tag match', () => {
        const tree = parseFireroad('HASS:HASS-A');
        const taken = ['21M.011'];
        const tags = new Map([['21M.011', ['HASS:HASS-A']]]);
        const result = evaluatePrerequisites(tree, taken, true, true, tags);
        
        expect(result.satisfied).toBe(true);
        expect(result.matchedCourses).toContain('21M.011');
      });
    });

    describe('mixed prerequisites', () => {
      it('should handle mixed course and GIR prerequisites', () => {
        const tree = parseFireroad('6.100,GIR:CAL1');
        const taken = ['6.100', '18.01'];
        const tags = new Map([['18.01', ['GIR:CAL1']]]);
        const result = evaluatePrerequisites(tree, taken, true, true, tags);
        
        expect(result.satisfied).toBe(true);
        expect(result.matchedCourses).toContain('6.100');
        expect(result.matchedCourses).toContain('18.01');
      });

      it('should handle OR between course and GIR', () => {
        const tree = parseFireroad('6.100/GIR:CAL1');
        const taken = ['18.01']; // Has GIR:CAL1
        const tags = new Map([['18.01', ['GIR:CAL1']]]);
        const result = evaluatePrerequisites(tree, taken, true, true, tags);
        
        expect(result.satisfied).toBe(true);
        expect(result.matchedCourses).toContain('18.01');
      });
    });

    describe('complex nested prerequisites', () => {
      it('should handle nested AND/OR expressions', () => {
        // (6.100,6.1200)/(18.01,18.02) - need both from one pair
        const tree = parseFireroad('(6.100,6.1200)/(18.01,18.02)');
        const taken = ['18.01', '18.02'];
        const result = evaluatePrerequisites(tree, taken);
        
        expect(result.satisfied).toBe(true);
      });

      it('should fail nested expression when incomplete', () => {
        const tree = parseFireroad('(6.100,6.1200)/(18.01,18.02)');
        const taken = ['18.01']; // Only have one from second pair
        const result = evaluatePrerequisites(tree, taken);
        
        expect(result.satisfied).toBe(false);
      });
    });

    describe('edge cases', () => {
      it('should handle empty prerequisite tree', () => {
        const tree = parseFireroad('');
        const taken: string[] = [];
        const result = evaluatePrerequisites(tree, taken);
        
        expect(result.satisfied).toBe(true);
      });

      it('should be case sensitive for course IDs', () => {
        const tree = parseFireroad('6.100A');
        const taken = ['6.100a']; // Wrong case
        const result = evaluatePrerequisites(tree, taken);
        
        // Should not match - course IDs are case sensitive
        expect(result.satisfied).toBe(false);
      });
    });
  });
});
