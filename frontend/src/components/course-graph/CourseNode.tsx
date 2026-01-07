
import * as React from "react";
import type { CourseNode } from "@/stores/roadStore";
import { CourseTooltip } from "@/components/CourseTooltip";
import { getNodeStyle, getTermBorderHighlight } from "@/lib/graph";
import { useCourseDetails } from "@/hooks/useCourseData";
import { useOptimizationStore } from "@/stores/optimizationStore";
import { TierSelector } from "@/components/app-sidebar/ParametersTab/TierSelector";

type CourseNodeComponentProps = {
  node: CourseNode & { optimizerAgreed?: boolean; missingPrereqs?: string[] };
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
  const optimizerAgreed = node.optimizerAgreed;
  const missingPrereqs = node.missingPrereqs || [];

  // Check node status
  const isBanished = markerStatus === 'banish';
  const isOverride = markerStatus === 'override';
  const hasUnsatisfiedPrereqs = missingPrereqs.length > 0;

  const getCourseCategoryTier = useOptimizationStore((state) => state.getCourseCategoryTier);
  const categoryTier = getCourseCategoryTier(courseId);

  // Fetch course details to get units and term availability
  const { data: courseDetails } = useCourseDetails(courseId);
  const units = courseDetails?.total_units || 12; // Default to 12 if not available

  // Check if course is placed in wrong semester
  // Special semesters (-2 for Must Take, -1 for ASE) are always valid
  // Regular semesters: 0,3,6,9 = Fall; 1,4,7,10 = IAP; 2,5,8,11 = Spring
  let isWrongSemester = false;
  if (section >= 0 && courseDetails) {
    const semesterType = section % 3; // 0=Fall, 1=IAP, 2=Spring
    
    isWrongSemester = 
      (semesterType === 0 && !courseDetails.offered_fall) ||
      (semesterType === 1 && !courseDetails.offered_IAP) ||
      (semesterType === 2 && !courseDetails.offered_spring);
    
    if (isWrongSemester) {
      console.log(`[CourseNode] ${courseId} wrong semester - section=${section}, type=${semesterType}, fall=${courseDetails.offered_fall}, IAP=${courseDetails.offered_IAP}, spring=${courseDetails.offered_spring}`);
    }
  }

  // Get node styling from shared utility
  let { borderColor, bgColor, textColor, boxShadow } = getNodeStyle({ section, userControlled, disabled });

  // Override styling based on node state
  if (isWrongSemester && !isBanished) {
    // Course placed in wrong semester: yellow warning with soft pulse
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
      <CourseTooltip courseId={courseId} disabled={disableTooltip}>
        <div
          data-node-circle={node.uuid}
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
          {(isBanished || termHighlight || optimizerAgreed) && (
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
                    isWrongSemester
                      ? "rgba(234, 179, 8, 0.9)" // Yellow for wrong semester
                      : hasUnsatisfiedPrereqs
                      ? "rgba(239, 68, 68, 0.8)" // Red for any node with errors
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
        {courseId}
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
