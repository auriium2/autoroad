# Graph Visualization System - Complete Documentation Index

This directory contains comprehensive documentation about the Autoroad course graph visualization system. Use this index to navigate the documentation.

## Documentation Files

### 1. **CODEBASE_ANALYSIS.md** - Main Technical Reference
Comprehensive breakdown of all graph visualization components with code locations.

**Contents:**
- Edge rendering and styling implementation
- Node positioning and ordering logic
- Prerequisite relationship data structures
- Edge color/tinting logic (distance-based, node-based, term-based)
- Data flow architecture
- Special cases and edge cases
- Future enhancement points
- File reference summary
- Key constants

**Best for:** Understanding the overall architecture and finding specific implementations.

---

### 2. **EDGE_COLORING_EXAMPLES.md** - Implementation Details
Detailed code examples and visual guides for edge rendering and coloring.

**Contents:**
- Edge rendering implementation (SVG and ReactFlow)
- Color and style decision tree
- Color values reference (hex, RGB)
- Term availability visualization
- Position calculation examples with walkthroughs
- Bezier curve control points formula
- Filter logic for "Must Take" column
- Responsive behavior and scroll handling
- Enhancement ideas (optional prerequisites, co-requisites)

**Best for:** Understanding how edges are colored and styled, implementing changes.

---

### 3. **CODE_LOCATIONS_QUICK_REFERENCE.md** - Navigation Guide
Quick lookup guide for common tasks and where to find the code.

**Contents:**
- File locations with key line numbers
- Quick lookup by feature
- Visual component tree
- Data flow diagram
- Key constants reference
- Search patterns for common tasks
- Implementation comparison (SVG vs ReactFlow)
- Testing checklist
- Common modifications with code

**Best for:** Finding code fast, implementing specific features, testing.

---

### 4. **VISUAL_GUIDE.md** - Architecture Diagrams
Visual representations of the system architecture and rendering logic.

**Contents:**
- System architecture diagram
- Column-based grid layout visualization
- Edge color decision flow chart
- Node styling decision tree
- SVG Bezier curve visualization
- Term availability highlighting patterns
- Component hierarchy tree
- Performance optimization points

**Best for:** Understanding system flow visually, designing new features.

---

## Key Files in the Codebase

### Core Rendering Files
```
/Users/matt/summer/autoroad/
├── components/course-graph/
│   ├── CourseEdges.tsx              ← SVG edge rendering (primary)
│   ├── CourseGraphFlow.tsx          ← ReactFlow integration
│   ├── CourseGraph.tsx              ← CSS-based alternative
│   ├── CourseNode.tsx               ← Individual node rendering
│   ├── CourseNodeHoverCard.tsx      ← Tooltip/card display
│   └── reactflow-custom.css
│
├── lib/
│   ├── nodeStyles.ts                ← Node color/styling logic
│   ├── termBorderHighlight.ts       ← Term availability visualization
│   └── dataTransformers.ts          ← Data format conversion
│
├── stores/
│   └── roadStore.ts                 ← State management (Zustand)
│
└── types.ts                          ← Type definitions
```

---

## Quick Start: Common Tasks

### Task 1: Change Edge Colors
**File:** `/Users/matt/summer/autoroad/components/course-graph/CourseEdges.tsx` (lines 109-125)

```typescript
// Close edges (≤ 300px)
let strokeColor = "#9ca3af";      // Change this
let strokeWidth = 2;               // Or this

// Long edges (> 300px)
let strokeColor = "#d1d5db";      // Or this
let strokeWidth = 1.5;             // Or this
```

**Also check:** `CourseGraphFlow.tsx` lines 337-340 for ReactFlow version.

---

### Task 2: Change Distance Threshold
**File:** `/Users/matt/summer/autoroad/components/course-graph/CourseEdges.tsx` (line 106)

```typescript
const isLongDistance = horizontalDistance > 300;  // Change 300
```

---

### Task 3: Adjust Node Spacing
**File:** `/Users/matt/summer/autoroad/components/course-graph/CourseGraphFlow.tsx` (lines 251-254)

```typescript
const COLUMN_WIDTH = 200;      // Horizontal
const NODE_SPACING = 120;      // Vertical spacing between nodes
const VIEWPORT_CENTER_Y = 400; // Where to center vertically
```

