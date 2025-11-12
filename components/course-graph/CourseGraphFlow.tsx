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
  useReactFlow,
  ReactFlowProvider,
  Handle,
  Position,
} from 'reactflow';
import 'reactflow/dist/style.css';
import './reactflow-custom.css';

import { CourseNode as CourseNodeComponent } from "@/components/course-graph/CourseNode";
import { useGraphStore, CourseNode as CourseNodeType, Section } from "@/stores/roadStore";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { ErrorDisplay } from "@/components/ErrorDisplay";
import { Pin, Ban, Trash2, Unlink } from "lucide-react";

// Custom node component wrapper for React Flow
function FlowCourseNode({ data }: { data: CourseNodeType & { onMouseEnter: () => void; onMouseLeave: () => void; disableTooltip?: boolean } }) {
  return (
    <div style={{ position: 'relative', transform: 'translate(-50%, 0)' }}>
      {/* Handles at edges of the circle - centered vertically on the 36px circle */}
      <Handle
        type="target"
        position={Position.Left}
        style={{ 
          background: 'transparent',
          border: 'none',
          left: '0px', // Left edge of circle
          top: '18px', // Center of 36px circle
        }}
      />
      <Handle
        type="source"
        position={Position.Right}
        style={{ 
          background: 'transparent',
          border: 'none',
          left: '36px', // Right edge of circle (36px width)
          top: '18px', // Center of 36px circle
        }}
      />
      <CourseNodeComponent
        node={data}
        isSpecial={data.section === -1}
        isHovered={false}
        onMouseEnter={data.onMouseEnter}
        onMouseLeave={data.onMouseLeave}
        disableTooltip={data.disableTooltip}
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
  const backgroundRef = React.useRef<HTMLDivElement>(null);
  const dividersRef = React.useRef<HTMLDivElement>(null);
  const headersRef = React.useRef<HTMLDivElement>(null);

  // Update viewport on changes - direct DOM manipulation for sync
  React.useEffect(() => {
    let rafId: number;
    
    const updateViewport = () => {
      const viewport = getViewport();
      
      // Update all three elements directly
      if (backgroundRef.current) {
        backgroundRef.current.style.transform = `translate(${viewport.x}px, 0) scale(${viewport.zoom})`;
      }
      if (dividersRef.current) {
        dividersRef.current.style.transform = `translate(${viewport.x}px, 0) scale(${viewport.zoom})`;
      }
      if (headersRef.current) {
        headersRef.current.style.transform = `translate(${viewport.x}px, 0) scale(${viewport.zoom})`;
      }
      
      rafId = requestAnimationFrame(updateViewport);
    };
    
    rafId = requestAnimationFrame(updateViewport);
    return () => cancelAnimationFrame(rafId);
  }, [getViewport]);

  return (
    <>
      {/* Column backgrounds */}
      <div 
        ref={backgroundRef}
        style={{ 
          position: 'absolute',
          top: 0,
          left: 0,
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
        ref={dividersRef}
        style={{ 
          position: 'absolute',
          top: 0,
          left: 0,
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
        ref={headersRef}
        style={{ 
          position: 'absolute',
          top: 0,
          left: 0,
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
  // Use Zustand selectors for optimal performance - only re-render when specific data changes
  const storeNodes = useGraphStore(state => state.nodes);
  const storeEdges = useGraphStore(state => state.edges);
  const sections = useGraphStore(state => state.sections);
  const loadingState = useGraphStore(state => state.loadingState);
  const error = useGraphStore(state => state.error);
  const fetchRoadData = useGraphStore(state => state.fetchRoadData);
  const addNode = useGraphStore(state => state.addNode);
  const updateNodeLocal = useGraphStore(state => state.updateNodeLocal);
  const removeNode = useGraphStore(state => state.removeNode);

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  // Context menu state
  const [contextMenu, setContextMenu] = React.useState<{
    nodeId: string;
    x: number;
    y: number;
  } | null>(null);

  // Context menu handlers
  const handlePin = (nodeId: string) => {
    updateNodeLocal(nodeId, { nodeStatus: 'pin' });
    setContextMenu(null);
  };

  const handleSolo = (nodeId: string) => {
    updateNodeLocal(nodeId, { nodeStatus: 'solo' });
    setContextMenu(null);
  };

  const handleBanish = (nodeId: string) => {
    updateNodeLocal(nodeId, { nodeStatus: 'banish' });
    setContextMenu(null);
  };

  const handleRemoveNode = async (nodeId: string) => {
    await removeNode(nodeId);
    setContextMenu(null);
  };

  // Handle right-click on node
  const onNodeContextMenu = (event: React.MouseEvent, node: Node) => {
    event.preventDefault();
    
    // Only show context menu for user-controlled nodes
    if (!node.data.userControlled) {
      return;
    }

    setContextMenu({
      nodeId: node.id,
      x: event.clientX,
      y: event.clientY,
    });
  };

  // Close context menu on click outside
  React.useEffect(() => {
    const handleClick = () => setContextMenu(null);
    if (contextMenu) {
      window.addEventListener('click', handleClick);
      return () => window.removeEventListener('click', handleClick);
    }
  }, [contextMenu]);



  // Build sections array with Must Take and ASEs as first two columns
  // Note: Memoized because used as dependency in useEffect hooks below
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
          disableTooltip: contextMenu?.nodeId === node.id,
        },
        draggable: node.userControlled || false,
      };
    });

    setNodes(flowNodes);
  }, [storeNodes, allSections, setNodes, contextMenu]);

  // Convert store edges to React Flow edges
  React.useEffect(() => {
    const flowEdges: FlowEdge[] = storeEdges.map((edge) => {
      const fromNode = storeNodes.find(n => n.id === edge.from_id);
      const toNode = storeNodes.find(n => n.id === edge.to_id);

      if (!fromNode || !toNode) {
        return null;
      }

      // Don't render edges if either node is in "Must Take" column (section -2)
      if (fromNode.section === -2 || toNode.section === -2) {
        return null;
      }

      // Don't render edges if either node is banished
      if (fromNode.nodeStatus === 'banish' || toNode.nodeStatus === 'banish') {
        return null;
      }

      // Don't render edges FROM solo nodes (they don't require dependencies)
      // but still show edges TO solo nodes (other things can depend on them)
      if (toNode.nodeStatus === 'solo') {
        return null;
      }

      // Check if prerequisite is incorrectly placed (same or later section than dependent)
      const isIncorrectOrder = fromNode.section >= toNode.section;

      const fromX = allSections.findIndex(s => s.id === fromNode?.section);
      const toX = allSections.findIndex(s => s.id === toNode?.section);
      const isLongDistance = Math.abs(toX - fromX) > 1;

      // Determine edge color based on order and distance
      let strokeColor: string;
      let strokeWidth: number;
      let strokeDasharray: string | undefined;

      if (isIncorrectOrder) {
        // Red tint for incorrectly placed prerequisites
        strokeColor = 'rgba(239, 68, 68, 0.8)';
        strokeWidth = 2;
        strokeDasharray = undefined;
      } else if (isLongDistance) {
        strokeColor = 'rgba(209, 213, 219, 0.4)';
        strokeWidth = 1.5;
        strokeDasharray = '5 5';
      } else {
        strokeColor = 'rgba(156, 163, 175, 0.7)';
        strokeWidth = 2;
        strokeDasharray = undefined;
      }

      return {
        id: `edge-${edge.from_id}-${edge.to_id}`,
        source: String(edge.from_id),
        target: String(edge.to_id),
        type: 'default', // Bezier curves
        animated: false,
        style: {
          stroke: strokeColor,
          strokeWidth: strokeWidth,
          strokeDasharray: strokeDasharray,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 10,
          height: 10,
          color: strokeColor,
        },
      };
    }).filter(Boolean) as FlowEdge[];

    setEdges(flowEdges);
  }, [storeEdges, storeNodes, allSections, setEdges]);

  // Handle node drag end
  const onNodeDragStop = (_event: React.MouseEvent, node: Node) => {
    if (!node.data.userControlled) return;

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
  };

  // Load data on mount
  React.useEffect(() => {
    const loadData = async () => {
      try {
        // Add 1 second delay for testing
        await new Promise(resolve => setTimeout(resolve, 1000));
        await fetchRoadData();
      } catch (error) {
        console.error('Failed to load road data:', error);
      }
    };

    if (loadingState === 'loading' && storeNodes.length === 0) {
      loadData();
    }
  }, [loadingState, fetchRoadData, storeNodes.length]);

  const { screenToFlowPosition } = useReactFlow();

  // Handle drop from sidebar
  const onDrop = async (event: React.DragEvent) => {
    event.preventDefault();

    try {
      const data = event.dataTransfer.getData('application/json');
      
      if (!data) {
        console.error('No drag data found');
        return;
      }
      
      const nodeData = JSON.parse(data);
      
      // Get the position where the user dropped the node
      const position = screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });

      // Determine which column based on x position
      const COLUMN_WIDTH = 200;
      const sectionIndex = Math.round((position.x - COLUMN_WIDTH / 2) / COLUMN_WIDTH);
      const clampedIndex = Math.max(0, Math.min(sectionIndex, allSections.length - 1));
      const section = allSections[clampedIndex];

      // Add the node with the correct section
      const newNode = {
        ...nodeData,
        section: section.id,
      };
      
      await addNode(newNode);
      console.log('Node added successfully at position:', position, 'section:', section.title);
    } catch (error) {
      console.error('Failed to add dropped node:', error);
    }
  };

  const onDragOver = (event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  };

  if (loadingState === 'loading' && storeNodes.length === 0) {
    return (
      <div className="h-full w-full rounded-md border border-border bg-card relative overflow-hidden">
        <LoadingSpinner message="Loading your course schedule..." />
      </div>
    );
  }

  if (loadingState === 'error' && storeNodes.length === 0 && error) {
    return (
      <div className="h-full w-full rounded-md border border-border bg-card relative overflow-hidden">
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
    <div 
      className="h-full w-full rounded-md border border-border bg-muted/30 relative" 
      style={{ overflow: 'hidden' }}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeDragStop={onNodeDragStop}
        onNodeContextMenu={onNodeContextMenu}
        onDrop={onDrop}
        onDragOver={onDragOver}
        nodeTypes={nodeTypes}
        fitView={false}
        minZoom={0.8}
        maxZoom={1.5}
        nodesDraggable
        nodesConnectable={false}
        elementsSelectable={true}
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

      {/* Context menu */}
      {contextMenu && (() => {
        const node = storeNodes.find(n => n.id === contextMenu.nodeId);
        if (!node) return null;
        
        const currentStatus = node.nodeStatus || 'pin';
        
        return (
          <div
            className="fixed bg-card border border-border rounded-md shadow-lg p-1 min-w-[180px]"
            style={{ 
              top: contextMenu.y,
              left: contextMenu.x,
              zIndex: 10000,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <button
              className="flex items-center gap-2 px-3 py-2 text-sm rounded cursor-pointer outline-none hover:bg-muted/50 transition-colors w-full text-left disabled:opacity-50 disabled:cursor-not-allowed"
              onClick={() => handlePin(contextMenu.nodeId)}
              disabled={currentStatus === 'pin'}
            >
              <Pin className="w-4 h-4" />
              <span>Pin (default)</span>
              {currentStatus === 'pin' && (
                <span className="ml-auto text-xs text-muted-foreground">✓</span>
              )}
            </button>

            <button
              className="flex items-center gap-2 px-3 py-2 text-sm rounded cursor-pointer outline-none hover:bg-muted/50 transition-colors w-full text-left disabled:opacity-50 disabled:cursor-not-allowed"
              onClick={() => handleSolo(contextMenu.nodeId)}
              disabled={currentStatus === 'solo'}
            >
              <Unlink className="w-4 h-4" />
              <span>Pin + Independent</span>
              {currentStatus === 'solo' && (
                <span className="ml-auto text-xs text-muted-foreground">✓</span>
              )}
            </button>

            <button
              className="flex items-center gap-2 px-3 py-2 text-sm rounded cursor-pointer outline-none hover:bg-muted/50 transition-colors w-full text-left disabled:opacity-50 disabled:cursor-not-allowed"
              onClick={() => handleBanish(contextMenu.nodeId)}
              disabled={currentStatus === 'banish'}
            >
              <Ban className="w-4 h-4" />
              <span>Banish</span>
              {currentStatus === 'banish' && (
                <span className="ml-auto text-xs text-muted-foreground">✓</span>
              )}
            </button>

            <div className="h-px bg-border my-1" />

            <button
              className="flex items-center gap-2 px-3 py-2 text-sm rounded cursor-pointer outline-none hover:bg-destructive/10 text-destructive transition-colors w-full text-left"
              onClick={() => handleRemoveNode(contextMenu.nodeId)}
            >
              <Trash2 className="w-4 h-4" />
              <span>Remove node</span>
            </button>
          </div>
        );
      })()}
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
