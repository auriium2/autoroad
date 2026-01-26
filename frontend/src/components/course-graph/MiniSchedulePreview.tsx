import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { hydrantApi, type TimeBlock } from "@/services/hydrant";
import { queryKeys } from "@/lib/queryKeys";
import { isPastSemesterById } from "@/lib/semesterUtils";
import { useOptimizationStore } from "@/stores/optimizationStore";

interface MiniSchedulePreviewProps {
  courseIds: string[];
  sectionId: number;
  graduationYear: number;
}

const DAYS = ["M", "T", "W", "R", "F"] as const;
const START_HOUR = 8;
const END_HOUR = 22; // 10pm
const HOURS = END_HOUR - START_HOUR;
const VISIBLE_HEIGHT = 80; // Height of visible area in pixels

const COURSE_COLORS = [
  { bg: "bg-blue-500", hex: "#3b82f6" },
  { bg: "bg-green-500", hex: "#22c55e" },
  { bg: "bg-purple-500", hex: "#a855f7" },
  { bg: "bg-orange-500", hex: "#f97316" },
  { bg: "bg-pink-500", hex: "#ec4899" },
  { bg: "bg-cyan-500", hex: "#06b6d4" },
  { bg: "bg-yellow-500", hex: "#eab308" },
  { bg: "bg-red-400", hex: "#f87171" },
];

interface RenderBlock {
  course_id: string;
  type: string;
  start_hour: number;
  end_hour: number;
  isRequired: boolean; // from backend: true if only 1 section of this type
}

