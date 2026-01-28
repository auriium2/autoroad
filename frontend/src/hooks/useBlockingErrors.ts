import { useMemo } from "react";
import { useQueries } from "@tanstack/react-query";
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
  const { hasDuplicateCourses, duplicateCourseIds } = useMemo(() => {
    const courseCounts = new Map<string, number>();
    const duplicates = new Set<string>();

    for (const marker of markers) {
      if (marker.status === "banish") continue;
      if (VIRTUAL_COURSE_IDS.has(marker.courseId)) continue;

      const count = (courseCounts.get(marker.courseId) || 0) + 1;
      courseCounts.set(marker.courseId, count);

      if (count > 1) {
        duplicates.add(marker.courseId);
      }
    }

    return {
      hasDuplicateCourses: duplicates.size > 0,
      duplicateCourseIds: duplicates,
    };
  }, [markers]);

  // Filter to only markers that need semester checking
  // - Not virtual markers (HASS-A, etc.)
  // - Not in special semesters (Must Take = -2, ASE = -1)
  // - Not banished (banished markers don't need to be offered)
  const markersToCheck = markers.filter(
    (m) =>
      !VIRTUAL_COURSE_IDS.has(m.courseId) &&
      m.section >= 0 &&
      m.status !== "banish" &&
      m.status !== "override"
  );

  // Get all non-banished markers in Freshman Fall (section 0) for unit limit check
  const freshmanFallMarkers = useMemo(() => 
    markers.filter(
      (m) =>
        !VIRTUAL_COURSE_IDS.has(m.courseId) &&
        m.section === 0 &&
        m.status !== "banish"
    ),
    [markers]
  );

  // Fetch course details for markers that need semester checking
  const courseQueries = useQueries({
    queries: markersToCheck.map((marker) => ({
      queryKey: queryKeys.courses.details(marker.courseId),
      queryFn: () => fireroadApi.getCourseDetails(marker.courseId),
      staleTime: 24 * 60 * 60 * 1000,
    })),
  });

  // Fetch course details for Freshman Fall markers (for unit check)
  const freshmanFallQueries = useQueries({
    queries: freshmanFallMarkers.map((marker) => ({
      queryKey: queryKeys.courses.details(marker.courseId),
      queryFn: () => fireroadApi.getCourseDetails(marker.courseId),
      staleTime: 24 * 60 * 60 * 1000,
    })),
  });

  const isLoading = courseQueries.some((q) => q.isLoading) || freshmanFallQueries.some((q) => q.isLoading);

  // Check for wrong semester placements
  let hasWrongSemester = false;

  if (!isLoading) {
    for (let i = 0; i < markersToCheck.length; i++) {
      const marker = markersToCheck[i];
      const courseDetails = courseQueries[i]?.data;

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
  if (!isLoading) {
    for (let i = 0; i < freshmanFallMarkers.length; i++) {
      const courseDetails = freshmanFallQueries[i]?.data;
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
