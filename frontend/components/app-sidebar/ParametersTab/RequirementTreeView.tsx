"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { optimizerApi, type RequirementNode } from "@/services/optimizer";
import { useGraphStore } from "@/stores/roadStore";
import { useOptimizationStore } from "@/stores/optimizationStore";
import { Progress } from "@/components/ui/progress";
import { ChevronDown, ChevronRight } from "lucide-react";

interface RequirementTreeViewProps {
  requirementKey: string;
}

export function RequirementTreeView({ requirementKey }: RequirementTreeViewProps) {
  const markers = useGraphStore((state) => state.markers);
  const optimizerNodes = useGraphStore((state) => state.optimizerNodes);
  const isOptimizing = useGraphStore((state) => state.isOptimizing);
  
  const expandedNodesRecord = useOptimizationStore((state) => state.expandedRequirementNodes);
  const expandedNodes = React.useMemo(
    () => expandedNodesRecord[requirementKey] || new Set(),
    [expandedNodesRecord, requirementKey]
  );
  const toggleNodeExpanded = useOptimizationStore((state) => state.toggleRequirementNodeExpanded);
  
  const allCourseIds = React.useMemo(() => {
    const ids = new Set([
      ...markers.map(m => m.courseId),
      ...optimizerNodes.map(n => n.courseId)
    ]);
    return Array.from(ids);
  }, [markers, optimizerNodes]);

  const courseIdsKey = React.useMemo(() => 
    allCourseIds.sort().join(','),
    [allCourseIds]
  );

  const { data: requirement, isLoading, error } = useQuery({
    queryKey: ['requirement-progress', requirementKey, courseIdsKey],
    queryFn: async () => {
      console.log(`[RequirementProgress] Fetching progress for ${requirementKey} with ${allCourseIds.length} courses:`, allCourseIds);
      const result = await optimizerApi.getRequirementProgress(requirementKey, allCourseIds);
      console.log('Progress API result for', requirementKey, ':', result);
      return result;
    },
    staleTime: 5000,
  });

  const toggleNode = (path: string) => {
    toggleNodeExpanded(requirementKey, path);
  };

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
          
          <span className="text-xs text-muted-foreground ml-2 tabular-nums">
            {progress}/{max}
          </span>
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
    return <div className="text-xs text-muted-foreground">Loading requirement tree...</div>;
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
        progress: acc.progress + (req.progress ?? 0),
        max: acc.max + (req.max ?? 1),
      }), { progress: 0, max: 0 })
    : { progress: 0, max: 0 };

  const rootPercentage = rootProgress.max > 0 
    ? (rootProgress.progress / rootProgress.max) * 100 
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
