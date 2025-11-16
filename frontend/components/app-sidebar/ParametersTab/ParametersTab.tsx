import * as React from "react";
import { Label } from "@/components/ui/label";
import { SimpleSelect } from "@/components/ui/simple-select";
import { ObjectiveSelector } from "./ObjectiveSelector";
import { RequirementSelector } from "./RequirementSelector";
import { useOptimizationStore } from "@/stores/optimizationStore";

const YEAR_OPTIONS = [
  { value: "freshman", label: "Freshman" },
  { value: "sophomore", label: "Sophomore" },
  { value: "junior", label: "Junior" },
  { value: "senior", label: "Senior" },
] satisfies { value: string; label: string }[];

export function ParametersTab() {
  const [activeTab, setActiveTab] = React.useState<'degrees' | 'objectives'>('degrees');
  
  const selectedYear = useOptimizationStore((state) => state.selectedYear);
  const setYear = useOptimizationStore((state) => state.setYear);

  return (
    <div className="flex flex-col h-full">
      {/* Class Selection - Always Visible */}
      <div className="p-4 space-y-2 border-b border-border">
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
        <p className="text-xs text-muted-foreground">
          Use this to pick your year. This is used to determine what classes are valid.
        </p>
      </div>

      {/* Tab Headers */}
      <div className="flex border-b border-border">
        <button
          onClick={() => setActiveTab('degrees')}
          className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
            activeTab === 'degrees'
              ? 'text-foreground border-b-2 border-primary'
              : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          Degrees
        </button>
        <button
          onClick={() => setActiveTab('objectives')}
          className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
            activeTab === 'objectives'
              ? 'text-foreground border-b-2 border-primary'
              : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          Objectives
        </button>
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-y-auto">
        {activeTab === 'degrees' && (
          <div className="p-4">
            <RequirementSelector />
          </div>
        )}

        {activeTab === 'objectives' && (
          <div className="p-4">
            <ObjectiveSelector />
          </div>
        )}
      </div>
    </div>
  );
}
