
import * as React from "react";
import { X, ChevronDown, ChevronRight, AlertTriangle } from "lucide-react";
import { useOptimizationStore } from "@/stores/optimizationStore";
import { useGraphStore } from "@/stores/roadStore";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { TierSelector } from "./TierSelector";
import type { ObjectiveMetadata } from "@/types/models/optimizer";

interface SelectedObjectiveCardProps {
  objectiveKey: string;
  objective: ObjectiveMetadata;
  isExpanded: boolean;
  onToggleExpanded: () => void;
  viewMode?: string;
}

export function SelectedObjectiveCard({
  objectiveKey,
  objective,
  isExpanded,
  onToggleExpanded,
  viewMode,
}: SelectedObjectiveCardProps) {
  const selectedObjectives = useOptimizationStore((state) => state.selectedObjectives);
  const setObjectives = useOptimizationStore((state) => state.setObjectives);
  const objectiveTiers = useOptimizationStore((state) => state.objectiveTiers);
  const setObjectiveTier = useOptimizationStore((state) => state.setObjectiveTier);
  const lastCostBreakdown = useGraphStore((state) => state.lastCostBreakdown);

  const [showRemoveWarning, setShowRemoveWarning] = React.useState(false);

  const config = selectedObjectives.find(o => o.key === objectiveKey);
  if (!config) return null;

  const isUnremovable = objective.unremovable ?? false;
  const isCategoryRewards = objective.key === 'category_rewards';
  const recommendation = objective.recommendation;
  const tier = objectiveTiers[objectiveKey] ?? objective.defaultTier;
  const costBreakdown = lastCostBreakdown?.[objectiveKey];

  const handleRemoveClick = () => {
    if (recommendation === 'builtin') {
      setShowRemoveWarning(true);
    } else {
      performRemove();
    }
  };

  const performRemove = () => {
    const newObjectives = selectedObjectives.filter(o => o.key !== objectiveKey);
    setObjectives(newObjectives);
    setShowRemoveWarning(false);
  };

  const handleParameterChange = (paramName: string, value: number | boolean | Record<string, string[]> | null) => {
    const newObjectives = selectedObjectives.map(obj =>
      obj.key === objectiveKey
        ? { ...obj, parameters: { ...obj.parameters, [paramName]: value } }
        : obj
    );
    setObjectives(newObjectives);
  };

  return (
    <div className="relative border border-border rounded overflow-hidden" data-tutorial="objective-card">
      {recommendation && !isCategoryRewards && (
        <div className={`absolute inset-0 pointer-events-none rounded ring-1 ring-inset ${recommendation === 'builtin' ? 'ring-red-500/25' : 'ring-blue-500/25'}`} />
      )}
      {recommendation && !isCategoryRewards && isExpanded && objective.hasParameters && (
        <div className="absolute right-3 bottom-1.5 pointer-events-none">
          <span className={`text-xs font-medium select-none tracking-wide uppercase ${recommendation === 'builtin' ? 'text-red-400/30' : 'text-blue-400/30'}`}>
            {recommendation === 'builtin' ? 'built-in' : 'suggested'}
          </span>
        </div>
      )}

      <div className="relative p-3">
        {isCategoryRewards && (
          <div className="absolute inset-0 pointer-events-none opacity-10" style={{
            backgroundImage: 'repeating-linear-gradient(45deg, transparent, transparent 10px, rgb(239 68 68) 10px, rgb(239 68 68) 20px)'
          }} />
        )}
        <div className="relative z-10 flex items-start justify-between gap-2">
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
                onClick={handleRemoveClick}
                className="text-muted-foreground hover:text-red-400 transition-colors shrink-0"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>
      </div>
      {isExpanded && (
        <div className="px-3 pb-3 space-y-2">
          <p className="text-xs text-muted-foreground">{objective.description}</p>
          {recommendation && !isCategoryRewards && !objective.hasParameters && (
            <p className={`text-xs font-medium text-right tracking-wide uppercase ${recommendation === 'builtin' ? 'text-red-400/30' : 'text-blue-400/30'}`}>
              {recommendation === 'builtin' ? 'built-in' : 'suggested'}
            </p>
          )}
          {objective.hasParameters && (
            <div className="space-y-2 pt-1">
              {Object.entries(objective.defaultParameters).map(([paramName, defaultValue]) => {
                // Boolean parameters render as checkbox
                if (typeof defaultValue === 'boolean') {
                  const currentValue = (config.parameters[paramName] as boolean) ?? defaultValue;
                  return (
                    <div key={paramName} className="flex items-center gap-2 min-w-0">
                      <Label className="text-xs text-muted-foreground capitalize shrink-0" style={{ width: '100px' }}>
                        {paramName.replace(/_/g, ' ')}:
                      </Label>
                      <Checkbox
                        checked={currentValue}
                        onCheckedChange={(checked: boolean) => handleParameterChange(paramName, checked)}
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
        </div>
      )}

      {/* Warning dialog for removing recommended objectives */}
      <Dialog open={showRemoveWarning} onOpenChange={setShowRemoveWarning}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-yellow-500" />
              Remove Built-in Objective?
            </DialogTitle>
            <DialogDescription>
              "{objective.name}" is a built-in objective that helps produce better schedules.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <p className="text-sm text-muted-foreground">
              Removing it may lead to unexpected or suboptimal results. Only remove this if you have a specific reason to do so.
            </p>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowRemoveWarning(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={performRemove}>
              Remove Anyway
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
