
import * as React from "react";
import { X, ChevronDown, ChevronRight } from "lucide-react";
import { useOptimizationStore } from "@/stores/optimizationStore";
import { RequirementTreeView } from "./RequirementTreeView";
import type { RequirementMetadata, RequirementTree } from "@/services/fireroad";

interface SelectedRequirementCardProps {
  requirementKey: string;
  metadata?: RequirementMetadata;
  viewMode?: string;
  requirementProgress?: RequirementTree;
  isProgressLoading?: boolean;
  validCourseIds?: Set<string>;
}

export function SelectedRequirementCard({
  requirementKey,
  metadata,
  viewMode,
  requirementProgress,
  isProgressLoading,
  validCourseIds,
}: SelectedRequirementCardProps) {
  const expandedRequirements = useOptimizationStore((state) => state.expandedRequirements);
  const toggleRequirementExpanded = useOptimizationStore((state) => state.toggleRequirementExpanded);
  const requirementSources = useOptimizationStore((state) => state.requirementSources);
  const setRequirementSource = useOptimizationStore((state) => state.setRequirementSource);
  const removeRequirement = useOptimizationStore((state) => state.removeRequirement);

  const displayName = metadata?.['medium-title'] || metadata?.['title-no-degree'] || metadata?.title || requirementKey;
  const isExpanded = expandedRequirements.includes(requirementKey);
  const storedSource = requirementSources[requirementKey] || 'canonical';
  const currentSource = metadata?.source === 'beta' && !metadata?.hasBothVersions ? 'beta' : storedSource;
  const hasBothVersions = metadata?.hasBothVersions || false;

  return (
    <div className="relative border border-border rounded overflow-hidden" data-tutorial="requirement-card" data-requirement-key={requirementKey}>
      <div className={`absolute inset-0 pointer-events-none bg-gradient-to-tr from-transparent ${currentSource === 'beta' ? 'to-cyan-400/15' : 'to-blue-500/15'}`} />

      <div className="relative z-10 p-3 space-y-2">
        <div className="flex items-start justify-between gap-2">
          <button
            onClick={() => toggleRequirementExpanded(requirementKey)}
            className="flex items-center gap-1 flex-1 text-left min-w-0"
          >
            {isExpanded ? <ChevronDown className="h-4 w-4 shrink-0" /> : <ChevronRight className="h-4 w-4 shrink-0" />}
            <span className="text-sm font-semibold truncate">{displayName}</span>
            {currentSource === 'beta' && (
              <span className="ml-1 px-1.5 py-0.5 text-[9px] font-medium bg-cyan-500/10 text-cyan-400/60 rounded shrink-0">
                BETA
              </span>
            )}
          </button>
          <div className="flex items-center gap-1 shrink-0">
            {hasBothVersions && (
              <button
                onClick={() => {
                  const newSource = currentSource === 'canonical' ? 'beta' : 'canonical';
                  setRequirementSource(requirementKey, newSource);
                }}
                className="px-1.5 py-0.5 text-[10px] font-medium bg-muted hover:bg-muted/70 text-muted-foreground hover:text-foreground rounded transition-colors"
                title={`Switch to ${currentSource === 'canonical' ? 'beta' : 'canonical'} version`}
              >
                {currentSource === 'canonical' ? '→β' : '→C'}
              </button>
            )}
            <button
              onClick={() => removeRequirement(requirementKey)}
              className="text-muted-foreground hover:text-red-400 transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {isExpanded && (
          <div className="pt-2">
            <RequirementTreeView
              requirementKey={requirementKey}
              viewMode={viewMode}
              requirement={requirementProgress}
              isLoading={isProgressLoading}
              validCourseIds={validCourseIds}
            />
          </div>
        )}
      </div>
    </div>
  );
}
