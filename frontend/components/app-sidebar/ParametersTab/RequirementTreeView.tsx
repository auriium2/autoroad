"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { fireroadApi, type RequirementNode } from "@/services/fireroad";
import { queryKeys } from "@/lib/queryKeys";
import { useGraphStore } from "@/stores/roadStore";
import { useOptimizationStore } from "@/stores/optimizationStore";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { ChevronDown, ChevronRight } from "lucide-react";
import { TierSelector } from "./TierSelector";

interface RequirementTreeViewProps {
  requirementKey: string;
  viewMode?: string;
}

export function RequirementTreeView({ requirementKey, viewMode = "default" }: RequirementTreeViewProps) {
  const markers = useGraphStore((state) => state.markers);
  const optimizerNodes = useGraphStore((state) => state.optimizerNodes);
  const isOptimizing = useGraphStore((state) => state.isOptimizing);
  const lastCostBreakdown = useGraphStore((state) => state.lastCostBreakdown);

  const expandedNodesRecord = useOptimizationStore((state) => state.expandedRequirementNodes);
  const expandedNodes = expandedNodesRecord[requirementKey] || new Set();
  const toggleNodeExpanded = useOptimizationStore((state) => state.toggleRequirementNodeExpanded);
  const requirementSources = useOptimizationStore((state) => state.requirementSources);

  const ids = new Set([
    ...markers.map(m => m.courseId),
    ...optimizerNodes.map(n => n.courseId)
  ]);
  const allCourseIds = Array.from(ids);

  const courseIdsKey = allCourseIds.sort().join(',');
  const source = requirementSources[requirementKey] || 'canonical';

  const { data: requirement, isLoading, error } = useQuery({
    queryKey: queryKeys.requirements.progress(requirementKey, courseIdsKey, source),
    queryFn: async () => {
      console.log(`[RequirementProgress] Fetching progress for ${requirementKey} (${source}) with ${allCourseIds.length} courses:`, allCourseIds);
      const result = await fireroadApi.getRequirementProgress(requirementKey, allCourseIds, source);
      console.log('Progress API result for', requirementKey, ':', result);
      return result;
    },
    staleTime: 10 * 60 * 1000, // Requirement progress can change - cache for 10 minutes
    enabled: !isOptimizing,
  });

  const toggleNode = (path: string) => {
    toggleNodeExpanded(requirementKey, path);
  };

  const requirementTiers = useOptimizationStore((state) => state.requirementTiers);
  const setRequirementTier = useOptimizationStore((state) => state.setRequirementTier);

  // Convert local path (e.g., "root.0") to namespaced path (e.g., "girs.0")
  // The backend uses requirement_key as root, so we replace "root" with it
  const getNamespacedPath = (localPath: string) => localPath.replace(/^root/, requirementKey);

  const renderNode = (req: RequirementNode, path: string, depth: number = 0): React.ReactNode => {
    const isExpanded = expandedNodes.has(path);
    const hasChildren = req.reqs && req.reqs.length > 0;

    // Determine the title
    let title = req.title || req['threshold-desc'];

    // If no title and this is a course requirement, show the course ID
    if (!title && req.req) {
      title = req.req;
    }

    // If still no title, use a generic label
    if (!title) {
      title = 'Requirement';
    }

    // Don't render nodes that have no title and no children (empty nodes)
    if (!title && !hasChildren) {
      return null;
    }

    const progress = req.progress ?? 0;
    const max = req.max ?? 1;
    const percentage = req.percent_fulfilled ?? 0;
    // Use namespaced path for tier storage to avoid collisions between different requirements
    const namespacedPath = getNamespacedPath(path);
    const nodeTier = requirementTiers[namespacedPath] ?? 0;

    return (
      <div key={path} style={{ marginLeft: `${depth * 12}px` }}>
        <div className="flex items-center justify-between py-1 hover:bg-muted/20 px-1 rounded">
          <div className="flex items-center gap-1 flex-1 min-w-0">
            {hasChildren && (
              <button
                onClick={() => toggleNode(path)}
                className="text-muted-foreground hover:text-foreground"
              >
                {isExpanded ? (
                  <ChevronDown className="h-3 w-3" />
                ) : (
                  <ChevronRight className="h-3 w-3" />
                )}
              </button>
            )}
            {!hasChildren && <div className="w-3" />}

            <span className={`text-xs truncate ${req.req ? 'font-mono' : ''}`}>
              {title}
            </span>
          </div>

          <div className="flex items-center gap-1.5">
            <span className="text-xs text-muted-foreground tabular-nums">
              {progress}/{max}
            </span>
            {viewMode === "cost" && lastCostBreakdown && nodeTier > 0 && (() => {
              // green THROBBING cost indicator - use namespaced path
              const categoryKey = `category:${namespacedPath}`;
              const categoryCost = lastCostBreakdown[categoryKey];

              if (categoryCost !== undefined) {
                return (
                  <span className="text-xs font-mono tabular-nums text-green-400 animate-pulse" title={`Category reward for ${namespacedPath}`}>
                    {categoryCost}
                  </span>
                );
              }
              return null;
            })()}
            <TierSelector
              tier={nodeTier}
              onChange={(tier) => setRequirementTier(namespacedPath, tier)}
              maxTier={3}
            />
          </div>
        </div>

        <div className="ml-4 mr-1">
          <Progress value={percentage} className="h-1" />
        </div>

        {hasChildren && isExpanded && (
          <div>
            {req.reqs!.map((child, idx) => renderNode(child, `${path}.${idx}`, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  if (isOptimizing) {
    return <div className="text-xs text-muted-foreground">Optimizing schedule...</div>;
  }

  if (isLoading) {
    return (
      <div className="space-y-3">
        <div className="space-y-2 pb-2 border-b border-border">
          <div className="flex items-center justify-between px-1">
            <Skeleton className="h-4 w-28 bg-muted" />
            <Skeleton className="h-4 w-10 bg-muted" />
          </div>
          <div className="mx-1">
            <Skeleton className="h-1 w-full bg-muted" />
          </div>
        </div>
        <div className="space-y-2">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="space-y-1">
              <div className="flex items-center justify-between py-1 px-1">
                <Skeleton className="h-3.5 w-36 bg-muted" />
                <Skeleton className="h-3.5 w-14 bg-muted" />
              </div>
              <div className="ml-4 mr-1">
                <Skeleton className="h-1 w-full bg-muted" />
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (!requirement) {
    return (
      <div className="text-xs text-red-400">
        Failed to load requirement
        {error && <div className="text-xs mt-1">{String(error)}</div>}
      </div>
    );
  }

  // Calculate overall progress from the top-level requirements
  const rootProgress = requirement.reqs
    ? requirement.reqs.reduce((acc, req) => ({
        progress: (acc.progress ?? 0) + (req.progress ?? 0),
        max: (acc.max ?? 0) + (req.max ?? 1),
      }), { progress: 0, max: 0 })
    : { progress: 0, max: 0 };

  const rootPercentage = (rootProgress.max ?? 0) > 0
    ? ((rootProgress.progress ?? 0) / (rootProgress.max ?? 1)) * 100
    : 0;

  return (
    <div className="space-y-2">
      <div className="space-y-1 pb-2 border-b border-border">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium">Overall Progress</span>
          <span className="text-xs text-muted-foreground tabular-nums">
            {rootProgress.progress}/{rootProgress.max}
          </span>
        </div>
        <Progress value={rootPercentage} className="h-1" />
      </div>

      <div>
        {requirement.reqs?.map((req, idx) => renderNode(req, `root.${idx}`, 0))}
      </div>
    </div>
  );
}
