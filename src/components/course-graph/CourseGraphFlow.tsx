"use client";

import * as React from "react";
import ReactFlow, {
  Node,
  Edge as FlowEdge,
  Background,
  BackgroundVariant,
  useNodesState,
  useEdgesState,
  NodeTypes,
  MarkerType,
  Panel,
  useReactFlow,
  ReactFlowProvider,
  Handle,
  Position,
} from 'reactflow';
import 'reactflow/dist/style.css';
import './reactflow-custom.css';

import { CourseNode as CourseNodeComponent } from "@/components/course-graph/CourseNode";
import { ColumnContextMenu } from "@/components/course-graph/ColumnContextMenu";
import { useGraphStore, CourseNode as CourseNodeType, Section } from "@/stores/roadStore";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { ErrorDisplay } from "@/components/ErrorDisplay";

// Custom node component wrapper for React Flow
function FlowCourseNode({ data }: { data: CourseNodeType & { onMouseEnter: () => void; onMouseLeave: () => void } }) {
  return (
    <div style={{ position: 'relative', transform: 'translate(-50%, 0)' }}>
      {/* Handles at edges of the circle - centered vertically on the 40px circle */}
      <Handle
        type="target"
        position={Position.Left}
        style={{ 
          background: 'transparent',
          border: 'none',
          left: '0px', // Left edge of circle
          top: '20px', // Center of 40px circle
        }}
      />
      <Handle
        type="source"
        position={Position.Right}
        style={{ 
          background: 'transparent',
          border: 'none',
          left: '40px', // Right edge of circle (40px width)
          top: '20px', // Center of 40px circle
        }}
      />
      <CourseNodeComponent
        node={data}
        isSpecial={data.section === -1}
        isHovered={false}
        onMouseEnter={data.onMouseEnter}
        onMouseLeave={data.onMouseLeave}
      />
    </div>
  );
}

const nodeTypes: NodeTypes = {
  courseNode: FlowCourseNode,
};



// Column headers and dividers that move with the viewport
function ColumnHeaders({ sections }: { sections: Section[] }) {
  const COLUMN_WIDTH = 200;
  const { getViewport } = useReactFlow();
  const [viewport, setViewport] = React.useState(getViewport());

  // Update viewport on changes
  React.useEffect(() => {
    const interval = setInterval(() => {
      setViewport(getViewport());
    }, 16); // ~60fps
    return () => clearInterval(interval);
  }, [getViewport]);

  return (
    <>
      {/* Column backgrounds */}
      <div 
        style={{ 
          position: 'absolute',
          top: 0,
          left: viewport.x,
          transform: `scale(${viewport.zoom})`,
          transformOrigin: 'top left',
          pointerEvents: 'none',
          zIndex: 0,
          width: sections.length * COLUMN_WIDTH,
          height: '100%',
        }}
      >
        {sections.map((section, index) => {
          // Must Take column (id: -2) - purple hazard overlay
          if (section.id === -2) {
            return (
              <div
                key={`bg-${section.id}`}
                style={{
                  position: 'absolute',
                  left: index * COLUMN_WIDTH,
                  top: -2000,
                  width: COLUMN_WIDTH,
                  height: 10000,
                  background: 'repeating-linear-gradient(45deg, rgba(168, 85, 247, 0.08), rgba(168, 85, 247, 0.08) 20px, rgba(168, 85, 247, 0.12) 20px, rgba(168, 85, 247, 0.12) 40px), rgba(255, 255, 255, 0.03)',
                }}
              />
            );
          }
          // ASEs column (id: -1) - lighter grey background
          if (section.id === -1) {
            return (
              <div
                key={`bg-${section.id}`}
                style={{
                  position: 'absolute',
                  left: index * COLUMN_WIDTH,
                  top: -2000,
                  width: COLUMN_WIDTH,
                  height: 10000,
                  backgroundColor: 'rgba(255, 255, 255, 0.03)',
                }}
              />
            );
          }
          return null;
        })}
      </div>

      {/* Column divider lines */}
      <div 
        style={{ 
          position: 'absolute',
          top: 0,
          left: viewport.x,
          transform: `scale(${viewport.zoom})`,
          transformOrigin: 'top left',
          pointerEvents: 'none',
          zIndex: 1,
          width: sections.length * COLUMN_WIDTH,
          height: '100%',
        }}
      >
        {sections.map((section, index) => (
          <div
            key={`divider-${section.id}`}
            style={{
              position: 'absolute',
              left: index * COLUMN_WIDTH,
              top: -2000,
              width: 1,
              height: 10000,
              backgroundColor: 'rgba(255, 255, 255, 0.1)',
            }}
          />
        ))}
        {/* Right edge of last column */}
        <div
          style={{
            position: 'absolute',
            left: sections.length * COLUMN_WIDTH,
            top: -2000,
            width: 1,
            height: 10000,
            backgroundColor: 'rgba(255, 255, 255, 0.1)',
          }}
        />
      </div>

      {/* Column headers */}
      <div 
        style={{ 
          position: 'absolute',
          top: 0,
          left: viewport.x,
          transform: `scale(${viewport.zoom})`,
          transformOrigin: 'top left',
          display: 'flex',
          gap: 0,
          pointerEvents: 'none',
          zIndex: 10,
        }}
      >
        {sections.map((section, index) => (
          <div
            key={section.id}
            className="flex items-center justify-center px-2 py-2"
            style={{
              width: `${COLUMN_WIDTH}px`,
            }}
          >
            <span className="glass-card px-3 py-1 rounded text-xs font-semibold text-gray-300 shadow-sm whitespace-nowrap">
              {section.title}
            </span>
          </div>
        ))}
      </div>
    </>
  );
}

