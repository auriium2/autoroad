# Autoroad Codebase Analysis: Graph Visualization Architecture

## Overview
This document maps the code responsible for graph visualization, edge rendering, node positioning, prerequisite relationships, and edge color/tinting logic in the Autoroad application.

---

## 1. Edge Rendering and Styling

### Primary File: `/Users/matt/summer/autoroad/components/course-graph/CourseEdges.tsx`

**Responsibility:** Renders prerequisite relationship edges as SVG paths between course nodes.

**Key Features:**
- Renders edges as curved SVG paths using cubic Bezier curves
- Two-layer styling based on edge distance:
  - **Close edges** (horizontal distance ≤ 300px):
    - Color: `#9ca3af` (gray)
    - Stroke width: 2px
    - Opacity: 0.6
    - Solid line
  - **Long distance edges** (horizontal distance > 300px):
    - Color: `#d1d5db` (light gray)
    - Stroke width: 1.5px
    - Opacity: 0.4
    - Dashed line (`strokeDasharray: "8 4"`)

**Key Code Sections:**
```typescript
// Line 109-125: Edge styling logic
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
```

**Positioning Logic:**
- Calculates circle positions using `data-node-circle` attribute
- Applies 20px circle radius offsets to prevent edges from overlapping nodes
- Uses cubic Bezier curve with control points calculated from vertical distance

**SVG Path Rendering:**
- Uses `M` (moveto) command to start from source node
- Uses `C` (cubic Bezier) command for curved path to target node
- Renders with `fill: "none"`, `strokeLinecap: "round"`

### Secondary Location: `/Users/matt/summer/autoroad/components/course-graph/CourseGraphFlow.tsx`

**Edge styling in ReactFlow context** (lines 327-360):
- Maps store edges to ReactFlow edge objects
- Applies similar distance-based styling
- Uses ReactFlow's `MarkerType.ArrowClosed` for arrowheads
- Filters out edges from "Must Take" column (section -2)

```typescript
// Line 335: Distance-based styling in ReactFlow
const isLongDistance = Math.abs(toX - fromX) > 1;

return {
  style: {
    stroke: isLongDistance ? 'rgba(209, 213, 219, 0.4)' : 'rgba(156, 163, 175, 0.7)',
    strokeWidth: isLongDistance ? 1.5 : 2,
    strokeDasharray: isLongDistance ? '5 5' : undefined,
  },
  markerEnd: {
    type: MarkerType.ArrowClosed,
    color: isLongDistance ? 'rgba(209, 213, 219, 0.4)' : 'rgba(156, 163, 175, 0.7)',
  },
};
```

---

## 2. Node Positioning and Ordering Logic

### Primary File: `/Users/matt/summer/autoroad/components/course-graph/CourseGraphFlow.tsx`

**Responsibility:** Manages layout and positioning of nodes in column-based grid system.

**Column System:**
- Fixed 200px wide columns
- Special columns at start:
  - Index 0: "Must Take" (section id: -2)
  - Index 1: "ASEs" (section id: -1)
  - Index 2+: Regular semester sections

**Node Positioning Algorithm** (lines 245-270):
```typescript
const COLUMN_WIDTH = 200;
const NODE_SPACING = 120;
const VIEWPORT_CENTER_Y = 400;

const sectionIndex = allSections.findIndex(s => s.id === node.section);
const nodesInSection = storeNodes.filter(n => n.section === node.section);
const nodeIndexInSection = nodesInSection.findIndex(n => n.id === node.id);

// Calculate total height of nodes in this section
const totalNodesHeight = (nodesInSection.length - 1) * NODE_SPACING;
// Start Y position to center the group vertically
const startY = VIEWPORT_CENTER_Y - (totalNodesHeight / 2);

return {
  x: sectionIndex * COLUMN_WIDTH + (COLUMN_WIDTH / 2),  // Column center
  y: startY + nodeIndexInSection * NODE_SPACING,  // Vertically spaced
};
```

**Key Features:**
- Vertical centering: Nodes are centered around Y=400 (viewport center)
- Vertical spacing: 120px between each node in a column
- Horizontal centering: Nodes placed at column midpoint (x = columnIndex * 200 + 100)

**Dynamic Node Ordering:**
- Nodes within a section are ordered by their position in the `storeNodes` array
- No explicit sorting is applied; order preserved from store

### Column Layout: `/Users/matt/summer/autoroad/components/course-graph/CourseGraph.tsx`

**Grid-based layout** (lines 147-155):
- Uses CSS Flexbox for column layout
- Each column: `minWidth: "180px"`, `flex: "0 0 180px"`
- Nodes centered in each column with `gap-16` (64px vertical gap)
- Sections marked with header and background colors

**Node Drag/Drop Positioning** (lines 102-127):
```typescript
const onNodeDragStop = (_event: React.MouseEvent, node: Node) => {
  const COLUMN_WIDTH = 200;
  const sectionIndex = Math.round((node.position.x - COLUMN_WIDTH / 2) / COLUMN_WIDTH);
  const clampedIndex = Math.max(0, Math.min(sectionIndex, allSections.length - 1));
  const section = allSections[clampedIndex];
  
  if (section && node.data.section !== section.id) {
    updateNodeLocal(node.id, { section: section.id });
  }
};
```

