"use client";

import * as React from "react";
import { useCourseDetails } from "@/hooks/useCourseData";
import { useGraphStore } from "@/stores/roadStore";

type Status = "Active" | "Locked" | "Disabled" | "Pending";

// CSS classes could be extracted to a separate file
const cardClassName =
  "absolute z-[30] bg-[oklch(0.2_0.015_264)] backdrop-blur-xl border border-[oklch(0.9_0.01_264_/_0.15)] rounded-xl shadow-xl p-4 min-w-[180px] max-w-[320px] overflow-x-auto break-words animate-in fade-in-0 zoom-in-95 duration-200";

const CARD_DEFAULT_WIDTH = 280;
const CARD_DEFAULT_HEIGHT = 200;
const NODE_CIRCLE_RADIUS = 20;
const MIN_VISIBLE_PADDING = 20;

export function CourseNodeHoverCard({
  nodeId,
  containerRef,
  scrollLeft,
  viewportWidth,
  onMouseEnter,
  onMouseLeave,
}: {
  nodeId: string;
  containerRef: React.RefObject<HTMLDivElement | null>;
  scrollLeft: number;
  totalWidth: number;
  viewportWidth: number;
  onMouseEnter?: () => void;
  onMouseLeave?: () => void;
}) {
  // Get node from store to find courseId
  const nodes = useGraphStore(state => state.nodes);
  const node = nodes.find(n => n.id === nodeId);
  const courseId = node?.courseId || nodeId;
  
  // Fetch course details
  const { data: courseDetails } = useCourseDetails(courseId);
  
  // Note: Memoized because used as dependency in useLayoutEffect below
  const details = React.useMemo(() => !courseDetails ? {
    title: `Loading ${courseId}...`,
    description: "Details are being loaded",
    type: "Unknown",
    status: "Pending" as Status,
    connections: 0,
    lastUpdated: "Loading..."
  } : {
    title: `${courseDetails.id} - ${courseDetails.name}`,
    description: courseDetails.description,
    type: "Course",
    status: "Active" as Status,
    connections: 0,
    lastUpdated: "Now"
  }, [courseDetails, courseId]);
  const cardRef = React.useRef<HTMLDivElement>(null);
  const [cardSize, setCardSize] = React.useState({
    width: CARD_DEFAULT_WIDTH,
    height: CARD_DEFAULT_HEIGHT,
  });

  React.useLayoutEffect(() => {
    if (cardRef.current) {
      const rect = cardRef.current.getBoundingClientRect();
        setCardSize({
          width: rect.width,
          height: rect.height,
        });
    }
  }, [details]);

  const getStatusClass = (status: Status | string) => {
    switch (status) {
      case "Active":
        return "text-green-600";
      case "Locked":
        return "text-yellow-600";
      case "Disabled":
        return "text-red-600";
      default:
        return "text-yellow-600";
    }
  };

  const getStatusBackgroundClass = (status: Status | string) => {
    switch (status) {
      case "Active":
        return "bg-green-500";
      case "Locked":
        return "bg-yellow-500";
      case "Disabled":
        return "bg-red-500";
      default:
        return "bg-yellow-500";
    }
  };

  const getHoverCardPosition = () => {
    const { width: cardWidth, height: cardHeight } = cardSize;
    
    // Get node position from DOM
    const nodeElement = document.querySelector(`[data-node-circle="${nodeId}"]`);
    if (!nodeElement || !containerRef.current) {
      return { cardStyle: { left: 0, top: 0, display: 'none' } };
    }
    
    const nodeRect = nodeElement.getBoundingClientRect();
    const containerRect = containerRef.current.getBoundingClientRect();
    const scrollTop = containerRef.current?.scrollTop || 0;
    
    const nodeRelativeX = nodeRect.left - containerRect.left + scrollLeft + nodeRect.width / 2;
    const nodeRelativeY = nodeRect.top - containerRect.top + scrollTop + nodeRect.height / 2;

    let cardX = nodeRelativeX + NODE_CIRCLE_RADIUS + MIN_VISIBLE_PADDING;
    let cardY = nodeRelativeY;

    const visibleLeft = scrollLeft + MIN_VISIBLE_PADDING;
    const containerWidth = viewportWidth || containerRef.current?.clientWidth || 0;
    const visibleRight = scrollLeft + containerWidth - MIN_VISIBLE_PADDING;

    const spaceRight = visibleRight - (nodeRelativeX + NODE_CIRCLE_RADIUS + MIN_VISIBLE_PADDING);
    const spaceLeft = nodeRelativeX - NODE_CIRCLE_RADIUS - MIN_VISIBLE_PADDING - visibleLeft;

    if (spaceRight >= cardWidth) {
      // Place card to the right of the node
      cardX = nodeRelativeX + NODE_CIRCLE_RADIUS + MIN_VISIBLE_PADDING;
    } else if (spaceLeft >= cardWidth) {
      // Place card to the left of the node
      cardX = nodeRelativeX - cardWidth - NODE_CIRCLE_RADIUS - MIN_VISIBLE_PADDING;
    } else if (spaceRight >= spaceLeft) {
      // Not enough space on either side, but more on the right
      cardX = Math.max(visibleLeft, nodeRelativeX + NODE_CIRCLE_RADIUS + MIN_VISIBLE_PADDING);
    } else {
      // Not enough space on either side, but more on the left
      cardX = Math.max(
        visibleLeft,
        nodeRelativeX - cardWidth - NODE_CIRCLE_RADIUS - MIN_VISIBLE_PADDING,
      );

  }

  // Vertical positioning
  if (cardY - cardHeight / 2 < MIN_VISIBLE_PADDING) {
    cardY = MIN_VISIBLE_PADDING + cardHeight / 2;
  } else if (
    cardY + cardHeight / 2 >
    (containerRef.current?.clientHeight || 0) - MIN_VISIBLE_PADDING
  ) {
    cardY =
      (containerRef.current?.clientHeight || 0) -
      MIN_VISIBLE_PADDING -
      cardHeight / 2;
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
      className={cardClassName}
      style={cardStyle}
      onMouseEnter={onMouseEnter || (() => {})}
      onMouseLeave={onMouseLeave || (() => {})}
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
              className={`font-medium ${getStatusClass(details.status)}`}
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
              className={`w-2 h-2 rounded-full ${getStatusBackgroundClass(
                details.status
              )}`}
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