function CourseGraphFlowInner() {
  const {
    nodes: storeNodes,
    edges: storeEdges,
    sections,
    specialSection,
    loadingState,
    error,
    fetchRoadData,
    addNode,
    updateNodeLocal,
  } = useGraphStore();

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  const [contextMenu, setContextMenu] = React.useState<{
    x: number;
    y: number;
    sectionId: number;
    sectionTitle: string;
  } | null>(null);

  // Build sections array with Must Take and ASEs as first two columns
  const allSections: Section[] = React.useMemo(() => {
    const mustTakeSection: Section = { id: -2, title: 'Must Take' };
    const asesSection: Section = { id: -1, title: 'ASEs' };
    return [mustTakeSection, asesSection, ...sections];
  }, [sections]);

  // Convert store nodes to React Flow nodes
  React.useEffect(() => {
    const COLUMN_WIDTH = 200;
    const NODE_SPACING = 120;
    const VIEWPORT_CENTER_Y = 400; // Approximate center of viewport

    const flowNodes: Node[] = storeNodes.map((node, index) => {
      const sectionIndex = allSections.findIndex(s => s.id === node.section);
      const nodesInSection = storeNodes.filter(n => n.section === node.section);
      const nodeIndexInSection = nodesInSection.findIndex(n => n.id === node.id);
      
      // Calculate total height of nodes in this section
      const totalNodesHeight = (nodesInSection.length - 1) * NODE_SPACING;
      // Start Y position to center the group vertically
      const startY = VIEWPORT_CENTER_Y - (totalNodesHeight / 2);

      return {
        id: node.id,
        type: 'courseNode',
        position: {
          x: sectionIndex * COLUMN_WIDTH + (COLUMN_WIDTH / 2),
          y: startY + nodeIndexInSection * NODE_SPACING,
        },
        data: {
          ...node,
          onMouseEnter: () => {},
          onMouseLeave: () => {},
        },
        draggable: node.locked || false,
      };
    });

    setNodes(flowNodes);
  }, [storeNodes, allSections, setNodes]);

  // Convert store edges to React Flow edges
  React.useEffect(() => {
    const flowEdges: FlowEdge[] = storeEdges.map((edge) => {
      const fromNode = storeNodes.find(n => n.id === edge.from_id);
      const toNode = storeNodes.find(n => n.id === edge.to_id);

      if (!fromNode || !toNode) {
        return null;
      }

      const fromX = allSections.findIndex(s => s.id === fromNode?.section);
      const toX = allSections.findIndex(s => s.id === toNode?.section);
      const isLongDistance = Math.abs(toX - fromX) > 1;

      return {
        id: `edge-${edge.from_id}-${edge.to_id}`,
        source: String(edge.from_id),
        target: String(edge.to_id),
        type: 'default', // Bezier curves
        animated: false,
        style: {
          stroke: isLongDistance ? 'rgba(209, 213, 219, 0.4)' : 'rgba(156, 163, 175, 0.7)',
          strokeWidth: isLongDistance ? 1.5 : 2,
          strokeDasharray: isLongDistance ? '5 5' : undefined,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 10,
          height: 10,
          color: isLongDistance ? 'rgba(209, 213, 219, 0.4)' : 'rgba(156, 163, 175, 0.7)',
        },
      };
    }).filter(Boolean) as FlowEdge[];

    setEdges(flowEdges);
  }, [storeEdges, storeNodes, allSections, setEdges]);

  // Handle node drag end
  const onNodeDragStop = React.useCallback((_event: React.MouseEvent, node: Node) => {
    if (!node.data.locked) return;

    // Determine which column the node is in based on x position
    const COLUMN_WIDTH = 200;
    // Nodes are positioned at column centers: 100, 300, 500, etc. (index * 200 + 100)
    // To find which column: (x - 100) / 200, then round to nearest
    const sectionIndex = Math.round((node.position.x - COLUMN_WIDTH / 2) / COLUMN_WIDTH);
    const clampedIndex = Math.max(0, Math.min(sectionIndex, allSections.length - 1));
    const section = allSections[clampedIndex];

    if (section && node.data.section !== section.id) {
      // Update the section in the store, which will trigger a re-render with correct positioning
      updateNodeLocal(node.id, { section: section.id });
    } else {
      // Same section, but need to snap back to center - force a re-render
      updateNodeLocal(node.id, { section: node.data.section });
    }
  }, [allSections, updateNodeLocal]);

  // Load data on mount
  React.useEffect(() => {
    const loadData = async () => {
      try {
        await fetchRoadData();
      } catch (error) {
        console.error('Failed to load road data:', error);
      }
    };

    if (loadingState === 'idle') {
      loadData();
    }
  }, [loadingState, fetchRoadData]);

  // Handle right-click on background
  const handlePaneContextMenu = React.useCallback((event: React.MouseEvent) => {
    event.preventDefault();

    // Determine which section was clicked based on x position
    const COLUMN_WIDTH = 200;
    const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
    const x = event.clientX - rect.left;
    const sectionIndex = Math.floor(x / COLUMN_WIDTH);
    const section = allSections[sectionIndex];

    if (section) {
      setContextMenu({
        x: event.clientX,
        y: event.clientY,
        sectionId: section.id,
        sectionTitle: section.title,
      });
    }
  }, [allSections]);

  // Handle add node
  const handleAddNodeToSection = (sectionId: number) => {
    const newNode: CourseNodeType = {
      id: `node_${Date.now()}`,
      label: `New Course`,
      section: sectionId,
      locked: true,
      user_added: true,
    };
    addNode(newNode);
  };

  if (loadingState === 'loading' && storeNodes.length === 0) {
    return (
      <div className="h-full w-full rounded-md border border-border bg-muted/30">
        <LoadingSpinner message="Loading your course schedule..." />
      </div>
    );
  }

  if (loadingState === 'error' && storeNodes.length === 0 && error) {
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

  const COLUMN_WIDTH = 200;
  const numColumns = allSections.length;
  
  return (
    <div className="h-full w-full rounded-md border border-border bg-muted/30 relative" style={{ overflow: 'hidden' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeDragStop={onNodeDragStop}
        onPaneContextMenu={handlePaneContextMenu}
        nodeTypes={nodeTypes}
        fitView={false}
        minZoom={0.8}
        maxZoom={1.5}
        nodesDraggable
        nodesConnectable={false}
        elementsSelectable={false}
        zoomOnScroll={false}
        panOnScroll
        panOnDrag
        translateExtent={[
          [0, -Infinity],
          [numColumns * COLUMN_WIDTH, Infinity]
        ]}
        defaultViewport={{ x: 0, y: 20, zoom: 1 }}
        proOptions={{ hideAttribution: true }}
        style={{ background: 'transparent' }}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={20}
          size={1}
          color="rgba(255, 255, 255, 0.1)"
        />
      </ReactFlow>

      {/* Column headers and dividers that move with viewport */}
      <ColumnHeaders sections={allSections} />

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

export function CourseGraphFlow() {
  return (
    <ReactFlowProvider>
      <CourseGraphFlowInner />
    </ReactFlowProvider>
  );
}
