import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { isPastSemester, isPastSemesterById, getPastSemesters } from '../semesterUtils';

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
    } as any;
  };

  describe('isPastSemester', () => {
    it('should return true for Freshman Fall when current date is Sophomore Fall', () => {
      // Mock current date: September 2026 (Sophomore Fall for Class of 2029)
      mockDate(2026, 8); // September (month 8)
      
      expect(isPastSemester('Freshman Fall', 2029)).toBe(true);
      expect(isPastSemester('Freshman IAP', 2029)).toBe(true);
      expect(isPastSemester('Freshman Spring', 2029)).toBe(true);
    });

    it('should return true for current semester (already started)', () => {
      // Mock current date: September 2025 (Freshman Fall for Class of 2029)
      mockDate(2025, 8); // September
      
      // Current semester is considered "past" since it has already started
      expect(isPastSemester('Freshman Fall', 2029)).toBe(true);
    });

    it('should return false for future semesters', () => {
      // Mock current date: September 2025 (Freshman Fall for Class of 2029)
      mockDate(2025, 8); // September
      
      expect(isPastSemester('Freshman IAP', 2029)).toBe(false);
      expect(isPastSemester('Freshman Spring', 2029)).toBe(false);
      expect(isPastSemester('Sophomore Fall', 2029)).toBe(false);
      expect(isPastSemester('Senior Spring', 2029)).toBe(false);
    });

    it('should handle IAP correctly', () => {
      // Mock current date: January 2026 (Freshman IAP for Class of 2029)
      mockDate(2026, 0); // January
      
      expect(isPastSemester('Freshman Fall', 2029)).toBe(true);
      expect(isPastSemester('Freshman IAP', 2029)).toBe(true); // Current semester is past
      expect(isPastSemester('Freshman Spring', 2029)).toBe(false);
    });

    it('should handle Spring correctly', () => {
      // Mock current date: February 2026 (Freshman Spring starts in February for Class of 2029)
      mockDate(2026, 1); // February
      
      expect(isPastSemester('Freshman Fall', 2029)).toBe(true);
      expect(isPastSemester('Freshman IAP', 2029)).toBe(true);
      expect(isPastSemester('Freshman Spring', 2029)).toBe(true); // Current semester is past
      expect(isPastSemester('Sophomore Fall', 2029)).toBe(false);
    });

    it('should handle all four years correctly', () => {
      // Mock current date: September 2027 (Junior Fall for Class of 2029)
      mockDate(2027, 8); // September
      
      // All of freshman and sophomore years should be past
      expect(isPastSemester('Freshman Fall', 2029)).toBe(true);
      expect(isPastSemester('Freshman IAP', 2029)).toBe(true);
      expect(isPastSemester('Freshman Spring', 2029)).toBe(true);
      expect(isPastSemester('Sophomore Fall', 2029)).toBe(true);
      expect(isPastSemester('Sophomore IAP', 2029)).toBe(true);
      expect(isPastSemester('Sophomore Spring', 2029)).toBe(true);
      
      // Current semester is past, future semesters are not
      expect(isPastSemester('Junior Fall', 2029)).toBe(true); // Current semester
      expect(isPastSemester('Junior IAP', 2029)).toBe(false);
      expect(isPastSemester('Junior Spring', 2029)).toBe(false);
      expect(isPastSemester('Senior Fall', 2029)).toBe(false);
    });

    it('should handle senior year correctly', () => {
      // Mock current date: February 2029 (Senior Spring for Class of 2029)
      mockDate(2029, 1); // February
      
      expect(isPastSemester('Senior Fall', 2029)).toBe(true);
      expect(isPastSemester('Senior IAP', 2029)).toBe(true);
      expect(isPastSemester('Senior Spring', 2029)).toBe(true); // Current semester is past
    });

    it('should return false for invalid semester labels', () => {
      mockDate(2026, 8);
      
      expect(isPastSemester('Invalid Semester', 2029)).toBe(false);
      expect(isPastSemester('Fall', 2029)).toBe(false);
      expect(isPastSemester('Freshman', 2029)).toBe(false);
      expect(isPastSemester('', 2029)).toBe(false);
    });

    it('should handle edge case at year boundary', () => {
      // Mock current date: August 2026 (just before Sophomore Fall starts)
      mockDate(2026, 7); // August
      
      // Freshman year is over
      expect(isPastSemester('Freshman Spring', 2029)).toBe(true);
      
      // Sophomore Fall hasn't started yet (starts in September)
      expect(isPastSemester('Sophomore Fall', 2029)).toBe(false);
    });

    it('should handle summer months (May, June, July, August)', () => {
      // May 2026 - still in Freshman Spring
      mockDate(2026, 4); // May (month 4 in 0-indexed)
      expect(isPastSemester('Freshman Fall', 2029)).toBe(true);
      expect(isPastSemester('Freshman IAP', 2029)).toBe(true);
      expect(isPastSemester('Freshman Spring', 2029)).toBe(true); // Spring started in Feb (month 1)
      expect(isPastSemester('Sophomore Fall', 2029)).toBe(false);

      // June 2026 - still in Freshman Spring
      mockDate(2026, 5); // June (month 5)
      expect(isPastSemester('Freshman Spring', 2029)).toBe(true);
      expect(isPastSemester('Sophomore Fall', 2029)).toBe(false);

      // July 2026 - still in Freshman Spring
      mockDate(2026, 6); // July (month 6)
      expect(isPastSemester('Freshman Spring', 2029)).toBe(true);
      expect(isPastSemester('Sophomore Fall', 2029)).toBe(false);

      // August 2026 - still in Freshman Spring (summer break before Sophomore Fall)
      mockDate(2026, 7); // August (month 7)
      expect(isPastSemester('Freshman Spring', 2029)).toBe(true);
      expect(isPastSemester('Sophomore Fall', 2029)).toBe(false);
    });
  });

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

    it('should match isPastSemester results', () => {
      // Ensure both functions return the same results
      mockDate(2027, 8); // Junior Fall
      
      const semesters = [
        { id: 0, label: 'Freshman Fall' },
        { id: 1, label: 'Freshman IAP' },
        { id: 2, label: 'Freshman Spring' },
        { id: 3, label: 'Sophomore Fall' },
        { id: 4, label: 'Sophomore IAP' },
        { id: 5, label: 'Sophomore Spring' },
        { id: 6, label: 'Junior Fall' },
        { id: 7, label: 'Junior IAP' },
        { id: 8, label: 'Junior Spring' },
        { id: 9, label: 'Senior Fall' },
        { id: 10, label: 'Senior IAP' },
        { id: 11, label: 'Senior Spring' },
      ];
      
      for (const sem of semesters) {
        const byId = isPastSemesterById(sem.id, 2029);
        const byLabel = isPastSemester(sem.label, 2029);
        expect(byId).toBe(byLabel);
      }
    });
  });

  describe('getPastSemesters', () => {
    it('should return all past semesters for a given graduation year', () => {
      // Mock current date: September 2026 (Sophomore Fall for Class of 2029)
      mockDate(2026, 8);
      
      const pastSemesters = getPastSemesters(2029);
      
      // Should include all freshman year semesters and current semester
      expect(pastSemesters).toContain('Freshman Fall');
      expect(pastSemesters).toContain('Freshman IAP');
      expect(pastSemesters).toContain('Freshman Spring');
      expect(pastSemesters).toContain('Sophomore Fall'); // Current semester is past
      
      // Should not include future semesters
      expect(pastSemesters).not.toContain('Sophomore IAP');
      expect(pastSemesters).not.toContain('Senior Spring');
    });

    it('should return empty array when no semesters have passed', () => {
      // Mock current date: August 2025 (before Freshman Fall for Class of 2029)
      mockDate(2025, 7);
      
      const pastSemesters = getPastSemesters(2029);
      expect(pastSemesters).toEqual([]);
    });

    it('should return all semesters after graduation', () => {
      // Mock current date: September 2029 (after Class of 2029 graduates)
      mockDate(2029, 8);
      
      const pastSemesters = getPastSemesters(2029);
      
      // All 12 semesters should be past
      expect(pastSemesters.length).toBe(12);
      expect(pastSemesters).toContain('Freshman Fall');
      expect(pastSemesters).toContain('Senior Spring');
    });
  });
});
