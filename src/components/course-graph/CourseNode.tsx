"use client";

import * as React from "react";
import type { CourseNode } from "@/stores/roadStore";
import { CourseTooltip } from "@/components/CourseTooltip";
import { getNodeStyle } from "@/utils/nodeStyles";
import { useCourseDetails } from "@/hooks/useCourseData";

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

  // Fetch course details to get units
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

  return (
    <div className="flex flex-col items-center">
      {/* Circle node */}
      <CourseTooltip courseId={courseId}>
        <div
          data-node-circle={node.id}
          className={`w-10 h-10 rounded-full border-2 shadow-sm hover:shadow-md transition-all duration-200 cursor-pointer flex items-center justify-center ${borderColor} ${bgColor}`}
          style={glowStyle}
          onMouseEnter={onMouseEnter}
          onMouseLeave={onMouseLeave}
          role="button"
          tabIndex={0}
        >
          <div className={`text-xs font-bold ${textColor}`}>
            {units}
          </div>
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
