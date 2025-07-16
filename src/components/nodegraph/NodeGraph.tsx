"use client";

import * as React from "react";
import { Plus } from "lucide-react";
import { Node as GraphNode } from "@/components/nodegraph/GraphNode";
import { GraphEdges } from "@/components/nodegraph/GraphEdges";
import { NodeHoverCard } from "@/components/nodegraph/NodeHoverCard";
import { AddNodeDropdown } from "@/components/AddNodeDropdown";
import { useGraphClassStore } from "./types";
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
  const [hoveredNodeRect, setHoveredNodeRect] = React.useState<DOMRect | null>(null);
  const [hoveredSection, setHoveredSection] = React.useState<number | null>(null);
  const [dropdownOpen, setDropdownOpen] = React.useState(false);
  // Removed fixed nodeGraphHeight for dynamic height

  const [dropdownPosition, setDropdownPosition] = React.useState<{ x: number; y: number } | null>(null);
  const [searchTerm, setSearchTerm] = React.useState("");
  const [selectedNode, setSelectedNode] = React.useState<typeof availableNodes[number] | null>(null);

  React.useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const handleScroll = () => setScrollLeft(container.scrollLeft);
    container.addEventListener("scroll", handleScroll);
    return () => container.removeEventListener("scroll", handleScroll);
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

  // Combine special section and regular sections for easier mapping
  const allSections = [specialSection, ...sections];
  const totalSections = allSections.length;

  // Calculate total width of the node graph content
  const totalWidth = totalSections * (sectionWidth + sectionPadding * 2);

  // Processed nodes with positions
  const positionedNodes = currentGraphClasses.map((graphClass) => {
    // If section is "special", its index is 0, otherwise find its index in sections and add 1
    const sectionIdx = graphClass.section === "special"
      ? 0
      : sections.findIndex(s => s.id === graphClass.section) + 1;

    const x = sectionIdx * (sectionWidth + sectionPadding * 2) + sectionWidth / 2 - nodeWidth / 2;

    // Calculate y position based on placement in section
    const nodesInSameSection = currentGraphClasses.filter((n) => n.section === graphClass.section);
    const nodeIndexInSection = nodesInSameSection.findIndex((n) => n.id === graphClass.id);
    const y =
      nodeIndexInSection * (nodeHeight + nodeMargin) +
      56 + // Padding from the top (header height)
      nodeHeight / 2;

    return { x, y, width: nodeWidth, height: nodeHeight, ...graphClass, sectionIdx };
  });

  return (
    <div ref={containerRef} className="h-full w-full min-h-screen overflow-x-auto overflow-y-hidden rounded-md border-border bg-muted/30 relative">
      <div
        ref={contentRef}
        className="relative h-full min-h-screen"
        style={{
          width: `${totalWidth}px`,
          height: "100%",
          minHeight: "100vh",
        }}
      >
        {/* Section backgrounds */}
        {allSections.map((section, idx) => (
          <div
            key={section.id}
            className={`absolute border-r border-border transition-colors duration-150`}
            style={{
              left: idx * (sectionWidth + sectionPadding * 2),
              top: 0,
              width: sectionWidth + sectionPadding * 2,
              height: "100%",
              minHeight: "100vh",
              background:
                hoveredSection === idx
                  ? "rgba(243, 244, 246, 0.7)" // bg-muted/70
                  : "transparent",
              zIndex: 1,
              cursor: "pointer",
            }}
            onMouseEnter={() => setHoveredSection(idx)}
            onMouseLeave={() => setHoveredSection(null)}
          />
        ))}

        {/* Section headers row */}
        <div
          className="grid"
          style={{
            gridTemplateColumns: `repeat(${totalSections}, ${sectionWidth + sectionPadding * 2}px)`,
            width: `${totalWidth}px`,
            position: "relative",
            zIndex: 2,
          }}
        >
          {allSections.map((section, idx) => (
            <div
              key={section.id}
              className="flex items-center w-full h-14"
              style={{
                padding: "0 12px",
                position: "relative",
                zIndex: 3,
              }}
            >
              <div className="flex-1 flex justify-center items-center relative w-full h-10">
                <span className="inline-block bg-white border border-border px-2 py-0.5 font-semibold text-xs text-muted-foreground text-center w-auto truncate shadow-sm">
                  {section.title}
                </span>
                <button
                  className="absolute right-0 top-1/2 -translate-y-1/2 w-5 h-5 flex items-center justify-center rounded-full border border-border bg-white text-muted-foreground hover:bg-muted hover:text-foreground transition z-10"
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
                  <Plus className="h-3 w-3" />
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Render connections */}
        <GraphEdges
          positionedNodes={positionedNodes}
          edges={edges}
          sectionWidth={sectionWidth}
          viewportHeight={containerRef.current?.clientHeight || window.innerHeight}
          totalWidth={totalWidth}
        />

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
          dropdownRef={dropdownRef as React.RefObject<HTMLDivElement>}
        />

        {/* Render nodes */}
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
            totalWidth={totalWidth}
            onMouseEnter={() => {}}
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
