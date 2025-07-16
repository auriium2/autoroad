"use client";

import * as React from "react";
import { Plus } from "lucide-react";
import { Node as GraphNode } from "@/components/nodegraph/GraphNode";
import { GraphEdges } from "@/components/nodegraph/GraphEdges";
import { NodeHoverCard } from "@/components/nodegraph/NodeHoverCard";
import { AddNodeDropdown } from "@/components/AddNodeDropdown";
import { useGraphClassStore, PositionedGraphClass } from "./types";
import {
  edges,
  sections,
  availableNodes,
  nodeDetails,
  specialSection,

} from "@/debug";


export function NodeGraph() {

  const currentGraphClasses = useGraphClassStore((state) => state.classes);

  const containerRef = React.useRef<HTMLDivElement>(null);
  const contentRef = React.useRef<HTMLDivElement>(null);
  const dropdownRef = React.useRef<HTMLDivElement>(null);
  const [scrollLeft, setScrollLeft] = React.useState(0);
  const [hoveredNode, setHoveredNode] = React.useState<number | null>(null);
  const [hoveredNodeRect, setHoveredNodeRect] = React.useState<DOMRect | null>(
    null,
  );
  const [hoveredSection, setHoveredSection] = React.useState<number | null>(
    null,
  );
  const [dropdownOpen, setDropdownOpen] = React.useState(false);
  // Fixed dimensions
  const nodeGraphHeight = 600; // Fixed height for consistent rendering

  const [dropdownPosition, setDropdownPosition] = React.useState<{
    x: number;
    y: number;
  } | null>(null);
  const [searchTerm, setSearchTerm] = React.useState("");
  const [selectedNode, setSelectedNode] = React.useState<typeof availableNodes[number] | null>(null);

  // Monitor scroll position


  React.useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const handleScroll = () => setScrollLeft(container.scrollLeft);
    container.addEventListener('scroll', handleScroll);
    return () => container.removeEventListener('scroll', handleScroll);
  }, []);

  React.useEffect(() => {
    if (!dropdownOpen) return;
    const h = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node) && !e.defaultPrevented) setDropdownOpen(false);
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, [dropdownOpen]);


  // Section width calculation
  const sectionWidth = 200; // Width of each section
  const sectionPadding = 10; // Padding between sections
  const nodeWidth = 140; // Width of each node
  const nodeHeight = 40; // Height of each node
  const nodeMargin = 20; // Margin between nodes

  // Calculate total width of the node graph content
  const totalWidth =
    (sections.length + 1) * (sectionWidth + sectionPadding) +
    sectionPadding * 2; // +1 for special section

  // Nodes data
  // Processed nodes with positions
  const positionedNodes = currentGraphClasses.map((graphClass) => {
    const x = graphClass.section * (sectionWidth + sectionPadding) + sectionWidth / 2 - nodeWidth / 2 + sectionPadding;

    // Calculate y position based on placement in section
    const nodesInSameSection = currentGraphClasses.filter((n) => n.section === graphClass.section);
    const nodeIndexInSection = nodesInSameSection.findIndex((n) => n.id === graphClass.id);
    const y =
      nodeIndexInSection * (nodeHeight + nodeMargin) +
      40 + // Padding from the top
      nodeHeight / 2;


    return { x, y, width: nodeWidth, height: nodeHeight, ...graphClass };
  });

  return (
    <div ref={containerRef} className="h-full w-full overflow-x-auto overflow-y-hidden border-t border-border bg-muted/30 relative">
      <div
        ref={contentRef}
        className="relative h-full"
        style={{
          width: `${totalWidth}px`,
          height: `${nodeGraphHeight}px`,
        }}
      >
        {/* Section backgrounds */}
        {/* Special section */}
        <div
          className={`absolute top-0 bottom-0 border-r border-border ${
            hoveredSection === 0
              ? "bg-muted/70 transition-colors duration-150"
              : "bg-transparent"
          }`}
          style={{
            left: 0,
            width: sectionWidth + sectionPadding * 2,
          }}
          onMouseEnter={() => setHoveredSection(0)}
          onMouseLeave={() => setHoveredSection(null)}
        >
          <div className="h-7 flex items-center px-3 text-xs font-medium text-muted-foreground">
            {specialSection.title}
          </div>
        </div>

        {/* Regular sections */}
        {sections.map((section, index) => (
          <div
            key={section.id}
            className={`absolute top-0 bottom-0 border-r border-border ${
              hoveredSection === index + 1
                ? "bg-muted/70 transition-colors duration-150"
                : "bg-transparent"
            }`}
            style={{
              left: (index + 1) * (sectionWidth + sectionPadding),
              width: sectionWidth + sectionPadding * 2,
            }}
            onMouseEnter={() => setHoveredSection(index + 1)}
            onMouseLeave={() => setHoveredSection(null)}
          >
            <div className="h-7 flex items-center px-3 text-xs font-medium text-muted-foreground">
              {section.title}
            </div>
          </div>
        ))}

        {/* Render connections */}
        <GraphEdges
          positionedNodes={positionedNodes}
          edges={edges}
          sectionWidth={sectionWidth}
          viewportHeight={nodeGraphHeight}
          totalWidth={totalWidth}
        />

        {/* Persistent Plus Icons for each section - Upper Right Corner */}
        {/* Special section plus icon */}
        <div
          key="special-section-plus"
          className="absolute top-2 w-5 h-5 rounded-full border cursor-pointer transition-all duration-200 flex items-center justify-center bg-background border-border text-muted-foreground hover:bg-muted hover:text-foreground hover:scale-110 hover:shadow-md z-[15]"
          style={{
            left: sectionWidth - 28, // Position from left (section width - icon width - padding)
          }}
          onClick={(e) => {
            setDropdownOpen((prev) => {
              // If already open, close it
              if (prev) {
                setDropdownPosition(null);
                return false;
              }
              // Open and set position
              const rect = (
                e.target as HTMLElement
              ).getBoundingClientRect();
              const contentRect =
                contentRef.current?.getBoundingClientRect();
              if (contentRect) {
                const x =
                  rect.left -
                  contentRect.left +
                  rect.width +
                  8 +
                  scrollLeft;
                const y = rect.top - contentRect.top;
                setDropdownPosition({ x, y });
              }
              return true;
            });
          }}
          title={`Add node to ${specialSection.title} section`}
        >
          <Plus className="h-2.5 w-2.5" />
        </div>

        {/* Regular section plus icons */}
        {sections.map((section, index) => (
          <div
            key={`section-plus-${section.id}`}
            className="absolute top-2 w-5 h-5 rounded-full border cursor-pointer transition-all duration-200 flex items-center justify-center bg-background border-border text-muted-foreground hover:bg-muted hover:border-border hover:text-foreground hover:scale-110 hover:shadow-md z-[15]"
            style={{
              left: (index + 1) * sectionWidth + sectionWidth - 28, // +1 to account for special section, position from right edge
            }}
            onClick={(e) => {
              setDropdownOpen((prev) => {
                if (prev) {
                  setDropdownPosition(null);
                  return false;
                }
                const rect = (
                  e.target as HTMLElement
                ).getBoundingClientRect();
                const contentRect =
                  contentRef.current?.getBoundingClientRect();
                if (contentRect) {
                  const x =
                    rect.left -
                    contentRect.left +
                    rect.width +
                    8 +
                    scrollLeft;
                  const y = rect.top - contentRect.top;
                  setDropdownPosition({ x, y });
                }
                return true;
              });
            }}
            title={`Add node to ${section.title} section`}
          >
            <Plus className="h-2.5 w-2.5" />
          </div>
        ))}

        <AddNodeDropdown
          dropdownOpen={dropdownOpen}
          dropdownPosition={dropdownPosition}
          setDropdownOpen={setDropdownOpen}
          setDropdownPosition={setDropdownPosition}
          searchTerm={searchTerm}
          setSearchTerm={setSearchTerm}
          availableNodes={availableNodes}
          selectedNode={selectedNode}
          setSelectedNode={setSelectedNode}
          scrollLeft={scrollLeft}
          viewportWidth={containerRef.current?.clientWidth || 0}
          totalWidth={totalWidth}
          viewportHeight={nodeGraphHeight}
          dropdownRef={dropdownRef as React.RefObject<HTMLDivElement>}
        />

        {/* Render nodes with reduced z-index */}
        {positionedNodes.map((node) => {
          const isSpecial = node.section === "special";
          const isHovered = hoveredNode === node.id;
          return (
            <GraphNode
              key={node.id}
              node={node}
              isSpecial={isSpecial}
              isHovered={isHovered}
              details={nodeDetails[node.id as keyof typeof nodeDetails] || {}}
              handleNodeHover={(nodeId, event) => {
                setHoveredNode(nodeId);
                setHoveredNodeRect(event.currentTarget.getBoundingClientRect());
              }}
              handleNodeLeave={() => {
                setHoveredNode(null);
                setHoveredNodeRect(null);
              }}
            />
          );
        })}

        {/* Render hover card last to be on top */}
        {hoveredNode !== null && hoveredNodeRect && (
          <NodeHoverCard
            node={positionedNodes.find((n) => n.id === hoveredNode)!}
            details={nodeDetails[hoveredNode as keyof typeof nodeDetails] || {}}
            containerRef={containerRef as React.RefObject<HTMLDivElement>}
            scrollLeft={scrollLeft}
            viewportWidth={containerRef.current?.clientWidth || 0}
            viewportHeight={nodeGraphHeight}
            totalWidth={totalWidth}
            onMouseEnter={() => {
              // Keep hover card visible
            }}
            onMouseLeave={() => {
              setHoveredNode(null);
              setHoveredNodeRect(null);
            }}
          />
        )}
      </div>
    </div>
  );
}
