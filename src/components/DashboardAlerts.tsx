"use client";

import * as React from "react";
import { useGraphStore } from "@/stores/roadStore";
import { toast as showToast } from "@/hooks/useToast";

interface AlertConfig {
  id: string;
  type: "info" | "warning" | "error";
  title: string;
  description: React.ReactNode;
  show: boolean;
  durationMs?: number;
  signature: string;
}

interface DashboardAlertsProps {
  optimizationError: string | null;
  onDismissError: () => void;
}

export function DashboardAlerts({
  optimizationError,
  onDismissError,
}: DashboardAlertsProps) {
  const hasChangesSinceOptimization = useGraphStore(
    (state) => state.hasChangesSinceOptimization
  );

  const toastRefs = React.useRef<Record<string, { dismiss: () => void }>>({});
  const welcomeShownRef = React.useRef(false);

  const showOrReplaceToast = React.useCallback(
    (id: string, config: Omit<AlertConfig, "id" | "show" | "signature">) => {
      toastRefs.current[id]?.dismiss();
      toastRefs.current[id] = showToast({
        title: config.title,
        description: config.description,
        variant: config.type === "error" ? "destructive" : "default",
        duration: config.durationMs ?? 6000,
        onOpenChange: (open) => {
          if (!open) {
            if (id === "optimization-error") {
              onDismissError();
            }
            delete toastRefs.current[id];
          }
        },
      });
    },
    [onDismissError]
  );

  React.useEffect(() => {
    if (welcomeShownRef.current) return;
    welcomeShownRef.current = true;
    showOrReplaceToast("welcome", {
      type: "info",
      title: "Welcome to Autoroad",
      description:
        "Plan semesters, drop in ASEs, and optimize your road whenever you're ready.",
      durationMs: 5000,
    });
  }, [showOrReplaceToast]);

  React.useEffect(() => {
    if (hasChangesSinceOptimization) {
      showOrReplaceToast("user-controlled-nodes", {
        type: "info",
        title: "Manual changes detected",
        description:
          "You’ve moved or added courses manually. Run Optimize to see updated suggestions that respect your tweaks.",
        durationMs: 5000,
      });
    } else if (toastRefs.current["user-controlled-nodes"]) {
      toastRefs.current["user-controlled-nodes"]?.dismiss();
      delete toastRefs.current["user-controlled-nodes"];
    }
  }, [hasChangesSinceOptimization, showOrReplaceToast]);

  React.useEffect(() => {
    if (optimizationError) {
      showOrReplaceToast("optimization-error", {
        type: "error",
        title: "Optimization failed",
        description: optimizationError,
        durationMs: 8000,
      });
    } else if (toastRefs.current["optimization-error"]) {
      toastRefs.current["optimization-error"]?.dismiss();
      delete toastRefs.current["optimization-error"];
    }
  }, [optimizationError, showOrReplaceToast]);

  return null;
}
