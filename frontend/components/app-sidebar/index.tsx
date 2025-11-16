"use client";

import * as React from "react";
import { Search, Sliders, LucideIcon } from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarHeader,
} from "@/components/ui/sidebar";
import { CourseSearchTab } from "./CourseSearchTab/CourseSearchTab";
import { ParametersTab } from "./ParametersTab/ParametersTab";

// Tab configuration - makes it easy to add/remove/reorder tabs
interface TabConfig {
  id: string;
  label: string;
  icon: LucideIcon;
  component: React.ComponentType;
}

const TABS: TabConfig[] = [
  {
    id: "courses",
    label: "Courses",
    icon: Search,
    component: CourseSearchTab,
  },
  {
    id: "parameters",
    label: "Parameters",
    icon: Sliders,
    component: ParametersTab,
  },
];

interface AppSidebarProps extends React.ComponentProps<typeof Sidebar> {}

export function AppSidebar({ ...props }: AppSidebarProps) {
  const [activeTab, setActiveTab] = React.useState<string>("courses");

  // Find the active tab component
  const activeTabConfig = TABS.find(tab => tab.id === activeTab);
  const ActiveComponent = activeTabConfig?.component || TABS[0].component;

  return (
    <Sidebar variant="sidebar" className="z-40" {...props}>
      <SidebarHeader>
        {/* Tab Navigation */}
        <div className="flex border-b">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex-1 px-3 py-2 text-xs font-medium transition-colors ${
                  isActive
                    ? "text-foreground border-b-2 border-primary"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <Icon className="h-3 w-3 inline mr-1" />
                {tab.label}
              </button>
            );
          })}
        </div>
      </SidebarHeader>
      
      <SidebarContent className="overflow-hidden">
        <ActiveComponent />
      </SidebarContent>
    </Sidebar>
  );
}
