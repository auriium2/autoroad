"use client";

import React from "react";
import { Search, X, ChevronDown } from "lucide-react";
import { Input } from "@/components/ui/input";
import type { AvailableNode } from "@/types";

interface AddNodeDropdownProps {
  dropdownOpen: boolean;
  dropdownPosition: { x: number; y: number } | null;
  setDropdownOpen: React.Dispatch<React.SetStateAction<boolean>>;
  setDropdownPosition: React.Dispatch<React.SetStateAction<{ x: number; y: number } | null>>;
  searchTerm: string;
  setSearchTerm: React.Dispatch<React.SetStateAction<string>>;
  availableNodes: AvailableNode[];
  selectedNode: AvailableNode | null;
  setSelectedNode: React.Dispatch<React.SetStateAction<AvailableNode | null>>;
  scrollLeft: number;
  viewportWidth: number;
  totalWidth: number;
  viewportHeight: number;
  dropdownRef?: React.RefObject<HTMLDivElement>;
}

function useNodeFiltering(availableNodes: AvailableNode[], searchTerm: string): AvailableNode[] {
  if (!searchTerm) return availableNodes;

  return availableNodes.filter(
    (node) =>
      node.courseId.toLowerCase().includes(searchTerm.toLowerCase()) ||
      node.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      node.department.toLowerCase().includes(searchTerm.toLowerCase()),
  );
}

function useNodeGrouping(filteredNodes: AvailableNode[]): Record<string, AvailableNode[]> {
  const groups: Record<string, AvailableNode[]> = {};
  filteredNodes.forEach((node) => {
    if (!groups[node.department]) {
      groups[node.department] = [];
    }
    groups[node.department].push(node);
  });
  return groups;
}

export function AddNodeDropdown({
  dropdownOpen,
  dropdownPosition,
  setDropdownOpen,
  setDropdownPosition,
  searchTerm,
  setSearchTerm,
  availableNodes,
  selectedNode,
  setSelectedNode,
  scrollLeft,
  viewportWidth,
  totalWidth,
  viewportHeight,
  dropdownRef,
}: AddNodeDropdownProps) {
  const filteredNodes = useNodeFiltering(availableNodes, searchTerm);
  const groupedNodes = useNodeGrouping(filteredNodes);

  // Only render if dropdown should be visible and has a position
  if (!dropdownOpen || !dropdownPosition) return null;

  return (
    <div
      ref={dropdownRef}
      className="fixed bg-popover text-popover-foreground border border-border rounded-lg shadow-lg min-w-[320px] max-w-[400px] z-50 overflow-hidden"
      style={{
        left: `${dropdownPosition.x}px`,
        top: `${dropdownPosition.y}px`,
      }}
    >
      {/* Header */}
      <div className="p-3 border-b border-border">
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-semibold text-sm text-foreground">Add Node</h3>
          <button
            onClick={() => setDropdownOpen(false)}
            className="text-muted-foreground hover:text-foreground transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="relative">
          <Search className="absolute left-2 top-1/2 transform -translate-y-1/2 h-3 w-3 text-muted-foreground" />
          <Input
            placeholder="Search nodes..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-7 h-8 text-sm"
            autoFocus
          />
        </div>
      </div>

      {/* Content */}
      <div className="max-h-[300px] overflow-y-auto">
        {filteredNodes.length === 0 ? (
          <div className="p-4 text-center text-muted-foreground text-sm">
            <div className="mb-2">No nodes found</div>
            <div className="text-xs">Try adjusting your search terms</div>
          </div>
        ) : (
          <div className="p-2">
            {Object.entries(groupedNodes).map(([category, nodes], categoryIndex) => (
              <div key={category} className="mb-3 last:mb-0">
                <div className="flex items-center gap-2 px-2 py-1 text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  <ChevronDown className="h-3 w-3" />
                  {category}
                </div>

                <div className="space-y-1">
                  {nodes.map((node) => (
                    <div
                      key={node.courseId}
                      onClick={() => setSelectedNode(node)}
                      className={`p-2 rounded-md cursor-pointer transition-all duration-150 ${
                        selectedNode?.courseId === node.courseId
                          ? "bg-primary/10 border border-primary/30 text-primary"
                          : "hover:bg-accent/50 text-foreground"
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1 min-w-0">
                          <div
                            className={`font-medium text-sm truncate ${
                              selectedNode?.courseId === node.courseId ? "text-primary" : "text-foreground"
                            }`}
                          >
                            {node.courseId}
                          </div>
                          <div
                            className={`text-xs mt-1 line-clamp-2 ${
                              selectedNode?.courseId === node.courseId ? "text-primary/70" : "text-muted-foreground"
                            }`}
                          >
                            {node.title} • {node.units} units
                          </div>
                        </div>
                        {selectedNode?.courseId === node.courseId && (
                          <div className="ml-2 flex-shrink-0">
                            <div className="w-2 h-2 rounded-full bg-primary"></div>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      {selectedNode && (
        <div className="p-3 border-t border-border bg-muted/30">
          <div className="text-xs text-muted-foreground">
            Selected:{" "}
            <span className="font-medium text-foreground">
              {selectedNode.courseId} - {selectedNode.title}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}