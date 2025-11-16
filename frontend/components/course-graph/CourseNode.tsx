"use client";

import * as React from "react";
import type { CourseNode } from "@/stores/roadStore";
import { CourseTooltip } from "@/components/CourseTooltip";
import { getNodeStyle } from "@/lib/nodeStyles";
import { useCourseDetails } from "@/hooks/useCourseData";
import { getTermBorderHighlight } from "@/lib/termBorderHighlight";

type CourseNodeComponentProps = {
  node: CourseNode & { optimizerAgreed?: boolean; missingPrereqs?: string[] };
  disableTooltip?: boolean;
};

function CourseNodeComponent(props: CourseNodeComponentProps) {
  const {
    node,
    disableTooltip = false,
  } = props;

  const { courseId, userControlled, disabled, section, nodeStatus: markerStatus } = node;
  const optimizerAgreed = node.optimizerAgreed;
  const missingPrereqs = node.missingPrereqs || [];

  // Check node status
  const isBanished = markerStatus === 'banish';
  const isSolo = markerStatus === 'solo';
  const hasUnsatisfiedPrereqs = missingPrereqs.length > 0;

  // Fetch course details to get units and term availability
  const { data: courseDetails } = useCourseDetails(courseId);
  const units = courseDetails?.units || 12; // Default to 12 if not available

  // Get node styling from shared utility
  let { borderColor, bgColor, textColor, boxShadow } = getNodeStyle({ section, userControlled, disabled });

  // Override styling based on node state
  if (hasUnsatisfiedPrereqs && !isBanished) {
    // User-controlled nodes with errors: purple
    // Optimizer nodes with errors: red
    if (userControlled) {
      borderColor = 'border-purple-500';
      bgColor = 'bg-purple-500/10';
      textColor = 'text-purple-400';
      boxShadow = 'none';
    } else {
      borderColor = 'border-red-500';
      bgColor = 'bg-red-500/10';
      textColor = 'text-red-400';
      boxShadow = 'none';
    }
  } else if (isSolo) {
    // Yellow glow for solo nodes (but keep blue colors)
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
            {displayedPrereqs.map((prereq, index) => (
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

          {/* Term highlight ring */}
          {termHighlight && !isBanished && (
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
                stroke={
                  hasUnsatisfiedPrereqs && userControlled
                    ? "rgba(168, 85, 247, 0.8)" // Purple for user-controlled with errors
                    : hasUnsatisfiedPrereqs && !userControlled
                    ? "rgba(239, 68, 68, 0.8)" // Red for optimizer nodes with errors
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
            </svg>
          )}

          {/* Double ring indicator when optimizer agrees with marker placement */}
          {optimizerAgreed && !isBanished && (
            <svg
              className="pointer-events-none absolute inset-0"
              viewBox="0 0 36 36"
              preserveAspectRatio="xMidYMid meet"
            >
              <circle
                cx="18"
                cy="18"
                r="11"
                fill="none"
                stroke="rgba(34, 197, 94, 1)"
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
