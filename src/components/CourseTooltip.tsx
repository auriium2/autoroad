"use client";

import * as React from "react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useCourseDetails } from "@/hooks/useCourseData";
import { Loader2 } from "lucide-react";

interface CourseTooltipProps {
  courseId: string;
  children: React.ReactNode;
}

export function CourseTooltip({ courseId, children }: CourseTooltipProps) {
  const [isOpen, setIsOpen] = React.useState(false);
  const { data: courseDetails, isLoading, isError } = useCourseDetails(isOpen ? courseId : null);

  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip open={isOpen} onOpenChange={setIsOpen}>
        <TooltipTrigger asChild>
          {children}
        </TooltipTrigger>
        <TooltipContent 
          side="right" 
          align="center"
          className="max-w-xs p-3 space-y-2 z-[9999]"
          sideOffset={10}
        >
          {isLoading && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Loader2 className="h-3 w-3 animate-spin" />
              Loading...
            </div>
          )}
          
          {isError && (
            <div className="text-xs text-destructive">
              Failed to load details
            </div>
          )}
          
          {courseDetails && (
            <div className="space-y-2">
              {/* Header */}
              <div className="space-y-0.5">
                <div className="font-semibold text-sm">{courseDetails.id}</div>
                <div className="text-xs font-medium text-muted-foreground">{courseDetails.name}</div>
              </div>

              {/* Quick info */}
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <span>{courseDetails.units} units</span>
                {courseDetails.terms_offered.length > 0 && (
                  <>
                    <span>•</span>
                    <span>{courseDetails.terms_offered.join(", ")}</span>
                  </>
                )}
              </div>

              {/* Description */}
              {courseDetails.description && (
                <div className="text-xs leading-snug text-muted-foreground border-t border-border/50 pt-2">
                  {courseDetails.description.length > 150 
                    ? `${courseDetails.description.substring(0, 150)}...` 
                    : courseDetails.description}
                </div>
              )}

              {/* Prerequisites/Corequisites */}
              {(courseDetails.prerequisites || courseDetails.corequisites) && (
                <div className="text-xs border-t border-border/50 pt-2 space-y-1">
                  {courseDetails.prerequisites && (
                    <div>
                      <span className="font-medium text-foreground">Prereq: </span>
                      <span className="text-muted-foreground">{courseDetails.prerequisites}</span>
                    </div>
                  )}
                  {courseDetails.corequisites && (
                    <div>
                      <span className="font-medium text-foreground">Coreq: </span>
                      <span className="text-muted-foreground">{courseDetails.corequisites}</span>
                    </div>
                  )}
                </div>
              )}

              {/* Attributes */}
              {(courseDetails.level || courseDetails.gir_attribute || courseDetails.hass_attribute) && (
                <div className="flex gap-1.5 flex-wrap">
                  {courseDetails.level && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                      {courseDetails.level}
                    </span>
                  )}
                  {courseDetails.gir_attribute && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400">
                      GIR
                    </span>
                  )}
                  {courseDetails.hass_attribute && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400">
                      HASS
                    </span>
                  )}
                </div>
              )}
            </div>
          )}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
