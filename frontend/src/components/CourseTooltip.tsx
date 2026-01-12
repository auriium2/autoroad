
import * as React from "react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useCourseDetails } from "@/hooks/useCourseData";
import { getTermsOffered } from "@/lib/fireroadUtils";
import { Loader2, Users, TicketPercent } from "lucide-react";

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
      <Tooltip open={isOpen && !disabled} onOpenChange={(open: boolean) => !disabled && setIsOpen(open)}>
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
                <div className="font-semibold text-sm">{courseDetails.subject_id}</div>
                <div className="text-xs font-medium text-muted-foreground">{courseDetails.title}</div>
              </div>

              {/* Quick info */}
              <div className="flex items-center gap-2 text-xs text-muted-foreground flex-wrap">
                <span>{courseDetails.total_units} units</span>
                {getTermsOffered(courseDetails).length > 0 && (
                  <>
                    <span>•</span>
                    <span>{getTermsOffered(courseDetails).join(", ")}</span>
                  </>
                )}
              </div>

              {/* Course metrics */}
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground/80">
                {courseDetails.in_class_hours !== undefined && courseDetails.in_class_hours !== null ? (
                  <span className="flex items-center gap-1 whitespace-nowrap">
                    <span className="font-semibold">{courseDetails.in_class_hours}h</span>
                    <span className="opacity-60 text-[10px]">in</span>
                  </span>
                ) : (
                  <span className="flex items-center gap-1 whitespace-nowrap text-muted-foreground/40">
                    <span className="font-semibold">—</span>
                    <span className="opacity-60 text-[10px]">in</span>
                  </span>
                )}
                {courseDetails.out_of_class_hours !== undefined && courseDetails.out_of_class_hours !== null ? (
                  <span className="flex items-center gap-1 whitespace-nowrap">
                    <span className="font-semibold">{courseDetails.out_of_class_hours}h</span>
                    <span className="opacity-60 text-[10px]">out</span>
                  </span>
                ) : (
                  <span className="flex items-center gap-1 whitespace-nowrap text-muted-foreground/40">
                    <span className="font-semibold">—</span>
                    <span className="opacity-60 text-[10px]">out</span>
                  </span>
                )}
                {courseDetails.enrollment_number !== undefined && courseDetails.enrollment_number !== null ? (
                  <span className="flex items-center gap-0.5 whitespace-nowrap">
                    <Users className="w-3 h-3 opacity-60" />
                    <span className="font-semibold">{Math.round(courseDetails.enrollment_number)}</span>
                  </span>
                ) : (
                  <span className="flex items-center gap-0.5 whitespace-nowrap text-muted-foreground/40">
                    <Users className="w-3 h-3 opacity-60" />
                    <span className="font-semibold">—</span>
                  </span>
                )}
                {courseDetails.rating !== undefined && courseDetails.rating !== null ? (
                  <span className="flex items-center gap-0.5 whitespace-nowrap">
                    <span className="font-semibold">★{courseDetails.rating.toFixed(1)}</span>
                  </span>
                ) : (
                  <span className="flex items-center gap-0.5 whitespace-nowrap text-muted-foreground/40">
                    <span className="font-semibold">★—</span>
                  </span>
                )}
                {courseDetails.imdb_rating !== undefined && courseDetails.imdb_rating !== null ? (
                  <span className="flex items-center gap-0.5 whitespace-nowrap">
                    <TicketPercent className="w-3 h-3 opacity-60" />
                    <span className="font-semibold">{courseDetails.imdb_rating}</span>
                  </span>
                ) : (
                  <span className="flex items-center gap-0.5 text-muted-foreground/40 whitespace-nowrap">
                    <TicketPercent className="w-3 h-3 opacity-60" />
                    <span className="font-semibold">—</span>
                  </span>
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
                    <>
                      {" "}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setShowFullDescription(!showFullDescription);
                        }}
                        className="text-primary/70 hover:text-primary hover:underline focus:outline-none text-[11px]"
                      >
                        {showFullDescription ? "Less" : "More"}
                      </button>
                    </>
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
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-900/30 text-amber-200/80">
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