function getRenderBlocks(blocks: TimeBlock[], dayIndex: number): RenderBlock[] {
  const dayBlocks = blocks.filter((b) => b.day === dayIndex);
  if (dayBlocks.length === 0) return [];

  // Deduplicate exact duplicates first
  const seen = new Set<string>();
  const dedupedBlocks = dayBlocks.filter((b) => {
    const key = `${b.course_id}-${b.type}-${b.start_hour}-${b.end_hour}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });

  // For optional blocks (is_required=false), merge adjacent/overlapping times
  // For required blocks (is_required=true), keep as-is
  const requiredBlocks = dedupedBlocks.filter((b) => b.is_required);
  const optionalBlocks = dedupedBlocks.filter((b) => !b.is_required);

  const renderBlocks: RenderBlock[] = [];

  // Add required blocks directly
  for (const block of requiredBlocks) {
    renderBlocks.push({
      course_id: block.course_id,
      type: block.type,
      start_hour: block.start_hour,
      end_hour: block.end_hour,
      isRequired: true,
    });
  }

  // Group optional blocks by course_id + type to merge overlapping ranges
  const optionalGroups = new Map<string, TimeBlock[]>();
  for (const block of optionalBlocks) {
    const key = `${block.course_id}-${block.type}`;
    if (!optionalGroups.has(key)) optionalGroups.set(key, []);
    optionalGroups.get(key)!.push(block);
  }

  for (const [, groupBlocks] of optionalGroups) {
    // Merge adjacent/overlapping blocks into continuous ranges
    const sorted = [...groupBlocks].sort((a, b) => a.start_hour - b.start_hour);

    let current: RenderBlock | null = null;
    for (const block of sorted) {
      if (!current) {
        current = {
          course_id: block.course_id,
          type: block.type,
          start_hour: block.start_hour,
          end_hour: block.end_hour,
          isRequired: false,
        };
      } else if (block.start_hour <= current.end_hour) {
        current.end_hour = Math.max(current.end_hour, block.end_hour);
      } else {
        renderBlocks.push(current);
        current = {
          course_id: block.course_id,
          type: block.type,
          start_hour: block.start_hour,
          end_hour: block.end_hour,
          isRequired: false,
        };
      }
    }
    if (current) renderBlocks.push(current);
  }

  return renderBlocks;
}

/**
 * Convert a sectionId + graduationYear to a Hydrant semester code (e.g., "s26", "f27").
 */
function sectionIdToTargetSemester(sectionId: number, graduationYear: number): string {
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

/**
 * Convert a Hydrant semester code to a human-readable label.
 */
function semesterCodeToLabel(code: string): string {
  if (!code) return "";
  const termCode = code[0];
  const yearNum = parseInt(code.slice(1), 10);
  const fullYear = 2000 + yearNum;
  const termName = termCode === "f" ? "Fall" : termCode === "s" ? "Spring" : "IAP";
  return `${termName} ${fullYear}`;
}

export function MiniSchedulePreview({ courseIds, sectionId, graduationYear }: MiniSchedulePreviewProps) {
  const isPast = isPastSemesterById(sectionId, graduationYear);
  const targetSemester = sectionIdToTargetSemester(sectionId, graduationYear);

  if (isPast) {
    return (
      <div className="p-3 max-w-[200px]">
        <div className="text-xs text-gray-400">
          This semester has already passed. Schedule data is not available for past semesters.
        </div>
      </div>
    );
  }

  if (courseIds.length === 0) {
    return (
      <div className="text-xs text-gray-500 p-2">
        No courses in this semester
      </div>
    );
  }

  return (
    <div className="p-2">
      <MiniScheduleGrid courseIds={courseIds} targetSemester={targetSemester} />
    </div>
  );
}

function MiniScheduleGrid({ courseIds, targetSemester }: { courseIds: string[]; targetSemester: string }) {
  const { data, isLoading } = useQuery({
    queryKey: queryKeys.hydrant.schedule(targetSemester, courseIds),
    queryFn: () => hydrantApi.getSchedule(targetSemester, courseIds),
    staleTime: 1000 * 60 * 60, // 1 hour
    enabled: courseIds.length > 0,
  });

  // Get blocked slots from the schedule_free_time constraint
  const selectedHardConstraints = useOptimizationStore((state) => state.selectedHardConstraints);
  const blockedSlots = React.useMemo(() => {
    const freeTimeConstraint = selectedHardConstraints.find(c => c.key === 'schedule_free_time');
    if (!freeTimeConstraint) return [];
    const slots = freeTimeConstraint.parameters.blocked_slots;
    return Array.isArray(slots) ? slots as number[][] : [];
  }, [selectedHardConstraints]);

  const courseId2Color = React.useMemo(() => {
    const map = new Map<string, { bg: string; hex: string }>();
    courseIds.forEach((id, i) => {
      map.set(id, COURSE_COLORS[i % COURSE_COLORS.length]);
    });
    return map;
  }, [courseIds]);

  const coursesWithData = React.useMemo(() => {
    if (!data?.blocks) return [];
    return [...new Set(data.blocks.map((b) => b.course_id))];
  }, [data]);

  if (courseIds.length === 0) {
    return <div className="text-xs text-gray-500">No courses in this semester</div>;
  }

  if (isLoading) {
    return (
      <div className="w-48 h-32 flex items-center justify-center">
        <div className="text-xs text-gray-400">Loading...</div>
      </div>
    );
  }

  const blocks = data?.blocks || [];
  const missingCourses = data?.missing_courses || [];
  const hasConflicts = data?.has_conflicts || false;
  const isExactMatch = !data || data.data_semester === data.target_semester;
  const dataSemesterLabel = data?.data_semester ? semesterCodeToLabel(data.data_semester) : "";

  return (
    <div style={{ width: 220 }}>
      {/* Data source warning */}
      {!isExactMatch && dataSemesterLabel && (
        <div className="text-xs text-gray-400 mb-2">
          Based on {dataSemesterLabel}. Actual times and offered classes may differ.
        </div>
      )}

      {/* Grid container with scroll */}
      <div className="rounded overflow-hidden bg-gray-700">
        {/* Header row - fixed */}
        <div className="flex gap-px">
          <div style={{ width: 16 }} />
          {DAYS.map((day) => (
            <div key={day} className="flex-1 text-[9px] text-gray-400 text-center font-medium bg-gray-800" style={{ minWidth: 28, height: 12 }}>
              {day}
            </div>
          ))}
        </div>

        {/* Scrollable body */}
        <div className="overflow-y-auto" style={{ maxHeight: VISIBLE_HEIGHT }}>
          <div className="flex gap-px">
            {/* Time labels column */}
            <div className="flex flex-col text-[8px] text-gray-500 pr-0.5" style={{ width: 16 }}>
              {Array.from({ length: HOURS }, (_, i) => (
                <div key={i} className="flex items-start justify-end pr-0.5" style={{ height: 8 }}>
                  {(START_HOUR + i) % 12 || 12}
                </div>
              ))}
            </div>

            {/* Day columns */}
            {DAYS.map((day, dayIndex) => {
              const renderBlocks = getRenderBlocks(blocks, dayIndex);

              // Separate required blocks (solid) from optional blocks (outlined)
              const solidBlocks = renderBlocks.filter((b) => b.isRequired);
              const optionBlocks = renderBlocks.filter((b) => !b.isRequired);

              // Get blocked slots for this day
              const dayBlockedSlots = blockedSlots.filter(([d]) => d === dayIndex);

              return (
                <div key={day} className="flex-1 bg-gray-800 relative" style={{ minWidth: 28, height: HOURS * 8 }}>
                {Array.from({ length: HOURS }, (_, i) => (
                  <div
                    key={i}
                    className="absolute w-full border-t border-gray-700/50"
                    style={{ top: i * 8 }}
                  />
                ))}
                {/* Render blocked time slots */}
                {dayBlockedSlots.map(([, startHour, endHour], idx) => {
                  const top = (startHour - START_HOUR) * 8;
                  const height = (endHour - startHour) * 8;
                  
                  if (endHour <= START_HOUR || startHour >= END_HOUR) return null;
                  
                  const clampedTop = Math.max(0, top);
                  const clampedHeight = Math.min(height, HOURS * 8 - clampedTop);
                  
                  return (
                    <div
                      key={`blocked-${idx}`}
                      className="absolute w-full"
                      style={{
                        top: clampedTop,
                        height: clampedHeight,
                        backgroundColor: 'rgba(239, 68, 68, 0.15)',
                        backgroundImage: 'repeating-linear-gradient(45deg, transparent, transparent 2px, rgba(239, 68, 68, 0.1) 2px, rgba(239, 68, 68, 0.1) 4px)',
                        zIndex: 0,
                      }}
                      title="Blocked time"
                    />
                  );
                })}
                {/* Render option blocks with nesting for overlaps */}
                {optionBlocks.map((block, idx) => {
                  const top = (block.start_hour - START_HOUR) * 8;
                  const height = (block.end_hour - block.start_hour) * 8;
                  const colorInfo = courseId2Color.get(block.course_id) || COURSE_COLORS[0];

                  if (block.end_hour <= START_HOUR || block.start_hour >= END_HOUR) {
                    return null;
                  }

                  // Calculate nesting depth - how many other option blocks overlap and are "larger"
                  const nestingDepth = optionBlocks.filter((other) => {
                    if (other === block) return false;
                    // Check overlap
                    const overlaps = block.start_hour < other.end_hour && block.end_hour > other.start_hour;
                    if (!overlaps) return false;
                    // "Larger" = starts earlier, or same start but ends later
                    const otherDuration = other.end_hour - other.start_hour;
                    const blockDuration = block.end_hour - block.start_hour;
                    return other.start_hour < block.start_hour ||
                           (other.start_hour === block.start_hour && otherDuration > blockDuration) ||
                           (other.start_hour === block.start_hour && otherDuration === blockDuration &&
                            other.course_id < block.course_id);
                  }).length;

                  const inset = nestingDepth * 3; // 3px inset per nesting level

                  const blockHeight = Math.max(2, Math.min(height, HOURS * 8 - Math.max(0, top)) - inset * 2);

                  return (
                    <div
                      key={`option-${block.course_id}-${block.type}-${block.start_hour}-${idx}`}
                      className="absolute rounded-sm"
                      style={{
                        top: Math.max(0, top) + inset,
                        height: blockHeight,
                        left: 2 + inset,
                        right: 2 + inset,
                        backgroundColor: "transparent",
                        border: `1px solid ${colorInfo.hex}99`,
                        zIndex: 1 + nestingDepth,
                      }}
                      title={`${block.course_id} ${block.type} (options)`}
                    />
                  );
                })}
                {/* Render solid blocks with overlap detection */}
                {solidBlocks.map((block, idx) => {
                  const top = (block.start_hour - START_HOUR) * 8;
                  const height = (block.end_hour - block.start_hour) * 8;
                  const colorInfo = courseId2Color.get(block.course_id) || COURSE_COLORS[0];

                  if (block.end_hour <= START_HOUR || block.start_hour >= END_HOUR) {
                    return null;
                  }

                  // Check for overlaps with other solid blocks
                  const overlappingBlocks = solidBlocks.filter((other, otherIdx) => {
                    if (otherIdx === idx) return false;
                    return block.start_hour < other.end_hour && block.end_hour > other.start_hour;
                  });

                  // Calculate nesting depth for overlapping solid blocks
                  const nestingDepth = overlappingBlocks.filter((other) => {
                    // "Larger" = starts earlier, or same start but different course (alphabetical)
                    return other.start_hour < block.start_hour ||
                           (other.start_hour === block.start_hour && other.course_id < block.course_id);
                  }).length;

                  const inset = nestingDepth * 4; // 4px inset per nesting level
                  const hasOverlap = overlappingBlocks.length > 0;

                  return (
                    <div
                      key={`solid-${block.course_id}-${block.type}-${block.start_hour}-${idx}`}
                      className="absolute rounded-sm"
                      style={{
                        top: Math.max(0, top) + inset,
                        height: Math.max(2, Math.min(height, HOURS * 8 - Math.max(0, top)) - inset * 2),
                        left: 2 + inset,
                        right: 2 + inset,
                        backgroundColor: colorInfo.hex,
                        opacity: 0.9,
                        zIndex: 2 + nestingDepth,
                        // Add diagonal stripe pattern for conflicting blocks
                        ...(hasOverlap && {
                          backgroundImage: `repeating-linear-gradient(
                            45deg,
                            transparent,
                            transparent 2px,
                            rgba(0,0,0,0.3) 2px,
                            rgba(0,0,0,0.3) 4px
                          ), linear-gradient(${colorInfo.hex}, ${colorInfo.hex})`,
                        }),
                      }}
                      title={`${block.course_id} ${block.type}${hasOverlap ? " (conflict)" : ""}`}
                    />
                  );
                })}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Legend */}
      <div className="mt-1.5 flex flex-wrap gap-x-2 gap-y-0.5">
        {courseIds.map((id) => {
          const colorInfo = courseId2Color.get(id) || COURSE_COLORS[0];
          return (
            <div key={id} className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-sm" style={{ backgroundColor: colorInfo.hex }} />
              <span className={`text-[9px] ${coursesWithData.includes(id) ? "text-gray-400" : "text-gray-600"}`}>
                {id}
              </span>
            </div>
          );
        })}
      </div>

      {/* Warnings */}
      {hasConflicts && (
        <div className="mt-1 text-[9px] text-amber-400">⚠ Schedule conflicts detected</div>
      )}
      {missingCourses.length > 0 && (
        <div className="mt-1 text-[9px] text-gray-500">
          No schedule data: {missingCourses.join(", ")}
        </div>
      )}
    </div>
  );
}
