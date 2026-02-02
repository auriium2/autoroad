import * as React from "react";
import { Loader2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useGraphStore } from "@/stores/roadStore";
import { useOptimizationStore } from "@/stores/optimizationStore";
import { useStoreNodes } from "@/hooks/useStoreNodes";
import { usePrerequisiteValidation } from "@/hooks/usePrerequisiteValidation";
import { useBlockingErrors } from "@/hooks/useBlockingErrors";
import { toast as showToast } from "@/hooks/useToast";
import { useBugReportStore } from "@/stores/bugReportStore";
import { ToastAction } from "@/components/ui/toast";

const SOLVER_TIMEOUT_SECONDS = 30;

export function OptimizeButton() {
  const [optimizationStartTime, setOptimizationStartTime] = React.useState<number | null>(null);
  const timeoutCircleRef = React.useRef<SVGCircleElement>(null);

  const optimizeRoadFromStore = useGraphStore(state => state.optimizeRoad);
  const cancelOptimization = useGraphStore(state => state.cancelOptimization);
  const optimizationProgress = useGraphStore(state => state.optimizationProgress);
  const markers = useGraphStore(state => state.markers);
  const optimizerNodes = useGraphStore(state => state.optimizerNodes);
  const isOptimizing = useGraphStore(state => state.isOptimizing);
  const lastOptimizationStatus = useGraphStore(state => state.lastOptimizationStatus);

  const { storeNodes } = useStoreNodes(markers, optimizerNodes);
  const { missing: uuid2missingPrereqs } = usePrerequisiteValidation(storeNodes);
  const { hasWrongSemester, hasDuplicateCourses, duplicateCourseIds, hasFreshmanFallOverload, freshmanFallUnits } = useBlockingErrors(markers);

  const hasBlockingPrereqErrors = React.useMemo(() => {
    if (!uuid2missingPrereqs || !(uuid2missingPrereqs instanceof Map)) return false;
    for (const [uuid, missingPrereqs] of uuid2missingPrereqs) {
      if (missingPrereqs.length > 0) {
        const marker = markers.find(m => m.uuid === uuid);
        if (marker && marker.status !== 'override') {
          return true;
        }
      }
    }
    return false;
  }, [uuid2missingPrereqs, markers]);

  const hasBlockingErrors = hasBlockingPrereqErrors || hasWrongSemester || hasDuplicateCourses || hasFreshmanFallOverload;

  // Show toast on optimization status change
  const prevStatusRef = React.useRef<string | null>(null);
  React.useEffect(() => {
    const feedbackAction = (
      <ToastAction altText="Send Feedback" onClick={() => useBugReportStore.getState().setOpen(true)}>
        Give Feedback
      </ToastAction>
    );
    if (lastOptimizationStatus === 'OPTIMAL' && prevStatusRef.current !== 'OPTIMAL') {
      showToast({
        title: "Optimization finished!",
        description: "Something look weird? Send feedback!",
        action: feedbackAction,
        duration: 5000,
      });
    } else if (lastOptimizationStatus === 'FEASIBLE' && prevStatusRef.current !== 'FEASIBLE') {
      showToast({
        title: "Optimization terminated!",
        description: "Something look weird? Send feedback!",
        action: feedbackAction,
        duration: 5000,
      });
    }
    prevStatusRef.current = lastOptimizationStatus;
  }, [lastOptimizationStatus]);

  // Track optimization time for timeout circle animation
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
    <div className="flex items-center gap-2">
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="inline-block" data-tutorial="optimize-button">
            <Button
              size="sm"
              variant="outline"
              onClick={handleOptimize}
              disabled={isOptimizing || hasBlockingErrors}
              className={`relative ${hasBlockingErrors ? 'border-red-500 border-2 text-red-500 hover:text-red-500' : ''}`}
            >
              {isOptimizing ? (
                <>
                  {optimizationProgress?.solutionNumber ? (
                    <div className="relative inline-flex items-center mr-2">
                      <svg className="h-4 w-4 -rotate-90">
                        <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="2" fill="none" className="opacity-25" />
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
          </span>
        </TooltipTrigger>
        {hasBlockingErrors && (
          <TooltipContent>
            <p>
              {hasDuplicateCourses
                ? `Remove duplicate courses: ${[...duplicateCourseIds].join(", ")}`
                : hasFreshmanFallOverload
                ? `Freshman Fall has ${freshmanFallUnits} units (max 54)`
                : hasBlockingPrereqErrors && hasWrongSemester
                ? "Fix missing prerequisites (red) and wrong semester placements (yellow)"
                : hasBlockingPrereqErrors
                ? "Fix missing prerequisites (red) before optimizing"
                : "Fix wrong semester placements (yellow) before optimizing"}
            </p>
          </TooltipContent>
        )}
      </Tooltip>

      {isOptimizing && (
        <Button size="sm" variant="destructive" onClick={cancelOptimization} className="h-8 w-8 p-0">
          <X className="h-4 w-4" />
        </Button>
      )}
    </div>
  );
}
