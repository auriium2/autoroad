
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
import { GraphStats } from "@/components/course-graph/GraphStats";
import { GraphOverlay } from "@/components/course-graph/GraphOverlay";
import { useGraphStore, CourseNode as CourseNodeType, Section, OptimizerNode, AvailableNode } from "@/stores/roadStore";
import { useOptimizationStore } from "@/stores/optimizationStore";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { ErrorDisplay } from "@/components/ErrorDisplay";
import { Pin, Ban, Trash2, Unlink } from "lucide-react";
import { usePrerequisiteEdges, useMissingPrerequisites } from "@/hooks/usePrerequisites";
import { useContextMenu } from "@/hooks/useContextMenu";
import { toast as showToast } from "@/hooks/useToast";
import { isPastSemesterById } from "@/lib/semesterUtils";

// Virtual marker types (attribute-based markers like HASS-A, HASS-H, etc.)
const VIRTUAL_MARKER_TYPES = new Set(['HASS-A', 'HASS-H', 'HASS-S', 'HASS-E']);

// Custom node component wrapper for React Flow
const FlowCourseNode = ({ data }: { data: CourseNodeType & { disableTooltip?: boolean; viewMode?: string; isOptimizing?: boolean } }) => {
  return (
    <div style={{
      position: 'relative',
      transform: 'translate(-50%, 0)',
      willChange: data.isOptimizing ? 'transform' : 'auto'
    }}>
      <Handle
        type="target"
        position={Position.Left}
        style={{
          background: 'transparent',
          border: 'none',
          left: '0px',
          top: '18px',
        }}
      />
      <Handle
        type="source"
        position={Position.Right}
        style={{
          background: 'transparent',
          border: 'none',
          left: '36px',
          top: '18px',
        }}
      />
      <CourseNodeComponent
        node={data}
        disableTooltip={data.disableTooltip}
        viewMode={data.viewMode}
      />
    </div>
  );
};

FlowCourseNode.displayName = 'FlowCourseNode';

// Define nodeTypes outside component to prevent re-creation
const nodeTypes: NodeTypes = {
  courseNode: FlowCourseNode,
};

