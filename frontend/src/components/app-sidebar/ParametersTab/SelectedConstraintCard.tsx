
import * as React from "react";
import { X } from "lucide-react";
import { useOptimizationStore } from "@/stores/optimizationStore";
import { Label } from "@/components/ui/label";
import type { HardConstraintMetadata } from "@/types/models/optimizer";

interface SelectedConstraintCardProps {
  constraint: HardConstraintMetadata;
}

export function SelectedConstraintCard({ constraint }: SelectedConstraintCardProps) {
  const toggleHardConstraint = useOptimizationStore((state) => state.toggleHardConstraint);

  return (
    <div className="relative border border-border rounded overflow-hidden">
      <div className="absolute inset-0 pointer-events-none bg-gradient-to-tr from-transparent to-purple-500/15" />

      <div className="relative z-10 p-3">
        <div className="flex items-start gap-2">
          <div className="flex-1">
            <div className="flex items-center justify-between">
              <Label className="text-sm font-semibold">{constraint.name}</Label>
              <button
                onClick={() => toggleHardConstraint(constraint.key)}
                className="text-muted-foreground hover:text-red-400 transition-colors shrink-0"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <p className="text-xs text-muted-foreground mt-1">{constraint.description}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
