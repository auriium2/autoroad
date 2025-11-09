"use client";

import * as React from "react";
import { Edge } from "@/stores/roadStore";

interface CourseEdgesProps {
  edges: Edge[];
  containerRef: React.RefObject<HTMLDivElement>;
}

export function CourseEdges({
  edges,
  containerRef,
}: CourseEdgesProps) {
  const [dimensions, setDimensions] = React.useState({ width: 0, height: 0 });
  const [updateKey, setUpdateKey] = React.useState(0);
  const [isUpdating, setIsUpdating] = React.useState(false);

  React.useEffect(() => {
    let timeoutId: NodeJS.Timeout;
    
    const updateDimensions = () => {
      setIsUpdating(true);
      
      if (containerRef.current) {
        setDimensions({
          width: containerRef.current.scrollWidth,
          height: containerRef.current.scrollHeight,
        });
      }
      // Force re-render by updating key
      setUpdateKey(k => k + 1);
      
      // Reset after a short delay to allow layout to settle
      clearTimeout(timeoutId);
      timeoutId = setTimeout(() => {
        setIsUpdating(false);
      }, 50);
    };

    const timer = setTimeout(updateDimensions, 100);
    window.addEventListener('resize', updateDimensions);
    const container = containerRef.current;
    container?.addEventListener('scroll', updateDimensions);
    
    // Use ResizeObserver to detect layout changes
    const resizeObserver = new ResizeObserver(() => {
      updateDimensions();
    });
    
    if (container) {
      resizeObserver.observe(container);
    }
    
    return () => {
      clearTimeout(timer);
      clearTimeout(timeoutId);
      window.removeEventListener('resize', updateDimensions);
      container?.removeEventListener('scroll', updateDimensions);
      resizeObserver.disconnect();
    };
  }, [containerRef, edges]);

  if (dimensions.width === 0 || dimensions.height === 0) return null;

  const containerRect = containerRef.current?.getBoundingClientRect();
  if (!containerRect) return null;

  const scrollLeft = containerRef.current?.scrollLeft || 0;
  const scrollTop = containerRef.current?.scrollTop || 0;

  return (
    <svg
      key={updateKey}
      className="absolute top-0 left-0 pointer-events-none transition-opacity duration-100"
      style={{
        width: `${dimensions.width}px`,
        height: `${dimensions.height}px`,
        zIndex: 0,
        opacity: isUpdating ? 0 : 1,
      }}
    >
      <g>
        {edges.map((edge, idx) => {
          // Get node elements directly from DOM
          const fromElement = document.querySelector(`[data-node-circle="${edge.from_id}"]`);
          const toElement = document.querySelector(`[data-node-circle="${edge.to_id}"]`);

          if (!fromElement || !toElement) return null;

          const fromRect = fromElement.getBoundingClientRect();
          const toRect = toElement.getBoundingClientRect();

          // Calculate center points: viewport position - container position + scroll offset
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
