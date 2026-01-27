
import * as React from "react";
import { useQueryClient, useQuery } from "@tanstack/react-query";
import { API_BASE_URL } from "@/config/api";
import { AppSidebar } from "@/components/app-sidebar";

import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { Button } from "@/components/ui/button";
import { Bug, Download, Upload, Loader2, Trash2, UserX, BrainCircuit, X, HelpCircle } from "lucide-react";
import { BugReportDialog } from "@/components/BugReportDialog";
import { HealthIndicator } from "@/components/ui/health-indicator";
import { CourseGraphFlow } from "@/components/course-graph/CourseGraphFlow";
import { RequirementPrefetcher } from "@/components/RequirementPrefetcher";
import { ErrorDisplay } from "@/components/ErrorDisplay";
import { optimizerApi } from "@/services/optimizer";
import { useGraphStore } from "@/stores/roadStore";
import { Toaster } from "@/components/ui/toaster";
import { toast as showToast } from "@/hooks/useToast";
import { queryKeys } from "@/lib/queryKeys";
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
import { useTutorial } from "@/components/tutorial/TutorialProvider";
import { DEMO_MARKERS_ALL_FIXED, DEMO_OPTIMIZER_NODES, DEMO_COST_BREAKDOWN } from "@/components/tutorial/demoData";
import { fireroadApi } from "@/services/fireroad";
import { prefetchCourses, prefetchStaticData } from "@/lib/cache";

