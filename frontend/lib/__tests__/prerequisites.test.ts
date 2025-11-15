/**
 * Tests for prerequisite parser
 */

import { parseFireroad, extractCourseIds } from '../prerequisites';

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
});
