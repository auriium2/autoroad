"use client";

import * as React from "react";
import { Edge } from "@/stores/roadStore";
import { PositionedNode } from "./DisplayGraph";

interface GraphEdgesProps {
  positionedNodes: PositionedNode[];
  edges: Edge[];
  containerRef: React.RefObject<HTMLDivElement>;
}

export function GraphEdges({
  positionedNodes,
  edges,
  containerRef,
}: GraphEdgesProps) {
  const [dimensions, setDimensions] = React.useState({ width: 0, height: 0 });

  React.useEffect(() => {
    const updateDimensions = () => {
      if (containerRef.current) {
        setDimensions({
          width: containerRef.current.scrollWidth,
          height: containerRef.current.scrollHeight,
        });
      }
    };

    updateDimensions();
    window.addEventListener('resize', updateDimensions);
    return () => window.removeEventListener('resize', updateDimensions);
  }, [containerRef, positionedNodes]);

  if (dimensions.width === 0 || dimensions.height === 0) return null;

  return (
    <svg
      className="absolute top-0 left-0 pointer-events-none"
      style={{
        width: `${dimensions.width}px`,
        height: `${dimensions.height}px`,
        zIndex: 0,
      }}
    >
      <g>
        {edges.map((edge, idx) => {
          const fromNode = positionedNodes.find(n => n.id === edge.from_id);
          const toNode = positionedNodes.find(n => n.id === edge.to_id);

          if (!fromNode || !toNode) return null;

          // Start and end points
          const fromX = fromNode.x;
          const fromY = fromNode.y;
          const toX = toNode.x;
          const toY = toNode.y;

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

          // Determine edge style based on distance
          const horizontalDistance = Math.abs(dx);
          const isLongDistance = horizontalDistance > 300;
          
          let strokeColor = "#9ca3af";
          let strokeWidth = 2;
          let opacity = 0.6;
          let isDashed = false;

          if (isLongDistance) {
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
