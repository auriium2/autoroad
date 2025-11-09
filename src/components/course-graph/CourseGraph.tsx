"use client";

import * as React from "react";
import { CourseNode as CourseNodeComponent } from "@/components/course-graph/CourseNode";
import { CourseEdges } from "@/components/course-graph/CourseEdges";
import { CourseNodeHoverCard } from "@/components/course-graph/CourseNodeHoverCard";
import { useGraphStore, CourseNode as CourseNodeType, Section } from "@/stores/roadStore";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { ErrorDisplay } from "@/components/ErrorDisplay";

export function CourseGraph() {
  const { 
    nodes, 
    edges, 
    sections, 
    specialSection,
    loadingState,
    error,
    fetchRoadData,
    loadInitialData,
  } = useGraphStore();

  const containerRef = React.useRef<HTMLDivElement>(null);
  const [hoveredNode, setHoveredNode] = React.useState<string | null>(null);
  const nodeRefs = React.useRef<Map<string, HTMLDivElement>>(new Map());

  // Load data on mount - try API first, fallback to demo data
  React.useEffect(() => {
    const loadData = async () => {
      try {
        await fetchRoadData();
      } catch (error) {
        // fetchRoadData already handles fallback to localStorage
        // and loadInitialData if needed
        console.error('Failed to load road data:', error);
      }
    };

    if (loadingState === 'idle') {
      loadData();
    }
  }, [loadingState, fetchRoadData]);

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



  // Show loading state
  if (loadingState === 'loading' && nodes.length === 0) {
    return (
      <div className="h-full w-full rounded-md border border-border bg-muted/30">
        <LoadingSpinner message="Loading your course schedule..." />
      </div>
    );
  }

  // Show error state
  if (loadingState === 'error' && nodes.length === 0 && error) {
    return (
      <div className="h-full w-full rounded-md border border-border bg-muted/30">
        <ErrorDisplay 
          error={error}
          onRetry={() => fetchRoadData()}
          title="Failed to load schedule"
        />
      </div>
    );
  }

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
                background: isSpecialSection ? "rgba(100, 116, 139, 0.15)" : "transparent",
              }}
            >
              {/* Section header */}
              <div className="sticky top-0 z-10 h-14 flex items-center justify-center px-2 pt-4">
                <span className="glass-card px-3 py-1 rounded text-xs font-semibold text-gray-300 shadow-sm whitespace-nowrap">
                  {section.title}
                </span>
              </div>

              {/* Nodes container - centered vertically with flex */}
              <div className="flex-1 flex flex-col items-center justify-center gap-16 py-8">
                {sectionNodes.map((node) => (
                  <div 
                    key={node.id} 
                    data-node-id={node.id}
                    ref={(el) => {
                      if (el) {
                        nodeRefs.current.set(node.id, el);
                      } else {
                        nodeRefs.current.delete(node.id);
                      }
                    }}
                  >
                    <CourseNodeComponent
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
      <CourseEdges
        edges={edges}
        containerRef={containerRef}
        nodeRefs={nodeRefs}
      />

      {/* Hover card */}
      {hoveredNode && (
        <CourseNodeHoverCard
          nodeId={hoveredNode}
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
