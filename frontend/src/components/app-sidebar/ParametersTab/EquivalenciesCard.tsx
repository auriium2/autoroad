import * as React from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { useOptimizationStore } from "@/stores/optimizationStore";
import { EquivalencyManager } from "./EquivalencyManager";

export function EquivalenciesCard() {
  const [isExpanded, setIsExpanded] = React.useState(false);

  const customEquivalencies = useOptimizationStore((state) => state.customEquivalencies);
  const addCustomEquivalency = useOptimizationStore((state) => state.addCustomEquivalency);
  const removeCustomEquivalency = useOptimizationStore((state) => state.removeCustomEquivalency);

  const handleChange = (newEquiv: Record<string, string[]>) => {
    // Diff against current state and apply adds/removes
    const currentPairs = new Set<string>();
    const newPairs = new Set<string>();

    for (const [a, bs] of Object.entries(customEquivalencies)) {
      for (const b of bs) {
        const key = [a, b].sort().join(":");
        currentPairs.add(key);
      }
    }

    for (const [a, bs] of Object.entries(newEquiv)) {
      for (const b of bs) {
        const key = [a, b].sort().join(":");
        newPairs.add(key);
      }
    }

    // Remove pairs no longer present
    for (const pair of currentPairs) {
      if (!newPairs.has(pair)) {
        const [a, b] = pair.split(":");
        removeCustomEquivalency(a, b);
      }
    }

    // Add new pairs
    for (const pair of newPairs) {
      if (!currentPairs.has(pair)) {
        const [a, b] = pair.split(":");
        addCustomEquivalency(a, b);
      }
    }
  };

  return (
    <div className="relative border border-border rounded overflow-hidden">

      <div className="relative p-3">
        <div className="absolute inset-0 pointer-events-none opacity-10" style={{
          backgroundImage: 'repeating-linear-gradient(45deg, transparent, transparent 10px, rgb(239 68 68) 10px, rgb(239 68 68) 20px)'
        }} />
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="relative z-10 flex items-center gap-1 w-full text-left"
        >
          {isExpanded ? <ChevronDown className="h-4 w-4 shrink-0" /> : <ChevronRight className="h-4 w-4 shrink-0" />}
          <span className="text-sm font-semibold">Equivalencies</span>
        </button>
      </div>

      {isExpanded && (
        <div className="px-3 pb-3 space-y-2">
          <p></p>
          <p className="text-xs text-muted-foreground">
            Define custom course equivalencies. Equivalent courses can substitute for each other in prerequisites and requirements.
          </p>
          <EquivalencyManager
            customEquivalencies={customEquivalencies}
            onChange={handleChange}
          />
        </div>
      )}
    </div>
  );
}
