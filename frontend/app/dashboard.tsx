"use client";

import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";
import { AppSidebar } from "@/components/app-sidebar";
import { StarOnGithubPopup } from "@/components/StarOnGithubPopup";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Separator } from "@/components/ui/separator";
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { Button } from "@/components/ui/button";
import { Download, Upload, Loader2, Trash2 } from "lucide-react";
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
import { useOptimizationStore } from "@/stores/optimizationStore";
import { exportToRoadFormat, importFromRoadFormat, downloadRoadFile, uploadRoadFile } from "@/lib/roadFormat";
import { fireroadApi } from "@/services/fireroad";
import { prefetchCourses } from "@/lib/coursePrefetch";

export default function Dashboard() {
  const [isExporting, setIsExporting] = React.useState(false);
  const [isImporting, setIsImporting] = React.useState(false);
  const [viewMode, setViewMode] = React.useState<string>("default");

  const queryClient = useQueryClient();
  const selectedRequirements = useOptimizationStore((state) => state.selectedRequirements);

  // Get store functions and state
  const optimizeRoadFromStore = useGraphStore(state => state.optimizeRoad);
  const optimizationProgress = useGraphStore(state => state.optimizationProgress);
  const markers = useGraphStore(state => state.markers);
  const optimizerNodes = useGraphStore(state => state.optimizerNodes);
  const loadRoadData = useGraphStore(state => state.loadRoadData);
  const lastOptimizationStatus = useGraphStore(state => state.lastOptimizationStatus);
  const isOptimizing = useGraphStore(state => state.isOptimizing);

  const prevStatusRef = React.useRef<string | null>(null);

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
          description: "Your schedule has been optimized!",
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
        <AppSidebar />
        <SidebarInset className="flex-1 min-w-0 z-0 flex flex-col">
          <header className="flex h-16 shrink-0 items-center gap-2 border-b border-border/50 px-4 relative z-10 glass dark:glass-dark">
            <div className="flex items-center gap-2">
              <SidebarTrigger />
              <Separator orientation="vertical" className="mr-2 h-4" />
              <Breadcrumb>
                <BreadcrumbList>
                  <BreadcrumbItem className="hidden md:block">
                    <BreadcrumbLink href="https://auriium.xyz">auriium.xyz</BreadcrumbLink>
                  </BreadcrumbItem>
                  <BreadcrumbSeparator className="hidden md:block" />
                  <BreadcrumbItem>
                    <BreadcrumbPage>autoroad</BreadcrumbPage>
                  </BreadcrumbItem>
                </BreadcrumbList>
              </Breadcrumb>
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
                    <SelectItem value="default">Default view</SelectItem>
                    <SelectItem value="compact">Compact view</SelectItem>
                  </SelectContent>
                </Select>

                <Button size="sm" variant="outline" onClick={handleClearMarkers} disabled={markers.length === 0}>
                  <Trash2 className="h-4 w-4" />
                  Clear
                </Button>

                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleOptimize}
                  disabled={isOptimizing}
                >
                  {isOptimizing ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      {optimizationProgress?.message || "Optimizing..."}
                    </>
                  ) : (
                    "Optimize!"
                  )}
                </Button>
              </div>
            </div>

            {/* Alerts */}
            <DashboardAlerts />

            {/* CourseGraph area fills remaining space without internal scroll */}
            <div className="flex-grow relative min-h-0">
              <CourseGraphFlow />
            </div>
          </div>
        </SidebarInset>
        <StarOnGithubPopup />
        <Toaster />
      </div>
    </SidebarProvider>
  );
}
