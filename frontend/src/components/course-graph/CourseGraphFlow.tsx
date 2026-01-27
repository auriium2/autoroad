import * as React from "react";
import ReactFlow, {
  Node,
  Background,
  BackgroundVariant,
  useNodesState,
  useEdgesState,
  NodeTypes,
  useReactFlow,
  ReactFlowProvider,
  Handle,
  Position,
} from 'reactflow';
import { Home } from 'lucide-react';

import 'reactflow/dist/style.css';
import './reactflow-custom.css';

import { CourseNode as CourseNodeComponent } from "@/components/course-graph/CourseNode";
import { GraphStats } from "@/components/course-graph/GraphStats";
import { GraphOverlay } from "@/components/course-graph/GraphOverlay";
import { ColumnHeaders } from "@/components/course-graph/ColumnHeaders";
import { NodeContextMenu } from "@/components/course-graph/NodeContextMenu";
import { Button } from "@/components/ui/button";
import { useGraphStore, CourseNode as CourseNodeType } from "@/stores/roadStore";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { ErrorDisplay } from "@/components/ErrorDisplay";
import { usePrerequisiteEdges, useMissingPrerequisites } from "@/hooks/usePrerequisites";
import { useContextMenu } from "@/hooks/useContextMenu";
import { useStoreNodes } from "@/hooks/useStoreNodes";
import { useFlowConversion } from "@/hooks/useFlowConversion";
import { useDragHandlers } from "@/hooks/useDragHandlers";
import { toast as showToast } from "@/hooks/useToast";
import { ALL_SECTIONS, COLUMN_WIDTH } from "@/lib/graphConstants";

// Custom node component wrapper for React Flow
const FlowCourseNode = ({ data }: { data: CourseNodeType & { disableTooltip?: boolean; viewMode?: string; isOptimizing?: boolean } }) => {
  return (
    <div style={{
      position: 'relative',
      transform: 'translate(-50%, 0)',
      willChange: data.isOptimizing ? 'transform' : 'auto'
    }}>
      <Handle type="target" position={Position.Left} style={{ background: 'transparent', border: 'none', left: '0px', top: '18px' }} />
      <Handle type="source" position={Position.Right} style={{ background: 'transparent', border: 'none', left: '36px', top: '18px' }} />
      <CourseNodeComponent
        node={data}
        disableTooltip={data.disableTooltip}
        viewMode={data.viewMode}
      />
    </div>
  );
};

FlowCourseNode.displayName = 'FlowCourseNode';

const nodeTypes: NodeTypes = {
  courseNode: FlowCourseNode,
};

interface CourseGraphFlowProps {
  viewMode?: string;
  disableEdgesDuringOptimization?: boolean;
}

