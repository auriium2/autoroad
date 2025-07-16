"use client";

import React from "react";
import { Search, X, ChevronDown } from "lucide-react";
import { Input } from "@/components/ui/input";

// Types
interface AvailableNode {
  id: string;
  name: string;
  category: string;
  description: string;
}

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
  return React.useMemo(() => {
    if (!searchTerm) return availableNodes;

    return availableNodes.filter(
      (node) =>
        node.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        node.category.toLowerCase().includes(searchTerm.toLowerCase()) ||
        node.description.toLowerCase().includes(searchTerm.toLowerCase()),
    );
  }, [searchTerm, availableNodes]);
}

function useNodeGrouping(filteredNodes: AvailableNode[]): Record<string, AvailableNode[]> {
  return React.useMemo(() => {
    const groups: Record<string, AvailableNode[]> = {};
    filteredNodes.forEach((node) => {
      if (!groups[node.category]) {
        groups[node.category] = [];
      }
      groups[node.category].push(node);
    });
    return groups;
  }, [filteredNodes]);
}

// Sub-components
interface DropdownHeaderProps {
  searchTerm: string;
  onSearchChange: (term: string) => void;
  onClose: () => void;
}

function DropdownHeader({ searchTerm, onSearchChange, onClose }: DropdownHeaderProps) {
  return (
    <div className="p-3 border-b border-border">
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-semibold text-sm text-foreground">Add Node</h3>
        <button
          onClick={onClose}
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
          onChange={(e) => onSearchChange(e.target.value)}
          className="pl-7 h-8 text-sm"
          autoFocus
        />
      </div>
    </div>
  );
}

interface NodeItemProps {
  node: AvailableNode;
  isSelected: boolean;
  onSelect: () => void;
}

function NodeItem({ node, isSelected, onSelect }: NodeItemProps) {
  return (
    <div
      onClick={onSelect}
      className={`p-2 rounded-md cursor-pointer transition-all duration-150 ${
        isSelected
          ? "bg-primary/10 border border-primary/30 text-primary"
          : "hover:bg-muted/50 text-foreground"
      }`}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <div
            className={`font-medium text-sm truncate ${
              isSelected ? "text-primary" : "text-foreground"
            }`}
          >
            {node.name}
          </div>
          <div
            className={`text-xs mt-1 line-clamp-2 ${
              isSelected ? "text-primary/70" : "text-muted-foreground"
            }`}
          >
            {node.description}
          </div>
        </div>
        {isSelected && (
          <div className="ml-2 flex-shrink-0">
            <div className="w-2 h-2 rounded-full bg-primary"></div>
          </div>
        )}
      </div>
    </div>
  );
}

interface NodeCategoryGroupProps {
  category: string;
  nodes: AvailableNode[];
  selectedNode: AvailableNode | null;
  onNodeSelect: (node: AvailableNode) => void;
}

function NodeCategoryGroup({ category, nodes, selectedNode, onNodeSelect }: NodeCategoryGroupProps) {
  return (
    <div className="mb-3 last:mb-0">
      <div className="flex items-center gap-2 px-2 py-1 text-xs font-medium text-muted-foreground uppercase tracking-wide">
        <ChevronDown className="h-3 w-3" />
        {category}
      </div>

      <div className="space-y-1">
        {nodes.map((node) => (
          <NodeItem
            key={node.id}
            node={node}
            isSelected={selectedNode?.id === node.id}
            onSelect={() => onNodeSelect(node)}
          />
        ))}
      </div>
    </div>
  );
}

interface NoResultsProps {
  message?: string;
}

function NoResults({ message = "No nodes found" }: NoResultsProps) {
  return (
    <div className="p-4 text-center text-muted-foreground text-sm">
      <div className="mb-2">{message}</div>
      <div className="text-xs">Try adjusting your search terms</div>
    </div>
  );
}

interface DropdownFooterProps {
  selectedNode: AvailableNode;
}

function DropdownFooter({ selectedNode }: DropdownFooterProps) {
  return (
    <div className="p-3 border-t border-border bg-muted/30">
      <div className="text-xs text-muted-foreground">
        Selected:{" "}
        <span className="font-medium text-foreground">
          {selectedNode.name}
        </span>
      </div>
    </div>
  );
}

// Main component
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
      className="node-dropdown absolute bg-card border border-border rounded-lg shadow-xl z-[9999] min-w-[320px] max-w-[400px] transition-all duration-200"
      style={{
        position: 'fixed' as const,
        left: `${dropdownPosition.x}px`, 
        top: `${dropdownPosition.y}px`,
      }}
    >
      <DropdownHeader
        searchTerm={searchTerm}
        onSearchChange={(term) => setSearchTerm(term)}
        onClose={() => setDropdownOpen(false)}
      />

      <div className="max-h-[300px] overflow-y-auto">
        {filteredNodes.length === 0 ? (
          <NoResults />
        ) : (
          <div className="p-2">
            {Object.entries(groupedNodes).map(([category, nodes]: [string, AvailableNode[]]) => (
              <NodeCategoryGroup
                key={category}
                category={category}
                nodes={nodes}
                selectedNode={selectedNode}
                onNodeSelect={(node) => setSelectedNode(node)}
              />
            ))}
          </div>
        )}
      </div>

      {selectedNode && <DropdownFooter selectedNode={selectedNode} />}
    </div>
  );
}
