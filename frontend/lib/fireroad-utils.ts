/**
 * Shared Fireroad utilities and types
 */

export interface FireroadCourse {
  subject_id: string;
  title: string;
  total_units: number;
  description?: string;
  prerequisites?: string;
  corequisites?: string;
  is_variable_units?: boolean;
  is_historical?: boolean;
  offered_fall?: boolean;
  offered_spring?: boolean;
  offered_IAP?: boolean;
  offered_summer?: boolean;
  public?: boolean;
  level?: string;
  lecture_units?: number;
  lab_units?: number;
  preparation_units?: number;
  design_units?: number;
  in_class_hours?: number;
  out_of_class_hours?: number;
  joint_subjects?: string[];
  equivalent_subjects?: string[];
  meets_with_subjects?: string[];
  children?: string[];
  instructors?: string[];
  rating?: number;
  enrollment_number?: number;
  imdb_rating?: number | null;
  gir_attribute?: string;
  hass_attribute?: string;
  communication_requirement?: string;
  schedule?: string;
  has_final?: boolean;
  pdf_option?: boolean;
  is_half_class?: boolean;
  url?: string;
  source_semester?: string;
}

/**
 * Calculate IMDB type weighted rating
 *
 * @param rating - Course rating (1-7 scale)
 * @param enrollment - Number of students enrolled
 * @returns Weighted rating, or null if data is missing
 */
export function calculateIMDBRating(
  rating: number | undefined,
  enrollment: number | undefined
): number | null {
  if (rating === undefined || rating === null || enrollment === undefined || enrollment === null) {
    return null;
  }

  // IMDB-style weighted rating formula: WR = (v/(v+m)) * R + (m/(v+m)) * C
  // where:
  // v = number of votes for the course (enrollment)
  // m = minimum votes required (we use 30 as threshold)
  // R = rating for the course
  // C = mean rating across all courses (assume 5.0)

  const m = 30;
  const C = 5.0;

  const weightedRating = (enrollment / (enrollment + m)) * rating + (m / (enrollment + m)) * C;

  return Math.round(weightedRating * 10) / 10; // Round to 1 decimal
}

/**
 * Enrich a course with computed fields (like IMDB rating)
 */
export function enrichCourse(course: FireroadCourse): FireroadCourse {
  const imdbRating = calculateIMDBRating(course.rating, course.enrollment_number);

  return {
    ...course,
    imdb_rating: imdbRating,
  };
}
