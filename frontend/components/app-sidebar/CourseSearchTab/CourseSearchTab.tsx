import * as React from "react";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useSearchCourses } from "@/hooks/useCourseData";
import { useCourseDrag } from "./useCourseDrag";
import { CourseCard } from "./CourseCard";
import { FilterBar } from "./FilterBar";
import type { FireroadCourse } from "@/services/fireroad";

const COURSES_PER_PAGE = 20;
const DEPARTMENTS = ["all", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "14", "15", "16", "17", "18", "20", "21A", "21G", "21H", "21M", "22", "24"];

const ALL_FILTERS = [
  ...DEPARTMENTS.filter(d => d !== "all").map(d => ({ id: `dept:${d}`, label: `Course ${d}`, category: "Department" })),
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
  { id: "term:FA", label: "Fall", category: "Term" },
  { id: "term:IAP", label: "IAP", category: "Term" },
  { id: "term:SP", label: "Spring", category: "Term" },
  { id: "sort:imdb-rating-asc", label: "IMDB Rating ↑", category: "Sort" },
  { id: "sort:imdb-rating-desc", label: "IMDB Rating ↓", category: "Sort" },
  { id: "sort:units-asc", label: "Units ↑", category: "Sort" },
  { id: "sort:units-desc", label: "Units ↓", category: "Sort" },
  { id: "sort:enrollment-asc", label: "Enrollment ↑", category: "Sort" },
  { id: "sort:enrollment-desc", label: "Enrollment ↓", category: "Sort" },
];

export function CourseSearchTab() {
  const [searchQuery, setSearchQuery] = React.useState("");
  const [activeFilters, setActiveFilters] = React.useState<Set<string>>(new Set());
  const [displayCount, setDisplayCount] = React.useState(COURSES_PER_PAGE);
  const loadMoreRef = React.useRef<HTMLDivElement>(null);

  const selectedDepartment = React.useMemo(() => {
    const deptFilter = Array.from(activeFilters).find(f => f.startsWith("dept:"));
    if (deptFilter) return deptFilter.split(":")[1];
    if (activeFilters.size > 0) return "all";
    return "all";
  }, [activeFilters]);

  const effectiveSearchQuery = React.useMemo(() => {
    if (searchQuery) return searchQuery;
    if (activeFilters.size > 0) return "*";
    return "";
  }, [searchQuery, activeFilters]);

  const apiFilters = React.useMemo(() => {
    const filters: Record<string, string> = {};
    for (const filterId of activeFilters) {
      const [category, value] = filterId.split(":");
      if (category === "dept") continue;
      filters[category] = value;
    }
    return Object.keys(filters).length > 0 ? filters : undefined;
  }, [activeFilters]);

  const { data: allCourses = [], isLoading, isError } = useSearchCourses(effectiveSearchQuery, selectedDepartment, apiFilters);
  const { handleDragStart, handleDragEnd } = useCourseDrag();

  React.useEffect(() => {
    setDisplayCount(COURSES_PER_PAGE);
  }, [effectiveSearchQuery, selectedDepartment, activeFilters]);

  const courses = allCourses.slice(0, displayCount);
  const hasMore = displayCount < allCourses.length;

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

  const createDragPreview = (courseId: string, units: number) => {
    const preview = document.createElement('div');
    preview.style.width = '36px';
    preview.style.height = '36px';
    preview.style.borderRadius = '50%';
    preview.style.border = '2px solid rgb(59, 130, 246)';
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
    const preview = createDragPreview(course.subject_id, course.total_units ?? 12);
    e.dataTransfer.setDragImage(preview, 18, 18);
    setTimeout(() => document.body.removeChild(preview), 0);
    handleDragStart(e, course);
  };

  const addFilter = (filterId: string) => {
    setActiveFilters(new Set(activeFilters).add(filterId));
  };

  const removeFilter = (filterId: string) => {
    const newFilters = new Set(activeFilters);
    newFilters.delete(filterId);
    setActiveFilters(newFilters);
  };

  return (
    <div className="flex flex-col h-full p-4 space-y-4">
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

        <FilterBar
          activeFilters={activeFilters}
          allFilters={ALL_FILTERS}
          onAddFilter={addFilter}
          onRemoveFilter={removeFilter}
        />
      </div>

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
        {!isLoading && !isError && courses.map((course) => (
          <CourseCard
            key={course.subject_id}
            course={course}
            onDragStart={handleCourseStart}
            onDragEnd={handleDragEnd}
          />
        ))}
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
        {!isLoading && !isError && hasMore && (
          <div ref={loadMoreRef} className="text-center py-4 text-xs text-muted-foreground/50">
            {allCourses.length - displayCount} more courses...
          </div>
        )}
      </div>
    </div>
  );
}
