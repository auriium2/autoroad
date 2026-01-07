import * as React from "react";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { X } from "lucide-react";
import { useOptimizationStore } from "@/stores/optimizationStore";
import { useSearchCourses } from "@/hooks/useCourseData";

export function EquivalencyManager() {
  const customEquivalencies = useOptimizationStore((state) => state.customEquivalencies);
  const addCustomEquivalency = useOptimizationStore((state) => state.addCustomEquivalency);
  const removeCustomEquivalency = useOptimizationStore((state) => state.removeCustomEquivalency);

  const [courseA, setCourseA] = React.useState("");
  const [courseB, setCourseB] = React.useState("");
  const [showDropdownA, setShowDropdownA] = React.useState(false);
  const [showDropdownB, setShowDropdownB] = React.useState(false);

  const { data: coursesA = [] } = useSearchCourses(courseA, "all");
  const { data: coursesB = [] } = useSearchCourses(courseB, "all");

  const dropdownRefA = React.useRef<HTMLDivElement>(null);
  const dropdownRefB = React.useRef<HTMLDivElement>(null);

  // Close dropdowns when clicking outside
  React.useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRefA.current && !dropdownRefA.current.contains(event.target as Node)) {
        setShowDropdownA(false);
      }
      if (dropdownRefB.current && !dropdownRefB.current.contains(event.target as Node)) {
        setShowDropdownB(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleAdd = () => {
    const trimmedA = courseA.trim();
    const trimmedB = courseB.trim();

    if (!trimmedA || !trimmedB) return;
    if (trimmedA === trimmedB) return;

    addCustomEquivalency(trimmedA, trimmedB);
    setCourseA("");
    setCourseB("");
    setShowDropdownA(false);
    setShowDropdownB(false);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleAdd();
    }
  };

  const handleSelectCourseA = (courseId: string) => {
    setCourseA(courseId);
    setShowDropdownA(false);
  };

  const handleSelectCourseB = (courseId: string) => {
    setCourseB(courseId);
    setShowDropdownB(false);
  };

  // Get all unique pairs (to avoid showing both A→B and B→A)
  const equivalencyPairs = React.useMemo(() => {
    const pairs: Array<{ courseA: string; courseB: string }> = [];
    const seen = new Set<string>();

    Object.entries(customEquivalencies).forEach(([courseId, equivalents]: [string, string[]]) => {
      equivalents.forEach((equiv: string) => {
        const key1 = `${courseId}:${equiv}`;
        const key2 = `${equiv}:${courseId}`;

        if (!seen.has(key1) && !seen.has(key2)) {
          pairs.push({ courseA: courseId, courseB: equiv });
          seen.add(key1);
          seen.add(key2);
        }
      });
    });

    return pairs.sort((a, b) => a.courseA.localeCompare(b.courseA));
  }, [customEquivalencies]);

  const filteredCoursesA = courseA.length > 0 ? coursesA.slice(0, 10) : [];
  const filteredCoursesB = courseB.length > 0 ? coursesB.slice(0, 10) : [];

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <p className="text-sm text-muted-foreground">
          Petition courses to be treated as equivalent. This only works if Discourage Equivalent Courses is enabled as an objective.
        </p>
      </div>

      {/* Add new equivalency */}
      <div className="space-y-3">
        <Label className="text-sm font-medium">Add Petition</Label>
        <div className="space-y-2">
          {/* Course A Input with Autocomplete */}
          <div ref={dropdownRefA} className="relative">
            <Input
              placeholder="First course (e.g., 6.100A)"
              value={courseA}
              onChange={(e) => setCourseA(e.target.value)}
              onFocus={() => setShowDropdownA(true)}
              onKeyPress={handleKeyPress}
              className="text-sm"
            />
            {showDropdownA && filteredCoursesA.length > 0 && (
              <div className="absolute z-50 left-0 right-0 mt-1 bg-popover border border-border rounded-md shadow-lg max-h-60 overflow-y-auto">
                {filteredCoursesA.map((course) => (
                  <button
                    key={course.subject_id}
                    onClick={() => handleSelectCourseA(course.subject_id)}
                    className="w-full px-3 py-2 text-left hover:bg-accent transition-colors"
                  >
                    <div className="font-medium text-xs">{course.subject_id}</div>
                    <div className="text-xs text-muted-foreground line-clamp-2 leading-tight">{course.title}</div>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Course B Input with Autocomplete */}
          <div ref={dropdownRefB} className="relative">
            <Input
              placeholder="Equivalent course (e.g., 6.100L)"
              value={courseB}
              onChange={(e) => setCourseB(e.target.value)}
              onFocus={() => setShowDropdownB(true)}
              onKeyPress={handleKeyPress}
              className="text-sm"
            />
            {showDropdownB && filteredCoursesB.length > 0 && (
              <div className="absolute z-50 left-0 right-0 mt-1 bg-popover border border-border rounded-md shadow-lg max-h-60 overflow-y-auto">
                {filteredCoursesB.map((course) => (
                  <button
                    key={course.subject_id}
                    onClick={() => handleSelectCourseB(course.subject_id)}
                    className="w-full px-3 py-2 text-left hover:bg-accent transition-colors"
                  >
                    <div className="font-medium text-xs">{course.subject_id}</div>
                    <div className="text-xs text-muted-foreground line-clamp-2 leading-tight">{course.title}</div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
        <Button onClick={handleAdd} disabled={!courseA.trim() || !courseB.trim() || courseA.trim() === courseB.trim()} className="w-full" size="sm">
          Add Petition
        </Button>
      </div>

      {/* List of existing equivalencies */}
      {equivalencyPairs.length > 0 && (
        <div className="space-y-3">
          <Label className="text-sm font-medium">Active Petitions</Label>
          <div className="space-y-2">
            {equivalencyPairs.map(({ courseA, courseB }) => (
              <div
                key={`${courseA}:${courseB}`}
                className="flex items-center justify-between p-2.5 rounded-md border border-border bg-card hover:bg-accent/50 transition-colors"
              >
                <span className="text-sm font-mono">
                  {courseA} ≡ {courseB}
                </span>
                <Button variant="ghost" size="sm" className="h-7 w-7 p-0 hover:bg-destructive/10 hover:text-destructive" onClick={() => removeCustomEquivalency(courseA, courseB)}>
                  <X className="h-3.5 w-3.5" />
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}

      {equivalencyPairs.length === 0 && (
        <div className="text-center py-6 text-sm text-muted-foreground">
          No petitions yet
        </div>
      )}
    </div>
  );
}
