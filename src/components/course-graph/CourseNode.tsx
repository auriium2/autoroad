"use client";

import * as React from "react";
import type { CourseNode } from "@/stores/roadStore";
import { CourseTooltip } from "@/components/CourseTooltip";
import { getNodeStyle } from "@/utils/nodeStyles";
import { useCourseDetails } from "@/hooks/useCourseData";
import { getTermBorderHighlight } from "@/utils/termBorderHighlight";

interface NodeProps {
  node: CourseNode;
  isSpecial?: boolean;
  isHovered?: boolean;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
}

const CourseNodeComponent = React.memo(function CourseNode({
  node,
  isSpecial = false,
  isHovered = false,
  onMouseEnter,
  onMouseLeave,
}: NodeProps) {
  const { courseId, userControlled, disabled, section } = node;

  // Fetch course details to get units and term availability
  const { data: courseDetails } = useCourseDetails(courseId);
  const units = courseDetails?.units || 12; // Default to 12 if not available

  // Get node styling from shared utility - memoize expensive computation
  const { borderColor, bgColor, textColor, boxShadow } = React.useMemo(
    () => getNodeStyle({ section, userControlled, disabled, isSpecial }),
    [section, userControlled, disabled, isSpecial]
  );

  const glowStyle = React.useMemo(
    () => (boxShadow !== "none" ? { boxShadow } : {}),
    [boxShadow]
  );

  // Get term-based border gradient
  const termHighlight = React.useMemo(() => {
    return getTermBorderHighlight({
      offeredFall: courseDetails?.offered_fall,
      offeredSpring: courseDetails?.offered_spring,
      offeredIAP: courseDetails?.offered_IAP,
    });
  }, [courseDetails?.offered_fall, courseDetails?.offered_spring, courseDetails?.offered_IAP]);

  return (
    <div className="flex flex-col items-center">
      {/* Circle node */}
      <CourseTooltip courseId={courseId}>
        <div
          data-node-circle={node.id}
          className="relative w-10 h-10 rounded-full cursor-pointer"
          style={glowStyle}
          onMouseEnter={onMouseEnter}
          onMouseLeave={onMouseLeave}
          role="button"
          tabIndex={0}
        >
          <div
            className={`absolute inset-0 rounded-full border-2 shadow-sm hover:shadow-md transition-all duration-200 flex items-center justify-center ${borderColor} ${bgColor}`}
          >
            <div className={`text-xs font-bold ${textColor}`}>
              {units}
            </div>
          </div>

          {termHighlight && (
            <svg
              className="pointer-events-none absolute inset-0"
              viewBox="0 0 40 40"
              preserveAspectRatio="xMidYMid meet"
            >
              <circle
                cx="20"
                cy="20"
                r="18"
                fill="none"
                stroke="rgba(255,255,255,0.25)"
                strokeWidth="2"
                pathLength={1}
                strokeDasharray={termHighlight.dasharray}
                strokeDashoffset={termHighlight.dashoffset}
                strokeLinecap="butt"
              />
            </svg>
          )}
        </div>
      </CourseTooltip>

      {/* Course ID label below */}
      <div className={`text-xs font-medium text-center mt-2 ${textColor}`}>
        {courseId}
      </div>
    </div>
  );
});

export { CourseNodeComponent as CourseNode };
