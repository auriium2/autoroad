"use client";

import * as React from "react";
import type { CourseNode } from "@/stores/roadStore";
import { CourseTooltip } from "@/components/CourseTooltip";
import { getNodeStyle } from "@/lib/nodeStyles";
import { useCourseDetails } from "@/hooks/useCourseData";
import { getTermBorderHighlight } from "@/lib/termBorderHighlight";

type CourseNodeComponentProps = {
  node: CourseNode & { optimizerAgreed?: boolean };
  isSpecial?: boolean;
  isHovered?: boolean;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
  disableTooltip?: boolean;
};

function CourseNodeComponent(props: CourseNodeComponentProps) {
  const {
    node,
    isSpecial = false,
    isHovered = false,
    onMouseEnter,
    onMouseLeave,
    disableTooltip = false,
  } = props;

  const { courseId, userControlled, disabled, section, nodeStatus: markerStatus } = node;
  const optimizerAgreed = (node as any).optimizerAgreed;

  // Check node status
  const isBanished = markerStatus === 'banish';
  const isSolo = markerStatus === 'solo';

  // Fetch course details to get units and term availability
  const { data: courseDetails } = useCourseDetails(courseId);
  const units = courseDetails?.units || 12; // Default to 12 if not available

  // Get node styling from shared utility
  const { borderColor, bgColor, textColor, boxShadow } = getNodeStyle({ section, userControlled, disabled, isSpecial });

  const glowStyle = boxShadow !== "none" ? { boxShadow } : {};

  // Get term-based border gradient
  const termHighlight = getTermBorderHighlight({
    offeredFall: courseDetails?.offered_fall,
    offeredSpring: courseDetails?.offered_spring,
    offeredIAP: courseDetails?.offered_IAP,
  });

  return (
    <div className="flex flex-col items-center">
      {/* Circle node */}
      <CourseTooltip courseId={courseId} disabled={disableTooltip}>
        <div
          data-node-circle={node.id}
          className="relative w-9 h-9 rounded-full cursor-pointer"
          style={glowStyle}
          onMouseEnter={onMouseEnter}
          onMouseLeave={onMouseLeave}
          role="button"
          tabIndex={0}
        >
          <div
            className={`absolute inset-0 rounded-full border-2 shadow-sm hover:shadow-md transition-all duration-200 flex items-center justify-center ${isBanished ? 'border-red-500 bg-red-500/10' : `${borderColor} ${bgColor}`}`}
          >
            <div className={`text-xs font-bold ${isBanished ? 'text-red-400' : textColor}`}>
              {isBanished ? '' : units}
            </div>
          </div>

          {/* Diagonal slash for banished nodes */}
          {isBanished && (
            <svg
              className="pointer-events-none absolute inset-0"
              viewBox="0 0 36 36"
              preserveAspectRatio="xMidYMid meet"
            >
              <line
                x1="4"
                y1="4"
                x2="32"
                y2="32"
                stroke="rgb(239, 68, 68)"
                strokeWidth="2"
                strokeLinecap="round"
              />
            </svg>
          )}

          {/* Dashed circle ring for solo nodes */}
          {isSolo && (
            <svg
              className="pointer-events-none absolute inset-0"
              viewBox="0 0 36 36"
              preserveAspectRatio="xMidYMid meet"
            >
              <circle
                cx="18"
                cy="18"
                r="16"
                fill="none"
                stroke="rgba(147, 197, 253, 0.5)"
                strokeWidth="2"
                strokeDasharray="4 4"
                strokeLinecap="round"
              />
            </svg>
          )}

          {termHighlight && !isBanished && !isSolo && (
            <svg
              className="pointer-events-none absolute inset-0"
              viewBox="0 0 36 36"
              preserveAspectRatio="xMidYMid meet"
            >
              <circle
                cx="18"
                cy="18"
                r="16"
                fill="none"
                stroke={userControlled ? "rgba(147, 197, 253, 0.8)" : "rgba(255,255,255,0.35)"}
                strokeWidth="3"
                pathLength={1}
                strokeDasharray={termHighlight.dasharray}
                strokeDashoffset={termHighlight.dashoffset}
                strokeLinecap="butt"
              />
            </svg>
          )}

          {/* Double ring indicator when optimizer agrees with marker placement */}
          {optimizerAgreed && !isBanished && !isSolo && (
            <svg
              className="pointer-events-none absolute inset-0"
              viewBox="0 0 36 36"
              preserveAspectRatio="xMidYMid meet"
            >
              <circle
                cx="18"
                cy="18"
                r="14"
                fill="none"
                stroke="rgba(34, 197, 94, 0.6)"
                strokeWidth="1.5"
              />
            </svg>
          )}
        </div>
      </CourseTooltip>

      {/* Course ID label below */}
      <div className={`text-xs font-medium text-center mt-2 ${isBanished ? 'text-red-400' : textColor}`}>
        {courseId}
      </div>
    </div>
  );
}

export { CourseNodeComponent as CourseNode };
