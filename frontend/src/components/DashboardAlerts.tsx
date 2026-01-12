
import * as React from "react";
import { toast as showToast } from "@/hooks/useToast";

interface BasicToastConfig {
  type: "info" | "warning" | "error";
  title: string;
  description: React.ReactNode;
  durationMs?: number;
}

export function DashboardAlerts() {
  const toastRefs = React.useRef<Record<string, { dismiss: () => void }>>({});

  const showOrReplaceToast = (id: string, config: BasicToastConfig) => {
    toastRefs.current[id]?.dismiss();
    toastRefs.current[id] = showToast({
      title: config.title,
      description: config.description,
      variant: config.type === "error" ? "destructive" : "default",
      duration: config.durationMs ?? 6000,
      onOpenChange: (open) => {
        if (!open) {
          delete toastRefs.current[id];
        }
      },
    });
  };

  // React.useEffect(() => {
  //   showOrReplaceToast("welcome", {
  //     type: "info",
  //     title: "Welcome to Autoroad",
  //     description:
  //       "Plan semesters, drop in ASEs, and optimize your road whenever you're ready.",
  //     durationMs: 30000,
  //   });
  // }, []);

  return null;
}
