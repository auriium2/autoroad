/**
 * Determines if a semester has already passed based on section ID and graduation year.
 * Works with section IDs (0-11) instead of parsing semester labels.
 * 
 * @param sectionId - Section ID (0-11 for regular semesters)
 * @param graduationYear - Year of graduation
 * @returns true if the semester has passed, false otherwise
 */
export function isPastSemesterById(
  sectionId: number,
  graduationYear: number
): boolean {
  // Special semesters are never "past" (ASE=-1, Must Take=-2)
  if (sectionId < 0) return false;
  
  // Invalid section IDs
  if (sectionId > 11) return false;
  
  const currentDate = new Date();
  const currentYear = currentDate.getFullYear();
  const currentMonth = currentDate.getMonth(); // 0-11
  
  // Calculate which year this section belongs to (0-3 for Freshman-Senior)
  const yearLevel = Math.floor(sectionId / 3);
  
  // Calculate which term within the year (0=Fall, 1=IAP, 2=Spring)
  const termInYear = sectionId % 3;
  
  const academicYear = graduationYear - 4 + yearLevel;
  
  // Determine the actual calendar year and month for this semester
  let semesterYear: number;
  let semesterMonth: number;
  
  if (termInYear === 0) { // Fall
    semesterYear = academicYear;
    semesterMonth = 8; // September (0-indexed)
  } else if (termInYear === 1) { // IAP
    semesterYear = academicYear + 1;
    semesterMonth = 0; // January
  } else { // Spring
    semesterYear = academicYear + 1;
    semesterMonth = 1; // February
  }
  
  // Compare with current date
  // We consider a semester "past" if it has already started (including current semester)
  if (semesterYear < currentYear) {
    return true;
  } else if (semesterYear === currentYear) {
    return semesterMonth <= currentMonth;
  }
  
  return false;
}

/**
 * Converts a graduation year to a planning year string (e.g., "2024" -> "2020-2021")
 */
export function graduationYearToPlanningYear(graduationYear: string): string {
  const gradYear = parseInt(graduationYear, 10);
  const freshmanFallYear = gradYear - 4;
  return `${freshmanFallYear}-${freshmanFallYear + 1}`;
}

export function getCurrentAcademicYearStart(): number {
  const currentDate = new Date();
  const currentYear = currentDate.getFullYear();
  const currentMonth = currentDate.getMonth(); // 0-11
  
  // If September (month 8) or later, we're in currentYear-currentYear+1 academic year
  // Otherwise, we're in currentYear-1 to currentYear academic year
  return currentMonth >= 8 ? currentYear : currentYear - 1;
}

export function getGraduationYearOptions(): Array<{ value: string; label: string }> {
  const academicYearStart = getCurrentAcademicYearStart();
  const freshmanGradYear = academicYearStart + 4;
  
  return [
    { value: String(freshmanGradYear), label: `Class of ${freshmanGradYear}` },
    { value: String(freshmanGradYear - 1), label: `Class of ${freshmanGradYear - 1}` },
    { value: String(freshmanGradYear - 2), label: `Class of ${freshmanGradYear - 2}` },
    { value: String(freshmanGradYear - 3), label: `Class of ${freshmanGradYear - 3}` },
  ];
}

/**
 * Converts a section ID (0-11) to the target Hydrant semester code.
 * This is the actual semester the section represents (e.g., "s27" for Spring 2027).
 * 
 * Section IDs: 0=Freshman Fall, 1=Freshman IAP, 2=Freshman Spring, etc.
 * Hydrant codes: f25, i26, s26, etc.
 */
export function sectionIdToTargetSemester(
  sectionId: number,
  graduationYear: number
): string | null {
  if (sectionId < 0 || sectionId > 11) return null;

  const termInYear = sectionId % 3; // 0=Fall, 1=IAP, 2=Spring
  const yearLevel = Math.floor(sectionId / 3); // 0=Freshman, 1=Sophomore, etc.
  
  const academicYear = graduationYear - 4 + yearLevel;
  
  let semesterYear: number;
  let termCode: string;
  
  if (termInYear === 0) { // Fall
    semesterYear = academicYear;
    termCode = "f";
  } else if (termInYear === 1) { // IAP
    semesterYear = academicYear + 1;
    termCode = "i";
  } else { // Spring
    semesterYear = academicYear + 1;
    termCode = "s";
  }
  
  return `${termCode}${semesterYear % 100}`;
}
