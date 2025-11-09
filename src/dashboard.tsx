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
import { SimpleSelect } from "./components/ui/simple-select";
import { Download, Rocket, Lock, X, Loader2 } from "lucide-react";
import { Alert, AlertDescription } from "./components/ui/alert";
import { CourseGraphFlow } from "./components/course-graph/CourseGraphFlow";
import { optimizeRoad } from "./services/optimizationService";
import { useGraphStore } from "./stores/roadStore";


export default function Dashboard() {
  // Info alert dismissed state
  const [infoAlertDismissed, setInfoAlertDismissed] = React.useState(false);
  const [isOptimizing, setIsOptimizing] = React.useState(false);
  const [optimizationError, setOptimizationError] = React.useState<string | null>(null);
  const [selectedYear, setSelectedYear] = React.useState<string | undefined>(undefined);

  // Get store data
  const { nodes, sections, loadRoadData } = useGraphStore();

  // Check if any nodes are disabled or locked
  const hasDisabledNodes = React.useMemo(() => {
    return nodes.some((node) => node.disabled === true);
  }, [nodes]);

  const hasLockedNodes = React.useMemo(() => {
    return nodes.some((node) => node.locked === true);
  }, [nodes]);

  // Get optimize function from store
  const optimizeRoadFromStore = useGraphStore(state => state.optimizeRoad);

  // Handle optimization
  const handleOptimize = async () => {
    try {
      setIsOptimizing(true);
      setOptimizationError(null);

      const result = await optimizeRoadFromStore({
        maxUnitsPerSemester: 60,
        minUnitsPerSemester: 36,
        preferredTimes: selectedYear ? [selectedYear] : undefined
      });

      if (!result.success) {
        setOptimizationError(result.error || 'Optimization failed');
      }

    } catch (error) {
      console.error('Error during optimization:', error);
      setOptimizationError(error instanceof Error ? error.message : 'Unknown error occurred');
    } finally {
      setIsOptimizing(false);
    }
  };
  return (
    <SidebarProvider>
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
                    <BreadcrumbLink href="#">Autoroad</BreadcrumbLink>
                  </BreadcrumbItem>
                  <BreadcrumbSeparator className="hidden md:block" />
                  <BreadcrumbItem>
                    <BreadcrumbPage>Autoroad</BreadcrumbPage>
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
              <div className="flex items-center gap-2">
                <SimpleSelect
                  className="w-40"
                  placeholder="Select Year"
                  options={[
                    { value: "freshman", label: "Freshman" },
                    { value: "sophomore", label: "Sophomore" },
                    { value: "junior", label: "Junior" },
                    { value: "senior", label: "Senior" },
                  ]}
                  onValueChange={setSelectedYear}
                  value={selectedYear}
                />
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleOptimize}
                  disabled={isOptimizing}
                >
                  {isOptimizing ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Optimizing...
                    </>
                  ) : (
                    "Optimize!"
                  )}
                </Button>
              </div>
            </div>

            {/* Alerts constrained with max height and internal scroll */}
            {hasDisabledNodes || hasLockedNodes || optimizationError || !infoAlertDismissed ? (
              <div className="space-y-2">
                {hasDisabledNodes && (
                  <Alert className="border-yellow-500 bg-yellow-50 dark:bg-yellow-950/20 py-2 px-3 text-sm">
                    <Lock className="h-4 w-4 text-yellow-600" />
                    <AlertDescription className="text-yellow-800 dark:text-yellow-200">
                      <strong>Warning:</strong> You&apos;ve added disabled classes
                      to a semester! Make sure to click the optimize button to
                      see if they can be included.
                    </AlertDescription>
                  </Alert>
                )}
                {/*
                {hasLockedNodes && (
                  <Alert className="border-yellow-500 bg-yellow-50 dark:bg-yellow-950/20 py-2 px-3 text-sm">
                    <Lock className="h-4 w-4 text-yellow-600" />
                    <AlertDescription className="text-yellow-800 dark:text-yellow-200">
                      <strong>Notice:</strong> You&apos;ve locked some classes in place.
                      The optimizer will respect these constraints.
                    </AlertDescription>
                  </Alert>
                )}*/}

                {optimizationError && (
                  <Alert className="border-red-500 bg-red-50 dark:bg-red-950/20 py-2 px-3 text-sm">
                    <X className="h-4 w-4 text-red-600" />
                    <AlertDescription className="text-red-800 dark:text-red-200">
                      <strong>Error:</strong> {optimizationError}
                    </AlertDescription>
                  </Alert>
                )}

                {!infoAlertDismissed && (
                  <Alert className="border-blue-500 bg-blue-50 dark:bg-blue-950/20 relative pr-10 py-2 px-3 text-sm">
                    <Rocket className="h-4 w-4 text-blue-600" />
                    <AlertDescription className="text-blue-800 dark:text-blue-200">
                      <strong>Welcome!</strong> This is the Autoroad dashboard.
                      Here you can plan your semesters and optimize your
                      schedule.
                    </AlertDescription>
                    <button
                      onClick={() => setInfoAlertDismissed(true)}
                      className="absolute top-0.5 right-0.5 text-muted-foreground hover:text-foreground transition-colors"
                      aria-label="Close"
                      style={{
                        background: "none",
                        border: "none",
                        fontSize: 20,
                        cursor: "pointer",
                        lineHeight: 1,
                      }}
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </Alert>
                )}
              </div>
            ) : null}

            {/* CourseGraph area fills remaining space without internal scroll */}
            <div className="flex-grow relative min-h-0">
              <CourseGraphFlow />
            </div>
          </div>
        </SidebarInset>
        <StarOnGithubPopup />
      </div>
    </SidebarProvider>
  );
}
