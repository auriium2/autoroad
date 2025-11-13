"use client";

import * as React from "react";
import { CourseNode as CourseNodeComponent } from "@/components/course-graph/CourseNode";
import { CourseEdges } from "@/components/course-graph/CourseEdges";
import { CourseNodeHoverCard } from "@/components/course-graph/CourseNodeHoverCard";
import { ColumnContextMenu } from "@/components/course-graph/ColumnContextMenu";
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
  } = useGraphStore();

  const containerRef = React.useRef<HTMLDivElement>(null);
  const [hoveredNode, setHoveredNode] = React.useState<string | null>(null);
  const nodeRefs = React.useRef<Map<string, HTMLDivElement>>(new Map());
  
  const [contextMenu, setContextMenu] = React.useState<{
    x: number;
    y: number;
    sectionId: number;
    sectionTitle: string;
  } | null>(null);
  
  const [draggedNode, setDraggedNode] = React.useState<CourseNodeType | null>(null);
  const [dragOverSection, setDragOverSection] = React.useState<number | null>(null);

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
    const grouped = new Map<number, CourseNodeType[]>();
    allSections.forEach(section => {
      grouped.set(section.id, nodes.filter(n => n.section === section.id));
    });
    return grouped;
  }, [nodes, allSections]);

  // Get actions from store
  const { addNode, updateNodeLocal } = useGraphStore();

  // Handle right-click on column
  const handleColumnContextMenu = (e: React.MouseEvent, section: Section) => {
    e.preventDefault();
    setContextMenu({
      x: e.clientX,
      y: e.clientY,
      sectionId: section.id,
      sectionTitle: section.title,
    });
  };

  // Handle add node from context menu
  const handleAddNodeToSection = (sectionId: number) => {
    const newNode: CourseNodeType = {
      id: `node_${Date.now()}`,
      courseId: `New Course`,
      section: sectionId,
      userControlled: true,
    };
    addNode(newNode);
  };

  // Handle node drag start
  const handleNodeDragStart = (e: React.DragEvent, node: CourseNodeType) => {
    if (node.userControlled) {
      setDraggedNode(node);
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', node.id);
    }
  };

  // Handle node drag end
  const handleNodeDragEnd = async (e: React.DragEvent) => {
    e.preventDefault();
    setDraggedNode(null);
    setDragOverSection(null);
  };

  // Handle drag over section
  const handleDragOver = (e: React.DragEvent, sectionId: number) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    if (draggedNode && sectionId !== draggedNode.section) {
      setDragOverSection(sectionId);
    }
  };

  // Handle drag leave
  const handleDragLeave = (e: React.DragEvent) => {
    // Only clear if leaving the column entirely
    const relatedTarget = e.relatedTarget as HTMLElement;
    if (!relatedTarget || !e.currentTarget.contains(relatedTarget)) {
      setDragOverSection(null);
    }
  };

  // Handle drop
  const handleDrop = (e: React.DragEvent, sectionId: number) => {
    e.preventDefault();
    e.stopPropagation();
    
    if (draggedNode && sectionId !== draggedNode.section) {
      // Update local state only, no API call
      updateNodeLocal(draggedNode.id, { section: sectionId });
    }
    
    setDraggedNode(null);
    setDragOverSection(null);
  };



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
              className="flex flex-col border-r border-border relative transition-colors duration-200"
              style={{
                minWidth: "180px",
                flex: "0 0 180px",
                background: isSpecialSection 
                  ? "rgba(100, 116, 139, 0.15)" 
                  : dragOverSection === section.id 
                    ? "rgba(59, 130, 246, 0.2)" 
                    : "transparent",
              }}
              onContextMenu={(e) => handleColumnContextMenu(e, section)}
              onDragOver={(e) => handleDragOver(e, section.id)}
              onDragLeave={handleDragLeave}
              onDrop={(e) => handleDrop(e, section.id)}
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
                    draggable={node.userControlled}
                    onDragStart={(e) => handleNodeDragStart(e, node)}
                    onDragEnd={handleNodeDragEnd}
                    ref={(el) => {
                      if (el) {
                        nodeRefs.current.set(node.id, el);
                      } else {
                        nodeRefs.current.delete(node.id);
                      }
                    }}
                    className="transition-opacity duration-150"
                    style={{
                      cursor: node.userControlled ? 'grab' : 'default',
                      opacity: draggedNode?.id === node.id ? 0.4 : 1,
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

      {/* Context menu */}
      {contextMenu && (
        <ColumnContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          sectionId={contextMenu.sectionId}
          sectionTitle={contextMenu.sectionTitle}
          onAddNode={() => handleAddNodeToSection(contextMenu.sectionId)}
          onClose={() => setContextMenu(null)}
        />
      )}
    </div>
  );
}
