import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

function getGraduationYearOptions() {
  const currentDate = new Date();
  const currentYear = currentDate.getFullYear();
  const currentMonth = currentDate.getMonth(); // 0-11
  
  const academicYearStart = currentMonth >= 8 ? currentYear : currentYear - 1;
  const freshmanGradYear = academicYearStart + 4;
  
  return [
    { value: String(freshmanGradYear), label: `Class of ${freshmanGradYear}` },
    { value: String(freshmanGradYear - 1), label: `Class of ${freshmanGradYear - 1}` },
    { value: String(freshmanGradYear - 2), label: `Class of ${freshmanGradYear - 2}` },
    { value: String(freshmanGradYear - 3), label: `Class of ${freshmanGradYear - 3}` },
  ];
}

describe('getGraduationYearOptions', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('should show correct years for November 2025 (2025-2026 academic year)', () => {
    vi.setSystemTime(new Date('2025-11-17'));
    
    const options = getGraduationYearOptions();
    
    // November 2025 = 2025-2026 academic year
    // Freshmen: Class of 2029
    // Sophomores: Class of 2028
    // Juniors: Class of 2027
    // Seniors: Class of 2026
    expect(options).toEqual([
      { value: '2029', label: 'Class of 2029' },
      { value: '2028', label: 'Class of 2028' },
      { value: '2027', label: 'Class of 2027' },
      { value: '2026', label: 'Class of 2026' },
    ]);
  });

  it('should show correct years for August 2025 (2024-2025 academic year)', () => {
    vi.setSystemTime(new Date('2025-08-15'));
    
    const options = getGraduationYearOptions();
    
    // August 2025 = still in 2024-2025 academic year
    // Freshmen: Class of 2028
    // Sophomores: Class of 2027
    // Juniors: Class of 2026
    // Seniors: Class of 2025
    expect(options).toEqual([
      { value: '2028', label: 'Class of 2028' },
      { value: '2027', label: 'Class of 2027' },
      { value: '2026', label: 'Class of 2026' },
      { value: '2025', label: 'Class of 2025' },
    ]);
  });

  it('should show correct years for September 2025 (2025-2026 academic year starts)', () => {
    vi.setSystemTime(new Date(2025, 8, 1)); // Month is 0-indexed, so 8 = September
    
    const options = getGraduationYearOptions();
    
    // September 2025 = new 2025-2026 academic year
    expect(options).toEqual([
      { value: '2029', label: 'Class of 2029' },
      { value: '2028', label: 'Class of 2028' },
      { value: '2027', label: 'Class of 2027' },
      { value: '2026', label: 'Class of 2026' },
    ]);
  });
});
