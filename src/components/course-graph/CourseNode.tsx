"use client";

import * as React from "react";
import { Lock, X } from "lucide-react";
import type { CourseNode } from "@/stores/roadStore";

interface NodeProps {
  node: CourseNode;
  isSpecial?: boolean;
  isHovered?: boolean;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
}

export function CourseNode({
  node,
  isSpecial = false,
  isHovered = false,
  onMouseEnter,
  onMouseLeave,
}: NodeProps) {
  const { label, locked, disabled, section } = node;

  // Check if node is in "Must Take" column
  const isMustTake = section === -2;

  // Determine node styling based on state
  let borderColor = "border-border";
  let bgColor = "bg-card";
  let textColor = "text-foreground";
  let icon: string | React.ReactElement = "D";
  let glowStyle = {};

  if (isMustTake) {
    // Must Take nodes: purple glow
    borderColor = "border-purple-500";
    bgColor = "bg-purple-950/40";
    textColor = "text-purple-300";
    glowStyle = {
      boxShadow: "0 0 20px rgba(168, 85, 247, 0.6), 0 0 40px rgba(168, 85, 247, 0.3)",
    };
  } else if (isSpecial) {
    borderColor = "border-primary";
    bgColor = "bg-primary/10";
  } else if (locked) {
    borderColor = "border-yellow-500";
    bgColor = "bg-yellow-50 dark:bg-yellow-950/20";
    textColor = "text-yellow-700 dark:text-yellow-400";
    icon = <Lock className="h-3 w-3" />;
  } else if (disabled) {
    borderColor = "border-red-500";
    bgColor = "bg-red-50 dark:bg-red-950/20";
    textColor = "text-red-700 dark:text-red-400";
    icon = <X className="h-3 w-3" />;
  }

  return (
    <div className="flex flex-col items-center">
      {/* Circle node */}
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

      {/* Label below */}
      <div className={`text-xs font-medium text-center mt-2 ${textColor}`}>
        {label}
      </div>
    </div>
  );
}