---

### Task 4: Add Edge Animation
**File:** `/Users/matt/summer/autoroad/components/course-graph/CourseEdges.tsx`

Add to the `<path>` element rendering:
```typescript
className="transition-opacity hover:opacity-100"
// Add hover state handling
```

---

### Task 5: Modify Node Styling
**File:** `/Users/matt/summer/autoroad/lib/nodeStyles.ts`

The `getNodeStyle()` function handles all node styling based on:
- `section` (which column)
- `userControlled` (user-added vs system)
- `disabled` (red styling)
- `isSpecial` (special section styling)

---

## Data Structure Reference

### Edge (Prerequisite Relationship)
```typescript
interface Edge {
  from_id: string;  // Source course node ID (e.g., "1")
  to_id: string;    // Target course node ID (e.g., "2")
}
// Means: from_id is a prerequisite for to_id
```

### CourseNode
```typescript
interface CourseNode {
  id: string;                    // Unique instance ID
  courseId: string;              // Course code (e.g., "6.1200")
  section: number;               // Column ID
  userControlled?: boolean;      // User-added node
  disabled?: boolean;            // Cannot take
  nodeStatus?: 'pin' | 'banish'; // User preference
  offeredFall?: boolean;         // Term availability
  offeredSpring?: boolean;
  offeredIAP?: boolean;
}
```

### Section
```typescript
interface Section {
  id: number;      // -2 (Must Take), -1 (ASEs), 0+ (Semesters)
  title: string;   // Display name
}
```

---

## Color Palette Reference

### Edge Colors
| Usage | Hex | RGB | Context |
|-------|-----|-----|---------|
| Close edges (≤ 300px) | `#9ca3af` | rgb(156, 163, 175) | Adjacent columns |
| Long edges (> 300px) | `#d1d5db` | rgb(209, 213, 219) | Distant columns |

### Node Background Colors
| Node Type | Tailwind Class | Usage |
|-----------|---|---|
| Must Take | `bg-purple-950/40` | Required courses |
| User-added | `bg-card` | User input |
| ASEs | `bg-gray-50 dark:bg-gray-900/40` | Electives |
| Disabled | `bg-red-50 dark:bg-red-950/20` | Cannot take |

### Glow Effects (Box Shadow)
| Node Type | Shadow |
|-----------|--------|
| Must Take | `0 0 20px rgba(168, 85, 247, 0.6), 0 0 40px rgba(168, 85, 247, 0.3)` |
| User-controlled | `0 0 20px rgba(59, 130, 246, 0.5), 0 0 40px rgba(59, 130, 246, 0.3)` |

---

## Architecture Decision: SVG vs ReactFlow

### When to Use SVG (CourseEdges.tsx)
- ✓ Full rendering control
- ✓ Custom curves and paths
- ✓ Simple prerequisite visualization
- ✗ No built-in interactivity
- ✗ Manual scroll/resize handling

### When to Use ReactFlow (CourseGraphFlow.tsx)
- ✓ Interactive features
- ✓ Pan/zoom built-in
- ✓ Automatic viewport handling
- ✗ Less customization
- ✗ Heavier bundle

**Current Implementation:** Both are available, CourseGraphFlow is the primary.

---

## State Management Flow

```
User Action
    ↓
useGraphStore.[addNode|removeNode|updateNodeLocal]()
    ↓
Zustand Store State Updated
    ↓
React Re-render
    ├─ CourseGraphFlow: Convert to ReactFlow format
    └─ CourseGraph: Render CSS grid + SVG overlay
    ↓
localStorage.save() (automatic)
```

---

## Testing Checklist

Before deploying changes to edge rendering or positioning:

- [ ] Edge colors correct for close edges (≤ 300px)
- [ ] Edge colors correct for long edges (> 300px)
- [ ] Edges dashed for long distance, solid for close
- [ ] Edges don't overlap nodes (20px offset)
- [ ] Edge curves smooth (Bezier control points correct)
- [ ] Nodes positioned correctly in columns (x = sectionIndex * 200 + 100)
- [ ] Nodes spaced correctly vertically (120px gap)
- [ ] Scroll/pan updates edges correctly
- [ ] Resize updates edges correctly
- [ ] Drag-and-drop repositions nodes and edges
- [ ] Term highlighting displays correctly
- [ ] "Must Take" column edges filtered out
- [ ] Node styling applies correctly (colors, shadows, glows)
- [ ] Works in both light and dark themes
- [ ] Performance acceptable with 50+ nodes
- [ ] No console errors or warnings

