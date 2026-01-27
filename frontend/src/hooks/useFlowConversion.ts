import { useMemo } from "react";
import type { Node, Edge as FlowEdge } from "reactflow";
import { MarkerType } from "reactflow";
import type { CourseNode } from "@/stores/roadStore";
import {
  COLUMN_WIDTH,
  NODE_SPACING,
  VIEWPORT_CENTER_Y,
  SECTION_INDEX_MAP,
} from "@/lib/graphConstants";

export interface PrerequisiteEdge {
  fromUuid: string;
  toUuid: string;
}

export interface FlowConversionResult {
  flowNodes: Node[];
  flowEdges: FlowEdge[];
}

export function useFlowConversion(
  storeNodes: CourseNode[],
  storeEdges: PrerequisiteEdge[],
  uuid2missingPrereqs: Map<string, string[]> | undefined,
  viewMode: string,
  isOptimizing: boolean
): FlowConversionResult {
  // useMemo required - flowNodes/flowEdges are passed directly to ReactFlow which
  // compares by reference. Without memoization, new arrays cause infinite loops.
  return useMemo(() => {
    const startTime = performance.now();

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
      const missingPrereqs = uuid2missingPrereqs?.get(node.uuid) || [];

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
          satisfiesHassMarker: (node as CourseNode & { satisfiesHassMarker?: boolean }).satisfiesHassMarker,
        },
        draggable: !isOptimizing && node.userControlled,
      };
    });

    // === EDGE CONVERSION ===
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

    const endTime = performance.now();
    console.log(`[Performance] Converted ${storeNodes.length} nodes and ${flowEdges.length} edges in ${(endTime - startTime).toFixed(2)}ms`);

    return { flowNodes, flowEdges };
  }, [storeNodes, storeEdges, uuid2missingPrereqs, viewMode, isOptimizing]);
}
