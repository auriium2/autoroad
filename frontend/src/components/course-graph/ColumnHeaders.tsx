import { useState, useEffect } from "react";
import { ExternalLink } from "lucide-react";
import { useQueries } from "@tanstack/react-query";
import type { Section } from "@/stores/roadStore";
import { useGraphStore } from "@/stores/roadStore";
import { useOptimizationStore } from "@/stores/optimizationStore";
import { isPastSemesterById, sectionIdToTargetSemester } from "@/lib/semesterUtils";
import { generateHydrantUrl } from "@/lib/hydrant";
import { COLUMN_WIDTH } from "@/lib/graphConstants";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { HoverCard, HoverCardContent, HoverCardTrigger } from "@/components/ui/hover-card";
import { MiniSchedulePreview } from "./MiniSchedulePreview";
import { fireroadApi } from "@/services/fireroad";
import { queryKeys } from "@/lib/queryKeys";

interface ColumnHeadersProps {
  sections: Section[];
  viewport: { x: number; y: number; zoom: number };
  viewMode?: string;
}

export function ColumnHeaders({ sections, viewport, viewMode = "default" }: ColumnHeadersProps) {
  const transform = `translate(${viewport.x}px, 0) scale(${viewport.zoom})`;
  const isNerdMode = viewMode === "nerd";

  // Controlled state for tutorial to open the semester header hover card
  const [tutorialHoverOpen, setTutorialHoverOpen] = useState(false);

  // Expose function for tutorial to trigger hover card
  useEffect(() => {
    (window as unknown as { openSemesterHoverCard?: (open: boolean) => void }).openSemesterHoverCard = setTutorialHoverOpen;
    return () => {
      delete (window as unknown as { openSemesterHoverCard?: (open: boolean) => void }).openSemesterHoverCard;
    };
  }, []);

  const lockPastSemesters = useOptimizationStore((state) => state.lockPastSemesters);
  const selectedYear = useOptimizationStore((state) => state.selectedYear);
  const graduationYear = selectedYear ? parseInt(selectedYear) : 0;

  const markers = useGraphStore((state) => state.markers);
  const optimizerNodes = useGraphStore((state) => state.optimizerNodes);

  const getCoursesForSection = (sectionId: number): string[] => {
    const courseIds = new Set<string>();

    markers
      .filter((m) => m.section === sectionId && m.status !== "banish")
      .forEach((m) => courseIds.add(m.courseId));

    optimizerNodes
      .filter((n) => n.section === sectionId)
      .forEach((n) => courseIds.add(n.courseId));

    return Array.from(courseIds);
  };

  const handleOpenInHydrant = (sectionId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!graduationYear) return;

    const semester = sectionIdToTargetSemester(sectionId, graduationYear);
    if (!semester) return;

    const courses = getCoursesForSection(sectionId);
    const url = generateHydrantUrl(courses, semester);

    window.open(url, "_blank", "noopener,noreferrer");
  };

  // Get all unique course IDs across all sections for batch fetching
  const allCourseIds = (() => {
    const ids = new Set<string>();
    sections.forEach((section) => {
      getCoursesForSection(section.id).forEach((id) => ids.add(id));
    });
    return Array.from(ids);
  })();

  // Batch fetch course details for stats calculation
  const courseQueries = useQueries({
    queries: allCourseIds.map((courseId) => ({
      queryKey: queryKeys.courses.details(courseId),
      queryFn: () => fireroadApi.getCourseDetails(courseId),
      staleTime: 24 * 60 * 60 * 1000,
      enabled: isNerdMode,
    })),
  });

  // Build a map of courseId -> course data
  const courseDataMap = (() => {
    const map = new Map<string, { units: number; hours: number; rating: number | null }>();
    allCourseIds.forEach((courseId, idx) => {
      const query = courseQueries[idx];
      if (query?.data) {
        const inClass = query.data.in_class_hours ?? 0;
        const outClass = query.data.out_of_class_hours ?? 0;
        map.set(courseId, {
          units: query.data.total_units ?? 0,
          hours: inClass + outClass,
          rating: query.data.rating ?? null,
        });
      }
    });
    return map;
  })();

  // Calculate stats for a section
  const getSectionStats = (sectionId: number) => {
    const courses = getCoursesForSection(sectionId);
    let totalUnits = 0;
    let totalHours = 0;
    let ratingSum = 0;
    let ratingCount = 0;

    for (const courseId of courses) {
      const data = courseDataMap.get(courseId);
      if (data) {
        totalUnits += data.units;
        totalHours += data.hours;
        if (data.rating != null) {
          ratingSum += data.rating;
          ratingCount++;
        }
      }
    }

    return {
      units: totalUnits,
      hours: Math.round(totalHours),
      avgRating: ratingCount > 0 ? (ratingSum / ratingCount).toFixed(1) : null,
      courseCount: courses.length,
    };
  };

  return (
    <>
      {/* Column backgrounds */}
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          transform,
          transformOrigin: 'top left',
          pointerEvents: 'none',
          zIndex: 0,
          width: sections.length * COLUMN_WIDTH,
          height: '100%',
        }}
      >
        {sections.map((section, index) => {
          // Must Take overlay
          if (section.id === -2) {
            return (
              <div
                key={`bg-${section.id}`}
                style={{
                  position: 'absolute',
                  left: index * COLUMN_WIDTH,
                  top: -2000,
                  width: COLUMN_WIDTH,
                  height: 10000,
                  background: 'repeating-linear-gradient(45deg, rgba(168, 85, 247, 0.08), rgba(168, 85, 247, 0.08) 20px, rgba(168, 85, 247, 0.12) 20px, rgba(168, 85, 247, 0.12) 40px), rgba(255, 255, 255, 0.03)',
                }}
              />
            );
          }
          // ASE overlay
          if (section.id === -1) {
            return (
              <div key={`bg-${section.id}`}
                style={{
                  position: 'absolute',
                  left: index * COLUMN_WIDTH,
                  top: -2000,
                  width: COLUMN_WIDTH,
                  height: 10000,
                  backgroundColor: 'rgba(255, 255, 255, 0.03)',
                }}
              />
            );
          }

          // Past semesters overlay
          if (lockPastSemesters && graduationYear && section.id >= 0 && isPastSemesterById(section.id, graduationYear)) {
            return (
              <div
                key={`bg-${section.id}`}
                style={{
                  position: 'absolute',
                  left: index * COLUMN_WIDTH,
                  top: -2000,
                  width: COLUMN_WIDTH,
                  height: 10000,
                  backgroundColor: 'rgba(239, 68, 68, 0.12)',
                }}
              />
            );
          }

          return null;
        })}
      </div>

      {/* Column divider lines */}
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          transform,
          transformOrigin: 'top left',
          pointerEvents: 'none',
          zIndex: 1,
          width: sections.length * COLUMN_WIDTH,
          height: '100%',
        }}
      >
        {sections.map((section, index) => (
          <div
            key={`divider-${section.id}`}
            style={{
              position: 'absolute',
              left: index * COLUMN_WIDTH,
              top: -2000,
              width: 1,
              height: 10000,
              backgroundColor: 'rgba(255, 255, 255, 0.1)',
            }}
          />
        ))}
        {/* Right edge of last column */}
        <div
          style={{
            position: 'absolute',
            left: sections.length * COLUMN_WIDTH,
            top: -2000,
            width: 1,
            height: 10000,
            backgroundColor: 'rgba(255, 255, 255, 0.1)',
          }}
        />
      </div>

      {/* Column headers */}
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          transform,
          transformOrigin: 'top left',
          display: 'flex',
          gap: 0,
          pointerEvents: 'none',
          zIndex: 10,
        }}
      >
        {sections.map((section) => {
          const isRegularSemester = section.id >= 0 && section.id <= 11;
          const hasGraduationYear = graduationYear > 0;
          const courses = isRegularSemester ? getCoursesForSection(section.id) : [];
          const canInteract = isRegularSemester && hasGraduationYear;

          const stats = isNerdMode && isRegularSemester ? getSectionStats(section.id) : null;

          return (
            <div
              key={section.id}
              className="flex flex-col items-center px-2 py-2"
              style={{
                width: `${COLUMN_WIDTH}px`,
                pointerEvents: canInteract ? 'auto' : 'none',
              }}
            >
              {canInteract ? (
                <HoverCard
                  openDelay={200}
                  closeDelay={100}
                  open={section.id === 0 && tutorialHoverOpen ? true : undefined}
                >
                  <HoverCardTrigger asChild>
                    <span
                      className="glass-card px-3 py-1 rounded text-xs font-semibold text-gray-300 shadow-sm whitespace-nowrap flex items-center gap-1.5 cursor-default hover:bg-white/5 transition-colors"
                      data-tutorial={section.id === -2 ? 'must-take-column' : section.id === -1 ? 'ase-column' : section.id === 0 ? 'semester-header' : undefined}
                    >
                      {section.title}
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <button
                            onClick={(e) => handleOpenInHydrant(section.id, e)}
                            className="text-gray-500 hover:text-gray-200 transition-colors"
                            aria-label="Open in Hydrant"
                          >
                            <ExternalLink className="h-3 w-3" />
                          </button>
                        </TooltipTrigger>
                        <TooltipContent side="bottom">
                          {courses.length > 0
                            ? `Open ${courses.length} course${courses.length > 1 ? "s" : ""} in Hydrant`
                            : "Open semester in Hydrant"}
                        </TooltipContent>
                      </Tooltip>
                    </span>
                  </HoverCardTrigger>
                  <HoverCardContent side="bottom" align="center" className="w-auto p-0" data-tutorial={section.id === 0 ? 'schedule-hover-card' : undefined}>
                    <MiniSchedulePreview courseIds={courses} sectionId={section.id} graduationYear={graduationYear} />
                  </HoverCardContent>
                </HoverCard>
              ) : (
                <span
                  className="glass-card px-3 py-1 rounded text-xs font-semibold text-gray-300 shadow-sm whitespace-nowrap flex items-center gap-1.5"
                  data-tutorial={section.id === -2 ? 'must-take-column' : section.id === -1 ? 'ase-column' : section.id === 0 ? 'semester-header' : undefined}
                >
                  {section.title}
                </span>
              )}
              {stats && stats.courseCount > 0 && (
                <div className="mt-1 text-[10px] text-gray-500 whitespace-nowrap">
                  {stats.units}u · {stats.hours}h{stats.avgRating && ` · ★${stats.avgRating}`}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </>
  );
}
