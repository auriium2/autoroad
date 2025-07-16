"use client";

import * as React from "react";
import { X, Lock } from "lucide-react";
import useSWR from 'swr'
import { PositionedGraphClass } from "./types";


// New Node Component
interface NodeProps {
  graphClass: PositionedGraphClass

  handleNodeHover: (
    nodeId: number,
    event: React.MouseEvent<HTMLDivElement>,
  ) => void;
  handleNodeLeave: () => void;
}

export function Node({
  graphClass,
  handleNodeHover,
  handleNodeLeave,
}: NodeProps) {


  const fetcher = (url: string) => fetch(url).then((res) => res.json());
  const { data, error, isLoading } = useSWR(
    "https://api.github.com/repos/vercel/swr",
    fetcher
  );


  const isLocked = "locked" in node && node.locked;
  const isDisabled = "disabled" in node && node.disabled;

  let borderColor = "border-border hover:border-primary/50";
  let bgColor = "bg-card";
  let textColor = "text-foreground";

  if (isSpecial) {
    borderColor = "border-primary hover:border-primary";
    bgColor = "bg-primary/20";
  } else if (isLocked) {
    borderColor = "border-yellow-500 hover:border-yellow-600";
    bgColor = "bg-yellow-50 dark:bg-yellow-950/20";
    textColor = "text-yellow-700 dark:text-yellow-400";
  } else if (isDisabled) {
    borderColor = "border-red-500 hover:border-red-600";
    bgColor = "bg-red-50 dark:bg-red-950/20";
    textColor = "text-red-700 dark:text-red-400";
  }

  return (
    <div className="relative">
      {/* Circle node */}
      <div
        className={`absolute rounded-full w-10 h-10 shadow-sm hover:shadow-md transition-all duration-200 cursor-pointer flex items-center justify-center z-[5] border-2 ${borderColor} ${bgColor}`}
        style={{
          left: graphClass.x,
          top: graphClass.y,
          transform: "translate(-50%, -50%)",
        }}
        tabIndex={0}
        role="button"
        onMouseEnter={(e) => handleNodeHover(node.id, e)}
        onMouseLeave={handleNodeLeave}
      >
        <div className={`text-xs font-bold ${textColor}`}>
          {isLocked ? (
            <Lock className="h-3 w-3" />
          ) : isDisabled ? (
            <X className="h-3 w-3" />
          ) : (
            "D" //center of the node
          )}
        </div>
      </div>

      {/* Node label underneath */}
      <div
        className="absolute text-xs font-medium text-center whitespace-nowrap pointer-events-none z-[5]"
        style={{
          left: graphClass.x,
          top: graphClass.y + 30,
          transform: "translateX(-50%)",
          maxWidth: "80px",
        }}
      >
        <div className={`${isSpecial ? "text-primary font-semibold" : isLocked ? "text-yellow-700 dark:text-yellow-400" : isDisabled ? "text-red-700 dark:text-red-400" : "text-foreground"}`}>
          {node.label}
        </div>
      </div>
    </div>
  );
}
