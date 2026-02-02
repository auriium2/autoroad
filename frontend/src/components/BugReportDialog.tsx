import * as React from "react";
import { Bug, Loader2 } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { API_BASE_URL } from "@/config/api";
import { useGraphStore } from "@/stores/roadStore";
import { useOptimizationStore } from "@/stores/optimizationStore";
import { toast } from "@/hooks/useToast";

// Import version from package.json
const APP_VERSION = "0.1.0";

// Capture console logs
const consoleLogs: { level: string; message: string; timestamp: string }[] = [];
const MAX_LOGS = 100;

// Override console methods to capture logs
const originalConsole = {
  log: console.log,
  warn: console.warn,
  error: console.error,
};

function captureLog(level: string, args: unknown[]) {
  const message = args.map(arg => {
    try {
      return typeof arg === 'object' ? JSON.stringify(arg) : String(arg);
    } catch {
      return String(arg);
    }
  }).join(' ');

  consoleLogs.push({
    level,
    message: message.slice(0, 500), // Limit message length
    timestamp: new Date().toISOString(),
  });

  // Keep only last N logs
  if (consoleLogs.length > MAX_LOGS) {
    consoleLogs.shift();
  }
}

console.log = (...args) => { captureLog('log', args); originalConsole.log(...args); };
console.warn = (...args) => { captureLog('warn', args); originalConsole.warn(...args); };
console.error = (...args) => { captureLog('error', args); originalConsole.error(...args); };

interface BugReportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function BugReportDialog({ open, onOpenChange }: BugReportDialogProps) {
  const [description, setDescription] = React.useState("");
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  React.useEffect(() => {
    if (!open) {
      setDescription("");
    }
  }, [open]);

  const getDebugInfo = () => {
    const graphStore = useGraphStore.getState();
    const optimizationStore = useOptimizationStore.getState();

    // Build .aroad format snapshot for Sentry attachment
    const requirements = optimizationStore.selectedRequirements.length > 0
      ? optimizationStore.selectedRequirements
      : ['girs'];

    const markerSubjects = graphStore.markers
      .filter(m => m.status !== 'banish' && m.section !== -2)
      .map(m => ({
        overrideWarnings: m.status === 'override',
        semester: m.section === -1 ? 0 : m.section < 0 ? 1 : m.section + 1,
        title: m.courseId,
        subject_id: m.courseId,
        units: 0,
      }));

    const optimizerNodeSubjects = graphStore.optimizerNodes.map(n => ({
      semester: n.section === -1 ? 0 : n.section < 0 ? 1 : n.section + 1,
      title: n.courseId,
      subject_id: n.courseId,
      units: n.units || 0,
    }));

    const mustTakeSubjects = graphStore.markers
      .filter(m => m.section === -2 && m.status !== 'banish')
      .map(m => ({
        overrideWarnings: m.status === 'override',
        semester: -2,
        title: m.courseId,
        subject_id: m.courseId,
        units: 0,
      }));

    const aroadData = {
      coursesOfStudy: requirements,
      progressOverrides: {},
      selectedSubjects: markerSubjects,
      progressAssertions: {},
      autoroad: {
        version: "1" as const,
        objectives: optimizationStore.selectedObjectives,
        objectiveTiers: optimizationStore.objectiveTiers,
        requirementTiers: optimizationStore.requirementTiers,
        requirementSources: optimizationStore.requirementSources,
        hardConstraints: optimizationStore.selectedHardConstraints,
        customEquivalencies: optimizationStore.customEquivalencies,
        selectedYear: optimizationStore.selectedYear ?? "",
        lockPastSemesters: optimizationStore.lockPastSemesters,
        mustTakeSubjects,
        optimizerNodes: optimizerNodeSubjects,
      },
    };

    return {
      version: APP_VERSION,
      userAgent: navigator.userAgent,
      timestamp: new Date().toISOString(),
      url: window.location.href,
      markers: graphStore.markers,
      optimizerNodes: graphStore.optimizerNodes,
      lastOptimizationStatus: graphStore.lastOptimizationStatus,
      lastCostBreakdown: graphStore.lastCostBreakdown,
      consoleLogs: [...consoleLogs],
      aroadData,
    };
  };

  const generateTitle = (desc: string): string => {
    const firstLine = desc.split('\n')[0].trim();
    const maxLen = 60;

    if (firstLine.length <= maxLen) {
      return `Auto: ${firstLine}`;
    }

    const truncated = firstLine.slice(0, maxLen);
    const lastSpace = truncated.lastIndexOf(' ');
    if (lastSpace > 30) {
      return `Auto: ${truncated.slice(0, lastSpace)}...`;
    }
    return `Auto: ${truncated}...`;
  };

  const handleSubmit = async () => {
    if (!description.trim()) {
      toast({
        title: "Description required",
        description: "Please describe the issue you're experiencing.",
        variant: "destructive",
      });
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/bug-report`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: generateTitle(description.trim()),
          description: description.trim(),
          debug_info: getDebugInfo(),
        }),
      });

      const result = await response.json();

      if (result.success) {
        toast({
          title: "Bug report submitted",
          description: "Thank you for reporting this issue!",
        });
        onOpenChange(false);
      } else {
        throw new Error(result.error || "Failed to submit bug report");
      }
    } catch (error) {
      console.error("Failed to submit bug report:", error);
      toast({
        title: "Submission failed",
        description: error instanceof Error ? error.message : "Please try again later.",
        variant: "destructive",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Bug className="h-5 w-5" />
            Send Feedback
          </DialogTitle>
          <DialogDescription>
            Report bugs, request features, or share any other feedback.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Description */}
          <div className="space-y-2">
            <label htmlFor="description" className="text-sm font-medium">
              What went wrong? <span className="text-destructive">*</span>
            </label>
            <textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Please describe the issue you encountered or feature you desire. Include steps to reproduce or interaction workflow if possible."
              className="w-full min-h-32 px-3 py-2 text-sm border rounded-md bg-background resize-y focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>

          <p className="text-xs text-muted-foreground">
            Your class markers and selected objectives will be included automatically to help diagnose the issue.
          </p>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={isSubmitting}>
            {isSubmitting ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Submitting...
              </>
            ) : (
              "Submit Report"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
