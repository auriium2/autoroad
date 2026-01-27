/**
 * Shared Fireroad utilities and types
 */

import type { FireroadCourse } from '@/types/models/fireroad';

export type { FireroadCourse };

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
