import * as React from "react";
import { Search, Users, TicketPercent, X, ChevronUp, Filter } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { useSearchCourses } from "@/hooks/useCourseData";
import { CourseTooltip } from "@/components/CourseTooltip";
import { useCourseDrag } from "./useCourseDrag";
import { getTermBorderHighlight } from "@/lib/termBorderHighlight";
import type { FireroadCourse } from "@/services/fireroad";

const COURSES_PER_PAGE = 20;

type GIRFilter = "ANY" | "LAB" | "REST";
type HASSFilter = "ANY" | "A" | "S" | "H" | "E";
type CIFilter = "ANY" | "CI-H" | "CI-HW" | "NONE";
type LevelFilter = "ANY" | "UG" | "G";
type UnitsFilter = "ANY" | "<6" | "6" | "9" | "12" | "15" | "6+";
type TermFilter = "ANY" | "FA" | "IAP" | "SP";

export function CourseSearchTab() {
  const [searchQuery, setSearchQuery] = React.useState("");
  const [filterQuery, setFilterQuery] = React.useState("");
  const [activeFilters, setActiveFilters] = React.useState<Set<string>>(new Set());
  const [displayCount, setDisplayCount] = React.useState(COURSES_PER_PAGE);
  const loadMoreRef = React.useRef<HTMLDivElement>(null);

  // Determine which department to search based on active filters
  const selectedDepartment = React.useMemo(() => {
    const deptFilter = Array.from(activeFilters).find(f => f.startsWith("dept:"));
    if (deptFilter) {
      return deptFilter.split(":")[1];
    }
    // If there are non-department filters but no department specified, search all departments
    if (activeFilters.size > 0) {
      return "all";
    }
    return "all";
  }, [activeFilters]);

  // Trigger search when filters are active but no search query
  const effectiveSearchQuery = React.useMemo(() => {
    if (searchQuery) return searchQuery;
    // If any filter is active, trigger a wildcard search to get courses
    if (activeFilters.size > 0) return "*";
    return "";
  }, [searchQuery, activeFilters]);

  const { data: allCourses = [], isLoading, isError } = useSearchCourses(effectiveSearchQuery, selectedDepartment);
  const { handleDragStart, handleDragEnd } = useCourseDrag();

  const departments = ["all", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "14", "15", "16", "17", "18", "20", "21A", "21G", "21H", "21M", "22", "24"];

  // All available filters with their display names
  const allFilters = React.useMemo(() => {
    const filters = [
      ...departments.filter(d => d !== "all").map(d => ({ id: `dept:${d}`, label: `Course ${d}`, category: "Department" })),
      { id: "gir:LAB", label: "GIR: LAB", category: "GIR" },
      { id: "gir:REST", label: "GIR: REST", category: "GIR" },
      { id: "hass:A", label: "HASS: A", category: "HASS" },
      { id: "hass:S", label: "HASS: S", category: "HASS" },
      { id: "hass:H", label: "HASS: H", category: "HASS" },
      { id: "hass:E", label: "HASS: E", category: "HASS" },
      { id: "ci:CI-H", label: "CI-H", category: "CI" },
      { id: "ci:CI-HW", label: "CI-HW", category: "CI" },
      { id: "ci:NONE", label: "No CI", category: "CI" },
      { id: "level:UG", label: "Undergrad", category: "Level" },
      { id: "level:G", label: "Graduate", category: "Level" },
      { id: "units:<6", label: "< 6 units", category: "Units" },
      { id: "units:6", label: "6 units", category: "Units" },
      { id: "units:9", label: "9 units", category: "Units" },
      { id: "units:12", label: "12 units", category: "Units" },
      { id: "units:15", label: "15 units", category: "Units" },
      { id: "units:6+", label: "6+ units", category: "Units" },
      { id: "term:FA", label: "Fall", category: "Term" },
      { id: "term:IAP", label: "IAP", category: "Term" },
      { id: "term:SP", label: "Spring", category: "Term" },
    ];
    return filters;
  }, [departments]);

  // Filter suggestions based on query (no limit)
  const filterSuggestions = React.useMemo(() => {
    const query = filterQuery.toLowerCase();
    const filtered = allFilters.filter(f => !activeFilters.has(f.id) && (
      !query ||
      f.label.toLowerCase().includes(query) ||
      f.category.toLowerCase().includes(query)
    ));
    return filtered;
  }, [filterQuery, activeFilters, allFilters]);

  const [showFilterDropdown, setShowFilterDropdown] = React.useState(false);

  // Apply client-side filters
  const filteredCourses = React.useMemo(() => {
    return allCourses.filter((course) => {
      for (const filterId of activeFilters) {
        const [category, value] = filterId.split(":");

        if (category === "dept") {
          // Check if course subject_id starts with the department number
          if (!course.subject_id?.startsWith(`${value}.`)) return false;
        }

        if (category === "gir") {
          if (value === "LAB" && !course.gir_attribute?.includes("LAB")) return false;
          if (value === "REST" && !course.gir_attribute?.includes("REST")) return false;
        }

        if (category === "hass") {
          if (!course.hass_attribute?.includes(value)) return false;
        }

        if (category === "ci") {
          if (value === "CI-H" && !course.communication_requirement?.includes("CI-H")) return false;
          if (value === "CI-HW" && !course.communication_requirement?.includes("CI-HW")) return false;
          if (value === "NONE" && course.communication_requirement) return false;
        }

        if (category === "level") {
          if (value === "UG" && course.level !== "U") return false;
          if (value === "G" && course.level !== "G") return false;
        }

        if (category === "units") {
          const units = course.total_units || 0;
          if (value === "<6" && units >= 6) return false;
          if (value === "6" && units !== 6) return false;
          if (value === "9" && units !== 9) return false;
          if (value === "12" && units !== 12) return false;
          if (value === "15" && units !== 15) return false;
          if (value === "6+" && units < 6) return false;
        }

        if (category === "term") {
          if (value === "FA" && !course.offered_fall) return false;
          if (value === "IAP" && !course.offered_IAP) return false;
          if (value === "SP" && !course.offered_spring) return false;
        }
      }

      return true;
    });
  }, [allCourses, activeFilters]);

  const addFilter = (filterId: string) => {
    setActiveFilters(new Set(activeFilters).add(filterId));
    setFilterQuery("");
  };

  const removeFilter = (filterId: string) => {
    const newFilters = new Set(activeFilters);
    newFilters.delete(filterId);
    setActiveFilters(newFilters);
  };

  // Reset display count when search params or filters change
  React.useEffect(() => {
    setDisplayCount(COURSES_PER_PAGE);
  }, [effectiveSearchQuery, selectedDepartment, activeFilters]);

  // Paginate courses for display
  const courses = filteredCourses.slice(0, displayCount);
  const hasMore = displayCount < filteredCourses.length;

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

        {/* Filter Search Bar */}
        <div className="relative">
          <Filter className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground pointer-events-none z-10" />
          <div className="flex h-10 w-full rounded-md border border-input bg-background overflow-hidden">
            <div className="overflow-x-auto scrollbar-thin flex-1">
              <div className="flex gap-1 items-center pl-8 pr-3 py-2 w-max min-w-full h-full">
                {/* Active Filters Tags */}
                {Array.from(activeFilters).map((filterId) => {
                  const filter = allFilters.find(f => f.id === filterId);
                  return filter ? (
                    <Badge key={filterId} variant="secondary" className="text-xs whitespace-nowrap shrink-0">
                      {filter.label}
                      <X className="h-3 w-3 ml-1 cursor-pointer" onClick={() => removeFilter(filterId)} />
                    </Badge>
                  ) : null;
                })}
                {/* Filter Input */}
                <input
                  type="text"
                  placeholder={activeFilters.size === 0 ? "Add filters..." : ""}
                  value={filterQuery}
                  onChange={(e) => setFilterQuery(e.target.value)}
                  onFocus={() => setShowFilterDropdown(true)}
                  onBlur={() => setTimeout(() => setShowFilterDropdown(false), 200)}
                  className="flex-1 min-w-[100px] outline-none bg-transparent text-sm placeholder:text-muted-foreground ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium disabled:cursor-not-allowed disabled:opacity-50"
                />
              </div>
            </div>
          </div>
          {/* Filter Suggestions Dropdown */}
          {showFilterDropdown && filterSuggestions.length > 0 && (
            <div className="absolute top-full left-0 right-0 mt-1 border rounded-md bg-popover shadow-md z-50 max-h-60 overflow-y-auto">
              {filterSuggestions.map((filter) => (
                <div
                  key={filter.id}
                  className="px-3 py-2 hover:bg-accent cursor-pointer text-xs"
                  onClick={() => addFilter(filter.id)}
                >
                  <span className="text-muted-foreground text-[10px]">{filter.category}</span>
                  <div>{filter.label}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Course List */}
      <div className="flex-1 overflow-y-auto space-y-2">
        <div className="text-xs text-muted-foreground mb-2">
          Drag circles (course nodes) to add them
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
