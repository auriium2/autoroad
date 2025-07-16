"use client";

import * as React from "react";

// Improved NodeHoverCard component using its own props interface
interface NodeHoverCardProps {
  node: {
    id: number;
    x: number;
    y: number;
  };
  details: {
    title: string;
    description: string;
    type: string;
    status: string;
    connections: number;
    lastUpdated: string;
  };
  containerRef: React.RefObject<HTMLDivElement>;
  scrollLeft: number;
  viewportWidth: number;
  viewportHeight: number;
  totalWidth: number;
}

export function NodeHoverCard({
  node,
  details,
  containerRef,
  scrollLeft,
  viewportWidth,
  viewportHeight,
  totalWidth,
  onMouseEnter,
  onMouseLeave,
}: NodeHoverCardProps & {
  onMouseEnter: () => void;
  onMouseLeave: () => void;
}) {
  const cardRef = React.useRef<HTMLDivElement>(null);
  const [cardSize, setCardSize] = React.useState({ width: 280, height: 200 });

  React.useLayoutEffect(() => {
    if (cardRef.current) {
      const rect = cardRef.current.getBoundingClientRect();
      setCardSize({
        width: rect.width,
        height: rect.height,
      });
    }
  }, [details]);

  const getHoverCardPosition = () => {
    const cardWidth = cardSize.width;
    const cardHeight = cardSize.height;
    const circleRadius = 20;

    // Node position relative to the total canvas
    const nodeRelativeX = node.x;
    const nodeRelativeY = node.y;

    // Calculate card position relative to the node
    let cardX = nodeRelativeX + circleRadius + 20;
    let cardY = nodeRelativeY;

    // Calculate visible bounds
    const visibleLeft = scrollLeft + 20;
    const visibleRight = scrollLeft + viewportWidth - 20;

    // Calculate available space on both sides
    const spaceRight = visibleRight - (nodeRelativeX + circleRadius + 20);
    const spaceLeft = nodeRelativeX - circleRadius - 20 - visibleLeft;

    if (spaceRight >= cardWidth) {
      // Place card to the right of the node
      cardX = nodeRelativeX + circleRadius + 20;
    } else if (spaceLeft >= cardWidth) {
      // Place card to the left of the node
      cardX = nodeRelativeX - cardWidth - circleRadius - 20;
    } else if (spaceRight >= spaceLeft) {
      // Not enough space on either side, but more on the right
      cardX = Math.max(visibleLeft, nodeRelativeX + circleRadius + 20);
    } else {
      // Not enough space on either side, but more on the left
      cardX = Math.max(
        visibleLeft,
        nodeRelativeX - cardWidth - circleRadius - 20,
      );
    }

    // Vertical positioning
    if (cardY - cardHeight / 2 < 20) {
      cardY = 20 + cardHeight / 2;
    } else if (
      cardY + cardHeight / 2 >
      containerRef.current?.clientHeight - 20
    ) {
      cardY = (containerRef.current?.clientHeight || 0) - 20 - cardHeight / 2;
    }

    return {
      cardStyle: {
        left: cardX,
        top: cardY,
        transform: "translateY(-50%)",
      },
    };
  };

  const { cardStyle } = getHoverCardPosition();

  return (
    <div
      ref={cardRef}
      className="absolute z-[30] bg-card border border-border rounded-lg shadow-xl p-4 min-w-[180px] max-w-[320px] overflow-x-auto break-words animate-in fade-in-0 zoom-in-95 duration-200"
      style={cardStyle}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
    >
      <div className="space-y-3">
        <div className="border-b border-border pb-2">
          <h3 className="font-semibold text-foreground break-words">
            {details.title}
          </h3>
          <p className="text-sm text-muted-foreground break-words">
            {details.description}
          </p>
        </div>

        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <span className="text-muted-foreground">Type:</span>
            <div className="font-medium text-foreground">{details.type}</div>
          </div>
          <div>
            <span className="text-muted-foreground">Status:</span>
            <div
              className={`font-medium ${
                details.status === "Active"
                  ? "text-green-600"
                  : details.status === "Locked"
                    ? "text-yellow-600"
                    : details.status === "Disabled"
                      ? "text-red-600"
                      : "text-yellow-600"
              }`}
            >
              {details.status}
            </div>
          </div>
          <div>
            <span className="text-muted-foreground">Connections:</span>
            <div className="font-medium text-foreground">
              {details.connections}
            </div>
          </div>
          <div>
            <span className="text-muted-foreground">Updated:</span>
            <div className="font-medium text-foreground">
              {details.lastUpdated}
            </div>
          </div>
        </div>

        <div className="pt-2 border-t border-border">
          <div className="flex items-center gap-2">
            <div
              className={`w-2 h-2 rounded-full ${
                details.status === "Active"
                  ? "bg-green-500"
                  : details.status === "Locked"
                    ? "bg-yellow-500"
                    : details.status === "Disabled"
                      ? "bg-red-500"
                      : "bg-yellow-500"
              }`}
            ></div>
            <span className="text-xs text-muted-foreground">
              {details.status === "Active"
                ? "Currently processing requests"
                : details.status === "Locked"
                  ? "Node is locked and cannot be modified"
                  : details.status === "Disabled"
                    ? "Node is disabled and not processing"
                    : "Ready for activation"}
            </span>
          </div>
        </div>
      </div>

    </div>
  );
}
