import * as React from "react";
import { Label } from "@/components/ui/label";
import { SimpleSelect } from "@/components/ui/simple-select";
import { Checkbox } from "@/components/ui/checkbox";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import { OptimizationParametersPanel } from "./OptimizationParametersPanel";
import { useOptimizationStore } from "@/stores/optimizationStore";
import { useGraphStore } from "@/stores/roadStore";
import { getGraduationYearOptions } from "@/lib/semesterUtils";

const YEAR_OPTIONS = getGraduationYearOptions();

interface ParametersTabProps {
  viewMode?: string;
}

export function ParametersTab({ viewMode }: ParametersTabProps) {
  const selectedYear = useOptimizationStore((state) => state.selectedYear);
  const setYear = useOptimizationStore((state) => state.setYear);
  const lockPastSemesters = useOptimizationStore((state) => state.lockPastSemesters);
  const setLockPastSemesters = useOptimizationStore((state) => state.setLockPastSemesters);
  const isOptimizing = useGraphStore((state) => state.isOptimizing);

  return (
    <div className="flex flex-col h-full">
      {/* Class Selection - Always Visible */}
      <div className="p-4 space-y-3 border-b border-border">
        <div className="space-y-2" data-tutorial="class-year">
          <Label className="text-sm font-medium">
            Select Class
          </Label>
          <SimpleSelect
            className="w-full"
            placeholder="Select Year"
            options={YEAR_OPTIONS}
            value={selectedYear}
            onValueChange={setYear}
            disabled={isOptimizing}
          />
        </div>

        {/* Lock Past Semesters */}
        <div className="flex items-center justify-between gap-3" data-tutorial="freeze-past">
          <div className="flex-1">
            <Label
              htmlFor="lock-past-semesters"
              className={`text-sm font-medium cursor-pointer ${isOptimizing ? 'opacity-50' : ''}`}
            >
              Freeze Past Semesters
            </Label>
            <p className="text-xs text-muted-foreground mt-0.5">
              Stops autoroad from{' '}
              <Tooltip>
                <TooltipTrigger asChild>
                  <span className="underline decoration-dotted cursor-help">time traveling</span>
                </TooltipTrigger>
                <TooltipContent>
                  This parameter changes whether autoroad can place classes in semesters that you have already taken (determined by your selected class year)
                </TooltipContent>
              </Tooltip>
              .
            </p>
          </div>
          <Checkbox
            id="lock-past-semesters"
            checked={lockPastSemesters}
            onCheckedChange={(checked: boolean) => setLockPastSemesters(!!checked)}
            disabled={isOptimizing}
          />
        </div>
        <p className="text-[10px] text-muted-foreground/70">
          5-year plans and MEng support coming soon.
        </p>
      </div>

      {/* Unified Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {isOptimizing ? (
          <div className="text-sm text-muted-foreground py-4">
            Optimizing schedule, please wait...
          </div>
        ) : (
          <OptimizationParametersPanel viewMode={viewMode} />
        )}
      </div>
    </div>
  );
}
