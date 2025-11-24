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
 * Determines if a semester has already passed based on the current date and graduation year.
 * Legacy string-based version - prefer isPastSemesterById for better performance.
 */
export function isPastSemester(
  semesterLabel: string,
  graduationYear: number
): boolean {
  const currentDate = new Date();
  const currentYear = currentDate.getFullYear();
  const currentMonth = currentDate.getMonth(); // 0-11
  
  // Parse semester label (e.g., "Freshman Fall", "Sophomore IAP", "Junior Spring")
  const yearMap: Record<string, number> = {
    'freshman': 0,
    'sophomore': 1,
    'junior': 2,
    'senior': 3,
  };
  
  const parts = semesterLabel.toLowerCase().split(' ');
  if (parts.length < 2) return false;
  
  const yearLevel = yearMap[parts[0]];
  if (yearLevel === undefined) return false;
  
  const term = parts[1]; // 'fall', 'iap', 'spring'

  const academicYear = graduationYear - 4 + yearLevel; //calculate true calendar year
  
  // Determine the actual calendar year and month for this semester
  let semesterYear: number;
  let semesterMonth: number;
  
  if (term === 'fall') {
    semesterYear = academicYear;
    semesterMonth = 8; // September
  } else if (term === 'iap') {
    semesterYear = academicYear + 1;
    semesterMonth = 0; // January
  } else if (term === 'spring') {
    semesterYear = academicYear + 1;
    semesterMonth = 1; // February
  } else {
    return false;
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
 * Gets all past semesters for a given graduation year
 */
export function getPastSemesters(graduationYear: number): string[] {
  const semesters: string[] = [];
  const years = ['Freshman', 'Sophomore', 'Junior', 'Senior'];
  const terms = ['Fall', 'IAP', 'Spring'];
  
  for (const year of years) {
    for (const term of terms) {
      const label = `${year} ${term}`;
      if (isPastSemester(label, graduationYear)) {
        semesters.push(label);
      }
    }
  }
  
  return semesters;
}

/**
 * Converts a graduation year to a planning year string (e.g., "2024" -> "2020-2021")
 */
export function graduationYearToPlanningYear(graduationYear: string): string {
  const gradYear = parseInt(graduationYear, 10);
  const freshmanFallYear = gradYear - 4;
  return `${freshmanFallYear}-${freshmanFallYear + 1}`;
}
