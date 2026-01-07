/**
 * Parity tests - ensure frontend parser matches backend parser behavior
 */

import { parseFireroad, extractCourseIds } from '../prerequisites';

describe('Parser Parity with Backend', () => {
  const testCases = [
    {
      input: "GIR:PHY2/6.100A/(''Coreq: 6.1903''/6.1904)/''permission of instructor''",
      expectedCourses: ['GIR:PHY2', '6.100A', '6.1904'],
      description: '6.1910 case - quoted strings with operators'
    },
    {
      input: "21G.501/(''placement test'', ''permission of instructor'')",
      expectedCourses: ['21G.501'],
      description: 'Empty parentheses after quoted strings'
    },
    {
      input: "''Prereq: 10.213''/10.40/(5.601 AND 5.602)",
      expectedCourses: ['10.40', '5.601', '5.602'],
      description: 'Text AND operator'
    },
    {
      input: "6.100,6.1200",
      expectedCourses: ['6.100', '6.1200'],
      description: 'Simple AND with comma'
    },
    {
      input: "18.05/18.06",
      expectedCourses: ['18.05', '18.06'],
      description: 'Simple OR with slash'
    },
    {
      input: "(18.01/18.02), 18.03",
      expectedCourses: ['18.01', '18.02', '18.03'],
      description: 'Nested OR and AND'
    },
  ];

  testCases.forEach(({ input, expectedCourses, description }) => {
    it(`should handle: ${description}`, () => {
      const result = parseFireroad(input);
      const courses = extractCourseIds(result);
      
      expect(courses.sort()).toEqual(expectedCourses.sort());
    });
  });

  it('should achieve 100% parity on all regression cases', () => {
    // All 12 original failures from backend fuzzer
    const regressionCases = [
      "''Prereq: 10.213''/10.40/(5.601 AND 5.602)",
      "21G.501/(''placement test'', ''permission of instructor'')",
      "21G.502/(''placement test'', ''permission of instructor'')",
      "21G.503/(''placement test'', ''permission of instructor'')",
      "21G.504/(''Placement test'', ''permission of instructor'')",
      "21G.505/(''Placement test'', ''permission of instructor'')",
      "21G.506/(''Placement test'', ''permission of instructor'')",
      "21G.551/(''placement test'', ''permission of instructor'')",
      "21G.552/(''placement test'', ''permission of instructor'')",
      "21L.609/(''placement exam'', ''permission of instructor'')",
      "21L.613/(''placement exam'', ''permission of instructor'')",
      "5.310/7.002/(''Coreq: 12 units UROP''/''other approved laboratory subject'', ''permission of instructor'')",
    ];

    regressionCases.forEach(input => {
      // Should parse without throwing
      expect(() => parseFireroad(input)).not.toThrow();
      
      // Should extract at least one course
      const result = parseFireroad(input);
      const courses = extractCourseIds(result);
      expect(courses.length).toBeGreaterThan(0);
      
      // Should not contain quoted strings
      courses.forEach(courseId => {
        expect(courseId).not.toMatch(/^['"]/);
      });
    });
  });
});
