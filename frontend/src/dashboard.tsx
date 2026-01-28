
import * as React from "react";
import { useQueryClient, useQuery } from "@tanstack/react-query";
import { API_BASE_URL } from "@/config/api";
import { AppSidebar } from "@/components/app-sidebar";

import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { Monitor } from "lucide-react";
import { HealthIndicator } from "@/components/ui/health-indicator";
import { CourseGraphFlow } from "@/components/course-graph/CourseGraphFlow";

import { ErrorDisplay } from "@/components/ErrorDisplay";
import { useGraphStore } from "@/stores/roadStore";
import { Toaster } from "@/components/ui/toaster";
import { queryKeys } from "@/lib/queryKeys";
import { OptimizeButton } from "@/components/dashboard/OptimizeButton";
import { ClearButtons } from "@/components/dashboard/ClearButtons";
import { ImportExportToolbar } from "@/components/dashboard/ImportExportToolbar";
import { ViewModeSelector } from "@/components/dashboard/ViewModeSelector";
import { BottomToolbar } from "@/components/dashboard/BottomToolbar";
import { prefetchCourses, prefetchStaticData } from "@/lib/cache";

export default function Dashboard() {
  const [viewMode, setViewMode] = React.useState<string>("default");
  const [isMobile, setIsMobile] = React.useState(() => {
    if (typeof window !== 'undefined') {
      return window.innerWidth < 768;
    }
    return false;
  });

  React.useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  const queryClient = useQueryClient();

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

  const markers = useGraphStore(state => state.markers);
  const optimizerNodes = useGraphStore(state => state.optimizerNodes);

  React.useEffect(() => {
    prefetchStaticData(queryClient);

    const courseIds = [
      ...markers.map(m => m.courseId),
      ...optimizerNodes.map(n => n.courseId)
    ];

    if (courseIds.length > 0) {
      prefetchCourses(queryClient, courseIds); //prefetch existing
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Show mobile warning before anything else renders
  if (isMobile) {
    return (
      <div className="fixed inset-0 z-[100] bg-background flex flex-col items-center justify-center p-8 text-center">
        <Monitor className="h-16 w-16 text-muted-foreground mb-6" />
        <h1 className="text-2xl font-bold mb-3">Desktop Required</h1>
        <p className="text-muted-foreground max-w-sm">
          Autoroad requires a larger screen to work properly. Please visit on a desktop or laptop computer.
        </p>
      </div>
    );
  }

  return (
    <SidebarProvider defaultOpen={true}>

      <div className="flex w-screen h-screen">
        <AppSidebar viewMode={viewMode} />
        <SidebarInset className="flex-1 min-w-0 z-0 flex flex-col">
          <header className="flex h-16 shrink-0 items-center gap-2 border-b border-border/50 px-4 relative z-10 glass dark:glass-dark">
            <div className="flex items-center gap-2">
              <SidebarTrigger />
              <HealthIndicator />
            </div>
            <div className="ml-auto">
              <ImportExportToolbar />
            </div>
          </header>
          <div className="flex flex-col p-4 gap-4 flex-grow min-h-0 relative z-0">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-3xl font-bold tracking-tight">
                  Autoroad
                  <sub className="ml-1 text-xs font-normal text-muted-foreground align-baseline">
                    <span className="font-serif">Alfa</span> {__APP_VERSION__}
                  </sub>
                </h1>
              </div>
              <div className="flex items-center gap-2">
                <ViewModeSelector value={viewMode} onChange={setViewMode} />
                <ClearButtons />
                <OptimizeButton />
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
        <BottomToolbar />
      </div>
    </SidebarProvider>
  );
}