function CourseGraphFlowInner({
  viewMode = "default",
}: CourseGraphFlowProps) {
  // Zustand selectors
  const markers = useGraphStore(state => state.markers);
  const optimizerNodes = useGraphStore(state => state.optimizerNodes);
  const loadingState = useGraphStore(state => state.loadingState);
  const error = useGraphStore(state => state.error);
  const fetchRoadData = useGraphStore(state => state.fetchRoadData);
  const addMarker = useGraphStore(state => state.addMarker);
  const updateMarker = useGraphStore(state => state.updateMarker);
  const removeMarker = useGraphStore(state => state.removeMarker);
  const isOptimizing = useGraphStore(state => state.isOptimizing);
  const markersChangedSinceOptimization = useGraphStore(state => state.markersChangedSinceOptimization);
  const lastOptimizationStatus = useGraphStore(state => state.lastOptimizationStatus);
  const lastCostBreakdown = useGraphStore(state => state.lastCostBreakdown);

  // React Flow state
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [viewport, setViewport] = React.useState({ x: 0, y: 20, zoom: 1 });
  const { screenToFlowPosition, getNodes } = useReactFlow();

  // Expose panToCourse globally for tutorial
  const { setViewport: setRFViewport, getViewport: getRFViewport } = useReactFlow();
  React.useEffect(() => {
    const numColumns = ALL_SECTIONS.length;
    const maxFlowX = numColumns * COLUMN_WIDTH;
    
    (window as unknown as { panToCourse?: (courseId: string) => void }).panToCourse = (courseId: string) => {
      const node = getNodes().find(n => n.data?.courseId === courseId);
      if (!node) return;
      
      const flowWrapper = document.querySelector('[data-tutorial="graph"]');
      if (!flowWrapper) return;
      
      const viewportWidth = flowWrapper.clientWidth;
      const viewportHeight = flowWrapper.clientHeight;
      const { zoom } = getRFViewport();
      
      // Calculate viewport position to center on node
      let targetX = -(node.position.x * zoom) + (viewportWidth / 2);
      const targetY = -(node.position.y * zoom) + (viewportHeight / 2);
      
      // Clamp X to respect translateExtent [[0, -Inf], [maxFlowX, Inf]]
      // viewport.x = 0 means flow x=0 is at left edge
      // viewport.x = -(maxFlowX * zoom) + viewportWidth means flow x=maxFlowX is at right edge
      const minViewportX = -(maxFlowX * zoom) + viewportWidth;
      const maxViewportX = 0;
      targetX = Math.max(minViewportX, Math.min(maxViewportX, targetX));
      
      setRFViewport({ x: targetX, y: targetY, zoom }, { duration: 300 });
    };
    return () => {
      delete (window as unknown as { panToCourse?: (courseId: string) => void }).panToCourse;
    };
  }, [getNodes, setRFViewport, getRFViewport]);

  // Debounce error display
  const [debouncedError, setDebouncedError] = React.useState<string | null>(null);
  React.useEffect(() => {
    if (loadingState === 'error' && error) {
      const timer = setTimeout(() => setDebouncedError(error), 500);
      return () => clearTimeout(timer);
    } else {
      setDebouncedError(null);
    }
  }, [loadingState, error]);

  // Stale warning tracking
  const [hasShownStaleWarning, setHasShownStaleWarning] = React.useState(false);

  // Custom hooks
  const { storeNodes } = useStoreNodes(markers, optimizerNodes);

  // Create stable key for storeNodes
  const storeNodesKey = React.useMemo(
    () => `${storeNodes.length}-${storeNodes.map(n => n.uuid).join(',')}`,
    [storeNodes]
  );

  // Debounce nodes during optimization
  const [debouncedNodes, setDebouncedNodes] = React.useState<typeof storeNodes>([]);

  React.useEffect(() => {
    if (!isOptimizing) {
      setDebouncedNodes(storeNodes);
    } else {
      const timer = setTimeout(() => {
        setDebouncedNodes(storeNodes);
      }, 800);
      return () => clearTimeout(timer);
    }

    // Handle stale warning toast
    if (markersChangedSinceOptimization && !hasShownStaleWarning) {
      showToast({
        title: "Optimizer results are stale",
        description: "You've modified the optimization problem. Press optimize to clear this.",
        variant: "default",
        duration: 5000,
      });
      setHasShownStaleWarning(true);
    }

    if (!markersChangedSinceOptimization && hasShownStaleWarning) {
      setHasShownStaleWarning(false);
    }
  }, [storeNodes, isOptimizing, markersChangedSinceOptimization, hasShownStaleWarning]);

  // Fetch prerequisite data
  const { data: prerequisiteData } = usePrerequisiteEdges(debouncedNodes);
  const storeEdges = prerequisiteData?.edges ?? [];

  const nodesToCheck = isOptimizing ? [] : storeNodes;
  const { data: uuid2missingPrereqs } = useMissingPrerequisites(nodesToCheck);

  // Convert to React Flow format
  const { flowNodes, flowEdges } = useFlowConversion(
    storeNodes,
    storeEdges,
    uuid2missingPrereqs instanceof Map ? uuid2missingPrereqs : undefined,
    viewMode,
    isOptimizing
  );

  // Update React Flow state when conversion results change
  React.useEffect(() => {
    setNodes(flowNodes);
    setEdges(flowEdges);
  }, [flowNodes, flowEdges, setNodes, setEdges]);

  // Context menu
  const { contextMenu, setContextMenu, onNodeContextMenu } = useContextMenu({
    setNodes,
    isOptimizing
  });

  // Context menu handlers
  const handlePin = (nodeId: string) => {
    updateMarker(nodeId, { status: 'pin' });
    setContextMenu(null);
  };

  const handleOverride = (nodeId: string) => {
    updateMarker(nodeId, { status: 'override' });
    setContextMenu(null);
  };

  const handleBanish = (nodeId: string) => {
    updateMarker(nodeId, { status: 'banish' });
    setContextMenu(null);
  };

  const handleRemoveNode = (nodeId: string) => {
    removeMarker(nodeId);
    setContextMenu(null);
  };

  const handleConvertToMarker = (nodeId: string) => {
    const node = storeNodes.find(n => n.uuid === nodeId);
    if (node) {
      addMarker(node.courseId, node.section, 'pin');
    }
    setContextMenu(null);
  };

  // Drag handlers
  const { onDrop, onDragOver, onNodeDragStop } = useDragHandlers(
    addMarker,
    updateMarker,
    isOptimizing,
    screenToFlowPosition
  );

  // Load data on mount
  React.useEffect(() => {
    const loadData = async () => {
      try {
        await fetchRoadData();
      } catch (error) {
        console.error('Failed to load road data:', error);
      }
    };

    if (loadingState === 'loading' && markers.length === 0 && optimizerNodes.length === 0) {
      loadData();
    }
  }, [loadingState, fetchRoadData, markers.length, optimizerNodes.length]);

  // Loading state
  if (loadingState === 'loading' && markers.length === 0 && optimizerNodes.length === 0) {
    return (
      <div className="h-full w-full rounded-md border border-border bg-card relative overflow-hidden">
        <LoadingSpinner message="Loading Autoroad..." />
      </div>
    );
  }

  // Error state
  if (loadingState === 'error' && markers.length === 0 && optimizerNodes.length === 0 && debouncedError) {
    return (
      <div className="h-full w-full rounded-md border border-border bg-card relative overflow-hidden">
        <ErrorDisplay
          error={debouncedError}
          onRetry={() => fetchRoadData()}
          title="Failed to load schedule"
        />
      </div>
    );
  }

  const numColumns = ALL_SECTIONS.length;

  const borderClass = markersChangedSinceOptimization
    ? 'border-yellow-500 border'
    : lastOptimizationStatus === 'OPTIMAL'
    ? 'border-2 border-green-500'
    : 'border border-border';

  return (
    <div
      className={`h-full w-full rounded-md ${borderClass} bg-muted/30 relative`}
      style={{ overflow: 'hidden' }}
      data-tutorial="graph"
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
        onMove={(_, newViewport) => setViewport(newViewport)}
        nodeTypes={nodeTypes}
        fitView={false}
        minZoom={0.8}
        maxZoom={1.5}
        nodesDraggable={!isOptimizing}
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
        onlyRenderVisibleElements={true}
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

      <ColumnHeaders sections={ALL_SECTIONS} viewport={viewport} viewMode={viewMode} />

      {/* Home button to reset viewport */}
      <Button
        variant="ghost"
        size="icon"
        className="absolute bottom-2 right-2 z-[50] opacity-60 hover:opacity-100 transition-opacity h-7 w-7"
        onClick={() => setRFViewport({ x: 0, y: 20, zoom: 1 }, { duration: 300 })}
        title="Reset view"
      >
        <Home className="h-4 w-4" />
      </Button>

      <GraphStats
        viewMode={viewMode}
        markers={markers}
        optimizerNodes={optimizerNodes}
        lastCostBreakdown={lastCostBreakdown}
      />

      <GraphOverlay isOptimizing={isOptimizing} />

      <NodeContextMenu
        contextMenu={contextMenu}
        storeNodes={storeNodes}
        onPin={handlePin}
        onOverride={handleOverride}
        onBanish={handleBanish}
        onRemove={handleRemoveNode}
        onConvertToMarker={handleConvertToMarker}
      />
    </div>
  );
}

export function CourseGraphFlow({
  viewMode = "default",
  disableEdgesDuringOptimization = false,
}: CourseGraphFlowProps = {}) {
  return (
    <ReactFlowProvider>
      <CourseGraphFlowInner
        viewMode={viewMode}
        disableEdgesDuringOptimization={disableEdgesDuringOptimization}
      />
    </ReactFlowProvider>
  );
}
