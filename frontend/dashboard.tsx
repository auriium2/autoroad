"use client";

import * as React from "react";
import { AppSidebar } from "./components/AppSidebar";
import { StarOnGithubPopup } from "./components/StarOnGithubPopup";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "./components/ui/breadcrumb";
import { Separator } from "./components/ui/separator";
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "./components/ui/sidebar";
import { Button } from "./components/ui/button";
import { Download, Loader2 } from "lucide-react";
import { CourseGraphFlow } from "./components/course-graph/CourseGraphFlow";
import { DashboardAlerts } from "./components/DashboardAlerts";
import { useGraphStore } from "./stores/roadStore";
import { Toaster } from "./components/ui/toaster";
import { toast as showToast } from "@/hooks/useToast";

export default function Dashboard() {
  const [isOptimizing, setIsOptimizing] = React.useState(false);
  const [selectedYear, setSelectedYear] = React.useState<string | undefined>(undefined);
  const handleYearChange = React.useCallback((value?: string) => {
    setSelectedYear(value);
  }, []);

  // Get optimize function and progress from store
  const optimizeRoadFromStore = useGraphStore(state => state.optimizeRoad);
  const optimizationProgress = useGraphStore(state => state.optimizationProgress);

  // Handle optimization
  const handleOptimize = async () => {
    try {
      setIsOptimizing(true);

      const result = await optimizeRoadFromStore({
        maxUnitsPerSemester: 60,
        minUnitsPerSemester: 36,
        preferredTimes: selectedYear ? [selectedYear] : undefined
      }, true); // Show progress during optimization

      if (!result.success) {
        showToast({
          title: "Optimization failed",
          description: result.error || "Optimization failed",
          variant: "destructive",
          duration: 1000,
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
    } finally {
      setIsOptimizing(false);
    }
  };
  return (
    <SidebarProvider>
      <div className="flex w-screen h-screen">
        <AppSidebar
          selectedYear={selectedYear}
          onSelectedYearChange={handleYearChange}
        />
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
              <Button variant="outline" size="sm">
                <Download className="h-4 w-4" />
                Export
              </Button>
              <Button size="sm">Open in CourseRoad</Button>
            </div>
          </header>
          <div className="flex flex-col p-4 gap-4 flex-grow min-h-0 relative z-0">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-3xl font-bold tracking-tight">Autoroad</h1>

              </div>
              <div className="flex items-center">
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