export default function Dashboard() {
  const [isExportingMarkers, setIsExportingMarkers] = React.useState(false);
  const [isExportingGenerated, setIsExportingGenerated] = React.useState(false);
  const [isImporting, setIsImporting] = React.useState(false);
  const [viewMode, setViewMode] = React.useState<string>("default");
  const [showBugReport, setShowBugReport] = React.useState(false);
  const [optimizationStartTime, setOptimizationStartTime] = React.useState<number | null>(null);
  const timeoutCircleRef = React.useRef<SVGCircleElement>(null);

  const queryClient = useQueryClient();
  const selectedRequirements = useOptimizationStore((state) => state.selectedRequirements);
  const { startTutorial, isActive: tutorialActive, getCurrentStepId, advanceTutorial } = useTutorial();

  // Check health of backend service
  const { data: healthData, isError: backendError, isPending: healthPending } = useQuery({
    queryKey: queryKeys.health.backend(),
    queryFn: async () => {
      const response = await fetch(`${API_BASE_URL}/api/health`, {
        signal: AbortSignal.timeout(15000),
      });
      if (!response.ok) throw new Error('Backend health check failed');
      return response.json();
    },
    refetchInterval: 30000,
    retry: 0,
    staleTime: 0,
  });

  // Only show health issues after the initial check completes
  const fireroadUnhealthy = !healthPending && healthData?.services?.fireroad?.status !== 'healthy';
  const hasHealthIssue = backendError || fireroadUnhealthy;


  const healthErrorMessage = backendError
    ? "Backend service is unavailable. Please contact mlui2@mit.edu if this persists."
    : fireroadUnhealthy
    ? "Fireroad API is unavailable. Course data may not load correctly."
    : "";

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
      return;
    }

    if (!isOptimizing || !optimizationStartTime) return;

    let rafId: number;
    const circumference = 2 * Math.PI * 4;
    const updateTime = () => {
      const elapsed = (Date.now() - optimizationStartTime) / 1000;
      if (timeoutCircleRef.current) {
        const offset = circumference * (1 - Math.min(elapsed / SOLVER_TIMEOUT_SECONDS, 1));
        timeoutCircleRef.current.setAttribute('stroke-dashoffset', String(offset));
      }
      rafId = requestAnimationFrame(updateTime);
    };

    rafId = requestAnimationFrame(updateTime);
    return () => cancelAnimationFrame(rafId);
  }, [isOptimizing, optimizationStartTime]);


  React.useEffect(() => {
    // Prefetch requirements list, objectives, and constraints
    prefetchStaticData(queryClient);

    // Prefetch course details for user's existing schedule
    const courseIds = [
      ...markers.map(m => m.courseId),
      ...optimizerNodes.map(n => n.courseId)
    ];

    if (courseIds.length > 0) {
      prefetchCourses(queryClient, courseIds);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Only run once on mount

  React.useEffect(() => {
    if (lastOptimizationStatus === 'OPTIMAL' && prevStatusRef.current !== 'OPTIMAL') {
      showToast({
        title: "Optimal solution found!",
        description: "The schedule generated could not be improved further!",
        duration: 3000,
      });
    } else if (lastOptimizationStatus == 'FEASIBLE' && prevStatusRef.current !== 'FEASIBLE') {
      showToast({
        title: "Feasible solution found...",
        description: "The schedule generated satisfies the constraints you placed but is not the most optimal. This usually happens when the solver runs out of time or you make the problem too complex. If it keeps happening please email mlui2@mit.edu.",
        duration: 3000,
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

  const handleExportMarkers = async () => {
    try {
      setIsExportingMarkers(true);

      const roadData = await exportToRoadFormat(
        markers,
        selectedRequirements,
        async (courseId) => {
          const details = await fireroadApi.getCourseDetails(courseId);
          return {
            title: details.title,
            total_units: details.total_units,
          };
        }
      );

      downloadRoadFile(roadData, "autoroad-markers.road");

      showToast({
        title: "Export successful",
        description: "Your markers have been exported to .road format",
        duration: 3000,
      });
    } catch (error) {
      console.error('Error during markers export:', error);
      showToast({
        title: "Export failed",
        description: error instanceof Error ? error.message : "Unknown error occurred",
        variant: "destructive",
        duration: 5000,
      });
    } finally {
      setIsExportingMarkers(false);
    }
  };

  const handleExportGenerated = async () => {
    try {
      setIsExportingGenerated(true);

      const generatedMarkers = optimizerNodes.map(node => ({
        uuid: `generated_${node.courseId}_${node.section}`,
        courseId: node.courseId,
        section: node.section,
        status: 'pin' as const,
      }));

      const roadData = await exportToRoadFormat(
        generatedMarkers,
        selectedRequirements,
        async (courseId) => {
          const details = await fireroadApi.getCourseDetails(courseId);
          return {
            title: details.title,
            total_units: details.total_units,
          };
        }
      );

      downloadRoadFile(roadData, "autoroad-generated.road");

      showToast({
        title: "Export successful",
        description: "Your generated schedule has been exported to .road format",
        duration: 3000,
      });
    } catch (error) {
      console.error('Error during generated export:', error);
      showToast({
        title: "Export failed",
        description: error instanceof Error ? error.message : "Unknown error occurred",
        variant: "destructive",
        duration: 5000,
      });
    } finally {
      setIsExportingGenerated(false);
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
    // // During tutorial on ready-to-optimize step, use demo data instead of real optimization
    // if (tutorialActive && getCurrentStepId() === 'ready-to-optimize') {
    //   useGraphStore.setState({
    //     markers: DEMO_MARKERS_ALL_FIXED,
    //     optimizerNodes: DEMO_OPTIMIZER_NODES,
    //     lastCostBreakdown: DEMO_COST_BREAKDOWN,
    //     lastOptimizationStatus: 'OPTIMAL',
    //     markersChangedSinceOptimization: false,
    //   });
    //   advanceTutorial();
    //   return;
    // }

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
              <Button variant="outline" size="sm" onClick={handleExportMarkers} disabled={isExportingMarkers}>
                <Download className="h-4 w-4" />
                {isExportingMarkers ? "Exporting..." : "Export Markers"}
              </Button>
              <Button variant="outline" size="sm" onClick={handleExportGenerated} disabled={isExportingGenerated}>
                <Download className="h-4 w-4" />
                {isExportingGenerated ? "Exporting..." : "Export Generated"}
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

                <div className="flex gap-1" data-tutorial="clear-buttons">
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
                      <span className="inline-block" data-tutorial="clear-optimizer-button">
                        <Button size="icon" variant="outline" onClick={handleClearOptimizer} disabled={optimizerNodes.length === 0} className="h-8 w-8">
                          <BrainCircuit className="h-4 w-4" />
                        </Button>
                      </span>
                    </TooltipTrigger>
                    <TooltipContent>Clear Optimizer Results</TooltipContent>
                  </Tooltip>
                </div>


                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleOptimize}
                  disabled={isOptimizing}
                  className="relative"
                  data-tutorial="optimize-button"
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
                              ref={timeoutCircleRef}
                              cx="8"
                              cy="8"
                              r="4"
                              stroke="rgb(34, 211, 238)"
                              strokeWidth="2"
                              fill="none"
                              strokeDasharray={`${2 * Math.PI * 4}`}
                              strokeDashoffset={`${2 * Math.PI * 4}`}
                            />
                          </svg>
                        </div>
                      ) : optimizationProgress?.queuePosition && optimizationProgress.queuePosition > 1 ? (
                        <span className="mr-2 text-xs font-medium bg-yellow-500/20 text-yellow-400 px-1.5 py-0.5 rounded">
                          #{optimizationProgress.queuePosition}
                        </span>
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

            {/* CourseGraph area fills remaining space without internal scroll */}
            <div className="flex-grow relative min-h-0">
              {hasHealthIssue ? (
                <ErrorDisplay
                  error={healthErrorMessage}
                  title="Service Unavailable"
                />
              ) : (
                <CourseGraphFlow viewMode={viewMode} />
              )}
            </div>
          </div>
        </SidebarInset>

        <Toaster />

        {/* Bottom left buttons */}
        <div className="fixed bottom-4 left-4 z-50 flex gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={startTutorial}
            className="text-muted-foreground hover:text-foreground opacity-60 hover:opacity-100 transition-opacity"
          >
            <HelpCircle className="h-4 w-4 mr-1" />
            Tutorial
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowBugReport(true)}
            className="text-muted-foreground hover:text-foreground opacity-60 hover:opacity-100 transition-opacity"
          >
            <Bug className="h-4 w-4 mr-1" />
            Send Feedback
          </Button>
        </div>
        <BugReportDialog open={showBugReport} onOpenChange={setShowBugReport} />
      </div>
    </SidebarProvider>
  );
}
