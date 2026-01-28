import { useQuery } from "@tanstack/react-query";
import { fireroadApi } from "@/services/fireroad";
import { queryKeys } from "@/lib/queryKeys";
import type { Marker } from "@/stores/roadStore";

const VIRTUAL_COURSE_IDS = new Set(["HASS-A", "HASS-H", "HASS-S", "HASS-E"]);
const FRESHMAN_FALL_UNIT_LIMIT = 54;

interface BlockingErrorsResult {
  hasWrongSemester: boolean;
  hasDuplicateCourses: boolean;
  duplicateCourseIds: Set<string>;
  hasFreshmanFallOverload: boolean;
  freshmanFallUnits: number;
  hasBlockingErrors: boolean;
  isLoading: boolean;
}

export function useBlockingErrors(markers: Marker[]): BlockingErrorsResult {
  // duplicate classes
  const courseCounts = new Map<string, number>();
  const duplicateCourseIds = new Set<string>();

  for (const marker of markers) {
    if (marker.status === "banish") continue;
    if (VIRTUAL_COURSE_IDS.has(marker.courseId)) continue;
    if (marker.section === -2) continue; // don't include must take

    const count = (courseCounts.get(marker.courseId) || 0) + 1;
    courseCounts.set(marker.courseId, count);

    if (count > 1) {
      duplicateCourseIds.add(marker.courseId);
    }
  }

  const hasDuplicateCourses = duplicateCourseIds.size > 0;

  // Collect all unique course IDs that need details fetched
  const courseIdSet = new Set<string>();
  for (const marker of markers) {
    if (marker.status === "banish") continue;
    if (VIRTUAL_COURSE_IDS.has(marker.courseId)) continue;
    courseIdSet.add(marker.courseId);
  }
  const courseIdsToFetch = Array.from(courseIdSet).sort();

  // Batch fetch all course details in one request
  const courseIdsKey = courseIdsToFetch.join(",");
  const { data: courseDetailsMap, isLoading } = useQuery({
    queryKey: queryKeys.courses.batch(courseIdsKey),
    queryFn: () => fireroadApi.getCourseDetailsBatch(courseIdsToFetch),
    staleTime: 24 * 60 * 60 * 1000,
    enabled: courseIdsToFetch.length > 0,
  });

  // Filter to only markers that need semester checking
  const markersToCheck = markers.filter(
    (m) =>
      !VIRTUAL_COURSE_IDS.has(m.courseId) &&
      m.section >= 0 &&
      m.status !== "banish" &&
      m.status !== "override"
  );

  // Get all non-banished markers in Freshman Fall (section 0) for unit limit check
  const freshmanFallMarkers = markers.filter(
    (m) =>
      !VIRTUAL_COURSE_IDS.has(m.courseId) &&
      m.section === 0 &&
      m.status !== "banish"
  );

  // Check for wrong semester placements
  let hasWrongSemester = false;
  if (!isLoading && courseDetailsMap) {
    for (const marker of markersToCheck) {
      const courseDetails = courseDetailsMap[marker.courseId];
      if (!courseDetails) continue;

      const semesterType = marker.section % 3; // 0=Fall, 1=IAP, 2=Spring

      const isWrong =
        (semesterType === 0 && !courseDetails.offered_fall) ||
        (semesterType === 1 && !courseDetails.offered_IAP) ||
        (semesterType === 2 && !courseDetails.offered_spring);

      if (isWrong) {
        hasWrongSemester = true;
        break;
      }
    }
  }

  // Calculate Freshman Fall total units
  let freshmanFallUnits = 0;
  if (!isLoading && courseDetailsMap) {
    for (const marker of freshmanFallMarkers) {
      const courseDetails = courseDetailsMap[marker.courseId];
      if (courseDetails?.total_units) {
        freshmanFallUnits += courseDetails.total_units;
      }
    }
  }
  const hasFreshmanFallOverload = freshmanFallUnits > FRESHMAN_FALL_UNIT_LIMIT;

  return {
    hasWrongSemester,
    hasDuplicateCourses,
    duplicateCourseIds,
    hasFreshmanFallOverload,
    freshmanFallUnits,
    hasBlockingErrors: hasWrongSemester || hasDuplicateCourses || hasFreshmanFallOverload,
    isLoading,
  };
}
