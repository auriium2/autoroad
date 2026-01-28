import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { fireroadApi } from "@/services/fireroad";
import { queryKeys } from "@/lib/queryKeys";
import type { Marker, OptimizerNode } from "@/stores/roadStore";

interface GraphStatsProps {
  viewMode: string;
  markers: Marker[];
  optimizerNodes: OptimizerNode[];
  lastCostBreakdown: Record<string, number> | null;
}

export function GraphStats({ 
  viewMode, 
  markers, 
  optimizerNodes, 
  lastCostBreakdown 
}: GraphStatsProps) {
  // Get marker-only courses (not covered by optimizer)
  const markerOnlyCourses = markers.filter(m =>
    !optimizerNodes.some(on => on.courseId === m.courseId && on.section === m.section)
  );

  // Get unique course IDs for batch fetch
  const courseIds = Array.from(new Set(markerOnlyCourses.map(m => m.courseId))).sort();
  const courseIdsKey = courseIds.join(',');

  // Batch fetch course details for marker-only courses
  const { data: courseDetailsMap } = useQuery({
    queryKey: queryKeys.courses.batch(courseIdsKey),
    queryFn: () => fireroadApi.getCourseDetailsBatch(courseIds),
    staleTime: 24 * 60 * 60 * 1000,
    enabled: courseIds.length > 0,
  });

  let totalUnits = 0;
  for (const node of optimizerNodes) {
    totalUnits += node.units || 0;
  }
  for (const marker of markerOnlyCourses) {
    const courseDetails = courseDetailsMap?.[marker.courseId];
    totalUnits += courseDetails?.total_units || 12; // Fallback to 12 if units missing or loading
  }

  // Calculate total cost from cost breakdown
  const totalCost = lastCostBreakdown
    ? Object.values(lastCostBreakdown).reduce((sum, cost) => sum + cost, 0)
    : null;

  if (viewMode === "default") return null;

  return (
    <div className="absolute top-12 right-4 z-[50] pointer-events-none space-y-1 text-right">
      <div className="text-white font-mono text-sm">
        Total Units: <span className="font-bold">{totalUnits}</span>
      </div>
      {viewMode === "cost" && totalCost !== null && (
        <div className="text-orange-400 font-mono text-sm animate-pulse">
          Total Cost: <span className="font-bold">{totalCost}</span>
        </div>
      )}
    </div>
  );
}
