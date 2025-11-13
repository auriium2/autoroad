# Quick Reference: Code Locations for Graph Visualization

## File Locations (All Absolute Paths)

### Core Graph Rendering Files

| Feature | File | Key Lines | Function |
|---------|------|-----------|----------|
| **Edge Rendering & SVG** | `/Users/matt/summer/autoroad/components/course-graph/CourseEdges.tsx` | 74-138 | `CourseEdges` component - renders SVG edges with distance-based coloring |
| **Edge Color Logic** | `/Users/matt/summer/autoroad/components/course-graph/CourseEdges.tsx` | 109-125 | Distance threshold and color assignment |
| **ReactFlow Integration** | `/Users/matt/summer/autoroad/components/course-graph/CourseGraphFlow.tsx` | 327-360 | `CourseGraphFlowInner` - converts edges to ReactFlow format |
| **Node Positioning** | `/Users/matt/summer/autoroad/components/course-graph/CourseGraphFlow.tsx` | 245-270 | Node position calculation with column and vertical spacing |
| **CSS Grid Layout** | `/Users/matt/summer/autoroad/components/course-graph/CourseGraph.tsx` | 147-155 | Column-based grid layout |
| **Drag/Drop Logic** | `/Users/matt/summer/autoroad/components/course-graph/CourseGraphFlow.tsx` | 291-310 | `onNodeDragStop` - section recalculation on drag |
| **Node Styling** | `/Users/matt/summer/autoroad/lib/nodeStyles.ts` | Full file | `getNodeStyle` function for node colors and shadows |
| **Term Highlighting** | `/Users/matt/summer/autoroad/lib/termBorderHighlight.ts` | Full file | SVG circle border patterns for term availability |
| **Individual Node** | `/Users/matt/summer/autoroad/components/course-graph/CourseNode.tsx` | 57-70 | Term availability SVG overlay |

### Data Management Files

| Feature | File | Key Lines | Function |
|---------|------|-----------|----------|
| **State Management** | `/Users/matt/summer/autoroad/stores/roadStore.ts` | Full file | Zustand store with nodes, edges, sections |
| **Edge Type Definition** | `/Users/matt/summer/autoroad/types.ts` | Lines 47-50 | `Edge` interface definition |
| **Demo Data** | `/Users/matt/summer/autoroad/stores/roadStore.ts` | 193-222 | Sample nodes and edges for development |
| **Edge Transformation** | `/Users/matt/summer/autoroad/lib/dataTransformers.ts` | 16-22, 48-73 | Backend to frontend edge conversion |

---

## Quick Lookup: What Code Does What?

### "I need to change edge colors"
**Go to:** `/Users/matt/summer/autoroad/components/course-graph/CourseEdges.tsx` lines 109-125

**Lines to modify:**
```typescript
let strokeColor = "#9ca3af";      // Close edge color
let strokeColor = "#d1d5db";      // Long edge color
let strokeWidth = 2;               // Close edge width
let strokeWidth = 1.5;             // Long edge width
```

**For ReactFlow version:**
Go to `/Users/matt/summer/autoroad/components/course-graph/CourseGraphFlow.tsx` lines 337-340

### "I need to change the distance threshold"
**Go to:** `/Users/matt/summer/autoroad/components/course-graph/CourseEdges.tsx` line 106

**Line to modify:**
```typescript
const isLongDistance = horizontalDistance > 300;  // Change 300 to your value
```

**Also update:** `/Users/matt/summer/autoroad/components/course-graph/CourseGraphFlow.tsx` line 334
```typescript
const isLongDistance = Math.abs(toX - fromX) > 1;  // For column-based distance
```

### "I need to change node positioning/spacing"
**Go to:** `/Users/matt/summer/autoroad/components/course-graph/CourseGraphFlow.tsx` lines 251-254

**Lines to modify:**
```typescript
const COLUMN_WIDTH = 200;      // Horizontal spacing
const NODE_SPACING = 120;      // Vertical spacing
const VIEWPORT_CENTER_Y = 400; // Vertical center
```

### "I need to find prerequisite edges"
**Go to:** `/Users/matt/summer/autoroad/stores/roadStore.ts` lines 193-222 (demo data)

**Or:** Check any `edges` array which contains:
```typescript
{ from_id: "source_node_id", to_id: "target_node_id" }
```

### "I need to style nodes based on properties"
**Go to:** `/Users/matt/summer/autoroad/lib/nodeStyles.ts`

**Functions:**
- `getNodeStyle()` - Returns border, background, text colors and shadows

### "I need to add term availability visual"
**Go to:** `/Users/matt/summer/autoroad/lib/termBorderHighlight.ts`

**Modify:** `HIGHLIGHT_CONFIG` object to change SVG stroke patterns

---

## Visual Component Tree

```
CourseGraphFlow (ReactFlow-based)
├── ColumnHeaders (sticky headers)
├── FlowCourseNode
│   └── CourseNode
│       ├── Circle (40px)
│       ├── Term Highlight SVG
│       └── Course ID Label
├── SVG Edges (ReactFlow's default)
└── Context Menu

OR

CourseGraph (CSS-based, simpler)
├── Section Columns (CSS Flex)
│   ├── Header
│   └── Nodes Container
│       └── CourseNode (repeated)
├── CourseEdges (SVG overlay)
│   └── SVG Paths (curved edges)
└── CourseNodeHoverCard
```

---

## Data Flow Diagram

