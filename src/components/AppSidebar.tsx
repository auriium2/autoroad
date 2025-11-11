"use client";

import * as React from "react";
import { Target, Search, Plus, ChevronDown, ChevronRight, X, User } from "lucide-react";
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
import { useSearchCourses } from "@/hooks/useCourseData";
import { CourseTooltip } from "@/components/CourseTooltip";
import { CourseNode as CourseNodeComponent } from "@/components/course-graph/CourseNode";
import { getNodeStyle } from "@/utils/nodeStyles";

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
  const { addNode } = useGraphStore();
  const [searchQuery, setSearchQuery] = React.useState("");
  const [selectedDepartment, setSelectedDepartment] = React.useState<string>("all");
  const [isDragging, setIsDragging] = React.useState(false);
  const [dragPosition, setDragPosition] = React.useState({ x: 0, y: 0 });
  const [currentSection, setCurrentSection] = React.useState(-2); // Track current hovered section
  const [isOverGraph, setIsOverGraph] = React.useState(false); // Track if cursor is over the graph

  // Use TanStack Query hook for course search
  const { data: courses = [], isLoading, isError } = useSearchCourses(searchQuery, selectedDepartment);

  const departments = ["all", "6", "18"];

  // Track mouse movement during drag using document event listener
  React.useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging) return;
      
      setDragPosition({ x: e.clientX, y: e.clientY });
      
      // Get the React Flow viewport to account for panning/zooming
      const flowViewport = document.querySelector('.react-flow__viewport');
      const canvas = document.querySelector('.react-flow');
      if (!canvas || !flowViewport) return;
      
      const canvasRect = canvas.getBoundingClientRect();
      
      // Check if cursor is actually over the graph
      const isInBounds = (
        e.clientX >= canvasRect.left &&
        e.clientX <= canvasRect.right &&
        e.clientY >= canvasRect.top &&
        e.clientY <= canvasRect.bottom
      );
      
      setIsOverGraph(isInBounds);
      
      if (!isInBounds) return; // Don't calculate section if not over graph
      
      const relativeX = e.clientX - canvasRect.left;
      
      // Get the viewport transform to account for panning
      const transform = window.getComputedStyle(flowViewport).transform;
      let panX = 0;
      if (transform && transform !== 'none') {
        const matrix = transform.match(/matrix\(([^)]+)\)/);
        if (matrix) {
          const values = matrix[1].split(',').map(parseFloat);
          panX = values[4] || 0; // translateX is at index 4
        }
      }
      
      // Adjust for pan offset
      const flowX = relativeX - panX;
      
      // Simple column detection (200px per column)
      const COLUMN_WIDTH = 200;
      const columnIndex = Math.floor(flowX / COLUMN_WIDTH);
      
      // Map column index to section ID
      // Column 0: Must Take (-2), Column 1: ASEs (-1), Column 2+: semester sections (0, 1, 2, ...)
      let sectionId: number;
      if (columnIndex === 0) {
        sectionId = -2; // Must Take
      } else if (columnIndex === 1) {
        sectionId = -1; // ASEs
      } else {
        sectionId = columnIndex - 2; // Semester sections start at column 2
      }
      
      setCurrentSection(sectionId);
    };

    if (isDragging) {
      document.addEventListener('dragover', handleMouseMove as any);
      return () => {
        document.removeEventListener('dragover', handleMouseMove as any);
      };
    }
  }, [isDragging]);

  // Compute drag preview style based on current section
  const dragPreviewStyle = React.useMemo(() => {
    return getNodeStyle({
      section: currentSection,
      userControlled: true, // Dragged nodes are always user-controlled
      disabled: false,
      isSpecial: false,
    });
  }, [currentSection]);

  const handleDragStart = (e: React.DragEvent, course: typeof courses[0]) => {
    e.dataTransfer.setData("application/json", JSON.stringify({
      id: `${course.subject_id}_${Date.now()}`,
      label: course.subject_id,
      section: -2, // Default to "Must Take" column
      userControlled: true,
    }));

    // Hide the default drag image by using an empty transparent image
    const img = new Image();
    img.src = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
    e.dataTransfer.setDragImage(img, 0, 0);
    
    setIsDragging(true);
    setDragPosition({ x: e.clientX, y: e.clientY });
  };

  const handleDragEnd = () => {
    setIsDragging(false);
    setIsOverGraph(false);
  };

  return (
    <div className="flex flex-col h-full p-4 space-y-4">
      {/* Custom drag preview that follows cursor - only show when over graph */}
      {isDragging && isOverGraph && (
        <div 
          className="fixed pointer-events-none z-50"
          style={{ 
            left: `${dragPosition.x - 20}px`, 
            top: `${dragPosition.y - 20}px`,
          }}
        >
          <div 
            className={`w-10 h-10 rounded-full border-2 ${dragPreviewStyle.borderColor} ${dragPreviewStyle.bgColor} flex items-center justify-center shadow-sm transition-colors duration-150`}
            style={{ boxShadow: dragPreviewStyle.boxShadow }}
          >
            <User className={`h-3 w-3 ${dragPreviewStyle.textColor}`} />
          </div>
        </div>
      )}

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
        {isLoading && (
          <div className="text-center text-sm text-muted-foreground py-8">
            Loading courses...
          </div>
        )}
        {isError && (
          <div className="text-center text-sm text-destructive py-8">
            Failed to load courses
          </div>
        )}
        {!isLoading && !isError && courses.map((course) => {
          // Guard against missing data
          if (!course || !course.subject_id || !course.title) {
            console.warn('Invalid course data:', course);
            return null;
          }
          
          return (
            <div
              key={course.subject_id}
              className="p-3 border border-border rounded-lg transition-colors"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="font-medium text-sm">{course.subject_id}</div>
                  <div className="text-xs text-muted-foreground line-clamp-2">
                    {course.title}
                  </div>
                </div>
                <CourseTooltip courseId={course.subject_id}>
                  <div
                    draggable
                    onDragStart={(e) => handleDragStart(e, course)}
                    onDragEnd={handleDragEnd}
                    className="w-8 h-8 rounded-full border-2 border-border bg-card hover:border-primary hover:bg-primary/10 hover:shadow-md flex items-center justify-center text-xs font-bold flex-shrink-0 ml-2 cursor-move transition-all duration-200"
                  >
                    D
                  </div>
                </CourseTooltip>
              </div>
            </div>
          );
        })}
        {!isLoading && !isError && courses.length === 0 && (
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
