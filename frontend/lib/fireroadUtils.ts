/**
 * Shared Fireroad utilities and types
 */

import type { FireroadCourse } from '@/types/models/fireroad';

export type { FireroadCourse };

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
 * Get terms offered as an array of strings
 */
export function getTermsOffered(course: FireroadCourse): string[] {
  const terms: string[] = [];
  if (course.offered_fall) terms.push('Fall');
  if (course.offered_spring) terms.push('Spring');
  if (course.offered_IAP) terms.push('IAP');
  if (course.offered_summer) terms.push('Summer');
  return terms;
}
