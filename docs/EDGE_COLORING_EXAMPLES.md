# Edge Rendering and Coloring: Implementation Examples

## 1. Edge Rendering Implementation

### SVG-Based Edge Rendering (CourseEdges.tsx)

```typescript
// Source: /Users/matt/summer/autoroad/components/course-graph/CourseEdges.tsx (lines 74-138)

edges.map((edge, idx) => {
  const fromNode = nodeRefs.current?.get(edge.from_id);
  const toNode = nodeRefs.current?.get(edge.to_id);

  if (!fromNode || !toNode) return null;

  const fromCircle = fromNode.querySelector('[data-node-circle]');
  const toCircle = toNode.querySelector('[data-node-circle]');

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

  // Determine edge style based on distance
  const horizontalDistance = Math.abs(dx);
  const isLongDistance = horizontalDistance > 300;
  
  let strokeColor = "#9ca3af";      // Gray for close edges
  let strokeWidth = 2;
  let opacity = 0.6;
  let isDashed = false;

  if (isLongDistance) {
    strokeColor = "#d1d5db";        // Light gray for long edges
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
})
```

### ReactFlow-Based Edge Rendering (CourseGraphFlow.tsx)

```typescript
// Source: /Users/matt/summer/autoroad/components/course-graph/CourseGraphFlow.tsx (lines 327-360)

const flowEdges: FlowEdge[] = storeEdges.map((edge) => {
  const fromNode = storeNodes.find(n => n.id === edge.from_id);
  const toNode = storeNodes.find(n => n.id === edge.to_id);

  if (!fromNode || !toNode) {
    return null;
  }

  // Don't render edges if either node is in "Must Take" column (section -2)
  if (fromNode.section === -2 || toNode.section === -2) {
    return null;
  }

  const fromX = allSections.findIndex(s => s.id === fromNode?.section);
  const toX = allSections.findIndex(s => s.id === toNode?.section);
  const isLongDistance = Math.abs(toX - fromX) > 1;

  return {
    id: `edge-${edge.from_id}-${edge.to_id}`,
    source: String(edge.from_id),
    target: String(edge.to_id),
    type: 'default', // Bezier curves
    animated: false,
    style: {
      stroke: isLongDistance ? 'rgba(209, 213, 219, 0.4)' : 'rgba(156, 163, 175, 0.7)',
      strokeWidth: isLongDistance ? 1.5 : 2,
      strokeDasharray: isLongDistance ? '5 5' : undefined,
    },
    markerEnd: {
      type: MarkerType.ArrowClosed,
      width: 10,
      height: 10,
      color: isLongDistance ? 'rgba(209, 213, 219, 0.4)' : 'rgba(156, 163, 175, 0.7)',
    },
  };
}).filter(Boolean) as FlowEdge[];
```

---

## 2. Color and Style Decision Tree

```
Edge Coloring Decision Logic:
├── Calculate Horizontal Distance (dx)
│   ├── If dx <= 300px
│   │   ├── Color: #9ca3af (gray)
│   │   ├── Stroke Width: 2px
│   │   ├── Opacity: 0.6
│   │   └── Style: Solid line ──────
│   │
│   └── If dx > 300px
│       ├── Color: #d1d5db (light gray)
│       ├── Stroke Width: 1.5px
│       ├── Opacity: 0.4
│       └── Style: Dashed line ─ ─ ─
│
└── Apply Path Rendering
    ├── Use Cubic Bezier (M C) commands
    ├── Circle radius offsets: 20px
    └── Control points: dy * 0.3
```

---

## 3. Color Values Reference

### Edge Colors

| Context | Color Hex | RGB | Use Case |
|---------|-----------|-----|----------|
| Close edges | `#9ca3af` | rgb(156, 163, 175) | Adjacent/nearby prerequisites |
| Long edges | `#d1d5db` | rgb(209, 213, 219) | Multi-column prerequisites |
| Edge glow | `rgba(156, 163, 175, 0.7)` | Semi-transparent gray | Close edge emphasis |
| Long edge glow | `rgba(209, 213, 219, 0.4)` | Semi-transparent light gray | Long edge emphasis |

### Node Colors

| Node Type | Color | Box Shadow |
|-----------|-------|-----------|
| Must Take (section -2) | `bg-purple-950/40` | `0 0 20px rgba(168, 85, 247, 0.6)` |
| User-controlled | `bg-card` | `0 0 20px rgba(59, 130, 246, 0.5)` |
| ASEs (section -1) | `bg-gray-50/900` | `none` |
| Disabled | `bg-red-50/950` | `none` |

### Term Availability Border Highlighting

```typescript
// SVG Circle stroke with dasharray patterns
const HIGHLIGHT_CONFIG = {
  fall: {      // Left half of circle
    dasharray: "0.5 0.5",
    dashoffset: 0.25,
  },
  spring: {    // Right half of circle
    dasharray: "0.5 0.5",
    dashoffset: 0.75,
  },
  iap: {       // Bottom half of circle
    dasharray: "0.5 0.5",
    dashoffset: 0.5,
  },
  both: {      // Full ring
    dasharray: "1 0",
    dashoffset: 0,
  },
};
```

