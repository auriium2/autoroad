"use client";

import React from "react";

import {
  TrendingUp,
  Plus,
  ChevronDown,
  ChevronRight,
  Target,
  Settings,
  X,
} from "lucide-react";

import { Slider } from "@/components/ui/slider";
import { Label } from "@/components/ui/label";
import {
  Sidebar,
  SidebarContent,
  SidebarHeader,
} from "@/components/ui/sidebar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";

// Sample objectives data
const objectives = [
  {
    id: 1,
    title: "Minimize Processing Time",
    progress: 75,
    nodes: [
      { id: 2, label: "Load Data", optimized: true },
      { id: 7, label: "Transform Data", optimized: true },
      { id: 8, label: "Apply Filters", optimized: false },
      { id: 11, label: "Calculate Metrics", optimized: false },
    ],
  },
  {
    id: 2,
    title: "Maximize Throughput",
    progress: 45,
    nodes: [
      { id: 5, label: "Verify User", optimized: true },
      { id: 15, label: "Process A", optimized: false },
      { id: 16, label: "Process B", optimized: false },
      { id: 18, label: "Generate Report", optimized: true },
    ],
    disabled: true,
  },
  {
    id: 3,
    title: "Reduce Resource Usage",
    progress: 90,
    nodes: [
      { id: 9, label: "Cache Results", optimized: true },
      { id: 10, label: "Log Activity", optimized: true },
      { id: 20, label: "Archive Data", optimized: true },
    ],
  },
];

const availableObjectives = [
  {
    title: "Minimize Processing Time",
    subObjectives: [
      "Reduce Data Loading Time",
      "Optimize Transform Operations",
      "Streamline Filter Processing",
      "Accelerate Metric Calculations",
    ],
  },
  "Maximize Throughput",
  "Reduce Resource Usage",
  "Improve Reliability",
  "Optimize Memory Usage",
  "Enhance Security",
];

