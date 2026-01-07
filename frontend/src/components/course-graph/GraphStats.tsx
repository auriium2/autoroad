import * as React from "react";
import { useQueries } from "@tanstack/react-query";
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
  const markerOnlyCourses = React.useMemo(() => 
    markers.filter(m =>
      !optimizerNodes.some(on => on.courseId === m.courseId && on.section === m.section)
    ),
    [markers, optimizerNodes]
  );

  // Fetch course details for marker-only courses to get real units
  const markerCourseQueries = useQueries({
    queries: markerOnlyCourses.map(marker => ({
      queryKey: queryKeys.courses.details(marker.courseId),
      queryFn: () => fireroadApi.getCourseDetails(marker.courseId),
      staleTime: 24 * 60 * 60 * 1000, // Course details are static - cache for 24 hours
    }))
  });

  const totalUnits = React.useMemo(() => {
    let total = 0;

    // Add units from optimizer nodes (they have units from backend)
    optimizerNodes.forEach(node => {
      total += node.units || 0;
    });

    // Add units from marker-only courses using fetched data
    markerCourseQueries.forEach(query => {
      if (query.data) {
        total += query.data.total_units || 12; // Fallback to 12 if units missing
      } else {
        total += 12; // Default while loading
      }
    });

    return total;
  }, [optimizerNodes, markerCourseQueries]);

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
