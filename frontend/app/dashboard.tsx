"use client";

import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";
import { AppSidebar } from "@/components/app-sidebar";
import { StarOnGithubPopup } from "@/components/StarOnGithubPopup";
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { Button } from "@/components/ui/button";
import { Download, Upload, Loader2, Trash2, UserX, BrainCircuit, X } from "lucide-react";
import { HealthIndicator } from "@/components/ui/health-indicator";
import { CourseGraphFlow } from "@/components/course-graph/CourseGraphFlow";
import { DashboardAlerts } from "@/components/DashboardAlerts";
import { RequirementPrefetcher } from "@/components/RequirementPrefetcher";
import { useGraphStore } from "@/stores/roadStore";
import { Toaster } from "@/components/ui/toaster";
import { toast as showToast } from "@/hooks/useToast";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useOptimizationStore } from "@/stores/optimizationStore";
import { exportToRoadFormat, importFromRoadFormat, downloadRoadFile, uploadRoadFile } from "@/lib/roadFormat";
import { fireroadApi } from "@/services/fireroad";
import { prefetchCourses } from "@/lib/coursePrefetch";

export default function Dashboard() {
  const [isExporting, setIsExporting] = React.useState(false);
  const [isImporting, setIsImporting] = React.useState(false);
  const [viewMode, setViewMode] = React.useState<string>("default");
  const [optimizationStartTime, setOptimizationStartTime] = React.useState<number | null>(null);
  const [timeElapsed, setTimeElapsed] = React.useState(0);

  const queryClient = useQueryClient();
  const selectedRequirements = useOptimizationStore((state) => state.selectedRequirements);

  // Get store functions and state
  const optimizeRoadFromStore = useGraphStore(state => state.optimizeRoad);
  const cancelOptimization = useGraphStore(state => state.cancelOptimization);
  const optimizationProgress = useGraphStore(state => state.optimizationProgress);
  const markers = useGraphStore(state => state.markers);
  const optimizerNodes = useGraphStore(state => state.optimizerNodes);
  const loadRoadData = useGraphStore(state => state.loadRoadData);
  const lastOptimizationStatus = useGraphStore(state => state.lastOptimizationStatus);
  const isOptimizing = useGraphStore(state => state.isOptimizing);

  const prevStatusRef = React.useRef<string | null>(null);

  const SOLVER_TIMEOUT_SECONDS = 30;

  // Track optimization time
  React.useEffect(() => {
    if (isOptimizing && !optimizationStartTime) {
      setOptimizationStartTime(Date.now());
    } else if (!isOptimizing && optimizationStartTime) {
      setOptimizationStartTime(null);
      setTimeElapsed(0);
    }
  }, [isOptimizing, optimizationStartTime]);

  // Update elapsed time during optimization
  React.useEffect(() => {
    if (!isOptimizing || !optimizationStartTime) return;
    const interval = setInterval(() => {
      setTimeElapsed((Date.now() - optimizationStartTime) / 1000);
    }, 250);

    return () => clearInterval(interval);
  }, [isOptimizing, optimizationStartTime]);

  // Prefetch courses from user's schedule on app load
  React.useEffect(() => {
    const courseIds = [
      ...markers.map(m => m.courseId),
      ...optimizerNodes.map(n => n.courseId)
    ];

    if (courseIds.length > 0) {
      prefetchCourses(queryClient, courseIds);
    }
  }, []); // Only run once on mount

  React.useEffect(() => {
    console.log('[Dashboard] lastOptimizationStatus changed:', lastOptimizationStatus, 'prev:', prevStatusRef.current);
    if (lastOptimizationStatus === 'OPTIMAL' && prevStatusRef.current !== 'OPTIMAL') {
      showToast({
        title: "Optimal solution found!",
        description: "This is the best possible schedule given your constraints and objectives. Note: Results are optimal only in the mathematical sense given your specific objective function and might be wonky to a human",
        duration: 5000,
      });
    }
    prevStatusRef.current = lastOptimizationStatus;
  }, [lastOptimizationStatus]);

  const handleClearMarkers = () => {
    loadRoadData({ markers: [] });
    showToast({
      title: "Markers cleared",
      description: "All course markers have been removed",
      duration: 2000,
    });
  };

  const handleClearOptimizer = () => {
    loadRoadData({ optimizerNodes: [] });
    showToast({
      title: "Optimizer results cleared",
      description: "All optimizer-suggested courses have been removed",
      duration: 2000,
    });
  };

  const handleExport = async () => {
    try {
      setIsExporting(true);

      const roadData = await exportToRoadFormat(
        markers,
        selectedRequirements,
        async (courseId) => {
          const details = await fireroadApi.getCourseDetails(courseId);
          return {
            name: details.name,
            units: details.units,
          };
        }
      );

      downloadRoadFile(roadData);

      showToast({
        title: "Export successful",
        description: "Your schedule has been exported to .road format",
        duration: 3000,
      });
    } catch (error) {
      console.error('Error during export:', error);
      showToast({
        title: "Export failed",
        description: error instanceof Error ? error.message : "Unknown error occurred",
        variant: "destructive",
        duration: 5000,
      });
    } finally {
      setIsExporting(false);
    }
  };

  const handleImport = async () => {
    try {
      setIsImporting(true);

      const roadData = await uploadRoadFile();

      if (!roadData) {
        return;
      }

      const { markers: importedMarkers, warnings } = importFromRoadFormat(roadData);

      loadRoadData({ markers: importedMarkers });

      if (warnings.length > 0) {
        showToast({
          title: "Import completed with warnings",
          description: `Imported ${importedMarkers.length} courses. ${warnings.length} generic requirement(s) skipped.`,
          variant: "destructive",
          duration: 5000,
        });
        // Log warnings to console for user to see details
        console.warn('Import warnings:', warnings);
        warnings.forEach(warning => console.warn('- ' + warning));
      } else {
        showToast({
          title: "Import successful",
          description: `Imported ${importedMarkers.length} courses from .road file`,
          duration: 3000,
        });
      }
    } catch (error) {
      console.error('Error during import:', error);
      showToast({
        title: "Import failed",
        description: error instanceof Error ? error.message : "Unknown error occurred",
        variant: "destructive",
        duration: 5000,
      });
    } finally {
      setIsImporting(false);
    }
  };

  const handleOptimize = async () => {
    try {
      const result = await optimizeRoadFromStore(undefined, true);

      if (!result.success) {
        showToast({
          title: "Optimization failed",
          description: result.error || "Optimization failed",
          variant: "destructive",
          duration: 10000,
        });
      } else {
        showToast({
          title: "Optimization complete",
          description: "Your courses should satisfy degree requirements, but it might not be the absolute best possible. You may be able to improve it further!",
          duration: 3000,
        });
      }

    } catch (error) {
      console.error('Error during optimization:', error);
      showToast({
        title: "Optimization failed",
        description: error instanceof Error ? error.message : "Unknown error occurred",
        variant: "destructive",
        duration: 8000,
      });
    }
  };
  return (
    <SidebarProvider defaultOpen={true}>
      <RequirementPrefetcher />
      <div className="flex w-screen h-screen">
        <AppSidebar viewMode={viewMode} />
        <SidebarInset className="flex-1 min-w-0 z-0 flex flex-col">
          <header className="flex h-16 shrink-0 items-center gap-2 border-b border-border/50 px-4 relative z-10 glass dark:glass-dark">
            <div className="flex items-center gap-2">
              <SidebarTrigger />
              <HealthIndicator />
            </div>
            <div className="ml-auto flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={handleImport} disabled={isImporting}>
                <Upload className="h-4 w-4" />
                {isImporting ? "Importing..." : "Import"}
              </Button>
              <Button variant="outline" size="sm" onClick={handleExport} disabled={isExporting}>
                <Download className="h-4 w-4" />
                {isExporting ? "Exporting..." : "Export"}
              </Button>
            </div>
          </header>
          <div className="flex flex-col p-4 gap-4 flex-grow min-h-0 relative z-0">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-3xl font-bold tracking-tight">Autoroad</h1>

              </div>
              <div className="flex items-center gap-2">
                <Select value={viewMode} onValueChange={setViewMode}>
                  <SelectTrigger className="w-[140px]">
                    <SelectValue placeholder="View mode" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="default">Friendly view</SelectItem>
                    <SelectItem value="cost">Nerd view</SelectItem>
                  </SelectContent>
                </Select>

                <Tooltip>
                  <TooltipTrigger asChild>
                    <span className="inline-block">
                      <Button size="icon" variant="outline" onClick={handleClearMarkers} disabled={markers.length === 0} className="h-8 w-8">
                        <UserX className="h-4 w-4" />
                      </Button>
                    </span>
                  </TooltipTrigger>
                  <TooltipContent>Clear Markers</TooltipContent>
                </Tooltip>

                <Tooltip>
                  <TooltipTrigger asChild>
                    <span className="inline-block">
                      <Button size="icon" variant="outline" onClick={handleClearOptimizer} disabled={optimizerNodes.length === 0} className="h-8 w-8">
                        <BrainCircuit className="h-4 w-4" />
                      </Button>
                    </span>
                  </TooltipTrigger>
                  <TooltipContent>Clear Optimizer Results</TooltipContent>
                </Tooltip>

                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleOptimize}
                  disabled={isOptimizing}
                  className="relative"
                >
                  {isOptimizing ? (
                    <>
                      {optimizationProgress?.solutionNumber ? (
                        <div className="relative inline-flex items-center mr-2">
                          <svg className="h-4 w-4 -rotate-90">
                            {/* Background circle */}
                            <circle
                              cx="8"
                              cy="8"
                              r="6"
                              stroke="currentColor"
                              strokeWidth="2"
                              fill="none"
                              className="opacity-25"
                            />
                            {/* Solution progress */}
                            <circle
                              cx="8"
                              cy="8"
                              r="6"
                              stroke="currentColor"
                              strokeWidth="2"
                              fill="none"
                              strokeDasharray={`${2 * Math.PI * 6}`}
                              strokeDashoffset={`${2 * Math.PI * 6 * (1 - Math.min(optimizationProgress.solutionNumber / 30, 1))}`}
                              className="transition-all duration-300"
                            />
                            {/* Timeout progress*/}
                            <circle
                              cx="8"
                              cy="8"
                              r="4"
                              stroke="rgb(34, 211, 238)"
                              strokeWidth="2"
                              fill="none"
                              strokeDasharray={`${2 * Math.PI * 4}`}
                              strokeDashoffset={`${2 * Math.PI * 4 * (1 - Math.min(timeElapsed / SOLVER_TIMEOUT_SECONDS, 1))}`}
                              className="transition-all duration-100"
                            />
                          </svg>
                        </div>
                      ) : (
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      )}
                      {optimizationProgress?.message || "Optimizing..."}
                      {optimizationProgress?.solutionNumber && (
                        <span className="ml-1.5 text-xs text-muted-foreground">
                          (#{optimizationProgress.solutionNumber})
                        </span>
                      )}
                    </>
                  ) : (
                    "Optimize!"
                  )}
                </Button>

                {isOptimizing && (
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={cancelOptimization}
                    className="h-8 w-8 p-0"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                )}
              </div>
            </div>

            {/* Alerts */}
            <DashboardAlerts />

            {/* CourseGraph area fills remaining space without internal scroll */}
            <div className="flex-grow relative min-h-0">
              <CourseGraphFlow viewMode={viewMode} />
            </div>
          </div>
        </SidebarInset>
        <StarOnGithubPopup />
        <Toaster />
      </div>
    </SidebarProvider>
  );
}
