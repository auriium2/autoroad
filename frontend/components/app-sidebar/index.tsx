"use client";

import * as React from "react";
import { Search, Sliders } from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarHeader,
} from "@/components/ui/sidebar";
import { CourseSearchTab } from "./CourseSearchTab/CourseSearchTab";
import { ParametersTab } from "./ParametersTab/ParametersTab";

interface AppSidebarProps extends React.ComponentProps<typeof Sidebar> {}

export function AppSidebar({ ...props }: AppSidebarProps) {
  const [activeTab, setActiveTab] = React.useState<'courses' | 'objectives'>('courses');

  return (
    <Sidebar variant="sidebar" className="z-40" {...props}>
      <SidebarHeader>
        {/* Header with Tabs */}
        <div className="flex border-b border-border">
          <button
            onClick={() => setActiveTab('courses')}
            className={`flex-1 px-4 py-3 text-sm font-medium transition-colors flex items-center justify-center gap-2 ${
              activeTab === 'courses'
                ? 'text-foreground border-b-2 border-primary'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            <Search className="h-4 w-4" />
            Courses
          </button>
          <button
            onClick={() => setActiveTab('objectives')}
            className={`flex-1 px-4 py-3 text-sm font-medium transition-colors flex items-center justify-center gap-2 ${
              activeTab === 'objectives'
                ? 'text-foreground border-b-2 border-primary'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            <Sliders className="h-4 w-4" />
            Objectives
          </button>
        </div>
      </SidebarHeader>
      
      <SidebarContent className="overflow-hidden">
        {activeTab === 'courses' ? <CourseSearchTab /> : <ParametersTab />}
      </SidebarContent>
    </Sidebar>
  );
}
