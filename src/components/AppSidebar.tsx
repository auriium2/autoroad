"use client";

import * as React from "react";
import { Target, Search, Plus, ChevronDown, ChevronRight, X } from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarHeader,
} from "@/components/ui/sidebar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { useGraphStore } from "@/stores/roadStore";

// Objectives tab component
function ObjectivesTab() {
  const [expandedObjectives, setExpandedObjectives] = React.useState<number[]>([]);
  const [objectives, setObjectives] = React.useState([
    {
      id: 1,
      title: "Complete Course 6 Requirements",
      progress: 60,
      constraints: [
        { id: 1, label: "Take 6.1200", fulfilled: true },
        { id: 2, label: "Take 6.1010", fulfilled: true },
        { id: 3, label: "Take 6.1020", fulfilled: false },
        { id: 4, label: "Complete 3 AUSes", fulfilled: false },
      ],
    },
  ]);
  const [showAddMenu, setShowAddMenu] = React.useState(false);
  const [newObjectiveTitle, setNewObjectiveTitle] = React.useState("");

  const toggleObjective = (objectiveId: number) => {
    setExpandedObjectives((prev) =>
      prev.includes(objectiveId)
        ? prev.filter((id) => id !== objectiveId)
        : [...prev, objectiveId],
    );
  };

  const handleAddObjective = () => {
    if (!newObjectiveTitle.trim()) return;
    
    const newObjective = {
      id: Date.now(),
      title: newObjectiveTitle,
      progress: 0,
      constraints: [],
    };
    
    setObjectives([...objectives, newObjective]);
    setNewObjectiveTitle("");
    setShowAddMenu(false);
  };

  const handleDeleteObjective = (objectiveId: number) => {
    setObjectives(objectives.filter(obj => obj.id !== objectiveId));
  };

  return (
    <div className="flex flex-col h-full p-4 space-y-4">
      {/* Add Objective Button */}
      <div className="relative">
        {!showAddMenu ? (
          <Button
            variant="outline"
            size="sm"
            className="w-full justify-start"
            onClick={() => setShowAddMenu(true)}
          >
            <Plus className="h-4 w-4 mr-2" />
            Add Objective
          </Button>
        ) : (
          <div className="space-y-2">
            <Input
              placeholder="Enter objective title..."
              value={newObjectiveTitle}
              onChange={(e) => setNewObjectiveTitle(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleAddObjective();
                if (e.key === 'Escape') setShowAddMenu(false);
              }}
              autoFocus
            />
            <div className="flex gap-2">
              <Button size="sm" onClick={handleAddObjective}>Add</Button>
              <Button size="sm" variant="outline" onClick={() => setShowAddMenu(false)}>Cancel</Button>
            </div>
          </div>
        )}
      </div>

      {/* Objectives List */}
      <div className="flex-1 overflow-y-auto space-y-3">
        {objectives.map((objective) => {
          const fulfilledCount = objective.constraints.filter(c => c.fulfilled).length;
          const progress = objective.constraints.length > 0 
            ? (fulfilledCount / objective.constraints.length) * 100 
            : 0;

          return (
            <Card key={objective.id} className="w-full">
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between">
                  <CardTitle className="text-sm font-medium flex-1">
                    {objective.title}
                  </CardTitle>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 w-6 p-0 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                    onClick={() => handleDeleteObjective(objective.id)}
                  >
                    <X className="h-3 w-3" />
                  </Button>
                </div>
                <div className="space-y-2">
                  <Progress value={progress} className="h-2" />
                  <div className="text-xs text-muted-foreground">
                    {fulfilledCount} / {objective.constraints.length} constraints fulfilled
                  </div>
                </div>
              </CardHeader>

              <CardContent className="pt-0">
                <Collapsible
                  open={expandedObjectives.includes(objective.id)}
                  onOpenChange={() => toggleObjective(objective.id)}
                >
                  <CollapsibleTrigger asChild>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="w-full justify-start p-0 h-6"
                    >
                      {expandedObjectives.includes(objective.id) ? (
                        <ChevronDown className="h-3 w-3 mr-1" />
                      ) : (
                        <ChevronRight className="h-3 w-3 mr-1" />
                      )}
                      <span className="text-xs">
                        {objective.constraints.length} constraint{objective.constraints.length !== 1 ? "s" : ""}
                      </span>
                    </Button>
                  </CollapsibleTrigger>
                  <CollapsibleContent className="mt-2">
                    <div className="space-y-1">
                      {objective.constraints.map((constraint) => (
                        <div
                          key={constraint.id}
                          className="flex items-center justify-between text-xs py-1 px-2 rounded hover:bg-muted/50"
                        >
                          <span className="truncate">{constraint.label}</span>
                          <div
                            className={`w-2 h-2 rounded-full ${constraint.fulfilled ? "bg-green-500" : "bg-yellow-500"}`}
                            title={constraint.fulfilled ? "Fulfilled" : "Not fulfilled"}
                          />
                        </div>
                      ))}
                    </div>
                  </CollapsibleContent>
                </Collapsible>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}

// Course Search tab component
function CourseSearchTab() {
  const { nodes: storeNodes, addNode } = useGraphStore();
  const [searchQuery, setSearchQuery] = React.useState("");
  const [selectedDepartment, setSelectedDepartment] = React.useState<string>("all");

  // Sample course data - in production this would come from an API
  const allCourses = [
    { id: "6.1200", label: "6.1200", department: "6", name: "Mathematics for Computer Science" },
    { id: "6.1010", label: "6.1010", department: "6", name: "Fundamentals of Programming" },
    { id: "6.1020", label: "6.1020", department: "6", name: "Software Construction" },
    { id: "6.1800", label: "6.1800", department: "6", name: "Computer Systems Engineering" },
    { id: "6.3700", label: "6.3700", department: "6", name: "Introduction to Probability" },
    { id: "18.01", label: "18.01", department: "18", name: "Single Variable Calculus" },
    { id: "18.02", label: "18.02", department: "18", name: "Multivariable Calculus" },
    { id: "18.03", label: "18.03", department: "18", name: "Differential Equations" },
  ];

  const departments = ["all", "6", "18"];

  const filteredCourses = allCourses.filter(course => {
    const matchesSearch = course.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         course.name.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesDepartment = selectedDepartment === "all" || course.department === selectedDepartment;
    return matchesSearch && matchesDepartment;
  });

  const handleDragStart = (e: React.DragEvent, course: typeof allCourses[0]) => {
    e.dataTransfer.setData("application/json", JSON.stringify({
      id: `${course.id}_${Date.now()}`,
      label: course.id,
      section: -2, // Default to "Must Take" column
      locked: true,
      user_added: true,
    }));
  };

  return (
    <div className="flex flex-col h-full p-4 space-y-4">
      {/* Search Input */}
      <div className="space-y-2">
        <Label htmlFor="course-search" className="text-sm font-medium">
          Search Courses
        </Label>
        <div className="relative">
          <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            id="course-search"
            placeholder="Search by number or name..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-8"
          />
        </div>
      </div>

      {/* Department Filter */}
      <div className="space-y-2">
        <Label className="text-sm font-medium">Department</Label>
        <div className="flex gap-2 flex-wrap">
          {departments.map((dept) => (
            <Button
              key={dept}
              size="sm"
              variant={selectedDepartment === dept ? "default" : "outline"}
              onClick={() => setSelectedDepartment(dept)}
            >
              {dept === "all" ? "All" : dept}
            </Button>
          ))}
        </div>
      </div>

      {/* Course List */}
      <div className="flex-1 overflow-y-auto space-y-2">
        <div className="text-xs text-muted-foreground mb-2">
          Drag courses to add them to the graph
        </div>
        {filteredCourses.map((course) => (
          <div
            key={course.id}
            draggable
            onDragStart={(e) => handleDragStart(e, course)}
            className="p-3 border border-border rounded-lg cursor-move hover:bg-muted/50 transition-colors"
          >
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="font-medium text-sm">{course.id}</div>
                <div className="text-xs text-muted-foreground line-clamp-2">
                  {course.name}
                </div>
              </div>
              <div className="w-8 h-8 rounded-full border-2 border-border bg-card flex items-center justify-center text-xs font-bold flex-shrink-0 ml-2">
                D
              </div>
            </div>
          </div>
        ))}
        {filteredCourses.length === 0 && (
          <div className="text-center text-sm text-muted-foreground py-8">
            No courses found
          </div>
        )}
      </div>
    </div>
  );
}

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const [activeTab, setActiveTab] = React.useState<"objectives" | "courses">("objectives");

  return (
    <Sidebar variant="sidebar" className="z-40" {...props}>
      <SidebarHeader>
        <div className="flex items-center gap-2 px-4 py-3 border-b">
          <div className="text-lg font-semibold">Autoroad</div>
        </div>
        {/* Tabs */}
        <div className="flex border-b">
          <button
            onClick={() => setActiveTab("objectives")}
            className={`flex-1 px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === "objectives"
                ? "text-foreground border-b-2 border-primary"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <Target className="h-4 w-4 inline mr-2" />
            Objectives
          </button>
          <button
            onClick={() => setActiveTab("courses")}
            className={`flex-1 px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === "courses"
                ? "text-foreground border-b-2 border-primary"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <Search className="h-4 w-4 inline mr-2" />
            Courses
          </button>
        </div>
      </SidebarHeader>
      <SidebarContent className="overflow-hidden">
        {activeTab === "objectives" ? <ObjectivesTab /> : <CourseSearchTab />}
      </SidebarContent>
    </Sidebar>
  );
}
