
import * as React from "react";
import { X, ChevronDown, ChevronRight } from "lucide-react";
import { useOptimizationStore } from "@/stores/optimizationStore";
import { useGraphStore } from "@/stores/roadStore";
import { Label } from "@/components/ui/label";
import { TierSelector } from "./TierSelector";
import { EquivalencyManager } from "./EquivalencyManager";
import type { ObjectiveMetadata } from "@/types/models/optimizer";

interface SelectedObjectiveCardProps {
  objectiveKey: string;
  objective: ObjectiveMetadata;
  isRecommended: boolean;
  isExpanded: boolean;
  onToggleExpanded: () => void;
  viewMode?: string;
}

export function SelectedObjectiveCard({
  objectiveKey,
  objective,
  isRecommended,
  isExpanded,
  onToggleExpanded,
  viewMode,
}: SelectedObjectiveCardProps) {
  const selectedObjectives = useOptimizationStore((state) => state.selectedObjectives);
  const setObjectives = useOptimizationStore((state) => state.setObjectives);
  const objectiveTiers = useOptimizationStore((state) => state.objectiveTiers);
  const setObjectiveTier = useOptimizationStore((state) => state.setObjectiveTier);
  const lastCostBreakdown = useGraphStore((state) => state.lastCostBreakdown);

  const config = selectedObjectives.find(o => o.key === objectiveKey);
  if (!config) return null;

  const isUnremovable = objective.unremovable ?? false;
  const isCategoryRewards = objective.key === 'category_rewards';
  const tier = objectiveTiers[objectiveKey] ?? objective.defaultTier;
  const costBreakdown = lastCostBreakdown?.[objectiveKey];

  const handleRemove = () => {
    const newObjectives = selectedObjectives.filter(o => o.key !== objectiveKey);
    setObjectives(newObjectives);
  };

  const handleParameterChange = (paramName: string, value: number | Record<string, string[]> | null) => {
    const newObjectives = selectedObjectives.map(obj =>
      obj.key === objectiveKey
        ? { ...obj, parameters: { ...obj.parameters, [paramName]: value } }
        : obj
    );
    setObjectives(newObjectives);
  };

  return (
    <div className="relative border border-border rounded overflow-hidden">
      {isCategoryRewards && (
        <div className="absolute inset-0 pointer-events-none opacity-10" style={{
          backgroundImage: 'repeating-linear-gradient(45deg, transparent, transparent 10px, rgb(239 68 68) 10px, rgb(239 68 68) 20px)'
        }} />
      )}
      {isRecommended && !isCategoryRewards && (
        <div className="absolute inset-0 pointer-events-none bg-gradient-to-tr from-transparent to-red-500/15" />
      )}

      <div className="relative z-10 p-3 space-y-2">
        <div className="flex items-start justify-between gap-2">
          <button
            onClick={onToggleExpanded}
            className="flex items-center gap-1 flex-1 text-left"
          >
            {isExpanded ? <ChevronDown className="h-4 w-4 shrink-0" /> : <ChevronRight className="h-4 w-4 shrink-0" />}
            <span className="text-sm font-semibold">{objective.name}</span>
          </button>
          <div className="flex items-center gap-1.5">
            {viewMode === "cost" && costBreakdown !== undefined && (
              <span className="text-xs font-mono tabular-nums text-orange-400 animate-pulse">
                {costBreakdown}
              </span>
            )}
            {!isCategoryRewards && (
              <TierSelector
                tier={tier}
                onChange={(newTier) => setObjectiveTier(objectiveKey, newTier)}
                minTier={1}
              />
            )}
            {!isUnremovable && (
              <button
                onClick={handleRemove}
                className="text-muted-foreground hover:text-red-400 transition-colors shrink-0"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>
        {isExpanded && (
          <>
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">{objective.description}</p>
            </div>
            {objective.hasParameters && (
              <div className="space-y-2 pt-1">
                {Object.entries(objective.defaultParameters).map(([paramName, defaultValue]) => {
                  if (paramName === 'custom_equivalencies') {
                    const currentEquiv = config.parameters[paramName];
                    const equivValue = currentEquiv === null || currentEquiv === undefined ? {} : currentEquiv;
                    return (
                      <div key={paramName} className="space-y-2">
                        <Label className="text-xs font-medium">Custom Equivalencies</Label>
                        <EquivalencyManager
                          customEquivalencies={equivValue as Record<string, string[]>}
                          onChange={(newEquiv) => handleParameterChange(paramName, newEquiv)}
                        />
                      </div>
                    );
                  }

                  return (
                    <div key={paramName} className="flex items-center gap-2 min-w-0">
                      <Label className="text-xs text-muted-foreground capitalize shrink-0" style={{ width: '100px' }}>
                        {paramName.replace(/_/g, ' ')}:
                      </Label>
                      <input
                        type="number"
                        value={(config.parameters[paramName] as number) ?? defaultValue}
                        onChange={(e) => handleParameterChange(
                          paramName,
                          typeof defaultValue === 'number' && !Number.isInteger(defaultValue)
                            ? parseFloat(e.target.value)
                            : parseInt(e.target.value)
                        )}
                        step={typeof defaultValue === 'number' && !Number.isInteger(defaultValue) ? 0.1 : 1}
                        className="w-14 px-2 py-1 text-xs bg-gray-800 border border-gray-700 rounded shrink-0 tabular-nums"
                      />
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
