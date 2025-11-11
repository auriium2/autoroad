"use client";

import React from "react";
import { toast as showToast } from "@/hooks/useToast";
import { ToastAction } from "@/components/ui/toast";
import { Button } from "@/components/ui/button";

const GITHUB_REPO_URL = "https://github.com/your-org/your-repo";
const STAR_TOAST_SESSION_KEY = "starToastShownInSession";

export function StarOnGithubPopup() {
  const hasRequestedToastRef = React.useRef(false);

  React.useEffect(() => {
    if (typeof window === "undefined" || hasRequestedToastRef.current) return;
    hasRequestedToastRef.current = true;

    const dismissed = window.localStorage.getItem("starToastDismissed") === "true";
    const shownThisSession = sessionStorage.getItem(STAR_TOAST_SESSION_KEY) === "true";
    if (dismissed || shownThisSession) return;

    sessionStorage.setItem(STAR_TOAST_SESSION_KEY, "true");

    showToast({
      title: "Enjoying Autoroad?",
      description: "Star the repo on GitHub to support future improvements.",
      duration: 7000,
      action: (
        <ToastAction altText="Open GitHub" asChild>
          <a
            href={GITHUB_REPO_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex"
          >
            <Button
              size="sm"
              variant="secondary"
              className="gap-2 bg-[#24292f] text-white hover:bg-[#1b1f23]"
            >
              GitHub
            </Button>
          </a>
        </ToastAction>
      ),
      onOpenChange: (open) => {
        if (!open) {
          window.localStorage.setItem("starToastDismissed", "true");
        }
      },
    });
  }, []);

  return null;
}

export default StarOnGithubPopup;