```
User Adds Course
    ↓
useGraphStore.addNode()
    ↓
Zustand Store Updated (nodes array)
    ↓
React Components Re-render
    ├── CourseGraphFlow:
    │   ├── Convert nodes → ReactFlow nodes
    │   ├── Convert edges → ReactFlow edges
    │   └── Calculate positions (COLUMN_WIDTH, NODE_SPACING)
    │
    └── CourseGraph:
        ├── Group nodes by section
        ├── Render in CSS grid
        └── Overlay SVG edges
            ├── Get node positions
            ├── Calculate paths
            ├── Apply distance-based colors
            └── Render SVG <path> elements
    ↓
Save to localStorage (automatic)
```

---

## Key Constants Reference

```typescript
// Position/Layout (CourseGraphFlow.tsx)
COLUMN_WIDTH = 200           // px - column width
NODE_SPACING = 120           // px - vertical gap between nodes
VIEWPORT_CENTER_Y = 400      // px - vertical centering baseline
COLUMN_HEADER_HEIGHT = 56    // px - (h-14 = 56px)

// Coloring (CourseEdges.tsx)
DISTANCE_THRESHOLD = 300     // px - close vs long edge threshold
CIRCLE_RADIUS = 20           // px - node circle size

// Colors (Hex & RGB)
CLOSE_EDGE_COLOR = "#9ca3af"     // rgb(156, 163, 175)
LONG_EDGE_COLOR = "#d1d5db"      // rgb(209, 213, 219)
CLOSE_EDGE_WIDTH = 2             // px
LONG_EDGE_WIDTH = 1.5            // px
CLOSE_EDGE_OPACITY = 0.6
LONG_EDGE_OPACITY = 0.4

// Special Columns (section IDs)
MUST_TAKE_SECTION = -2           // Purple hazard overlay
ASES_SECTION = -1                // Light gray background

// Curves (Bezier control points)
CONTROL_POINT_FACTOR = 0.3       // dy * 0.3 for curve control
```

---

## Search Patterns for Common Tasks

### Find all edge color assignments
```bash
grep -r "strokeColor\|stroke:" \
  /Users/matt/summer/autoroad/components/course-graph/ \
  /Users/matt/summer/autoroad/lib/
```

### Find all node positioning logic
```bash
grep -r "position\|x:\|y:" \
  /Users/matt/summer/autoroad/components/course-graph/CourseGraphFlow.tsx
```

### Find prerequisite/edge relationships
```bash
grep -r "from_id\|to_id\|edge" \
  /Users/matt/summer/autoroad/stores/ \
  /Users/matt/summer/autoroad/types.ts
```

### Find node styling conditions
```bash
grep -r "isMustTake\|isASE\|userControlled\|disabled" \
  /Users/matt/summer/autoroad/lib/nodeStyles.ts
```

---

## Implementation Comparison: SVG vs ReactFlow

### SVG-Based (CourseEdges.tsx)
- ✓ Full control over rendering
- ✓ Can customize every aspect
- ✓ Lighter weight for simple graphs
- ✗ Manual position calculations
- ✗ Must handle scroll/resize updates
- ✗ No built-in interactivity

**Use when:** You need precise visual control and custom interactions

### ReactFlow-Based (CourseGraphFlow.tsx)
- ✓ Built-in node/edge selection
- ✓ Automatic pan/zoom
- ✓ Handles viewport updates
- ✓ Rich ecosystem of plugins
- ✗ Less customization
- ✗ Heavier bundle size
- ✗ Opinionated layout system

**Use when:** You need a feature-rich, interactive graph

---

## Testing Checklist

When modifying edge colors or positioning:

- [ ] Check edge rendering at different zoom levels
- [ ] Test scroll/resize updates (edges should move with nodes)
- [ ] Verify long-distance edges (> 300px) render dashed
- [ ] Verify close edges (≤ 300px) render solid
- [ ] Test drag-and-drop (node moves, edges follow)
- [ ] Verify edges don't overlap nodes (20px offset)
- [ ] Test with multiple nodes in same section
- [ ] Verify "Must Take" edges are filtered out
- [ ] Check term highlighting on nodes
- [ ] Test with very long prerequisite chains

---

## Common Modifications

### Add edge animation on hover
**Location:** `/Users/matt/summer/autoroad/components/course-graph/CourseEdges.tsx`

```typescript
// After line 118, add:
const isHovered = hoveredEdge === `${edge.from_id}-${edge.to_id}`;

// Apply in <path> element:
opacity={isHovered ? 1 : opacity}
strokeWidth={isHovered ? strokeWidth + 1 : strokeWidth}
```

### Change edge curve intensity
**Location:** `/Users/matt/summer/autoroad/components/course-graph/CourseEdges.tsx` line 121

```typescript
// Current: dy * 0.3
// For more curve: dy * 0.5
// For less curve: dy * 0.1
const controlY1 = offsetFromY + dy * 0.3;  // Adjust multiplier
const controlY2 = offsetToY - dy * 0.3;    // Adjust multiplier
```

### Add prerequisite type visualization
**Location:** `/Users/matt/summer/autoroad/types.ts`

```typescript
export interface Edge {
  from_id: string;
  to_id: string;
  prerequisiteType?: 'required' | 'optional' | 'corequisite';  // Add this
}
```

Then in `CourseEdges.tsx` or `CourseGraphFlow.tsx`, use the type to determine color.

