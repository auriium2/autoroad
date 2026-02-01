import * as React from "react";
import { Bug, HelpCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { BugReportDialog } from "@/components/BugReportDialog";
import { useTutorial } from "@/components/tutorial/TutorialProvider";

export function BottomToolbar() {
  const [showBugReport, setShowBugReport] = React.useState(false);
  const { startTutorial } = useTutorial();

  return (
    <>
      <div className="fixed bottom-4 left-4 z-50 flex gap-2">
        <Button
          variant="ghost"
          size="sm"
          onClick={startTutorial}
          className="text-muted-foreground hover:text-foreground opacity-60 hover:opacity-100 transition-opacity"
        >
          <HelpCircle className="h-4 w-4 mr-1" />
          Tutorial
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setShowBugReport(true)}
          className="text-muted-foreground hover:text-foreground opacity-80 hover:opacity-100 transition-opacity"
        >
          <Bug className="h-4 w-4 mr-1" />
          Bug Report
        </Button>
      </div>
      <BugReportDialog open={showBugReport} onOpenChange={setShowBugReport} />
    </>
  );
}
