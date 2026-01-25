
import * as React from "react";
import { X } from "lucide-react";
import { useOptimizationStore } from "@/stores/optimizationStore";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import type { HardConstraintMetadata, ConstraintConfig } from "@/types/models/optimizer";

interface SelectedConstraintCardProps {
  metadata: HardConstraintMetadata;
  config: ConstraintConfig;
}

export function SelectedConstraintCard({ metadata, config }: SelectedConstraintCardProps) {
  const toggleHardConstraint = useOptimizationStore((state) => state.toggleHardConstraint);
  const updateConstraintParameters = useOptimizationStore((state) => state.updateConstraintParameters);

  const handleParameterChange = (paramKey: string, value: unknown) => {
    updateConstraintParameters(metadata.key, {
      ...config.parameters,
      [paramKey]: value,
    });
  };

  const getParamValue = (paramKey: string): unknown => {
    return config.parameters[paramKey] ?? metadata.defaultParameters[paramKey];
  };

  return (
    <div className="relative border border-border rounded overflow-hidden">
      <div className="absolute inset-0 pointer-events-none bg-gradient-to-tr from-transparent to-purple-500/15" />

      <div className="relative z-10 p-3">
        <div className="flex items-start gap-2">
          <div className="flex-1">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Label className="text-sm font-semibold">{metadata.name}</Label>
                {metadata.beta && (
                  <span className="px-1.5 py-0.5 text-[9px] font-medium bg-cyan-500/10 text-cyan-400/60 rounded">BETA</span>
                )}
              </div>
              <button
                onClick={() => toggleHardConstraint(metadata.key)}
                className="text-muted-foreground hover:text-red-400 transition-colors shrink-0"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <p className="text-xs text-muted-foreground mt-1">{metadata.description}</p>
            
            {metadata.hasParameters && Object.keys(metadata.parameterTypes).length > 0 && (
              <div className="mt-2 space-y-2 pt-1">
                {Object.entries(metadata.parameterTypes).map(([paramKey, paramType]) => (
                  <div key={paramKey} className="flex items-center gap-2 min-w-0">
                    {paramType === 'bool' ? (
                      <>
                        <Checkbox
                          id={`${metadata.key}-${paramKey}`}
                          checked={Boolean(getParamValue(paramKey))}
                          onCheckedChange={(checked: boolean) => handleParameterChange(paramKey, checked)}
                        />
                        <Label htmlFor={`${metadata.key}-${paramKey}`} className="text-xs text-muted-foreground capitalize cursor-pointer">
                          {paramKey.replace(/_/g, ' ')}
                        </Label>
                      </>
                    ) : (
                      <>
                        <Label className="text-xs text-muted-foreground capitalize shrink-0" style={{ width: '100px' }}>
                          {paramKey.replace(/_/g, ' ')}:
                        </Label>
                        <input
                          type="text"
                          value={String(getParamValue(paramKey) ?? '')}
                          onChange={(e) => handleParameterChange(paramKey, e.target.value)}
                          className="w-24 px-2 py-1 text-xs bg-gray-800 border border-gray-700 rounded shrink-0"
                          placeholder={String(metadata.defaultParameters[paramKey] ?? '')}
                        />
                      </>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
