import * as React from "react";
import { Rocket, X, Info } from "lucide-react";
import { Alert, AlertDescription } from "./ui/alert";
import { useGraphStore } from "@/stores/roadStore";

interface AlertConfig {
  id: string;
  type: "info" | "warning" | "error";
  icon: React.ReactElement;
  message: React.ReactNode;
  dismissible?: boolean;
  show: boolean;
}

interface DashboardAlertsProps {
  optimizationError: string | null;
  onDismissError: () => void;
}

export function DashboardAlerts({
  optimizationError,
  onDismissError,
}: DashboardAlertsProps) {
  // Access store to calculate state
  const hasChangesSinceOptimization = useGraphStore(state => state.hasChangesSinceOptimization);
  
  // Local dismissed state
  const [dismissed, setDismissed] = React.useState<Set<string>>(new Set());

  // Define all alerts in one clean place
  const alerts: AlertConfig[] = [
    {
      id: "welcome",
      type: "info",
      icon: <Rocket className="h-4 w-4" />,
      message: (
        <>
          <strong>Welcome!</strong> This is the Autoroad dashboard. Here you can
          plan your semesters and optimize your schedule.
        </>
      ),
      dismissible: true,
      show: true,
    },
    {
      id: "user-controlled-nodes",
      type: "info",
      icon: <Info className="h-4 w-4" />,
      message: (
        <>
          <strong>Notice:</strong> You&apos;ve added or moved courses manually.
          Click the optimize button to see if the optimizer can improve your
          schedule while respecting your changes.
        </>
      ),
      dismissible: false,
      show: hasChangesSinceOptimization,
    },
    {
      id: "optimization-error",
      type: "error",
      icon: <X className="h-4 w-4" />,
      message: (
        <>
          <strong>Error:</strong> {optimizationError}
        </>
      ),
      dismissible: true,
      show: optimizationError !== null,
    },
  ];

  // Filter alerts based on show condition and dismissed state
  const visibleAlerts = alerts.filter(
    (alert) => alert.show && !dismissed.has(alert.id)
  );

  if (visibleAlerts.length === 0) {
    return null;
  }

  const handleDismiss = (alertId: string) => {
    setDismissed((prev) => new Set(prev).add(alertId));
    
    // Special handling for optimization error
    if (alertId === "optimization-error") {
      onDismissError();
    }
  };

  const getAlertStyles = (type: AlertConfig["type"]) => {
    switch (type) {
      case "info":
        return {
          container: "border-blue-500 bg-blue-50 dark:bg-blue-950/20",
          icon: "text-blue-600",
          text: "text-blue-800 dark:text-blue-200",
        };
      case "warning":
        return {
          container: "border-yellow-500 bg-yellow-50 dark:bg-yellow-950/20",
          icon: "text-yellow-600",
          text: "text-yellow-800 dark:text-yellow-200",
        };
      case "error":
        return {
          container: "border-red-500 bg-red-50 dark:bg-red-950/20",
          icon: "text-red-600",
          text: "text-red-800 dark:text-red-200",
        };
    }
  };

  return (
    <div className="space-y-2">
      {visibleAlerts.map((alert) => {
        const styles = getAlertStyles(alert.type);
        
        return (
          <Alert
            key={alert.id}
            className={`${styles.container} ${alert.dismissible ? "relative pr-10" : ""} py-2 px-3 text-sm`}
          >
            <div className={styles.icon}>{alert.icon}</div>
            <AlertDescription className={styles.text}>
              {alert.message}
            </AlertDescription>
            {alert.dismissible && (
              <button
                onClick={() => handleDismiss(alert.id)}
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
            )}
          </Alert>
        );
      })}
    </div>
  );
}
