import { describe, it, expect } from 'vitest';
import { graduationYearToPlanningYear } from '../yearUtils';

describe('yearUtils', () => {
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
