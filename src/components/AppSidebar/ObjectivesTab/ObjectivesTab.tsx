import * as React from "react";
import { Plus, ChevronDown, ChevronRight, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Input } from "@/components/ui/input";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";

interface Constraint {
  id: number;
  label: string;
  fulfilled: boolean;
}

interface Objective {
  id: number;
  title: string;
  progress: number;
  constraints: Constraint[];
}

export function ObjectivesTab() {
  const [expandedObjectives, setExpandedObjectives] = React.useState<number[]>([]);
  const [objectives, setObjectives] = React.useState<Objective[]>([
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

    const newObjective: Objective = {
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
