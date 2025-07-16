"use client";

interface GraphEdgesProps {
  positionedNodes: any[];
  edges: { from: number; to: number }[];
  sectionWidth: number;
  viewportHeight: number;
  totalWidth: number;
}

// Helper function for connection style
function getConnectionStyle(
  fromNode: any,
  toNode: any,
  sectionWidth: number
) {
  const dx = toNode.x - fromNode.x;
  const dy = toNode.y - fromNode.y;
  const sectionDistance = Math.abs(toNode.x - fromNode.x) / sectionWidth;

  let strokeWidth = 2.2;
  let opacity = 0.8;
  let strokeColor = "#6b7280"; // gray-500
  let isDashed = false;

  if (sectionDistance <= 1.5) {
    strokeWidth = 2;
    opacity = 0.8;
    strokeColor = "#9ca3af"; // gray-700
  } else if (sectionDistance <= 3) {
    strokeWidth = 1.8;
    opacity = 0.6;
    strokeColor = "#9ca3af"; // gray-400
    isDashed = true;
  } else {
    strokeWidth = 1.5;
    opacity = 0.4;
    strokeColor = "#d1d5db"; // gray-300
    isDashed = true;
  }

  return {
    strokeWidth,
    opacity,
    strokeColor,
    isDashed,
    isLongDistance: sectionDistance > 1.5,
  };
}

// Helper function for curved path
function generateCurvedPath(
  fromNode: any,
  toNode: any,
  sectionWidth: number,
  viewportHeight: number
) {
  const circleRadius = 20;
  const dx = toNode.x - fromNode.x;
  const dy = toNode.y - fromNode.y;
  const distance = Math.sqrt(dx * dx + dy * dy);

  const fromX = fromNode.x + (dx / distance) * circleRadius;
  const fromY = fromNode.y + (dy / distance) * circleRadius;
  const toX = toNode.x - (dx / distance) * circleRadius;
  const toY = toNode.y - (dy / distance) * circleRadius;

  const sectionDistance = Math.abs(toNode.x - fromNode.x) / sectionWidth;
  const isLongDistance = sectionDistance > 1.5;

  if (!isLongDistance) {
    return `M ${fromX} ${fromY} L ${toX} ${toY}`;
  }

  const midX = (fromX + toX) / 2;
  const midY = (fromY + toY) / 2;
  const baseCurveOffset = Math.min(80, Math.abs(dx) * 0.3);
  const distanceMultiplier = Math.min(1.5, sectionDistance / 3);
  const curveOffset = baseCurveOffset * distanceMultiplier;

  const shouldCurveUp =
    fromY > viewportHeight / 2 || toY > viewportHeight / 2;
  const controlY = shouldCurveUp ? midY - curveOffset : midY + curveOffset;

  const control1X = fromX + dx * 0.25;
  const control1Y = fromY + (controlY - fromY) * 0.4;
  const control2X = toX - dx * 0.25;
  const control2Y = toY + (controlY - toY) * 0.4;

  return `M ${fromX} ${fromY} C ${control1X} ${control1Y}, ${control2X} ${control2Y}, ${toX} ${toY}`;
}

export function GraphEdges({
  positionedNodes,
  edges,
  sectionWidth,
  viewportHeight,
  totalWidth,
}: GraphEdgesProps) {
  return (
    <g>
      {edges.map((edge, index) => {
        const fromNode = positionedNodes.find((n) => n.id === edge.from);
        const toNode = positionedNodes.find((n) => n.id === edge.to);
        if (!fromNode || !toNode) return null;

        const pathData = generateCurvedPath(fromNode, toNode, sectionWidth, viewportHeight);
        const connectionStyle = getConnectionStyle(fromNode, toNode, sectionWidth);

        return (
          <g key={index}>
            {/* Main connection path */}
            <path
              d={pathData}
              stroke={connectionStyle.strokeColor}
              strokeWidth={connectionStyle.strokeWidth}
              fill="none"
              opacity={connectionStyle.opacity}
              strokeDasharray={connectionStyle.isDashed ? "8 4" : "none"}
              strokeLinecap="round"
              strokeLinejoin="round"
            />

            {/* Add subtle animation for long connections */}
            {connectionStyle.isLongDistance && (
              <path
                d={pathData}
                stroke={connectionStyle.strokeColor}
                strokeWidth="1"
                fill="none"
                opacity="0.3"
                strokeDasharray="4 8"
                strokeLinecap="round"
              >
                <animate
                  attributeName="stroke-dashoffset"
                  values="0;12"
                  dur="2s"
                  repeatCount="indefinite"
                />
              </path>
            )}
          </g>
        );
      })}
    </g>
  );
}
