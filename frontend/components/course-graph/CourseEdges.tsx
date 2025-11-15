"use client";

import * as React from "react";
import { Edge, useGraphStore } from "@/stores/roadStore";

interface CourseEdgesProps {
  edges: Edge[];
  containerRef: React.RefObject<HTMLDivElement | null>;
  nodeRefs: React.RefObject<Map<string, HTMLDivElement>>;
}

export function CourseEdges({
  edges,
  containerRef,
  nodeRefs,
}: CourseEdgesProps) {
  const svgRef = React.useRef<SVGSVGElement>(null);
  const [, forceUpdate] = React.useReducer((x) => x + 1, 0);

  // Get nodes from store to check section positions
  const storeNodes = useGraphStore(state => state.nodes);

  // Update on scroll
  React.useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handleUpdate = () => forceUpdate();
    
    container.addEventListener('scroll', handleUpdate);
    window.addEventListener('resize', handleUpdate);
    
    return () => {
      container.removeEventListener('scroll', handleUpdate);
      window.removeEventListener('resize', handleUpdate);
    };
  }, [containerRef]);

  // Update when layout changes using ResizeObserver
  React.useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const resizeObserver = new ResizeObserver(() => {
      forceUpdate();
    });

    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
    };
  }, [containerRef]);

  if (!containerRef.current) return null;

  const containerRect = containerRef.current.getBoundingClientRect();
  const scrollLeft = containerRef.current.scrollLeft;
  const scrollTop = containerRef.current.scrollTop;
  const width = containerRef.current.scrollWidth;
  const height = containerRef.current.scrollHeight;

  return (
    <svg
      ref={svgRef}
      className="absolute top-0 left-0 pointer-events-none"
      style={{
        width: `${width}px`,
        height: `${height}px`,
        zIndex: 0,
      }}
    >
      <g>
        {edges.map((edge, idx) => {
          const fromNodeElement = nodeRefs.current?.get(edge.fromUuid);
          const toNodeElement = nodeRefs.current?.get(edge.toUuid);

          if (!fromNodeElement || !toNodeElement) return null;

          const fromCircle = fromNodeElement.querySelector('[data-node-circle]');
          const toCircle = toNodeElement.querySelector('[data-node-circle]');

          if (!fromCircle || !toCircle) return null;

          const fromRect = fromCircle.getBoundingClientRect();
          const toRect = toCircle.getBoundingClientRect();

          // Calculate center points relative to container
          const fromX = fromRect.left - containerRect.left + fromRect.width / 2 + scrollLeft;
          const fromY = fromRect.top - containerRect.top + fromRect.height / 2 + scrollTop;
          const toX = toRect.left - containerRect.left + toRect.width / 2 + scrollLeft;
          const toY = toRect.top - containerRect.top + toRect.height / 2 + scrollTop;

          // Calculate distance
          const dx = toX - fromX;
          const dy = toY - fromY;
          const distance = Math.sqrt(dx * dx + dy * dy);

          // Offset from circle edge (20px radius)
          const circleRadius = 20;
          const offsetFromX = fromX + (dx / distance) * circleRadius;
          const offsetFromY = fromY + (dy / distance) * circleRadius;
          const offsetToX = toX - (dx / distance) * circleRadius;
          const offsetToY = toY - (dy / distance) * circleRadius;

          // Check if prerequisite is incorrectly placed (same or later section than dependent)
          const fromNode = storeNodes.find(n => n.uuid === edge.fromUuid);
          const toNode = storeNodes.find(n => n.uuid === edge.toUuid);
          const isIncorrectOrder = fromNode && toNode && fromNode.section >= toNode.section;

          // Determine edge style based on distance and prerequisite order
          const horizontalDistance = Math.abs(dx);
          const isLongDistance = horizontalDistance > 300;
          
          let strokeColor = "#9ca3af";
          let strokeWidth = 2;
          let opacity = 0.6;
          let isDashed = false;

          if (isIncorrectOrder) {
            // Red tint for incorrectly placed prerequisites
            strokeColor = "#ef4444";
            opacity = 0.8;
          } else if (isLongDistance) {
            strokeColor = "#d1d5db";
            strokeWidth = 1.5;
            opacity = 0.4;
            isDashed = true;
          }

          // Create curved path using cubic bezier
          const midX = (offsetFromX + offsetToX) / 2;
          const controlY1 = offsetFromY + dy * 0.3;
          const controlY2 = offsetToY - dy * 0.3;

          const path = `M ${offsetFromX} ${offsetFromY} C ${midX} ${controlY1}, ${midX} ${controlY2}, ${offsetToX} ${offsetToY}`;

          return (
            <path
              key={idx}
              d={path}
              stroke={strokeColor}
              strokeWidth={strokeWidth}
              fill="none"
              opacity={opacity}
              strokeDasharray={isDashed ? "8 4" : "none"}
              strokeLinecap="round"
            />
          );
        })}
      </g>
    </svg>
  );
}
