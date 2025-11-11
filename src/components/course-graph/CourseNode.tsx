"use client";

import * as React from "react";
import { User, Sparkles } from "lucide-react";
import type { CourseNode } from "@/stores/roadStore";
import { CourseTooltip } from "@/components/CourseTooltip";
import { getNodeStyle } from "@/utils/nodeStyles";

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

  // Determine icon based on userControlled flag
  // User-controlled: User icon (manually placed by user)
  // Optimizer-controlled: Sparkles icon (automatically placed by optimizer)
  const icon: string | React.ReactElement = userControlled ? <User className="h-3 w-3" /> : <Sparkles className="h-3 w-3" />;

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
            {typeof icon === 'string' ? icon : icon}
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
