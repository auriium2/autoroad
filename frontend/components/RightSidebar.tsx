"use client";

import * as React from "react";
import { Sliders } from "lucide-react";
import { ParametersTab } from "./app-sidebar/ParametersTab/ParametersTab";

export function RightSidebar() {
  return (
    <div className="w-80 border-l border-border/50 bg-background flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex h-16 shrink-0 items-center gap-2 border-b border-border/50 px-4 relative z-10 glass dark:glass-dark">
        <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <Sliders className="h-4 w-4" />
          Parameters
        </div>
      </div>
      
      {/* Content */}
      <div className="flex-1 overflow-hidden">
        <ParametersTab />
      </div>
    </div>
  );
}
