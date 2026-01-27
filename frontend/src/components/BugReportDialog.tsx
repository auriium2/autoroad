import * as React from "react";
import { Bug, Loader2, Upload } from "lucide-react";
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
  const [screenshot, setScreenshot] = React.useState<string | null>(null);
  const [isCapturing, setIsCapturing] = React.useState(false);
  const [isSubmitting, setIsSubmitting] = React.useState(false);


  React.useEffect(() => {
    if (!open && !isCapturing) {
      setDescription("");
      setScreenshot(null);
    }
  }, [open, isCapturing]);

  const captureScreenshot = async () => {
    setIsCapturing(true);

    try {

      const stream = await navigator.mediaDevices.getDisplayMedia({
        video: { displaySurface: "browser" } as MediaTrackConstraints,
        preferCurrentTab: true,
      } as DisplayMediaStreamOptions);

      const video = document.createElement("video");
      video.srcObject = stream;
      await video.play();

      // Close the dialog via React state to hide it from the screen
      onOpenChange(false);

      // Wait for React to unmount the dialog and for the video to get a fresh frame
      await new Promise(resolve => setTimeout(resolve, 300));

      const canvas = document.createElement("canvas");
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext("2d");
      ctx?.drawImage(video, 0, 0);

      // Stop the stream
      stream.getTracks().forEach(track => track.stop());

      const dataUrl = canvas.toDataURL("image/png", 0.8);

      // Reopen the dialog and set the screenshot
      onOpenChange(true);
      // Small delay to ensure dialog is mounted before setting state
      await new Promise(resolve => setTimeout(resolve, 50));
      setScreenshot(dataUrl);
    } catch (error) {
      console.error("Failed to capture screenshot:", error);
      setScreenshot(null);
    } finally {
      setIsCapturing(false);
    }
  };

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      setScreenshot(e.target?.result as string);
    };
    reader.readAsDataURL(file);
  };

  const getDebugInfo = () => {
    const graphStore = useGraphStore.getState();
    const optimizationStore = useOptimizationStore.getState();

    // Build .road format data for markers
    const markersRoadData = {
      coursesOfStudy: optimizationStore.selectedRequirements.length > 0
        ? optimizationStore.selectedRequirements
        : ['girs'],
      progressOverrides: {},
      selectedSubjects: graphStore.markers
        .filter(m => m.status !== 'banish')
        .map(m => ({
          overrideWarnings: m.status === 'override',
          semester: m.section === -1 ? 0 : m.section < 0 ? 1 : m.section + 1,
          title: m.courseId,
          subject_id: m.courseId,
          units: 0,
        })),
      progressAssertions: {},
    };

    // Build .road format data for optimizer nodes (if any)
    const optimizerRoadData = graphStore.optimizerNodes.length > 0 ? {
      coursesOfStudy: optimizationStore.selectedRequirements.length > 0
        ? optimizationStore.selectedRequirements
        : ['girs'],
      progressOverrides: {},
      selectedSubjects: graphStore.optimizerNodes.map(n => ({
        overrideWarnings: false,
        semester: n.section === -1 ? 0 : n.section < 0 ? 1 : n.section + 1,
        title: n.courseId,
        subject_id: n.courseId,
        units: n.units || 0,
      })),
      progressAssertions: {},
    } : null;

    return {
      version: APP_VERSION,
      userAgent: navigator.userAgent,
      timestamp: new Date().toISOString(),
      url: window.location.href,
      markers: graphStore.markers,
      optimizerNodes: graphStore.optimizerNodes,
      objectives: optimizationStore.selectedObjectives,
      objectiveTiers: optimizationStore.objectiveTiers,
      requirements: optimizationStore.selectedRequirements,
      requirementTiers: optimizationStore.requirementTiers,
      requirementSources: optimizationStore.requirementSources,
      selectedYear: optimizationStore.selectedYear,
      lockPastSemesters: optimizationStore.lockPastSemesters,
      lastOptimizationStatus: graphStore.lastOptimizationStatus,
      lastCostBreakdown: graphStore.lastCostBreakdown,
      consoleLogs: [...consoleLogs],
      markersRoadData,
      optimizerRoadData,
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
          screenshot,
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
          {/* Screenshot */}
          <div className="space-y-2">
            <label className="text-sm font-medium">Screenshot (optional)</label>
            <div className="border rounded-md overflow-hidden bg-muted/50">
              {isCapturing ? (
                <div className="flex items-center justify-center h-32">
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                  <span className="ml-2 text-sm text-muted-foreground">Capturing...</span>
                </div>
              ) : screenshot ? (
                <img src={screenshot} alt="Screenshot" className="w-full h-auto max-h-48 object-contain" />
              ) : (
                <div className="flex items-center justify-center h-32 text-muted-foreground">
                  <span className="text-sm">No screenshot attached</span>
                </div>
              )}
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={captureScreenshot} disabled={isCapturing} className="text-xs">
                {screenshot ? "Recapture" : "Capture screen"}
              </Button>
              <label>
                <input type="file" accept="image/*" onChange={handleFileUpload} className="hidden" />
                <Button variant="outline" size="sm" asChild className="text-xs cursor-pointer">
                  <span><Upload className="h-3 w-3 mr-1" />Upload image</span>
                </Button>
              </label>
              {screenshot && (
                <Button variant="ghost" size="sm" onClick={() => setScreenshot(null)} className="text-xs text-muted-foreground">
                  Remove
                </Button>
              )}
            </div>
          </div>

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
          <Button onClick={handleSubmit} disabled={isSubmitting || isCapturing}>
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
