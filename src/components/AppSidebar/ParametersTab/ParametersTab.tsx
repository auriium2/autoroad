import * as React from "react";
import { Label } from "@/components/ui/label";

export function ParametersTab() {
  const [maxUnits, setMaxUnits] = React.useState(60);
  const [minUnits, setMinUnits] = React.useState(36);
  const [preferredSemesterLoad, setPreferredSemesterLoad] = React.useState(48);

  return (
    <div className="flex flex-col h-full p-4 space-y-6">
      <div className="space-y-4">
        <div>
          <Label htmlFor="max-units" className="text-sm font-medium">
            Maximum Units Per Semester
          </Label>
          <div className="flex items-center gap-3 mt-2">
            <input
              id="max-units"
              type="range"
              min="12"
              max="72"
              step="3"
              value={maxUnits}
              onChange={(e) => setMaxUnits(Number(e.target.value))}
              className="flex-1 h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary [&::-webkit-slider-thumb]:cursor-pointer [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:h-4 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-primary [&::-moz-range-thumb]:border-0 [&::-moz-range-thumb]:cursor-pointer"
            />
            <span className="text-sm font-medium w-12 text-right">{maxUnits}</span>
          </div>
        </div>

        <div>
          <Label htmlFor="min-units" className="text-sm font-medium">
            Minimum Units Per Semester
          </Label>
          <div className="flex items-center gap-3 mt-2">
            <input
              id="min-units"
              type="range"
              min="12"
              max="60"
              step="3"
              value={minUnits}
              onChange={(e) => setMinUnits(Number(e.target.value))}
              className="flex-1 h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary [&::-webkit-slider-thumb]:cursor-pointer [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:h-4 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-primary [&::-moz-range-thumb]:border-0 [&::-moz-range-thumb]:cursor-pointer"
            />
            <span className="text-sm font-medium w-12 text-right">{minUnits}</span>
          </div>
        </div>

        <div>
          <Label htmlFor="preferred-load" className="text-sm font-medium">
            Preferred Semester Load
          </Label>
          <div className="flex items-center gap-3 mt-2">
            <input
              id="preferred-load"
              type="range"
              min="12"
              max="72"
              step="3"
              value={preferredSemesterLoad}
              onChange={(e) => setPreferredSemesterLoad(Number(e.target.value))}
              className="flex-1 h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary [&::-webkit-slider-thumb]:cursor-pointer [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:h-4 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-primary [&::-moz-range-thumb]:border-0 [&::-moz-range-thumb]:cursor-pointer"
            />
            <span className="text-sm font-medium w-12 text-right">{preferredSemesterLoad}</span>
          </div>
        </div>
      </div>

      <div className="pt-4 border-t border-border">
        <p className="text-xs text-muted-foreground">
          These parameters will be used when you click the Optimize button to automatically arrange your courses.
        </p>
      </div>
    </div>
  );
}
