import { useMemo } from "react";
import type { Marker, OptimizerNode, CourseNode } from "@/stores/roadStore";
import { VIRTUAL_MARKER_TYPES } from "@/lib/graphConstants";

export interface StoreNodesResult {
  storeNodes: CourseNode[];
  hassMarkerToOptimizerNode: Map<string, OptimizerNode>;
}

export function useStoreNodes(
  markers: Marker[],
  optimizerNodes: OptimizerNode[]
): StoreNodesResult {
  // useMemo required - the returned objects are used by ReactFlow which compares
  // by reference. Without memoization, new objects on every render cause infinite loops.
  return useMemo(() => {
    // Map (section, markerType) -> list of marker uuids for controlling virtual markers
    const virtualMarkerLookup = new Map<string, string[]>();
    for (const marker of markers) {
      if (VIRTUAL_MARKER_TYPES.has(marker.courseId) && marker.status !== 'banish') {
        const key = `${marker.section}_${marker.courseId}`;
        const existing = virtualMarkerLookup.get(key) || [];
        existing.push(marker.uuid);
        virtualMarkerLookup.set(key, existing);
      }
    }

    // Build map of which optimizer node satisfies which HASS marker: markerUuid -> optimizerNode
    // Matches optimizer nodes to markers in order (first node -> first marker, etc.)
    const hassMarkerToOptimizerNode = new Map<string, OptimizerNode>();
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
        hassMarkerToOptimizerNode.set(markerUuids[i], nodes[i]);
      }
    }

    // Compute display nodes from markers + optimizer nodes
    const optimizerMap = new Map<string, OptimizerNode>();
    const optimizerCourseIds = new Set<string>();
    for (const on of optimizerNodes) {
      const key = `${on.courseId}_${on.section}`;
      optimizerMap.set(key, on);
      optimizerCourseIds.add(on.courseId);
    }

    // Markers become nodes with userControlled=true
    const markerNodes: CourseNode[] = markers.map((marker) => {
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
      } as CourseNode & { optimizerAgreed?: boolean; satisfiesHassMarker?: boolean };

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

    const optimizerOnlyNodes: CourseNode[] = optimizerNodes
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

    const storeNodes = [...markerNodes, ...optimizerOnlyNodes];

    return { storeNodes, hassMarkerToOptimizerNode };
  }, [markers, optimizerNodes]);
}
