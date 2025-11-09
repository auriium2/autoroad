import React, { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

const GITHUB_REPO_URL = "https://github.com/your-org/your-repo";

const githubIcon = (
  <svg
    height="20"
    width="20"
    viewBox="0 0 16 16"
    fill="currentColor"
    aria-hidden="true"
  >
    <path
      d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38
      0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52
      -.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2
      -3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64
      -.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08
      2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01
      1.93-.01 2.19 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8z"
    />
  </svg>
);

export function StarOnGithubPopup() {
  const [visible, setVisible] = useState(true);
  const [mounted, setMounted] = useState(false);

  React.useEffect(() => {
    // Check localStorage only after mount to avoid hydration mismatch
    const isDismissed = localStorage.getItem('starPopupDismissed') === 'true';
    if (isDismissed) {
      setVisible(false);
    }
    setMounted(true);
  }, []);

  if (!visible || !mounted) return null;

  return (
    <div
      style={{
        position: "fixed",
        bottom: 24,
        right: 24,
        zIndex: 1000,
        maxWidth: 340,
      }}
    >
      <Card className="relative flex flex-row items-center gap-4 px-5 py-4 shadow-lg border bg-background">
        <button
          aria-label="Close"
          className="absolute top-2 right-2 text-muted-foreground hover:text-foreground transition-colors"
          onClick={() => { 
            setVisible(false); 
            if (typeof window !== 'undefined') {
              localStorage.setItem('starPopupDismissed', 'true');
            }
          }}
          title="Dismiss"
          style={{
            background: "none",
            border: "none",
            fontSize: 20,
            cursor: "pointer",
            lineHeight: 1,
          }}
        >
          ×
        </button>
        <CardContent className="p-0 flex-1">
          <div className="font-semibold text-base mb-1">Enjoying Autoroad?</div>
          <div className="text-muted-foreground text-sm mb-2">
            Please give it a star on github!
          </div>
        </CardContent>
        <a
          href={GITHUB_REPO_URL}
          target="_blank"
          rel="noopener noreferrer"
          aria-label="Star us on GitHub"
          className="ml-2"
        >
          <Button
            variant="secondary"
            className="gap-2 px-4 py-2 bg-[#24292f] text-white hover:bg-[#1b1f23]"
          >
            {githubIcon}
            Star
          </Button>
        </a>
      </Card>
    </div>
  );
}

export default StarOnGithubPopup;
