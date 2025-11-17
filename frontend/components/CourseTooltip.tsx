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

export function CourseTooltip({ courseId, children, disabled = false }: { courseId: string; children: React.ReactNode; disabled?: boolean }) {
  const [isOpen, setIsOpen] = React.useState(false);
  const [showFullDescription, setShowFullDescription] = React.useState(false);
  const { data: courseDetails, isLoading, isError } = useCourseDetails(isOpen ? courseId : null);

  // Close tooltip if disabled prop changes to true
  React.useEffect(() => {
    if (disabled && isOpen) {
      setIsOpen(false);
    }
  }, [disabled, isOpen]);

  // Reset description expansion when tooltip closes
  React.useEffect(() => {
    if (!isOpen) {
      setShowFullDescription(false);
    }
  }, [isOpen]);

  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip open={isOpen && !disabled} onOpenChange={(open) => !disabled && setIsOpen(open)}>
        <TooltipTrigger asChild>
          {children}
        </TooltipTrigger>
        <TooltipContent
          side="right"
          align="center"
          className="max-w-xs p-3 space-y-2 z-[9999] max-h-96 overflow-y-auto"
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

              {/* Quick info - includes hours breakdown */}
              <div className="flex items-center gap-2 text-xs text-muted-foreground flex-wrap">
                <span>{courseDetails.units} units</span>
                {courseDetails.terms_offered.length > 0 && (
                  <>
                    <span>•</span>
                    <span>{courseDetails.terms_offered.join(", ")}</span>
                  </>
                )}
                {(courseDetails.in_class_hours || courseDetails.out_of_class_hours) && (
                  <>
                    <span>•</span>
                    <span>
                      {courseDetails.in_class_hours && courseDetails.out_of_class_hours && `${Number((courseDetails.in_class_hours + courseDetails.out_of_class_hours).toFixed(2))}h`}
{/*
                      {courseDetails.in_class_hours && `${courseDetails.in_class_hours}h in`}
                      {courseDetails.in_class_hours && courseDetails.out_of_class_hours && ', '}
                      {courseDetails.out_of_class_hours && `${courseDetails.out_of_class_hours}h out`}*/}
                    </span>
                  </>
                )}
              </div>

              {/* Instructors and Prerequisites - grouped together */}
              {(courseDetails.instructors?.length || courseDetails.prerequisites || courseDetails.corequisites) && (
                <div className="text-xs border-t border-border/50 pt-2 space-y-1">
                  {courseDetails.instructors && courseDetails.instructors.length > 0 && (
                    <div>
                      <span className="font-medium text-foreground">Instructor: </span>
                      <span className="text-muted-foreground">{courseDetails.instructors.join(", ")}</span>
                    </div>
                  )}
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

              {/* Description with show more/less */}
              {courseDetails.description && (
                <div className="text-xs leading-snug text-muted-foreground border-b border-border/50 pb-2">
                  {showFullDescription
                    ? courseDetails.description
                    : courseDetails.description.length > 150
                      ? `${courseDetails.description.substring(0, 150)}...`
                      : courseDetails.description}
                  {courseDetails.description.length > 150 && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setShowFullDescription(!showFullDescription);
                      }}
                      className="ml-1 text-primary hover:underline focus:outline-none"
                    >
                      {showFullDescription ? "Show less" : "Show more"}
                    </button>
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
