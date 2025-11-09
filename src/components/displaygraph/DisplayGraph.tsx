"use client";

import * as React from "react";
import { Node as GraphNode } from "@/components/displaygraph/GraphNode";
import { GraphEdges } from "@/components/displaygraph/GraphEdges";
import { NodeHoverCard } from "@/components/displaygraph/NodeHoverCard";
import { useGraphStore, CourseNode, Section } from "@/stores/roadStore";

// Node with position info
export interface PositionedNode extends CourseNode {
  x: number;
  y: number;
}

export function NodeGraph() {
  const { nodes, edges, sections, specialSection } = useGraphStore();

  const containerRef = React.useRef<HTMLDivElement>(null);
  const [hoveredNode, setHoveredNode] = React.useState<string | null>(null);
  const [positionedNodes, setPositionedNodes] = React.useState<PositionedNode[]>([]);

  // Load initial data
  React.useEffect(() => {
    useGraphStore.getState().loadInitialData();
  }, []);

  // Build sections array (special section first, then regular sections)
  const allSections: Section[] = React.useMemo(() => {
    return specialSection ? [specialSection, ...sections] : sections;
  }, [specialSection, sections]);

  // Group nodes by section
  const nodesBySection = React.useMemo(() => {
    const grouped = new Map<number, CourseNode[]>();
    allSections.forEach(section => {
      grouped.set(section.id, nodes.filter(n => n.section === section.id));
    });
    return grouped;
  }, [nodes, allSections]);

  // Calculate positions after render
  React.useEffect(() => {
    const calculatePositions = () => {
      const positioned: PositionedNode[] = [];
      const containerRect = containerRef.current?.getBoundingClientRect();
      
      if (!containerRect) return;
      
      allSections.forEach((section) => {
        const sectionNodes = nodesBySection.get(section.id) || [];
        
        sectionNodes.forEach((node) => {
          // Get the circle element specifically, not the container
          const circleElement = document.querySelector(`[data-node-circle="${node.id}"]`);
          if (circleElement) {
            const rect = circleElement.getBoundingClientRect();
            const scrollLeft = containerRef.current?.scrollLeft || 0;
            const scrollTop = containerRef.current?.scrollTop || 0;
            
            // Center point of the circle
            positioned.push({
              ...node,
              x: rect.left - containerRect.left + scrollLeft + rect.width / 2,
              y: rect.top - containerRect.top + scrollTop + rect.height / 2,
            });
          }
        });
      });
      
      setPositionedNodes(positioned);
    };

    // Wait for DOM to be ready, then calculate
    const timer = setTimeout(calculatePositions, 100);
    
    // Recalculate on resize or scroll
    window.addEventListener('resize', calculatePositions);
    const container = containerRef.current;
    container?.addEventListener('scroll', calculatePositions);
    
    return () => {
      clearTimeout(timer);
      window.removeEventListener('resize', calculatePositions);
      container?.removeEventListener('scroll', calculatePositions);
    };
  }, [nodes, allSections, nodesBySection]);

  return (
    <div 
      ref={containerRef} 
      className="h-full w-full overflow-x-auto overflow-y-hidden rounded-md border border-border bg-muted/30 relative"
    >
      <div className="flex h-full">
        {/* Render each section as a column */}
        {allSections.map((section, idx) => {
          const sectionNodes = nodesBySection.get(section.id) || [];
          const isSpecialSection = section.id === -1;
          
          return (
            <div
              key={section.id}
              className="flex flex-col border-r border-border"
              style={{
                minWidth: "180px",
                flex: "0 0 180px",
                background: isSpecialSection ? "rgba(209, 213, 219, 0.2)" : "transparent",
              }}
            >
              {/* Section header */}
              <div className="sticky top-0 z-10 h-14 flex items-center justify-center px-2 pt-4">
                <span className="bg-white border border-border px-3 py-1 rounded text-xs font-semibold text-muted-foreground shadow-sm whitespace-nowrap">
                  {section.title}
                </span>
              </div>

              {/* Nodes container - centered vertically with flex */}
              <div className="flex-1 flex flex-col items-center justify-center gap-16 py-8">
                {sectionNodes.map((node) => (
                  <div key={node.id} data-node-id={node.id}>
                    <GraphNode
                      node={node}
                      isSpecial={isSpecialSection}
                      isHovered={hoveredNode === node.id}
                      onMouseEnter={() => setHoveredNode(node.id)}
                      onMouseLeave={() => setHoveredNode(null)}
                    />
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {/* Edges overlay */}
      {positionedNodes.length > 0 && (
        <GraphEdges
          positionedNodes={positionedNodes}
          edges={edges}
          containerRef={containerRef}
        />
      )}

      {/* Hover card */}
      {hoveredNode && positionedNodes.length > 0 && (
        <NodeHoverCard
          node={positionedNodes.find(n => n.id === hoveredNode)!}
          containerRef={containerRef}
          scrollLeft={containerRef.current?.scrollLeft || 0}
          viewportWidth={containerRef.current?.clientWidth || 0}
          totalWidth={containerRef.current?.scrollWidth || 0}
          onMouseEnter={() => {}}
          onMouseLeave={() => setHoveredNode(null)}
        />
      )}
    </div>
  );
}
