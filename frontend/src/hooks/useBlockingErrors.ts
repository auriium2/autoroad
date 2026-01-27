import { useQueries } from "@tanstack/react-query";
import { fireroadApi } from "@/services/fireroad";
import { queryKeys } from "@/lib/queryKeys";
import type { Marker } from "@/stores/roadStore";

const VIRTUAL_COURSE_IDS = new Set(["HASS-A", "HASS-H", "HASS-S", "HASS-E"]);

interface BlockingErrorsResult {
  hasWrongSemester: boolean;
  hasBlockingErrors: boolean;
  isLoading: boolean;
}

export function useBlockingErrors(markers: Marker[]): BlockingErrorsResult {
  // Filter to only markers that need semester checking
  // - Not virtual markers (HASS-A, etc.)
  // - Not in special semesters (Must Take = -2, ASE = -1)
  // - Not banished (banished markers don't need to be offered)
  const markersToCheck = markers.filter(
    (m) =>
      !VIRTUAL_COURSE_IDS.has(m.courseId) &&
      m.section >= 0 &&
      m.status !== "banish"
  );

  // Fetch course details for each marker
  const courseQueries = useQueries({
    queries: markersToCheck.map((marker) => ({
      queryKey: queryKeys.courses.details(marker.courseId),
      queryFn: () => fireroadApi.getCourseDetails(marker.courseId),
      staleTime: 24 * 60 * 60 * 1000,
    })),
  });

  const isLoading = courseQueries.some((q) => q.isLoading);

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

  return {
    hasWrongSemester,
    hasBlockingErrors: hasWrongSemester,
    isLoading,
  };
}
