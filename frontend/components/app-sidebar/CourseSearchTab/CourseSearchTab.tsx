import * as React from "react";
import { Search, Users, TicketPercent } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useSearchCourses } from "@/hooks/useCourseData";
import { CourseTooltip } from "@/components/CourseTooltip";
import { useCourseDrag } from "./useCourseDrag";
import { getTermBorderHighlight } from "@/lib/termBorderHighlight";
import type { FireroadCourse } from "@/services/fireroad";

const COURSES_PER_PAGE = 20;

export function CourseSearchTab() {
  const [searchQuery, setSearchQuery] = React.useState("");
  const [selectedDepartment, setSelectedDepartment] = React.useState<string>("all");
  const [displayCount, setDisplayCount] = React.useState(COURSES_PER_PAGE);
  const loadMoreRef = React.useRef<HTMLDivElement>(null);

  const { data: allCourses = [], isLoading, isError } = useSearchCourses(searchQuery, selectedDepartment);
  const { handleDragStart, handleDragEnd } = useCourseDrag();

  const departments = ["all", "6", "18"];

  // Reset display count when search params change
  React.useEffect(() => {
    setDisplayCount(COURSES_PER_PAGE);
  }, [searchQuery, selectedDepartment]);

  // Paginate courses for display
  const courses = allCourses.slice(0, displayCount);
  const hasMore = displayCount < allCourses.length;

  // Infinite scroll: load more when the sentinel element is visible
  React.useEffect(() => {
    if (!loadMoreRef.current || !hasMore || isLoading) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          setDisplayCount(prev => prev + COURSES_PER_PAGE);
        }
      },
      { threshold: 0.1 }
    );

    observer.observe(loadMoreRef.current);

    return () => observer.disconnect();
  }, [hasMore, isLoading]);

  // Create a custom drag preview element that matches graph node size (36x36)
  const createDragPreview = (courseId: string, units: number) => {
    const preview = document.createElement('div');
    preview.style.width = '36px';
    preview.style.height = '36px';
    preview.style.borderRadius = '50%';
    preview.style.border = '2px solid rgb(59, 130, 246)'; // border-primary
    preview.style.backgroundColor = 'rgba(59, 130, 246, 0.1)';
    preview.style.display = 'flex';
    preview.style.alignItems = 'center';
    preview.style.justifyContent = 'center';
    preview.style.fontSize = '12px';
    preview.style.fontWeight = 'bold';
    preview.style.color = 'rgb(147, 197, 253)';
    preview.style.position = 'fixed';
    preview.style.top = '-9999px';
    preview.style.left = '-9999px';
    preview.style.pointerEvents = 'none';
    preview.textContent = String(units);

    document.body.appendChild(preview);
    return preview;
  };

  const handleCourseStart = (e: React.DragEvent, course: FireroadCourse) => {
    // Create custom drag preview
    const preview = createDragPreview(course.subject_id, course.total_units ?? 12);

    // Set the custom drag image (centered on cursor)
    e.dataTransfer.setDragImage(preview, 18, 18);

    // Clean up the preview element after a short delay
    setTimeout(() => {
      document.body.removeChild(preview);
    }, 0);

    // Call the original drag start handler
    handleDragStart(e, course);
  };

  return (
    <div className="flex flex-col h-full p-4 space-y-4">
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
          Drag circles to add them to the graph
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
            offeredIAP: 'offered_IAP' in course ? course.offered_IAP : undefined,
          });

          // Determine current semester instructor
          const currentMonth = new Date().getMonth(); // 0-11
          const isFallSemester = currentMonth >= 8 || currentMonth <= 0; // Sept-Jan
          const currentInstructor = course.instructors && course.instructors.length > 0
            ? (isFallSemester ? course.instructors[0] : course.instructors[1] || course.instructors[0])
            : null;

          // Get enrollment and rating (now single values, not arrays)
          const enrollment = course.enrollment_number !== undefined && course.enrollment_number !== null
            ? Math.round(course.enrollment_number)
            : null;
          const rating = course.rating !== undefined && course.rating !== null
            ? course.rating.toFixed(1)
            : null;

          // Check if graduate level
          const isGraduate = course.level === 'G';

          return (
            <div
              key={course.subject_id}
              className="relative p-4 pb-2.5 border border-border rounded-lg transition-colors overflow-hidden min-h-[100px]"
            >
              {/* Graduate gradient overlay */}
              {isGraduate && (
                <div className="absolute inset-0 pointer-events-none bg-gradient-to-tr from-transparent to-purple-500/8" />
              )}

              {/* Background instructor name - scrolling marquee */}
              {currentInstructor && (
                <div className="absolute left-0 right-0 bottom-2 flex items-center pointer-events-none overflow-hidden">
                  <div className="animate-marquee whitespace-nowrap">
                    <span className="text-3xl font-bold text-muted-foreground/[0.15] select-none mx-8">
                      {currentInstructor}
                    </span>
                    <span className="text-3xl font-bold text-muted-foreground/[0.15] select-none mx-8">
                      {currentInstructor}
                    </span>
                  </div>
                </div>
              )}

              <div className="relative flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0 flex flex-col">
                  <div className="font-medium text-sm mb-0.5">{course.subject_id}</div>
                  <div className="text-xs text-muted-foreground line-clamp-2 mb-2">
                    {course.title}
                  </div>

                  {/* Course metrics */}
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground/80 mt-auto">
                    {(course.in_class_hours !== undefined && course.in_class_hours !== null &&
                      course.out_of_class_hours !== undefined && course.out_of_class_hours !== null) ? (
                      <span className="flex items-center gap-1 whitespace-nowrap">
                        <span className="font-semibold">{(course.in_class_hours + course.out_of_class_hours).toFixed(1)}h</span>
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 whitespace-nowrap text-muted-foreground/40">
                        <span className="font-semibold">—</span>
                      </span>
                    )}
                    {enrollment ? (
                      <span className="flex items-center gap-0.5 whitespace-nowrap">
                        <Users className="w-3 h-3 opacity-60" />
                        <span className="font-semibold">{enrollment}</span>
                      </span>
                    ) : (
                      <span className="flex items-center gap-0.5 whitespace-nowrap text-muted-foreground/40">
                        <Users className="w-3 h-3 opacity-60" />
                        <span className="font-semibold">—</span>
                      </span>
                    )}
                    {rating ? (
                      <span className="flex items-center gap-0.5 whitespace-nowrap">
                        <span className="font-semibold">★{rating}</span>
                      </span>
                    ) : (
                      <span className="flex items-center gap-0.5 whitespace-nowrap text-muted-foreground/40">
                        <span className="font-semibold">★—</span>
                      </span>
                    )}
                    {course.imdb_rating !== undefined && course.imdb_rating !== null ? (
                      <span className="flex items-center gap-0.5 whitespace-nowrap">
                        <TicketPercent className="w-3 h-3 opacity-60" />
                        <span className="font-semibold">{course.imdb_rating}</span>
                      </span>
                    ) : (
                      <span className="flex items-center gap-0.5 text-muted-foreground/40 whitespace-nowrap">
                        <TicketPercent className="w-3 h-3 opacity-60" />
                        <span className="font-semibold">—</span>
                      </span>
                    )}
                  </div>
                </div>
                <CourseTooltip courseId={course.subject_id}>
                  <div
                    draggable
                    onDragStart={(e) => handleCourseStart(e, course)}
                    onDragEnd={handleDragEnd}
                    className="relative w-9 h-9 rounded-full flex-shrink-0 cursor-move transition-all duration-200"
                  >
                    <div className="absolute inset-0 rounded-full border-2 border-border bg-card hover:border-primary hover:bg-primary/10 hover:shadow-md flex items-center justify-center text-xs font-bold">
                      {course.total_units ?? 12}
                    </div>
                    {termHighlight && (
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
            {searchQuery === "" && selectedDepartment === "all" ? (
              <>
                <div className="mb-2">Select a department or search for courses</div>
                <div className="text-xs opacity-70">Tip: Try selecting &quot;6&quot; or &quot;18&quot; to browse courses</div>
              </>
            ) : (
              "No courses found"
            )}
          </div>
        )}
        {/* Infinite scroll sentinel */}
        {!isLoading && !isError && hasMore && (
          <div ref={loadMoreRef} className="text-center py-4 text-xs text-muted-foreground/50">
            {allCourses.length - displayCount} more courses...
          </div>
        )}
      </div>
    </div>
  );
}