// Column headers and dividers that move with the viewport
function ColumnHeaders({ sections, viewport }: { sections: Section[]; viewport: { x: number; y: number; zoom: number } }) {
  const COLUMN_WIDTH = 200;
  const transform = `translate(${viewport.x}px, 0) scale(${viewport.zoom})`;

  const lockPastSemesters = useOptimizationStore((state) => state.lockPastSemesters);
  const selectedYear = useOptimizationStore((state) => state.selectedYear);
  const graduationYear = selectedYear ? parseInt(selectedYear) : 0;

  return (
    <>
      {/* Column backgrounds */}
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          transform,
          transformOrigin: 'top left',
          pointerEvents: 'none',
          zIndex: 0,
          width: sections.length * COLUMN_WIDTH,
          height: '100%',
        }}
      >
        {sections.map((section, index) => {
          //must take overlay
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
          //ase overlay
          if (section.id === -1) {
            return (
              <div key={`bg-${section.id}`}
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

          //past semesters overlay
          if (lockPastSemesters && graduationYear && section.id >= 0 && isPastSemesterById(section.id, graduationYear)) {
            return (
              <div
                key={`bg-${section.id}`}
                style={{
                  position: 'absolute',
                  left: index * COLUMN_WIDTH,
                  top: -2000,
                  width: COLUMN_WIDTH,
                  height: 10000,
                  backgroundColor: 'rgba(239, 68, 68, 0.12)',
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
          left: 0,
          transform,
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
          left: 0,
          transform,
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

const ALL_SECTIONS: Section[] = [
  { id: -2, title: 'Must Take' },
  { id: -1, title: 'ASEs' },
  { id: 0, title: "Freshman Fall" },
  { id: 1, title: "Freshman IAP" },
  { id: 2, title: "Freshman Spring" },
  { id: 3, title: "Sophomore Fall" },
  { id: 4, title: "Sophomore IAP" },
  { id: 5, title: "Sophomore Spring" },
  { id: 6, title: "Junior Fall" },
  { id: 7, title: "Junior IAP" },
  { id: 8, title: "Junior Spring" },
  { id: 9, title: "Senior Fall" },
  { id: 10, title: "Senior IAP" },
  { id: 11, title: "Senior Spring" },
];

// Pre-compute section index map once
const SECTION_INDEX_MAP = new Map(
  ALL_SECTIONS.map((section, index) => [section.id, index])
);

interface CourseGraphFlowProps {
  viewMode?: string;
}

function CourseGraphFlowInner({
  viewMode = "default",
  disableEdgesDuringOptimization = false,
}: CourseGraphFlowProps & {
  disableEdgesDuringOptimization?: boolean;
}) {
  // Use Zustand selectors for optimal performance - only re-render when specific data changes
  const markers = useGraphStore(state => state.markers);
  const optimizerNodes = useGraphStore(state => state.optimizerNodes);
  const availableNodes = useGraphStore(state => state.availableNodes);
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

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  // Track viewport for column headers
  const [viewport, setViewport] = React.useState({ x: 0, y: 20, zoom: 1 });

  // Debounce error display to avoid flash on initial load
  const [debouncedError, setDebouncedError] = React.useState<string | null>(null);
  React.useEffect(() => {
    if (loadingState === 'error' && error) {
      const timer = setTimeout(() => setDebouncedError(error), 500);
      return () => clearTimeout(timer);
    } else {
      setDebouncedError(null);
    }
  }, [loadingState, error]);

  // Track if we've shown the stale warning alert
  const [hasShownStaleWarning, setHasShownStaleWarning] = React.useState(false);

  // Map (section, markerType) -> list of marker uuids for controlling virtual markers
  const virtualMarkerLookup = React.useMemo(() => {
    const map = new Map<string, string[]>(); // "section_HASS-A" -> [marker uuid, ...]
    for (const marker of markers) {
      if (VIRTUAL_MARKER_TYPES.has(marker.courseId) && marker.status !== 'banish') {
        const key = `${marker.section}_${marker.courseId}`;
        const existing = map.get(key) || [];
        existing.push(marker.uuid);
        map.set(key, existing);
      }
    }
    return map;
  }, [markers]);

  // Build map of which optimizer node satisfies which HASS marker: markerUuid -> optimizerNode
  // Matches optimizer nodes to markers in order (first node -> first marker, etc.)
  const hassMarkerToOptimizerNode = React.useMemo(() => {
    const map = new Map<string, OptimizerNode>();
    // Group optimizer nodes by (section, hassAttr)
    const optimizerNodesByKey = new Map<string, OptimizerNode[]>();
    for (const on of optimizerNodes) {
      const hassAttr = on.attributes?.hass_attribute;
      if (hassAttr && VIRTUAL_MARKER_TYPES.has(hassAttr)) {
        const key = `${on.section}_${hassAttr}`;
        const existing = optimizerNodesByKey.get(key) || [];
        existing.push(on);
        optimizerNodesByKey.set(key, existing);
      }
    }
    // Match optimizer nodes to markers
    for (const [key, markerUuids] of virtualMarkerLookup) {
      const nodes = optimizerNodesByKey.get(key) || [];
      for (let i = 0; i < Math.min(markerUuids.length, nodes.length); i++) {
        map.set(markerUuids[i], nodes[i]);
      }
    }
    return map;
  }, [optimizerNodes, virtualMarkerLookup]);

  // Compute display nodes from markers + optimizer nodes
  const storeNodes = React.useMemo(() => {

    const optimizerMap = new Map<string, OptimizerNode>();
    const optimizerCourseIds = new Set<string>();
    for (const on of optimizerNodes) {
      const key = `${on.courseId}_${on.section}`;
      optimizerMap.set(key, on);
      optimizerCourseIds.add(on.courseId);
    }

    // Markers become nodes with userControlled=true
    const markerNodes: CourseNodeType[] = markers
      .map((marker) => {
        const isVirtualHass = VIRTUAL_MARKER_TYPES.has(marker.courseId) && marker.status !== 'banish';
        const satisfyingOptimizerNode = isVirtualHass ? hassMarkerToOptimizerNode.get(marker.uuid) : undefined;
        
        let hasOptimizerOverlap = false;
        let displayCourseId = marker.courseId;

        if (satisfyingOptimizerNode) {
          // HASS marker is satisfied - show the actual course instead of "HASS-A"
          hasOptimizerOverlap = true;
          displayCourseId = satisfyingOptimizerNode.courseId;
        } else if (marker.status !== 'banish' && !isVirtualHass) {
          // For regular (non-virtual) markers, check for optimizer overlap
          if (marker.section === -2) {
            // Must Take: satisfied if course exists in ANY optimizer semester
            hasOptimizerOverlap = optimizerCourseIds.has(marker.courseId);
          } else {
            // Regular sections: satisfied if course exists in exact same section
            const key = `${marker.courseId}_${marker.section}`;
            hasOptimizerOverlap = optimizerMap.has(key);
          }
        }

        const result = {
          uuid: marker.uuid,
          courseId: displayCourseId,
          section: marker.section,
          userControlled: true,
          nodeStatus: marker.status,
          ...(hasOptimizerOverlap ? { optimizerAgreed: true } : {}),
          ...(satisfyingOptimizerNode ? { satisfiesHassMarker: true } : {}),
        } as CourseNodeType & { optimizerAgreed?: boolean; satisfiesHassMarker?: boolean };
        
        return result;
      });

    // Filter out optimizer nodes that overlap with non-banish markers (including satisfied HASS markers)
    const markerKeys = new Set(
      markers
        .filter(m => m.status !== 'banish')
        .map(m => {
          // For satisfied HASS markers, use the satisfying course's key
          const satisfying = hassMarkerToOptimizerNode.get(m.uuid);
          if (satisfying) {
            return `${satisfying.courseId}_${m.section}`;
          }
          return `${m.courseId}_${m.section}`;
        })
    );

    const optimizerOnlyNodes: CourseNodeType[] = optimizerNodes
      .filter(on => {
        const key = `${on.courseId}_${on.section}`;
        return !markerKeys.has(key);
      })
      .map((on, index) => ({
        uuid: `optimizer_${on.courseId}_${on.section}_${index}`,
        courseId: on.courseId,
        section: on.section,
        userControlled: false,
        units: on.units,
      }));

    return [...markerNodes, ...optimizerOnlyNodes];
  }, [markers, optimizerNodes, hassMarkerToOptimizerNode]);

  // Create a stable key for storeNodes to prevent infinite loops
  const storeNodesKey = React.useMemo(
    () => `${storeNodes.length}-${storeNodes.map(n => n.uuid).join(',')}`,
    [storeNodes]
  );

  // Debounce edge calculation during optimization to reduce lag
  const [debouncedNodes, setDebouncedNodes] = React.useState<typeof storeNodes>([]);

  React.useEffect(() => {
    if (!isOptimizing) {
      setDebouncedNodes(storeNodes);
    } else {
      // During optimization - debounce updates
      const timer = setTimeout(() => {
        setDebouncedNodes(storeNodes);
      }, 800); // Wait 800ms after last change

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

    // Reset warning flag when optimization completes
    if (!markersChangedSinceOptimization && hasShownStaleWarning) {
      setHasShownStaleWarning(false);
    }
  }, [storeNodes, isOptimizing, markersChangedSinceOptimization, hasShownStaleWarning]);

  // Fetch prerequisite edges using the hook
  const { data: prerequisiteData } = usePrerequisiteEdges(debouncedNodes);
  const storeEdges = prerequisiteData?.edges ?? [];

  // Fetch missing prerequisites for all nodes (skip during optimization for performance)
  const nodesToCheck = isOptimizing ? [] : storeNodes;

  const { data: uuid2missingPrereqs } = useMissingPrerequisites(nodesToCheck);

  // Context menu hook
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



  // Create stable key for edges
  const storeEdgesKey = React.useMemo(
    () => storeEdges.map(e => `${e.fromUuid}-${e.toUuid}`).sort().join('|'),
    [storeEdges]
  );

  // Convert store nodes and edges to React Flow nodes and edges in a single batch
  // This prevents double renders by updating both nodes and edges together
  React.useEffect(() => {
    const startTime = performance.now();
    const COLUMN_WIDTH = 200;
    const NODE_SPACING = 120;
    const VIEWPORT_CENTER_Y = 400;

    // === NODE CONVERSION ===
    const nodesBySection = new Map<number, typeof storeNodes>();
    for (const node of storeNodes) {
      if (!nodesBySection.has(node.section)) {
        nodesBySection.set(node.section, []);
      }
      nodesBySection.get(node.section)!.push(node);
    }

    const nodeIndicesByUuid = new Map<string, number>();
    for (const nodesInSection of nodesBySection.values()) {
      nodesInSection.forEach((node, index) => {
        nodeIndicesByUuid.set(node.uuid, index);
      });
    }

    const flowNodes: Node[] = storeNodes.map((node) => {
      const sectionIndex = SECTION_INDEX_MAP.get(node.section) ?? 0;
      const nodesInSection = nodesBySection.get(node.section)!;
      const nodeIndexInSection = nodeIndicesByUuid.get(node.uuid)!;

      const totalNodesHeight = (nodesInSection.length - 1) * NODE_SPACING;
      const startY = VIEWPORT_CENTER_Y - (totalNodesHeight / 2);

      // Get missing prerequisites for this node
      const missingPrereqs = (uuid2missingPrereqs && uuid2missingPrereqs instanceof Map)
        ? (uuid2missingPrereqs.get(node.uuid) || [])
        : [];

      return {
        id: node.uuid,
        type: 'courseNode',
        position: {
          x: sectionIndex * COLUMN_WIDTH + (COLUMN_WIDTH / 2),
          y: startY + nodeIndexInSection * NODE_SPACING,
        },
        data: {
          ...node,
          missingPrereqs,
          viewMode,
          isOptimizing,
          satisfiesHassMarker: node.satisfiesHassMarker,
        },
        draggable: !isOptimizing && node.userControlled,
      };
    });

    // === EDGE CONVERSION ===
    // Pre-compute node map for O(1) access
    const nodesByUuid = new Map(storeNodes.map(n => [n.uuid, n]));

    const flowEdges = storeEdges.map((edge) => {
      const fromNode = nodesByUuid.get(edge.fromUuid);
      const toNode = nodesByUuid.get(edge.toUuid);

      if (!fromNode || !toNode) return null;

      // Don't render edges if either node is in "Must Take" column (section -2)
      if (fromNode.section === -2 || toNode.section === -2) return null;

      // Don't render edges if either node is banished
      if (fromNode.nodeStatus === 'banish' || toNode.nodeStatus === 'banish') return null;

      // Don't render edges FROM override nodes (they don't require dependencies)
      if (toNode.nodeStatus === 'override') return null;

      // Check if prerequisite is incorrectly placed
      const isIncorrectOrder = fromNode.section >= toNode.section;

      const fromX = SECTION_INDEX_MAP.get(fromNode.section) ?? 0;
      const toX = SECTION_INDEX_MAP.get(toNode.section) ?? 0;
      const isLongDistance = Math.abs(toX - fromX) > 1;

      // Determine edge color based on order and distance
      let strokeColor: string;
      let strokeWidth: number;
      let strokeDasharray: string | undefined;

      if (isIncorrectOrder) {
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
        id: `edge-${edge.fromUuid}-${edge.toUuid}`,
        source: String(edge.fromUuid),
        target: String(edge.toUuid),
        type: 'default',
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

    // Batch update both nodes and edges together (single render instead of two)
    setNodes(flowNodes);
    setEdges(flowEdges);

    const endTime = performance.now();
    console.log(`[Performance] Converted ${storeNodes.length} nodes and ${flowEdges.length} edges in ${(endTime - startTime).toFixed(2)}ms`);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storeNodesKey, storeEdgesKey, setNodes, setEdges, uuid2missingPrereqs, viewMode]);

  // Handle node drag end
  const onNodeDragStop = (_event: React.MouseEvent, node: Node) => {
    if (!node.data.userControlled || isOptimizing) return;

    // Determine which column the node is in based on x position
    const COLUMN_WIDTH = 200;
    // Nodes are positioned at column centers: 100, 300, 500, etc. (index * 200 + 100)
    // To find which column: (x - 100) / 200, then round to nearest
    const sectionIndex = Math.round((node.position.x - COLUMN_WIDTH / 2) / COLUMN_WIDTH);
    const clampedIndex = Math.max(0, Math.min(sectionIndex, ALL_SECTIONS.length - 1));
    let section = ALL_SECTIONS[clampedIndex];

    // HASS markers cannot be placed in Must Take section
    const isVirtualMarker = VIRTUAL_MARKER_TYPES.has(node.data.courseId);
    if (isVirtualMarker && section.id === -2) {
      section = ALL_SECTIONS[1]; // Fall back to first regular semester
    }

    if (section && node.data.section !== section.id) {
      // Reset invalid statuses when moving to special sections
      const currentStatus = node.data.nodeStatus || 'pin';
      const needsReset = 
        (section.id === -2 && currentStatus === 'override') || // Override not allowed in Must Take
        (section.id === -1 && currentStatus === 'banish');     // Banish not allowed in ASE
      
      if (needsReset) {
        updateMarker(node.id, { section: section.id, status: 'pin' });
      } else {
        updateMarker(node.id, { section: section.id });
      }
    } else {
      // Same section, snap back to center
      updateMarker(node.id, { section: node.data.section });
    }
  };

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
      const clampedIndex = Math.max(0, Math.min(sectionIndex, ALL_SECTIONS.length - 1));
      let section = ALL_SECTIONS[clampedIndex];

      // HASS markers cannot be placed in Must Take section
      const isVirtualMarker = VIRTUAL_MARKER_TYPES.has(nodeData.courseId);
      if (isVirtualMarker && section.id === -2) {
        section = ALL_SECTIONS[1]; // Fall back to first regular semester
      }

      // Add the marker with the correct section
      addMarker(nodeData.courseId, section.id, 'pin');
      console.log('Marker added successfully at position:', position, 'section:', section.title);
    } catch (error) {
      console.error('Failed to add dropped node:', error);
    }
  };

  const onDragOver = (event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  };

  if (loadingState === 'loading' && markers.length === 0 && optimizerNodes.length === 0) {
    return (
      <div className="h-full w-full rounded-md border border-border bg-card relative overflow-hidden">
        <LoadingSpinner message="Loading Autoroad..." />
      </div>
    );
  }

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

  const COLUMN_WIDTH = 200;
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

      {/* Column headers and dividers that move with viewport */}
      <ColumnHeaders sections={ALL_SECTIONS} viewport={viewport} />

      {/* Total Units and Cost Display */}
      <GraphStats
        viewMode={viewMode}
        markers={markers}
        optimizerNodes={optimizerNodes}
        lastCostBreakdown={lastCostBreakdown}
      />

      {/* Optimization overlay - disable interactions */}
      <GraphOverlay isOptimizing={isOptimizing} />

      {/* Context menu */}
      {contextMenu && (() => {
        const node = storeNodes.find(n => n.uuid === contextMenu.nodeUuid);
        if (!node) return null;

        const isUserControlled = node.userControlled;
        const currentStatus = node.nodeStatus || 'pin';
        const isInMustTake = node.section === -2;
        const isInASE = node.section === -1;

        return (
          <div
            className="fixed bg-popover/95 border border-border rounded-lg shadow-lg backdrop-blur-md p-1"
            style={{
              top: contextMenu.y,
              left: contextMenu.x,
              zIndex: 10000,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {isUserControlled ? (
              <>
                <button
                  className="flex items-center gap-1.5 px-2 py-1 text-xs rounded cursor-pointer outline-none hover:bg-muted/50 transition-colors w-full text-left disabled:opacity-50 disabled:cursor-not-allowed"
                  onClick={() => handlePin(contextMenu.nodeUuid)}
                  disabled={currentStatus === 'pin'}
                >
                  <Pin className="w-3 h-3" />
                  <span>Pin (default)</span>
                  {currentStatus === 'pin' && (
                    <span className="ml-auto text-[10px] text-muted-foreground">✓</span>
                  )}
                </button>

                <button
                  className="flex items-center gap-1.5 px-2 py-1 text-xs rounded cursor-pointer outline-none hover:bg-muted/50 transition-colors w-full text-left disabled:opacity-50 disabled:cursor-not-allowed"
                  onClick={() => handleOverride(contextMenu.nodeUuid)}
                  disabled={currentStatus === 'override' || isInMustTake}
                  title={isInMustTake ? "Override not available in Must Take - move to a specific semester" : undefined}
                >
                  <Unlink className="w-3 h-3" />
                  <span>Pin + ignore prerequisites</span>
                  {currentStatus === 'override' && (
                    <span className="ml-auto text-[10px] text-muted-foreground">✓</span>
                  )}
                </button>

                <button
                  className="flex items-center gap-1.5 px-2 py-1 text-xs rounded cursor-pointer outline-none hover:bg-muted/50 transition-colors w-full text-left disabled:opacity-50 disabled:cursor-not-allowed"
                  onClick={() => handleBanish(contextMenu.nodeUuid)}
                  disabled={currentStatus === 'banish' || isInASE}
                  title={isInASE ? "Banish not available in ASE" : undefined}
                >
                  <Ban className="w-3 h-3" />
                  <span>{isInMustTake ? "Banish (never take)" : "Banish"}</span>
                  {currentStatus === 'banish' && (
                    <span className="ml-auto text-[10px] text-muted-foreground">✓</span>
                  )}
                </button>

                <div className="h-px bg-border/50 my-0.5" />

                <button
                  className="flex items-center gap-1.5 px-2 py-1 text-xs rounded cursor-pointer outline-none hover:bg-destructive/10 text-destructive transition-colors w-full text-left"
                  onClick={() => handleRemoveNode(contextMenu.nodeUuid)}
                >
                  <Trash2 className="w-3 h-3" />
                  <span>Remove marker</span>
                </button>
              </>
            ) : (
              <button
                className="flex items-center gap-1.5 px-2 py-1 text-xs rounded cursor-pointer outline-none hover:bg-muted/50 transition-colors w-full text-left"
                onClick={() => handleConvertToMarker(contextMenu.nodeUuid)}
              >
                <Pin className="w-3 h-3" />
                <span>Convert to marker</span>
              </button>
            )}
          </div>
        );
      })()}
    </div>
  );
}

export function CourseGraphFlow({
  viewMode = "default",
  disableEdgesDuringOptimization = false,
}: CourseGraphFlowProps & {
  disableEdgesDuringOptimization?: boolean;
} = {}) {
  return (
    <ReactFlowProvider>
      <CourseGraphFlowInner
        viewMode={viewMode}
        disableEdgesDuringOptimization={disableEdgesDuringOptimization}
      />
    </ReactFlowProvider>
  );
}