import { useOptimizationStore } from "../optimizer";

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const optimizationIntensity = useOptimizationStore((s) => s.optimizationIntensity);
  const setOptimizationIntensity = useOptimizationStore((s) => s.setOptimizationIntensity);
  const convergenceThreshold = useOptimizationStore((s) => s.convergenceThreshold);
  const setConvergenceThreshold = useOptimizationStore((s) => s.setConvergenceThreshold);

  const [expandedObjectives, setExpandedObjectives] = React.useState<number[]>([
    1,
  ]);
  const [showAddMenu, setShowAddMenu] = React.useState(false);
  const [submenuOpen, setSubmenuOpen] = React.useState<string | null>(null);

  const toggleObjective = (objectiveId: number) => {
    setExpandedObjectives((prev) =>
      prev.includes(objectiveId)
        ? prev.filter((id) => id !== objectiveId)
        : [...prev, objectiveId],
    );
  };

  const handleAddObjective = (objectiveTitle: string) => {
    // This would typically add a new objective to the state
    console.log("Adding objective:", objectiveTitle);
  };

  const handleDeleteObjective = (objectiveId: number) => {
    // This would typically remove the objective from the state
    console.log("Deleting objective:", objectiveId);
    // For demo purposes, you could implement actual deletion logic here
  };

  return (
    <Sidebar variant="sidebar" className="z-40 overflow-visible" {...props}>
      <SidebarHeader>
        <div className="flex items-center gap-2 px-2 py-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <TrendingUp className="h-4 w-4" />
          </div>
          <div className="flex flex-col">
            <span className="text-sm font-semibold">Dashboard</span>
            <span className="text-xs text-muted-foreground">v2.0.0</span>
          </div>
        </div>
      </SidebarHeader>
      <SidebarContent className="flex flex-col h-full z-40 overflow-visible">
        {/* Add Objective Button with Click Menu */}
        <div className="px-2 pb-4 relative overflow-visible">
          <div className="relative overflow-visible">
            <Button
              variant="outline"
              size="sm"
              className="w-full justify-start"
              onClick={() => setShowAddMenu((prev) => !prev)}
            >
              <Plus className="h-4 w-4 mr-2" />
              Add Objective
            </Button>
            {showAddMenu && (
              <div className="absolute left-0 top-full mt-1 w-56 bg-card border border-border rounded-md shadow-lg z-[999]">
                {availableObjectives.map((objective) =>
                  typeof objective === "string" ? (
                    <div
                      key={objective}
                      onClick={() => {
                        handleAddObjective(objective);
                        setShowAddMenu(false);
                      }}
                      className="flex items-center px-3 py-2 text-sm cursor-pointer hover:bg-muted/50 first:rounded-t-md last:rounded-b-md"
                    >
                      <Target className="h-4 w-4 mr-2" />
                      {objective}
                    </div>
                  ) : (
                    <div
                      key={objective.title}
                      className="relative"
                      onMouseEnter={() => setSubmenuOpen(objective.title)}
                      onMouseLeave={() => setSubmenuOpen(null)}
                    >
                      <div className="flex items-center justify-between px-3 py-2 text-sm cursor-pointer hover:bg-muted/50">
                        <div className="flex items-center">
                          <Target className="h-4 w-4 mr-2" />
                          {objective.title}
                        </div>
                        <ChevronRight className="h-4 w-4" />
                      </div>
                      {submenuOpen === objective.title && (
                        <div className="absolute left-full top-0 ml-1 w-56 bg-card border border-border rounded-md shadow-lg z-[999]">
                          {objective.subObjectives.map((subObjective) => (
                            <div
                              key={subObjective}
                              onClick={() => {
                                handleAddObjective(subObjective);
                                setShowAddMenu(false);
                              }}
                              className="flex items-center px-3 py-2 text-sm cursor-pointer hover:bg-muted/50 first:rounded-t-md last:rounded-b-md"
                            >
                              <Target className="h-4 w-4 mr-2" />
                              {subObjective}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ),
                )}
              </div>
            )}
          </div>
        </div>

        {/* Objectives Container - 70% of sidebar height */}
        <div
          className="flex-1 px-2 overflow-y-auto"
          style={{ maxHeight: "70%" }}
        >
          <div className="space-y-3">
            {objectives.map((objective) => (
              <Card
                key={objective.id}
                className={`w-full transition-all duration-200 gap-2 ${objective.disabled ? "opacity-60 bg-muted/30 border-muted cursor-not-allowed" : ""}`}
              >
                <CardHeader className="pb-0">
                  <div className="flex items-start justify-between">
                    <CardTitle
                      className={`text-sm font-medium flex-1 ${objective.disabled ? "text-muted-foreground line-through" : ""}`}
                    >
                      {objective.title}
                    </CardTitle>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 w-6 p-0 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                      onClick={() => handleDeleteObjective(objective.id)}
                      disabled={objective.disabled}
                    >
                      <X className="h-3 w-3" />
                    </Button>
                  </div>
                  <div className="space-y-2">
                    <Progress
                      value={objective.progress}
                      className={`h-2 ${objective.disabled ? "opacity-50" : ""}`}
                    />
                    <div
                      className={`text-xs ${objective.disabled ? "text-muted-foreground" : "text-muted-foreground"}`}
                    >
                      {objective.disabled
                        ? "Disabled"
                        : `${objective.progress}% optimized`}
                    </div>
                  </div>
                </CardHeader>

                <CardContent className="pt-0">
                  <Collapsible
                    open={expandedObjectives.includes(objective.id)}
                    onOpenChange={() => toggleObjective(objective.id)}
                  >
                    <CollapsibleTrigger asChild disabled={objective.disabled}>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="w-full justify-start p-0 h-6 m-0 ml-0 !pl-0"
                      >
                        {expandedObjectives.includes(objective.id) ? (
                          <ChevronDown className="h-3 w-3 mr-1" />
                        ) : (
                          <ChevronRight className="h-3 w-3 mr-1" />
                        )}
                        <span className="text-xs">
                          {objective.nodes.length} node
                          {objective.nodes.length !== 1 ? "s" : ""}
                        </span>
                      </Button>
                    </CollapsibleTrigger>
                    <CollapsibleContent className="mt-2">
                      <div className="space-y-1">
                        {objective.nodes.map((node) => (
                          <div
                            key={node.id}
                            className={`flex items-center justify-between text-xs py-1 px-2 rounded hover:bg-muted/50 ${objective.disabled ? "opacity-50" : ""}`}
                          >
                            <span
                              className={`truncate ${objective.disabled ? "text-muted-foreground" : ""}`}
                            >
                              {node.label}
                            </span>
                            <div
                              className={`w-2 h-2 rounded-full ${objective.disabled ? "bg-muted-foreground" : node.optimized ? "bg-green-500" : "bg-yellow-500"}`}
                              title={
                                objective.disabled
                                  ? "Disabled"
                                  : node.optimized
                                    ? "Optimized"
                                    : "Pending"
                              }
                            />
                          </div>
                        ))}
                      </div>
                    </CollapsibleContent>
                  </Collapsible>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* Bottom 30% - Reserved for future content */}
        <div className="flex-1 px-2 pt-4 border-t">
          <div className="space-y-4">
            {/* Section Header */}
            <div className="flex items-center gap-2 mb-3">
              <Settings className="h-4 w-4 text-muted-foreground" />
              <h3 className="text-sm font-semibold text-foreground">
                Optimization Parameters
              </h3>
            </div>

            {/* Optimization Intensity */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label
                  htmlFor="optimization-intensity"
                  className="text-xs font-medium text-foreground"
                >
                  Optimization Intensity
                </Label>
                <span className="text-xs text-muted-foreground">
                  {optimizationIntensity[0]}%
                </span>
              </div>
              <Slider
                id="optimization-intensity"
                value={optimizationIntensity}
                onValueChange={setOptimizationIntensity}
                max={100}
                step={5}
                className="w-full"
              />
              <p className="text-xs text-muted-foreground">
                Controls how aggressively the system optimizes workflows
              </p>
            </div>

            {/* Convergence Threshold */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label
                  htmlFor="convergence-threshold"
                  className="text-xs font-medium text-foreground"
                >
                  Convergence Threshold
                </Label>
                <span className="text-xs text-muted-foreground">
                  {convergenceThreshold[0]}%
                </span>
              </div>
              <Slider
                id="convergence-threshold"
                value={convergenceThreshold}
                onValueChange={setConvergenceThreshold}
                max={100}
                step={5}
                className="w-full"
              />
              <p className="text-xs text-muted-foreground">
                Minimum improvement required to continue optimization
              </p>
            </div>
          </div>
        </div>
      </SidebarContent>
    </Sidebar>
  );
}
