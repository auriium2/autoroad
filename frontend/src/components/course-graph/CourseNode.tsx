
import * as React from "react";
import type { CourseNode } from "@/stores/roadStore";
import type { FireroadCourse } from "@/services/fireroad";
import { useGraphStore } from "@/stores/roadStore";
import { CourseTooltip } from "@/components/CourseTooltip";
import { getNodeStyle, getTermBorderHighlight } from "@/lib/graph";
import { useOptimizationStore } from "@/stores/optimizationStore";
import { sectionIdToAcademicYear } from "@/lib/semesterUtils";
import { TierSelector } from "@/components/app-sidebar/ParametersTab/TierSelector";
import { Sparkles, Users } from "lucide-react";

type CourseNodeComponentProps = {
  node: CourseNode & { 
    optimizerAgreed?: boolean; 
    missingPrereqs?: string[];
    satisfiesHassMarker?: boolean;
    courseDetails?: FireroadCourse;
  };
  disableTooltip?: boolean;
  viewMode?: string;
};

function CourseNodeComponent(props: CourseNodeComponentProps) {
  const {
    node,
    disableTooltip = false,
    viewMode = "default",
  } = props;

  const { courseId, userControlled, disabled, section, nodeStatus: markerStatus } = node;
  const missingPrereqs = node.missingPrereqs || [];
  const satisfiesHassMarker = node.satisfiesHassMarker || false;

  // Check node status
  const isBanished = markerStatus === 'banish';
  const isOverride = markerStatus === 'override';
  const hasUnsatisfiedPrereqs = missingPrereqs.length > 0;

  const getCourseCategoryTier = useOptimizationStore((state) => state.getCourseCategoryTier);
  const selectedYear = useOptimizationStore((state) => state.selectedYear);
  const categoryTier = getCourseCategoryTier(courseId);
  const graduationYear = selectedYear ? parseInt(selectedYear) : 0;

  // Check if this course is a duplicate (appears multiple times in markers)
  const markers = useGraphStore((state) => state.markers);
  const isDuplicate = React.useMemo(() => {
    const placedMarkers = markers.filter(m => m.status !== 'banish' && m.section !== -2);
    const count = placedMarkers.filter(m => m.courseId === courseId).length;
    return count > 1;
  }, [markers, courseId]);

  // Check if this is a virtual/generic marker (HASS-A, etc.)
  const isVirtual = courseId.startsWith('HASS-');

  const courseDetails = node.courseDetails;
  const units = courseDetails?.total_units || 12; // Default to 12 if not available
  const hasFinal = courseDetails?.has_final ?? false;

  // Combine explicit optimizerAgreed prop with HASS marker satisfaction (but use different styling)
  const optimizerAgreed = node.optimizerAgreed;

  // Check if course is placed in wrong semester or wrong year
  // Special semesters (-2 for Must Take, -1 for ASE) are always valid
  // Regular semesters: 0,3,6,9 = Fall; 1,4,7,10 = IAP; 2,5,8,11 = Spring
  let isWrongSemester = false;
  if (section >= 0 && courseDetails && !isOverride) {
    const semesterType = section % 3; // 0=Fall, 1=IAP, 2=Spring
    
    const isWrongTerm = 
      (semesterType === 0 && !courseDetails.offered_fall) ||
      (semesterType === 1 && !courseDetails.offered_IAP) ||
      (semesterType === 2 && !courseDetails.offered_spring);
    
    // Check if course is not offered in this academic year
    let isWrongYear = false;
    if (courseDetails.not_offered_year && graduationYear) {
      const academicYear = sectionIdToAcademicYear(section, graduationYear);
      isWrongYear = academicYear === courseDetails.not_offered_year;
    }
    
    isWrongSemester = isWrongTerm || isWrongYear;
  }

  // Get node styling from shared utility
  let { borderColor, bgColor, textColor, boxShadow } = getNodeStyle({ 
    section, 
    userControlled: userControlled && !satisfiesHassMarker, 
    disabled 
  });

  // Override styling based on node state
  if (isDuplicate && !isBanished) {
    // Pink glow for duplicate courses - highest priority error
    borderColor = 'border-pink-500';
    bgColor = 'bg-pink-500/10';
    textColor = 'text-pink-400';
    boxShadow = "0 0 20px rgba(236, 72, 153, 0.6), 0 0 40px rgba(236, 72, 153, 0.3)";
  } else if (satisfiesHassMarker && !isBanished) {
    borderColor = 'border-amber-600/50';
    bgColor = 'bg-amber-900/20';
    textColor = 'text-amber-200/80';
  } else if (isWrongSemester && !isBanished) {
    borderColor = 'border-yellow-500';
    bgColor = 'bg-yellow-500/10';
    textColor = 'text-yellow-400';
    boxShadow = '0 0 0 0 rgba(234, 179, 8, 0.4)';
  } else if (hasUnsatisfiedPrereqs && !isBanished) {
    // Both user-controlled and optimizer nodes with errors: red
    borderColor = 'border-red-500';
    bgColor = 'bg-red-500/10';
    textColor = 'text-red-400';
    // Override nodes keep their glow even with errors
    boxShadow = isOverride ? "0 0 20px rgba(234, 179, 8, 0.6), 0 0 40px rgba(234, 179, 8, 0.3)" : 'none';
  } else if (isOverride) {
    // Yellow glow for override nodes (but keep blue colors)
    boxShadow = "0 0 20px rgba(234, 179, 8, 0.6), 0 0 40px rgba(234, 179, 8, 0.3)";
  }

  const glowStyle = boxShadow !== "none" ? { boxShadow } : {};

  // Get term-based border gradient
  const termHighlight = getTermBorderHighlight({
    offeredFall: courseDetails?.offered_fall,
    offeredSpring: courseDetails?.offered_spring,
    offeredIAP: courseDetails?.offered_IAP,
  });

  // Limit displayed prerequisites (show max 3, then "...")
  const MAX_DISPLAYED_PREREQS = 3;
  const displayedPrereqs = missingPrereqs.slice(0, MAX_DISPLAYED_PREREQS);
  const hasMore = missingPrereqs.length > MAX_DISPLAYED_PREREQS;

  if (isVirtual) {
    return (
      <div className="flex flex-col items-center">
        <CourseTooltip courseId={courseId} disabled={disableTooltip}>
          <div
            data-node-circle={node.uuid}
            className="relative w-9 h-9 rounded-full cursor-pointer"
            style={{ boxShadow: '0 0 12px rgba(251, 191, 36, 0.4)' }}
            role="button"
            tabIndex={0}
          >
            <div className="absolute inset-0 rounded-full border-2 border-amber-600/50 bg-amber-900/20 shadow-sm hover:shadow-md transition-all duration-200 flex items-center justify-center">
              <Sparkles className="w-4 h-4 text-amber-200/80" />
            </div>
          </div>
        </CourseTooltip>
        <div className="text-xs font-medium text-center mt-2 text-white">
          {courseId}
        </div>
        {viewMode === "default" && courseDetails?.title && (
          <div className="absolute text-[10px] text-gray-300 w-[120px] h-[28px] flex items-center justify-center left-1/2 -translate-x-1/2" style={{ top: '64px' }}>
            <div className="text-center w-full truncate">{courseDetails.title}</div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center">
      {/* Missing prerequisites floating above and to the right */}
      {hasUnsatisfiedPrereqs && !isBanished && (
        <div className="absolute" style={{ top: -8, left: 46, zIndex: 1000 }}>
          <div className="flex flex-col gap-0.5">
            {displayedPrereqs.map((prereq: string, index: number) => (
              <div
                key={index}
                className="glass-card px-1 py-0 rounded text-[9px] font-medium text-red-400 whitespace-nowrap shadow-sm border border-red-500/30"
              >
                {prereq}
              </div>
            ))}
            {hasMore && (
              <div
                className="glass-card px-1 py-0 rounded text-[9px] font-medium text-red-400 whitespace-nowrap shadow-sm border border-red-500/30 text-center"
              >
                ...
              </div>
            )}
          </div>
        </div>
      )}

      {/* Circle node */}
      <CourseTooltip courseId={courseId} disabled={disableTooltip} tutorialId={courseId === "18.01" ? "18.01" : undefined}>
        <div
          data-node-circle={node.uuid}
          data-course-id={courseId}
          data-tutorial="course-node"
          className="relative w-9 h-9 rounded-full cursor-pointer"
          style={glowStyle}
          role="button"
          tabIndex={0}
        >
          <div
            className={`absolute inset-0 rounded-full border-2 shadow-sm hover:shadow-md transition-all duration-200 flex items-center justify-center ${isBanished ? 'border-red-500 bg-red-500/10' : `${borderColor} ${bgColor}`}`}
          >
            {isWrongSemester ? (
              <div className={`text-base font-bold ${textColor} animate-pulse-warning`}>
                ⚠
              </div>
            ) : (
              <div className={`text-xs font-bold ${isBanished ? 'text-red-400' : textColor}`}>
                {isBanished ? '' : units}
              </div>
            )}
          </div>

          {/* Combined SVG overlay for all decorations */}
          {(isBanished || termHighlight || optimizerAgreed || satisfiesHassMarker) && (
            <svg
              className="pointer-events-none absolute inset-0"
              viewBox="0 0 36 36"
              preserveAspectRatio="xMidYMid meet"
            >
              {/* Diagonal slash for banished nodes */}
              {isBanished && (
                <line
                  x1="4"
                  y1="4"
                  x2="32"
                  y2="32"
                  stroke="rgb(239, 68, 68)"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              )}

              {/* Term highlight ring */}
              {termHighlight && !isBanished && (
                <circle
                  cx="18"
                  cy="18"
                  r="16"
                  fill="none"
                  stroke={
                    isDuplicate
                      ? "rgba(236, 72, 153, 0.9)" // Pink for duplicate courses
                      : isWrongSemester
                      ? "rgba(234, 179, 8, 0.9)" // Yellow for wrong semester
                      : hasUnsatisfiedPrereqs
                      ? "rgba(239, 68, 68, 0.8)" // Red for any node with errors
                      : satisfiesHassMarker
                      ? "rgba(251, 146, 60, 0.8)" // Orange for HASS-satisfying markers (checked before userControlled!)
                      : userControlled
                      ? "rgba(147, 197, 253, 0.8)" // Blue for user-controlled without errors
                      : "rgba(255,255,255,0.35)" // White for optimizer nodes without errors
                  }
                  strokeWidth="4"
                  pathLength={1}
                  strokeDasharray={termHighlight.dasharray}
                  strokeDashoffset={termHighlight.dashoffset}
                  strokeLinecap="butt"
                />
              )}

              {/* Double ring indicator when optimizer agrees with marker placement */}
              {optimizerAgreed && !isBanished && (
                <circle
                  cx="18"
                  cy="18"
                  r="11"
                  fill="none"
                  stroke="rgba(34, 197, 94, 1)"
                  strokeWidth="1.5"
                />
              )}
            </svg>
          )}
        </div>
      </CourseTooltip>

      {/* Course ID label below */}
      <div className={`text-xs font-medium text-center mt-2 ${isBanished ? 'text-red-400' : textColor}`}>
        {hasFinal ? (
          <span className="bg-yellow-500/30 px-1 rounded-sm">{courseId}</span>
        ) : (
          courseId
        )}
      </div>

      {/* Course name in friendly mode - absolute positioned to not affect node width */}
      {viewMode === "default" && courseDetails?.title && (
        <div className="absolute text-[10px] text-muted-foreground w-[120px] h-[28px] flex items-center justify-center left-1/2 -translate-x-1/2" style={{ top: '64px' }}>
          {courseDetails.title.length > 20 ? (
            <div className="overflow-hidden w-full">
              <div className="inline-block whitespace-nowrap animate-marquee">
                {courseDetails.title}&nbsp;&nbsp;&nbsp;{courseDetails.title}
              </div>
            </div>
          ) : (
            <div className="text-center w-full truncate">{courseDetails.title}</div>
          )}
        </div>
      )}

      {/* Stats bar in nerd/cost mode */}
      {viewMode === "cost" && courseDetails && (
        <div className="absolute text-[9px] text-muted-foreground/70 w-[120px] flex items-center justify-center gap-1.5 left-1/2 -translate-x-1/2" style={{ top: '64px' }}>
          {(courseDetails.in_class_hours != null || courseDetails.out_of_class_hours != null) && (
            <span className="whitespace-nowrap">
              {((courseDetails.in_class_hours ?? 0) + (courseDetails.out_of_class_hours ?? 0)).toFixed(0)}h
            </span>
          )}
          {courseDetails.enrollment_number != null && (
            <span className="flex items-center gap-0.5 whitespace-nowrap">
              <Users className="w-2.5 h-2.5" />
              {Math.round(courseDetails.enrollment_number)}
            </span>
          )}
          {courseDetails.rating != null && (
            <span className="whitespace-nowrap">
              ★{courseDetails.rating.toFixed(1)}
            </span>
          )}
        </div>
      )}

      {/* Category tier stars - always show if tier > 0 */}
      {categoryTier > 0 && (
        <div className="flex justify-center mt-1" onClick={(e) => e.stopPropagation()}>
          {isOverride ? (
            // Pulsing purple star for must-take courses
            <div className="text-purple-400 animate-pulse text-lg">★</div>
          ) : (
            <TierSelector
              tier={categoryTier}
              onChange={() => {}} // Read-only display
              maxTier={3}
              minTier={0}
            />
          )}
        </div>
      )}
    </div>
  );
}

export { CourseNodeComponent as CourseNode };
