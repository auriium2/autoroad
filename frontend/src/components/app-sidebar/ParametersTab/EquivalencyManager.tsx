import * as React from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { X } from "lucide-react";
import { useSearchCourses } from "@/hooks/useCourseData";

interface EquivalencyManagerProps {
  customEquivalencies: Record<string, string[]>;
  onChange: (newEquiv: Record<string, string[]>) => void;
}

type EquivalencyDirection = "bidirectional" | "unidirectional";

interface EquivalencyEntry {
  courseA: string;
  courseB: string;
  direction: "bidirectional" | "a_to_b" | "b_to_a";
}

export function EquivalencyManager({ customEquivalencies, onChange }: EquivalencyManagerProps) {
  const [courseA, setCourseA] = React.useState("");
  const [courseB, setCourseB] = React.useState("");
  const [direction, setDirection] = React.useState<EquivalencyDirection>("bidirectional");
  const [showDropdownA, setShowDropdownA] = React.useState(false);
  const [showDropdownB, setShowDropdownB] = React.useState(false);

  const { data: dataA } = useSearchCourses(courseA, "all");
  const { data: dataB } = useSearchCourses(courseB, "all");

  const coursesA = dataA?.pages.flatMap(p => p.courses) ?? [];
  const coursesB = dataB?.pages.flatMap(p => p.courses) ?? [];

  const dropdownRefA = React.useRef<HTMLDivElement>(null);
  const dropdownRefB = React.useRef<HTMLDivElement>(null);

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

  const addEquivalency = (a: string, b: string, dir: EquivalencyDirection) => {
    const newEquiv = { ...customEquivalencies };

    // A counts as B: add A -> [B]
    if (!newEquiv[a]) newEquiv[a] = [];
    if (!newEquiv[a].includes(b)) {
      newEquiv[a] = [...newEquiv[a], b];
    }

    if (dir === "bidirectional") {
      // B also counts as A: add B -> [A]
      if (!newEquiv[b]) newEquiv[b] = [];
      if (!newEquiv[b].includes(a)) {
        newEquiv[b] = [...newEquiv[b], a];
      }
    }

    onChange(newEquiv);
  };

  const removeEquivalency = (a: string, b: string, entryDirection: EquivalencyEntry["direction"]) => {
    const newEquiv = { ...customEquivalencies };

    if (entryDirection === "bidirectional" || entryDirection === "a_to_b") {
      if (newEquiv[a]) {
        newEquiv[a] = newEquiv[a].filter(c => c !== b);
        if (newEquiv[a].length === 0) delete newEquiv[a];
      }
    }
    if (entryDirection === "bidirectional" || entryDirection === "b_to_a") {
      if (newEquiv[b]) {
        newEquiv[b] = newEquiv[b].filter(c => c !== a);
        if (newEquiv[b].length === 0) delete newEquiv[b];
      }
    }

    onChange(newEquiv);
  };

  const handleAdd = () => {
    const trimmedA = courseA.trim();
    const trimmedB = courseB.trim();

    if (!trimmedA || !trimmedB) return;
    if (trimmedA === trimmedB) return;

    addEquivalency(trimmedA, trimmedB, direction);
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

  // Build display entries, deduplicating bidirectional pairs
  const equivalencyEntries: EquivalencyEntry[] = (() => {
    const entries: EquivalencyEntry[] = [];
    const seen = new Set<string>();

    for (const [courseId, equivalents] of Object.entries(customEquivalencies)) {
      for (const equiv of equivalents) {
        const forwardKey = `${courseId}:${equiv}`;
        const reverseKey = `${equiv}:${courseId}`;

        if (seen.has(forwardKey) || seen.has(reverseKey)) continue;

        const hasReverse = customEquivalencies[equiv]?.includes(courseId) ?? false;

        if (hasReverse) {
          entries.push({ courseA: courseId, courseB: equiv, direction: "bidirectional" });
          seen.add(forwardKey);
          seen.add(reverseKey);
        } else {
          entries.push({ courseA: courseId, courseB: equiv, direction: "a_to_b" });
          seen.add(forwardKey);
        }
      }
    }

    return entries.sort((a, b) => a.courseA.localeCompare(b.courseA));
  })();

  const filteredCoursesA = courseA.length > 0 ? coursesA.slice(0, 10) : [];
  const filteredCoursesB = courseB.length > 0 ? coursesB.slice(0, 10) : [];

  const directionSymbol = direction === "bidirectional" ? "≡" : "→";
  const directionTooltip = direction === "bidirectional"
    ? "Bidirectional: A and B count as each other"
    : "Unidirectional: left counts as right";

  return (
    <div className="space-y-2" data-tutorial="equivalency-manager">
      {/* Add new equivalency */}
      <div className="grid grid-cols-[1fr_auto_1fr] gap-1.5 items-center">
        <div ref={dropdownRefA} className="relative">
          <Input
            placeholder="6.100A"
            value={courseA}
            onChange={(e) => setCourseA(e.target.value)}
            onFocus={() => setShowDropdownA(true)}
            onKeyPress={handleKeyPress}
            className="text-xs h-7 px-2"
          />
          {showDropdownA && filteredCoursesA.length > 0 && (
            <div className="absolute z-50 left-0 right-0 mt-1 bg-popover border border-border rounded-md shadow-lg max-h-48 overflow-y-auto">
              {filteredCoursesA.map((course) => (
                <button
                  key={course.subject_id}
                  onClick={() => { setCourseA(course.subject_id); setShowDropdownA(false); }}
                  className="w-full px-2 py-1.5 text-left hover:bg-accent transition-colors"
                >
                  <div className="font-medium text-xs">{course.subject_id}</div>
                  <div className="text-xs text-muted-foreground line-clamp-1 leading-tight">{course.title}</div>
                </button>
              ))}
            </div>
          )}
        </div>

        <button
          onClick={() => setDirection(d => d === "bidirectional" ? "unidirectional" : "bidirectional")}
          className="text-xs font-mono border border-border rounded px-1.5 py-0.5 hover:bg-accent transition-colors"
          title={directionTooltip}
        >
          {directionSymbol}
        </button>

        <div ref={dropdownRefB} className="relative">
          <Input
            placeholder="6.100L"
            value={courseB}
            onChange={(e) => setCourseB(e.target.value)}
            onFocus={() => setShowDropdownB(true)}
            onKeyPress={handleKeyPress}
            className="text-xs h-7 px-2"
          />
          {showDropdownB && filteredCoursesB.length > 0 && (
            <div className="absolute z-50 left-0 right-0 mt-1 bg-popover border border-border rounded-md shadow-lg max-h-48 overflow-y-auto">
              {filteredCoursesB.map((course) => (
                <button
                  key={course.subject_id}
                  onClick={() => { setCourseB(course.subject_id); setShowDropdownB(false); }}
                  className="w-full px-2 py-1.5 text-left hover:bg-accent transition-colors"
                >
                  <div className="font-medium text-xs">{course.subject_id}</div>
                  <div className="text-xs text-muted-foreground line-clamp-1 leading-tight">{course.title}</div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <Button onClick={handleAdd} disabled={!courseA.trim() || !courseB.trim() || courseA.trim() === courseB.trim()} className="w-full h-7" size="sm">
        Add
      </Button>

      {/* List of existing equivalencies */}
      {equivalencyEntries.length > 0 && (
        <div className="space-y-1.5">
          {equivalencyEntries.map((entry) => {
            const symbol = entry.direction === "bidirectional" ? "≡" : "→";
            return (
              <div
                key={`${entry.courseA}:${entry.courseB}:${entry.direction}`}
                className="flex items-center justify-between p-2 rounded-md border border-border bg-card hover:bg-accent/50 transition-colors"
              >
                <span className="text-xs font-mono">
                  {entry.courseA} {symbol} {entry.courseB}
                </span>
                <Button variant="ghost" size="sm" className="h-6 w-6 p-0 hover:bg-destructive/10 hover:text-destructive" onClick={() => removeEquivalency(entry.courseA, entry.courseB, entry.direction)}>
                  <X className="h-3 w-3" />
                </Button>
              </div>
            );
          })}
        </div>
      )}

      {equivalencyEntries.length === 0 && (
        <div className="text-center py-3 text-xs text-muted-foreground">
          No custom equivalencies
        </div>
      )}
    </div>
  );
}
