import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { isPastSemesterById, graduationYearToPlanningYear } from '../semesterUtils';

describe('semesterUtils', () => {
  let originalDate: typeof Date;

  beforeEach(() => {
    originalDate = global.Date;
  });

  afterEach(() => {
    global.Date = originalDate;
  });

  const mockDate = (year: number, month: number) => {
    global.Date = class extends Date {
      constructor() {
        super();
        return new originalDate(year, month, 15);
      }
      
      static now() {
        return new originalDate(year, month, 15).getTime();
      }
    } as unknown as typeof Date;
  };

  describe('isPastSemesterById', () => {
    it('should return true for past semesters based on section ID', () => {
      // Mock current date: September 2026 (Sophomore Fall for Class of 2029)
      mockDate(2026, 8); // September
      
      // Section IDs 0-2 are Freshman year (past)
      expect(isPastSemesterById(0, 2029)).toBe(true); // Freshman Fall
      expect(isPastSemesterById(1, 2029)).toBe(true); // Freshman IAP
      expect(isPastSemesterById(2, 2029)).toBe(true); // Freshman Spring
      
      // Section ID 3 is Sophomore Fall (current - also considered past)
      expect(isPastSemesterById(3, 2029)).toBe(true);
      
      // Future semesters
      expect(isPastSemesterById(4, 2029)).toBe(false); // Sophomore IAP
      expect(isPastSemesterById(11, 2029)).toBe(false); // Senior Spring
    });

    it('should return false for special semesters', () => {
      mockDate(2026, 8);
      
      expect(isPastSemesterById(-1, 2029)).toBe(false); // ASE
      expect(isPastSemesterById(-2, 2029)).toBe(false); // Must Take
    });

    it('should return false for invalid section IDs', () => {
      mockDate(2026, 8);
      
      expect(isPastSemesterById(12, 2029)).toBe(false); // Out of range
      expect(isPastSemesterById(100, 2029)).toBe(false); // Way out of range
    });

    it('should handle all semester transitions correctly', () => {
      // Freshman IAP (section 1) - January 2026
      mockDate(2026, 0); // January
      expect(isPastSemesterById(0, 2029)).toBe(true); // Freshman Fall is past
      expect(isPastSemesterById(1, 2029)).toBe(true); // Freshman IAP is current (also considered past)
      
      // Freshman Spring (section 2) - February 2026
      mockDate(2026, 1); // February
      expect(isPastSemesterById(0, 2029)).toBe(true); // Freshman Fall is past
      expect(isPastSemesterById(1, 2029)).toBe(true); // Freshman IAP is past
      expect(isPastSemesterById(2, 2029)).toBe(true); // Freshman Spring is current (also considered past)
    });
  });

  describe('graduationYearToPlanningYear', () => {
    it('should convert Class of 2029 to 2025-2026 planning year', () => {
      expect(graduationYearToPlanningYear('2029')).toBe('2025-2026');
    });

    it('should convert Class of 2028 to 2024-2025 planning year', () => {
      expect(graduationYearToPlanningYear('2028')).toBe('2024-2025');
    });

    it('should convert Class of 2027 to 2023-2024 planning year', () => {
      expect(graduationYearToPlanningYear('2027')).toBe('2023-2024');
    });

    it('should convert Class of 2026 to 2022-2023 planning year', () => {
      expect(graduationYearToPlanningYear('2026')).toBe('2022-2023');
    });
  });
});
