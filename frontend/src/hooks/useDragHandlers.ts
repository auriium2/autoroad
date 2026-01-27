import { useCallback, type DragEvent, type MouseEvent } from "react";
import type { Node } from "reactflow";
import type { Marker } from "@/stores/roadStore";
import { useDragStore } from "@/stores/dragStore";
import { useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/lib/queryKeys";
import type { FireroadCourse } from "@/types/models/fireroad";
import { COLUMN_WIDTH, ALL_SECTIONS, VIRTUAL_MARKER_TYPES } from "@/lib/graphConstants";

export interface DragHandlersResult {
  onDrop: (event: DragEvent) => void;
  onDragOver: (event: DragEvent) => void;
  onDragLeave: (event: DragEvent) => void;
  onNodeDragStart: (event: MouseEvent, node: Node) => void;
  onNodeDrag: (event: MouseEvent, node: Node) => void;
  onNodeDragStop: (event: MouseEvent, node: Node) => void;
}

export function useDragHandlers(
  addMarker: (courseId: string, section: number, status?: 'pin' | 'banish' | 'override') => void,
  updateMarker: (id: string, updates: Partial<Marker>) => void,
  isOptimizing: boolean,
  screenToFlowPosition: (position: { x: number; y: number }) => { x: number; y: number }
): DragHandlersResult {
  const queryClient = useQueryClient();
  const setHoveredSection = useDragStore((state) => state.setHoveredSection);
  const startDrag = useDragStore((state) => state.startDrag);
  const endDrag = useDragStore((state) => state.endDrag);
  
  // useCallback required here - these handlers are passed to ReactFlow which uses them
  // as effect dependencies. Without stable references, ReactFlow's StoreUpdater
  // enters an infinite update loop.
  const onDrop = useCallback((event: DragEvent) => {
    event.preventDefault();
    setHoveredSection(null);

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
    } catch (error) {
      console.error('Failed to add dropped node:', error);
    }
  }, [addMarker, screenToFlowPosition, setHoveredSection]);

  const onDragOver = useCallback((event: DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
    
    // Calculate which section is being hovered
    const position = screenToFlowPosition({
      x: event.clientX,
      y: event.clientY,
    });
    
    const sectionIndex = Math.round((position.x - COLUMN_WIDTH / 2) / COLUMN_WIDTH);
    const clampedIndex = Math.max(0, Math.min(sectionIndex, ALL_SECTIONS.length - 1));
    const section = ALL_SECTIONS[clampedIndex];
    
    setHoveredSection(section.id);
  }, [screenToFlowPosition, setHoveredSection]);

  const onDragLeave = useCallback((event: DragEvent) => {
    // Only clear if leaving the entire graph area
    const relatedTarget = event.relatedTarget as HTMLElement | null;
    const currentTarget = event.currentTarget as HTMLElement;
    if (!relatedTarget || !currentTarget.contains(relatedTarget)) {
      setHoveredSection(null);
    }
  }, [setHoveredSection]);

  const onNodeDragStart = useCallback((_event: MouseEvent, node: Node) => {
    if (!node.data.userControlled || isOptimizing) return;
    
    const courseId = node.data.courseId;
    
    // Try to get course data from cache
    const courseData = queryClient.getQueryData<FireroadCourse>(
      queryKeys.courses.details(courseId)
    );
    
    startDrag(courseId, {
      fall: courseData?.offered_fall ?? true,
      spring: courseData?.offered_spring ?? true,
      iap: courseData?.offered_IAP ?? false,
      notOfferedYear: courseData?.not_offered_year ?? null,
    });
  }, [isOptimizing, queryClient, startDrag]);

  const onNodeDrag = useCallback((_event: MouseEvent, node: Node) => {
    if (!node.data.userControlled || isOptimizing) return;
    
    // Calculate which section the node is over
    const sectionIndex = Math.round((node.position.x - COLUMN_WIDTH / 2) / COLUMN_WIDTH);
    const clampedIndex = Math.max(0, Math.min(sectionIndex, ALL_SECTIONS.length - 1));
    const section = ALL_SECTIONS[clampedIndex];
    
    setHoveredSection(section.id);
  }, [isOptimizing, setHoveredSection]);

  const onNodeDragStop = useCallback((_event: MouseEvent, node: Node) => {
    endDrag();
    if (!node.data.userControlled || isOptimizing) return;

    // Determine which column the node is in based on x position
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
  }, [isOptimizing, updateMarker]);

  return { onDrop, onDragOver, onDragLeave, onNodeDragStart, onNodeDrag, onNodeDragStop };
}