---

## 3. Prerequisite Relationships Between Nodes

### Data Structure: `/Users/matt/summer/autoroad/types.ts`

**Edge Type Definition:**
```typescript
export interface Edge {
  from_id: string;  // Source course node ID
  to_id: string;    // Target course node ID
}
```

Represents a prerequisite relationship: `from_id` is a prerequisite for `to_id`.

### Store Management: `/Users/matt/summer/autoroad/stores/roadStore.ts`

**Prerequisite Data Storage:**
- Stored as array in `GraphStore.edges`
- Loaded from localStorage or API

**Edge Management Functions:**

1. **setEdges**: Sets all edges at once
   ```typescript
   setEdges: (edges) => set({ edges })
   ```

2. **removeNode**: Cascades edge removal when node deleted
   ```typescript
   edges: edges.filter(e => e.from_id !== id && e.to_id !== id)
   ```

3. **Demo/Initial Data**: `/Users/matt/summer/autoroad/stores/roadStore.ts` lines 193-222
   ```typescript
   edges: [
     { from_id: "1", to_id: "2" },  // 6.100 -> 6.1200
     { from_id: "2", to_id: "4" },  // 6.1200 -> 6.1010
     { from_id: "3", to_id: "4" },  // 6.120a -> 6.1010
     // ... more prerequisite relationships
   ]
   ```

### Backend Integration: `/Users/matt/summer/autoroad/lib/dataTransformers.ts`

**Edge Transformation** (lines 16-22):
```typescript
const edges: Edge[] = ((data.prerequisites as unknown[]) || []).map((prereq: unknown) => {
  const p = prereq as Record<string, unknown>;
  return {
    from_id: String(p.course),
    to_id: String(p.prerequisite)
  };
});
```

**Prerequisite Generation** (lines 48-73):
```typescript
export function generateEdgesFromPrerequisites(courseData: unknown[]): Edge[] {
  const edges: Edge[] = [];
  courseData.forEach(course => {
    const sourceId = String(c.subject_id);
    if (c.prerequisites) {
      if (Array.isArray(c.prerequisites)) {
        c.prerequisites.forEach((prereq: unknown) => {
          edges.push({
            from_id: String(prereq),
            to_id: sourceId
          });
        });
      }
    }
  });
  return edges;
}
```

---

## 4. Edge Color/Tinting Logic

### 4.1 Distance-Based Edge Coloring (Primary)

**File:** `/Users/matt/summer/autoroad/components/course-graph/CourseEdges.tsx` (lines 109-125)

**Logic:**
- Edges are colored based on horizontal distance between nodes
- **Calculation:** `horizontalDistance = Math.abs(dx)` where dx is column difference × 200px

**Color Mapping:**
| Distance | Scenario | Color | Width | Opacity | Style |
|----------|----------|-------|-------|---------|-------|
| ≤ 300px | Adjacent/close columns | `#9ca3af` (gray) | 2px | 0.6 | Solid |
| > 300px | Multi-column gap | `#d1d5db` (light gray) | 1.5px | 0.4 | Dashed |

### 4.2 Node-Based Styling (Secondary)

**File:** `/Users/matt/summer/autoroad/lib/nodeStyles.ts`

**Node styling hierarchy** (affects nodes, not edges directly):

```typescript
export function getNodeStyle(node: NodeStyleProperties): NodeStyleConfig {
  const { section, userControlled, disabled, isSpecial } = node;
  
  // Must Take column (section -2)
  if (isMustTake) {
    bgColor = "bg-purple-950/40";
    textColor = "text-purple-300";
    boxShadow = "0 0 20px rgba(168, 85, 247, 0.6), 0 0 40px rgba(168, 85, 247, 0.3)";
  }
  // User-controlled nodes
  else if (userControlled) {
    bgColor = "bg-card";
    boxShadow = "0 0 20px rgba(59, 130, 246, 0.5), 0 0 40px rgba(59, 130, 246, 0.3)";
  }
  // ASEs column (section -1)
  else if (isASE) {
    borderColor = "border-gray-300 dark:border-gray-600";
    bgColor = "bg-gray-50 dark:bg-gray-900/40";
    textColor = "text-gray-300";
    boxShadow = "none";
  }
  // Disabled nodes
  else if (disabled) {
    borderColor = "border-red-500";
    bgColor = "bg-red-50 dark:bg-red-950/20";
    textColor = "text-red-400";
    boxShadow = "none";
  }
}
```

### 4.3 Term-Based Border Highlighting

**File:** `/Users/matt/summer/autoroad/lib/termBorderHighlight.ts`

**Purpose:** Highlight portions of node circle border based on term availability.

**Pattern Mapping:**
```typescript
const HIGHLIGHT_CONFIG: Record<TermPattern, TermBorderHighlight> = {
  fall: { dasharray: "0.5 0.5", dashoffset: 0.25 },      // Left half
  spring: { dasharray: "0.5 0.5", dashoffset: 0.75 },    // Right half
  iap: { dasharray: "0.5 0.5", dashoffset: 0.5 },        // Bottom half
  both: { dasharray: "1 0", dashoffset: 0 },             // Full ring
};
```

