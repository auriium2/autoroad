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
          className="max-w-md p-4 space-y-3 z-[9999]"
          sideOffset={15}
        >
          {isLoading && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading course details...
            </div>
          )}
          
          {isError && (
            <div className="text-sm text-destructive">
              Failed to load course details
            </div>
          )}
          
          {courseDetails && (
            <div className="space-y-3">
              {/* Header */}
              <div className="space-y-1">
                <div className="font-semibold text-base">{courseDetails.id}</div>
                <div className="text-sm font-medium">{courseDetails.name}</div>
                <div className="text-xs text-muted-foreground">
                  {courseDetails.units} units
                  {courseDetails.terms_offered.length > 0 && (
                    <> • {courseDetails.terms_offered.join(", ")}</>
                  )}
                </div>
              </div>

              {/* Description */}
              {courseDetails.description && (
                <div className="text-sm leading-relaxed border-t pt-2">
                  {courseDetails.description}
                </div>
              )}

              {/* Prerequisites */}
              {courseDetails.prerequisites && (
                <div className="text-sm">
                  <span className="font-medium">Prerequisites: </span>
                  <span className="text-muted-foreground">{courseDetails.prerequisites}</span>
                </div>
              )}

              {/* Corequisites */}
              {courseDetails.corequisites && (
                <div className="text-sm">
                  <span className="font-medium">Corequisites: </span>
                  <span className="text-muted-foreground">{courseDetails.corequisites}</span>
                </div>
              )}

              {/* Instructors */}
              {courseDetails.instructors && courseDetails.instructors.length > 0 && (
                <div className="text-sm">
                  <span className="font-medium">Instructors: </span>
                  <span className="text-muted-foreground">{courseDetails.instructors.join(", ")}</span>
                </div>
              )}

              {/* Attributes */}
              <div className="flex gap-2 flex-wrap pt-2 border-t">
                {courseDetails.level && (
                  <span className="text-xs px-2 py-1 rounded bg-muted">
                    {courseDetails.level}
                  </span>
                )}
                {courseDetails.gir_attribute && (
                  <span className="text-xs px-2 py-1 rounded bg-blue-500/10 text-blue-500">
                    GIR: {courseDetails.gir_attribute}
                  </span>
                )}
                {courseDetails.hass_attribute && (
                  <span className="text-xs px-2 py-1 rounded bg-purple-500/10 text-purple-500">
                    HASS: {courseDetails.hass_attribute}
                  </span>
                )}
              </div>
            </div>
          )}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