**Visual Representation:**
```
Fall only:          Spring only:        IAP only:           Fall + Spring:
  ╱─────╲             ╱─────╲             ╱─────╲              ╭─────╮
 ╱   ··· ╲           ╱       ╲           ╱       ╲            ╱       ╲
│  ·····  │         │  · ····  │        │        ·· │        │         │
│ ····   ·│        │ ·· ····· │        │ ········· │        │         │
 ╲ ····· ╱          ╲ ····    ╱         ╲ ····· ╱          ╲         ╱
  ╲─────╱            ╲─────╱             ╲─────╱              ╰─────╯
(Left dash)        (Right dash)      (Bottom dash)         (Full solid)
```

---

## 4. Position Calculation Examples

### Example 1: Close Edge (Same/Adjacent Columns)

```
Input:
  - From node: Section 0 (x=100), y=100
  - To node: Section 1 (x=300), y=250
  - Circle radius: 20px

Calculation:
  dx = 300 - 100 = 200
  dy = 250 - 100 = 150
  distance = √(200² + 150²) = 250px
  
  horizontalDistance = |200| = 200px
  isLongDistance = 200 > 300? → FALSE
  
Output Styling:
  strokeColor: "#9ca3af"
  strokeWidth: 2
  opacity: 0.6
  isDashed: false
  Path: Solid gray line with 2px width
```

### Example 2: Long Edge (Multi-Column Gap)

```
Input:
  - From node: Section 0 (x=100), y=100
  - To node: Section 3 (x=700), y=150
  - Circle radius: 20px

Calculation:
  dx = 700 - 100 = 600
  dy = 150 - 100 = 50
  distance = √(600² + 50²) ≈ 602px
  
  horizontalDistance = |600| = 600px
  isLongDistance = 600 > 300? → TRUE
  
Output Styling:
  strokeColor: "#d1d5db"
  strokeWidth: 1.5
  opacity: 0.4
  isDashed: true (strokeDasharray: "8 4")
  Path: Dashed light gray line with 1.5px width
```

---

## 5. Bezier Curve Control Points

### Curve Formula

```typescript
// Create curved path using cubic bezier
const midX = (offsetFromX + offsetToX) / 2;
const controlY1 = offsetFromY + dy * 0.3;
const controlY2 = offsetToY - dy * 0.3;

const path = `M ${offsetFromX} ${offsetFromY} C ${midX} ${controlY1}, ${midX} ${controlY2}, ${offsetToX} ${offsetToY}`;
```

### Curve Visualization

```
Vertical Layout Example (dy=150):

  From Node (offsetFromY=120)
        ○
        │ midX=200, controlY1=120+150*0.3=165
        │
      ╱─╲
    ╱     ╲  Bezier curves down to midpoint
   │       │ then back up
    ╲     ╱
      ╲─╱
        │ midX=200, controlY2=270-150*0.3=225
        │
  To Node (offsetToY=270)
        ○

Control points create smooth arc that avoids node circles
```

---

## 6. Filter Logic: Must Take Column

```typescript
// Source: CourseGraphFlow.tsx, line 338

if (fromNode.section === -2 || toNode.section === -2) {
  return null;  // Don't render edge
}

/**
 * Why filter "Must Take" edges?
 * - Must Take courses are prerequisites/requirements
 * - Don't affect the optimization logic
 * - Keep graph focus on planned semester courses
 * - Reduces visual clutter
 * - These courses stay in dedicated column
 */
```

---

## 7. Responsive Behavior

### Scroll and Resize Handling (CourseEdges.tsx)

```typescript
// Force re-render on scroll/resize
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

// Update on ResizeObserver changes
React.useEffect(() => {
  const resizeObserver = new ResizeObserver(() => {
    forceUpdate();
  });

  resizeObserver.observe(container);

  return () => {
    resizeObserver.disconnect();
  };
}, [containerRef]);
```

---

## 8. Enhancement Ideas

### Current Limitation
- Only distance-based edge coloring
- No prerequisite type differentiation
- No co-requisite indicators

### Proposed Enhancements

```typescript
// Pseudo-code for enhanced coloring

interface EdgeMetadata {
  from_id: string;
  to_id: string;
  prerequisiteType?: 'required' | 'optional' | 'corequisite';
  isSatisfied?: boolean;
  semesterSpan?: number;  // How many semesters apart
}

function getEdgeColor(edge: EdgeMetadata, distance: number): string {
  // Prerequisite type takes priority over distance
  if (edge.prerequisiteType === 'optional') {
    return '#a78bfa';  // Purple for optional
  }
  if (edge.prerequisiteType === 'corequisite') {
    return '#60a5fa';  // Blue for corequisite
  }
  
  // For required prerequisites, use distance-based coloring
  if (distance > 300) {
    return '#d1d5db';  // Light gray for long distance
  }
  return '#9ca3af';    // Gray for close distance
}

function getEdgeStyle(edge: EdgeMetadata): {
  strokeDasharray?: string;
  strokeWidth: number;
  opacity: number;
} {
  if (!edge.isSatisfied) {
    return {
      strokeDasharray: '10 5',  // Dashed for unsatisfied
      strokeWidth: 2.5,
      opacity: 0.8,
    };
  }
  
  return {
    strokeWidth: 2,
    opacity: 0.6,
  };
}
```

