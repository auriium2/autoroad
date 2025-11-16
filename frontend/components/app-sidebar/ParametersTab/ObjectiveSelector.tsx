"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { optimizerApi, type ObjectiveMetadata, type ObjectiveConfig } from "@/services/optimizer";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { useOptimizationStore } from "@/stores/optimizationStore";

export function ObjectiveSelector() {
  const selectedObjectives = useOptimizationStore((state) => state.selectedObjectives);
  const setObjectives = useOptimizationStore((state) => state.setObjectives);

  const { data, isLoading, error } = useQuery({
    queryKey: ['objectives'],
    queryFn: () => optimizerApi.getObjectives(),
    staleTime: 60 * 60 * 1000, // Cache for 1 hour
  });

  // Initialize with default configuration if no objectives selected
  React.useEffect(() => {
    if (data && selectedObjectives.length === 0) {
      setObjectives(data.defaultConfiguration);
    }
  }, [data, selectedObjectives.length, setObjectives]);

  const handleToggleObjective = (objective: ObjectiveMetadata) => {
    const existing = selectedObjectives.find(o => o.key === objective.key);
    
    if (existing) {
      // Remove objective
      const newObjectives = selectedObjectives.filter(o => o.key !== objective.key);
      // Renormalize weights
      setObjectives(normalizeWeights(newObjectives));
    } else {
      // Add objective with default weight
      const newObjectives = [
        ...selectedObjectives,
        {
          key: objective.key,
          weight: 0.1,
          parameters: { ...objective.defaultParameters },
        },
      ];
      // Renormalize weights
      setObjectives(normalizeWeights(newObjectives));
    }
  };

  const handleWeightChange = (key: string, newWeight: number) => {
    const newObjectives = selectedObjectives.map(obj =>
      obj.key === key ? { ...obj, weight: newWeight } : obj
    );
    setObjectives(normalizeWeights(newObjectives));
  };

  const handleParameterChange = (key: string, paramName: string, value: any) => {
    const newObjectives = selectedObjectives.map(obj =>
      obj.key === key
        ? { ...obj, parameters: { ...obj.parameters, [paramName]: value } }
        : obj
    );
    setObjectives(newObjectives);
  };

  if (isLoading) {
    return <div className="p-4 text-sm text-muted-foreground">Loading objectives...</div>;
  }

  if (error) {
    return <div className="p-4 text-sm text-red-400">Failed to load objectives</div>;
  }

  if (!data) {
    return null;
  }

  // Group objectives by category
  const objectivesByCategory = data.objectives.reduce((acc, obj) => {
    if (!acc[obj.category]) {
      acc[obj.category] = [];
    }
    acc[obj.category].push(obj);
    return acc;
  }, {} as Record<string, ObjectiveMetadata[]>);

  const categoryLabels: Record<string, string> = {
    units: 'Units & Load',
    ratings: 'Course Quality',
    workload: 'Workload Management',
    scheduling: 'Schedule Preferences',
    social: 'Social',
  };

  return (
    <div className="space-y-6">
      {Object.entries(objectivesByCategory).map(([category, objectives]) => (
        <div key={category} className="space-y-3">
          <h3 className="text-sm font-semibold text-foreground">
            {categoryLabels[category] || category}
          </h3>
          
          {objectives.map(objective => {
            const isSelected = selectedObjectives.some(o => o.key === objective.key);
            const config = selectedObjectives.find(o => o.key === objective.key);
            
            return (
              <div key={objective.key} className="space-y-2">
                <div className="flex items-start gap-2">
                  <Checkbox
                    id={objective.key}
                    checked={isSelected}
                    onCheckedChange={() => handleToggleObjective(objective)}
                    className="mt-1"
                  />
                  <div className="flex-1 space-y-1">
                    <Label
                      htmlFor={objective.key}
                      className="text-sm font-medium cursor-pointer"
                    >
                      {objective.name}
                    </Label>
                    <p className="text-xs text-muted-foreground">
                      {objective.description}
                    </p>
                  </div>
                </div>

                {isSelected && config && (
                  <div className="ml-6 space-y-2">
                    <div className="flex items-center gap-3">
                      <Label className="text-xs text-muted-foreground w-16">Weight:</Label>
                      <input
                        type="range"
                        min="0"
                        max="100"
                        step="1"
                        value={Math.round(config.weight * 100)}
                        onChange={(e) => handleWeightChange(objective.key, Number(e.target.value) / 100)}
                        className="flex-1 h-1.5 bg-gray-700 rounded-lg appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary [&::-webkit-slider-thumb]:cursor-pointer"
                      />
                      <span className="text-xs font-medium w-12 text-right">
                        {Math.round(config.weight * 100)}%
                      </span>
                    </div>

                    {objective.hasParameters && (
                      <div className="space-y-2 pt-1">
                        {Object.entries(objective.defaultParameters).map(([paramName, defaultValue]) => (
                          <div key={paramName} className="flex items-center gap-3">
                            <Label className="text-xs text-muted-foreground w-32 capitalize">
                              {paramName.replace(/_/g, ' ')}:
                            </Label>
                            <input
                              type="number"
                              value={config.parameters[paramName] ?? defaultValue}
                              onChange={(e) => handleParameterChange(
                                objective.key,
                                paramName,
                                typeof defaultValue === 'number' && !Number.isInteger(defaultValue)
                                  ? parseFloat(e.target.value)
                                  : parseInt(e.target.value)
                              )}
                              step={typeof defaultValue === 'number' && !Number.isInteger(defaultValue) ? 0.1 : 1}
                              className="flex-1 px-2 py-1 text-xs bg-gray-800 border border-gray-700 rounded"
                            />
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ))}

      <div className="pt-4 border-t border-border">
        <p className="text-xs text-muted-foreground">
          Weights are automatically normalized to sum to 100%. Higher weights prioritize that objective.
        </p>
      </div>
    </div>
  );
}

function normalizeWeights(objectives: ObjectiveConfig[]): ObjectiveConfig[] {
  if (objectives.length === 0) return objectives;
  
  const totalWeight = objectives.reduce((sum, obj) => sum + obj.weight, 0);
  
  if (totalWeight === 0) {
    // If all weights are 0, distribute equally
    return objectives.map(obj => ({ ...obj, weight: 1 / objectives.length }));
  }
  
  // Normalize so weights sum to 1
  return objectives.map(obj => ({
    ...obj,
    weight: obj.weight / totalWeight,
  }));
}