---

## Performance Optimization Tips

### Current Optimizations
- ResizeObserver for layout change detection
- Memoized node positions in ReactFlow
- localStorage for persistence
- Vuew culling in ReactFlow

### Potential Improvements
- Virtualization for large graphs (100+ nodes)
- Canvas rendering instead of SVG for very dense graphs
- Web Workers for position calculations
- Lazy edge loading
- Path caching

---

## Troubleshooting

### Edges not rendering
1. Check that nodes have `data-node-circle` attribute
2. Verify edges are in store with correct from_id/to_id
3. Check if edge is filtered (Must Take column)
4. Check console for errors

### Edges rendering incorrectly
1. Check CIRCLE_RADIUS offset (should be 20)
2. Verify Bezier control point multiplier (should be 0.3)
3. Check scrollLeft/scrollTop calculations
4. Ensure containerRef is valid

### Nodes in wrong positions
1. Check COLUMN_WIDTH (should be 200 for ReactFlow)
2. Check NODE_SPACING (should be 120)
3. Verify section IDs are correct
4. Check allSections array order

### Nodes not styled correctly
1. Check section ID in node data
2. Verify getNodeStyle() conditions
3. Check Tailwind theme configuration
4. Verify dark mode CSS variables

---

## Future Roadmap

### Short Term (Next Sprint)
- [ ] Add optional/required prerequisite differentiation
- [ ] Add co-requisite indicators
- [ ] Implement prerequisite satisfaction status visualization

### Medium Term (Next Quarter)
- [ ] Topological sorting of nodes
- [ ] Automatic layout algorithms
- [ ] Edge bundling for dense graphs
- [ ] Advanced filtering and search

### Long Term
- [ ] 3D visualization option
- [ ] Collaborative editing
- [ ] Advanced constraint solver integration
- [ ] Custom theme support

---

## External Dependencies

### Rendering
- **ReactFlow** - Interactive graph visualization
- **SVG** - Native browser rendering (no library needed)
- **Tailwind CSS** - Styling

### State Management
- **Zustand** - Lightweight state management

### Data
- **localStorage API** - Persistence
- **Custom API** - Backend optimization

---

## Related Documentation

- `/Users/matt/summer/autoroad/CODEBASE_ANALYSIS.md` - Detailed technical analysis
- `/Users/matt/summer/autoroad/EDGE_COLORING_EXAMPLES.md` - Code examples
- `/Users/matt/summer/autoroad/CODE_LOCATIONS_QUICK_REFERENCE.md` - Quick lookup
- `/Users/matt/summer/autoroad/VISUAL_GUIDE.md` - Architecture diagrams

---

## Questions & Support

For questions about specific implementations:

1. Check CODEBASE_ANALYSIS.md for comprehensive overview
2. Check CODE_LOCATIONS_QUICK_REFERENCE.md for quick lookup
3. Review EDGE_COLORING_EXAMPLES.md for implementation details
4. Consult VISUAL_GUIDE.md for architecture diagrams
5. Check comments in source code files

---

## Summary

The Autoroad graph visualization system consists of:

1. **Data Layer** - Zustand store with nodes, edges, sections
2. **Position Layer** - Column-based grid with vertical spacing
3. **Rendering Layer** - SVG overlay or ReactFlow framework
4. **Styling Layer** - Distance-based edge colors, node styling, term highlighting
5. **Interaction Layer** - Drag-drop, hover, context menus

Key characteristics:
- Distance-based edge coloring (300px threshold)
- SVG Bezier curves for smooth prerequisite lines
- Column-based layout (200px per column)
- Term availability visualization (border patterns)
- Two rendering backends (SVG, ReactFlow)
- Responsive to scroll and resize events

All code is self-contained within the `/components/course-graph/` directory with utility functions in `/lib/`.