**Usage in CourseNode** (`/Users/matt/summer/autoroad/components/course-graph/CourseNode.tsx` lines 57-70):
```typescript
{termHighlight && (
  <svg className="pointer-events-none absolute inset-0">
    <circle
      cx="20" cy="20" r="18"
      fill="none"
      stroke="rgba(255,255,255,0.25)"
      strokeWidth="2"
      pathLength={1}
      strokeDasharray={termHighlight.dasharray}
      strokeDashoffset={termHighlight.dashoffset}
      strokeLinecap="butt"
    />
  </svg>
)}
```

---

## 5. Data Flow Architecture

### State Management
```
Store (Zustand) → React Components
    ↓
/stores/roadStore.ts
    - nodes: CourseNode[]
    - edges: Edge[]
    - sections: Section[]
    ↓
Components:
    - CourseGraphFlow (ReactFlow)
    - CourseGraph (CSS-based)
    - CourseEdges (SVG)
    - CourseNode (Individual node)
```

### Rendering Pipeline

**CourseGraphFlow (ReactFlow):**
1. Convert store nodes → ReactFlow nodes (with positions)
2. Convert store edges → ReactFlow edges (with styling)
3. Apply distance-based edge coloring
4. Filter edges from "Must Take" column
5. Render with ReactFlow engine

**CourseGraph (CSS):**
1. Group nodes by section
2. Position in column grid
3. Render edges as SVG overlay
4. Calculate edge paths from node positions
5. Apply distance-based styling

---

## 6. Special Cases and Edge Cases

### Filtered Edge Rendering

**File:** `/Users/matt/summer/autoroad/components/course-graph/CourseGraphFlow.tsx` (line 338)

Edges from/to "Must Take" column (section -2) are hidden:
```typescript
if (fromNode.section === -2 || toNode.section === -2) {
  return null;
}
```

### Node Dragging

**Files:** 
- `CourseGraphFlow.tsx` (lines 291-310)
- `CourseGraph.tsx` (lines 102-127)

When user drags a node:
1. Calculate new column position
2. Update node's section property
3. Trigger re-render with new positioning
4. Save to localStorage automatically

### Viewport-Aware Rendering

**CourseEdges.tsx** (lines 48-57):
```typescript
const containerRect = containerRef.current.getBoundingClientRect();
const scrollLeft = containerRef.current.scrollLeft;
const scrollTop = containerRef.current.scrollTop;
const width = containerRef.current.scrollWidth;
const height = containerRef.current.scrollHeight;
```

- Edges update on scroll/resize
- Uses ResizeObserver for dynamic layout changes
- Force re-render on viewport changes

---

## 7. Future Enhancement Points

Based on the current architecture, here are areas for enhancement:

### Edge Color Customization
- Currently distance-based only
- Could add:
  - Prerequisite type visualization (optional vs required)
  - Co-requisite indicators
  - Semester-spanning prerequisites
  - Prerequisite satisfaction status

### Node Ordering
- Currently preserves store order
- Could implement:
  - Topological sorting (prerequisites before dependents)
  - Degree-based sorting (high connectivity)
  - User-defined ordering
  - Automatic layout algorithms (Sugiyama, Hierarchical)

### Edge Rendering
- Currently SVG with cubic Bezier curves
- Could implement:
  - Spline interpolation for smoother curves
  - Multiple routing strategies (orthogonal, hierarchical)
  - Edge bundling for dense graphs
  - Interactive edge highlighting

---

## 8. File Reference Summary

| File | Responsibility |
|------|-----------------|
| `CourseEdges.tsx` | SVG edge rendering with distance-based styling |
| `CourseGraphFlow.tsx` | ReactFlow integration, node positioning, edge conversion |
| `CourseGraph.tsx` | CSS-based column layout, drag-drop positioning |
| `CourseNode.tsx` | Individual node rendering, term highlighting |
| `CourseNodeHoverCard.tsx` | Node details tooltip |
| `nodeStyles.ts` | Node styling configuration |
| `termBorderHighlight.ts` | Term availability visualization |
| `roadStore.ts` | State management for nodes, edges, sections |
| `dataTransformers.ts` | Backend ↔ Frontend data conversion |
| `types.ts` | Type definitions (Edge, CourseNode, Section) |

---

## 9. Key Constants

| Constant | Value | Usage |
|----------|-------|-------|
| `COLUMN_WIDTH` | 200px | Column container width |
| `NODE_SPACING` | 120px | Vertical gap between nodes |
| `VIEWPORT_CENTER_Y` | 400px | Vertical centering baseline |
| `LONG_DISTANCE_THRESHOLD` | 300px | Edge color/style threshold |
| `CIRCLE_RADIUS` | 20px | Node circle size |
| `EDGE_LONG_DISTANCE_WIDTH` | 1.5px | Long edge stroke width |
| `EDGE_CLOSE_DISTANCE_WIDTH` | 2px | Close edge stroke width |

