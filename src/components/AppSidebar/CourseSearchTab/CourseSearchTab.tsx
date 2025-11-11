import * as React from "react";
import { Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useSearchCourses } from "@/hooks/useCourseData";
import { CourseTooltip } from "@/components/CourseTooltip";
import { getNodeStyle } from "@/utils/nodeStyles";
import { useCourseDrag } from "./useCourseDrag";
import { getTermBorderHighlight } from "@/utils/termBorderHighlight";

export function CourseSearchTab() {
  const [searchQuery, setSearchQuery] = React.useState("");
  const [selectedDepartment, setSelectedDepartment] = React.useState<string>("all");

  // Use TanStack Query hook for course search
  const { data: courses = [], isLoading, isError } = useSearchCourses(searchQuery, selectedDepartment);

  // Use custom drag hook
  const {
    isDragging,
    dragPosition,
    currentSection,
    isOverGraph,
    handleDragStart,
    handleDragEnd,
  } = useCourseDrag();

  const departments = ["all", "6", "18"];

  // Compute drag preview style based on current section
  const dragPreviewStyle = React.useMemo(() => {
    return getNodeStyle({
      section: currentSection,
      userControlled: true, // Dragged nodes are always user-controlled
      disabled: false,
      isSpecial: false,
    });
  }, [currentSection]);

  return (
    <div className="flex flex-col h-full p-4 space-y-4">
      {/* Custom drag preview that follows cursor - only show when over graph */}
      {isDragging && isOverGraph && (
        <div
          className="fixed pointer-events-none z-50"
          style={{
            left: `${dragPosition.x - 20}px`,
            top: `${dragPosition.y - 20}px`,
          }}
        >
          <div
            className={`w-10 h-10 rounded-full border-2 ${dragPreviewStyle.borderColor} ${dragPreviewStyle.bgColor} flex items-center justify-center shadow-sm transition-colors duration-150`}
            style={{ boxShadow: dragPreviewStyle.boxShadow }}
          >
            <div className={`text-xs font-bold ${dragPreviewStyle.textColor}`}>
              12
            </div>
          </div>
        </div>
      )}

      {/* Search Input */}
      <div className="space-y-2">
        <Label htmlFor="course-search" className="text-sm font-medium">
          Search Courses
        </Label>
        <div className="relative">
          <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            id="course-search"
            placeholder="Search by number or name..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-8"
          />
        </div>
      </div>

      {/* Department Filter */}
      <div className="space-y-2">
        <Label className="text-sm font-medium">Department</Label>
        <div className="flex gap-2 flex-wrap">
          {departments.map((dept) => (
            <Button
              key={dept}
              size="sm"
              variant={selectedDepartment === dept ? "default" : "outline"}
              onClick={() => setSelectedDepartment(dept)}
            >
              {dept === "all" ? "All" : dept}
            </Button>
          ))}
        </div>
      </div>

      {/* Course List */}
      <div className="flex-1 overflow-y-auto space-y-2">
        <div className="text-xs text-muted-foreground mb-2">
          Drag courses to add them to the graph
        </div>
        {isLoading && (
          <div className="text-center text-sm text-muted-foreground py-8">
            Loading courses...
          </div>
        )}
        {isError && (
          <div className="text-center text-sm text-destructive py-8">
            Failed to load courses
          </div>
        )}
        {!isLoading && !isError && courses.map((course) => {
          // Guard against missing data
          if (!course || !course.subject_id || !course.title) {
            console.warn('Invalid course data:', course);
            return null;
          }

          const termHighlight = getTermBorderHighlight({
            offeredFall: course.offered_fall,
            offeredSpring: course.offered_spring,
            offeredIAP: course.offered_IAP,
          });
          
          const dragProps = {
            draggable: true,
            onDragStart: (e: React.DragEvent<HTMLDivElement>) => handleDragStart(e, course),
            onDragEnd: handleDragEnd,
          };

          return (
            <div
              key={course.subject_id}
              className="p-3 border border-border rounded-lg transition-colors"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="font-medium text-sm">{course.subject_id}</div>
                  <div className="text-xs text-muted-foreground line-clamp-2">
                    {course.title}
                  </div>
                </div>
                <CourseTooltip courseId={course.subject_id}>
                  <div
                    {...dragProps}
                    className="relative w-8 h-8 rounded-full flex-shrink-0 ml-2 cursor-move transition-all duration-200"
                  >
                    <div className="absolute inset-0 rounded-full border-2 border-border bg-card hover:border-primary hover:bg-primary/10 hover:shadow-md flex items-center justify-center text-xs font-bold">
                      {course.total_units ?? 12}
                    </div>
                    {termHighlight && (
                      <svg
                        className="pointer-events-none absolute inset-0"
                        viewBox="0 0 32 32"
                        preserveAspectRatio="xMidYMid meet"
                      >
                        <circle
                          cx="16"
                          cy="16"
                          r="13"
                          fill="none"
                          stroke="rgba(255,255,255,0.35)"
                          strokeWidth="2"
                          pathLength={1}
                          strokeDasharray={termHighlight.dasharray}
                          strokeDashoffset={termHighlight.dashoffset}
                          strokeLinecap="butt"
                        />
                      </svg>
                    )}
                  </div>
                </CourseTooltip>
              </div>
            </div>
          );
        })}
        {!isLoading && !isError && courses.length === 0 && (
          <div className="text-center text-sm text-muted-foreground py-8">
            No courses found
          </div>
        )}
      </div>
    </div>
  );
}
