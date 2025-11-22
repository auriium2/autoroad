import * as React from "react";
import { Label } from "@/components/ui/label";
import { SimpleSelect } from "@/components/ui/simple-select";
import { Checkbox } from "@/components/ui/checkbox";
import { UnifiedParameterSelector } from "./UnifiedParameterSelector";
import { useOptimizationStore } from "@/stores/optimizationStore";

function getGraduationYearOptions() {
  const currentDate = new Date();
  const currentYear = currentDate.getFullYear();
  const currentMonth = currentDate.getMonth(); // 0-11

  // Determine the current academic year
  // If September (month 8) or later, we're in currentYear-currentYear+1 academic year
  // Otherwise, we're in currentYear-1 to currentYear academic year
  const academicYearStart = currentMonth >= 8 ? currentYear : currentYear - 1;

  const freshmanGradYear = academicYearStart + 4;
  return [
    { value: String(freshmanGradYear), label: `Class of ${freshmanGradYear}` },
    { value: String(freshmanGradYear - 1), label: `Class of ${freshmanGradYear - 1}` },
    { value: String(freshmanGradYear - 2), label: `Class of ${freshmanGradYear - 2}` },
    { value: String(freshmanGradYear - 3), label: `Class of ${freshmanGradYear - 3}` },
  ];
}

const YEAR_OPTIONS = getGraduationYearOptions();

export function ParametersTab() {
  const selectedYear = useOptimizationStore((state) => state.selectedYear);
  const setYear = useOptimizationStore((state) => state.setYear);
  const lockPastSemesters = useOptimizationStore((state) => state.lockPastSemesters);
  const setLockPastSemesters = useOptimizationStore((state) => state.setLockPastSemesters);

  return (
    <div className="flex flex-col h-full">
      {/* Class Selection - Always Visible */}
      <div className="p-4 space-y-3 border-b border-border">
        <div className="space-y-2">
          <Label className="text-sm font-medium">
            Select Class
          </Label>
          <SimpleSelect
            className="w-full"
            placeholder="Select Year"
            options={YEAR_OPTIONS}
            value={selectedYear}
            onValueChange={setYear}
          />
        </div>

        {/* Lock Past Semesters */}
        <div className="flex items-start gap-2">
          <Checkbox
            id="lock-past-semesters"
            checked={lockPastSemesters}
            onCheckedChange={(checked) => setLockPastSemesters(!!checked)}
            className="mt-0.5"
          />
          <div className="flex-1">
            <Label
              htmlFor="lock-past-semesters"
              className="text-sm font-medium cursor-pointer"
            >
              Lock Past Semesters
            </Label>
            <p className="text-xs text-muted-foreground mt-1">
              Stop autoroad from time traveling.
            </p>
          </div>
        </div>
      </div>

      {/* Unified Content */}
      <div className="flex-1 overflow-y-auto p-4">
        <UnifiedParameterSelector />
      </div>
    </div>
  );
}
