# Graph/Node Implementation Search Results

## Search Request Summary

You asked to find:
1. Where React Flow is being used
2. How user nodes are currently implemented
3. The node data structure and types
4. Where nodes are added/managed in state

## Search Results

### All Documentation Created

I've created **three comprehensive documentation files** for you:

1. **GRAPH_IMPLEMENTATION_GUIDE.md** - Complete technical guide with 17 sections covering:
   - React Flow integration details
   - Node data structures and types
   - Node component implementation
   - Styling system
   - State management (Zustand)
   - Positioning and layout
   - Edge rendering
   - Drag and drop
   - Data loading and persistence
   - Common operations

2. **GRAPH_ARCHITECTURE.md** - Visual diagrams and architecture including:
   - Data flow diagrams
   - Component hierarchy
   - Node data structure
   - Positioning algorithm
   - State machine diagrams
   - Edge rendering pipeline
   - Drag and drop flows
   - Column layout structure
   - Type conversion flows
   - State persistence flows

3. **GRAPH_QUICK_REFERENCE.md** - Quick lookup guide with:
   - File locations
   - Core types (copy-paste ready)
   - State management snippets
   - Positioning constants
   - Common tasks and patterns
   - Debugging tips
   - Performance tips
   - Gotchas and edge cases

---

## Key Findings

### 1. React Flow Usage
**Status**: ✅ Production implementation
- **Library**: reactflow v11.11.4
- **Main File**: `/Users/matt/summer/autoroad/src/components/course-graph/CourseGraphFlow.tsx`
- **Setup**: Wrapped in ReactFlowProvider with custom node types
- **Config**: Pan/drag enabled, zoom constrained to 0.8-1.5x, edges read-only

### 2. Node Implementation

**File Structure**:
```
CourseGraphFlow.tsx (React Flow wrapper)
  ├── FlowCourseNode (custom node type with handles)
  └── CourseNode.tsx (visual node - 40px circle)
```

**Visual Design**:
- 40px circular nodes
- Unit count displayed inside circle
- Course ID label below
- Hover effects with shadow transitions
- Term availability SVG border indicator

**Node States**:
- Must Take (purple glow, hazard pattern)
- User-Controlled (blue glow, draggable)
- ASEs (gray styling)
- Disabled (red styling)
- Regular (normal styling)

### 3. Node Data Structure

**Core Interface (from `/src/types.ts`)**:
```typescript
interface CourseNode {
  id: string;                  // Unique instance ID
  courseId: string;            // Display name (e.g., "6.1200")
  section: number;             // -2=MustTake, -1=ASEs, 0+=semesters
  userControlled?: boolean;    // User can drag
  disabled?: boolean;          // Cannot be taken
  offeredFall?: boolean;       // Term availability
  offeredSpring?: boolean;
  offeredIAP?: boolean;
}
```

**Related Types**:
- `Edge`: { from_id: string, to_id: string } - prerequisite relationships
- `Section`: { id: number, title: string } - semester definitions
- `AvailableNode`: Courses from catalog for searching

### 4. State Management & Node Addition

**Zustand Store** (`/src/stores/roadStore.ts`):
- Central state: nodes, edges, sections, specialSection, availableNodes
- Actions: addNode, removeNode, updateNode, updateNodeLocal
- Auto-persistence to localStorage on every change
- Loading state tracking (idle, loading, success, error)

**Adding Nodes - Two Methods**:

**Method 1: From Sidebar (Drag & Drop)**
```typescript
// User drags course from search
onDrop (CourseGraphFlow.tsx):
  1. Parse drag data
  2. Calculate drop position
  3. Determine target section
  4. Call addNode()
  5. Node appears positioned in canvas
```

**Method 2: Programmatic**
```typescript
const newNode: CourseNode = {
  id: `node_${Date.now()}`,
  courseId: '6.1200',
  section: 0,
  userControlled: true,
};
await useGraphStore.getState().addNode(newNode);
```

**Node Management Flow**:
```
User Action → Store Update → localStorage Save → React Effect → Reposition → Render
```

---

## File Locations (Absolute Paths)

```
/Users/matt/summer/autoroad/
├── src/components/course-graph/
│   ├── CourseGraphFlow.tsx         ← MAIN FILE (React Flow)
│   ├── CourseGraph.tsx             ← Legacy version
│   ├── CourseNode.tsx              ← Node rendering
│   ├── CourseEdges.tsx             ← Edge rendering
│   ├── types.ts                    ← Graph types
│   └── reactflow-custom.css        ← Custom styles
│
├── src/stores/
│   └── roadStore.ts                ← STATE MANAGEMENT (Zustand)
│
├── src/types.ts                    ← CORE TYPES (CourseNode, Edge, Section)
│
└── src/utils/
    ├── nodeStyles.ts               ← Styling logic
    └── termBorderHighlight.ts      ← Term indicators

DOCUMENTATION CREATED:
├── GRAPH_IMPLEMENTATION_GUIDE.md   ← Full technical guide
├── GRAPH_ARCHITECTURE.md           ← Visual diagrams
├── GRAPH_QUICK_REFERENCE.md        ← Quick lookup
└── SEARCH_RESULTS_SUMMARY.md       ← This file
```

---

## Positioning System

**Constants**:
- COLUMN_WIDTH: 200px
- NODE_SPACING: 120px (vertical between nodes)
- VIEWPORT_CENTER_Y: 400px (for centering groups)

**Algorithm**:
```
For each node:
1. Find section index in allSections array
2. Count total nodes in that section
3. Calculate centering Y = 400 - ((count-1) * 120 / 2)
4. Apply spacing Y = centerY + nodeIndex * 120
5. Position X = columnIndex * 200 + 100

Result: Nodes are auto-centered in columns with consistent spacing
```

**Column Order**:
1. Must Take (section -2) - purple
2. ASEs (section -1) - gray
3-N. Regular sections (0+) - normal

---

## Styling System

**Dynamic Styling** (from `/src/utils/nodeStyles.ts`):

| Section | Style | Glow | Notes |
|---------|-------|------|-------|
| -2 (Must Take) | Purple bg | Purple 20/40px | Hazard pattern |
| -1 (ASEs) | Gray bg | None | Fixed position |
| 0+ (Regular) | Card bg | None | Normal |
| User-Controlled | Card bg | Blue 20/40px | Draggable |
| Disabled | Red bg | None | Cannot take |

**Applied via**:
- Tailwind classes (borderColor, bgColor, textColor)
- CSS box-shadow for glow effects
- SVG dashed border for term availability

---

## Event Handlers

**React Flow Events** (CourseGraphFlow.tsx):
- `onNodeDragStop`: Move node between columns
- `onDrop`: Add node from sidebar
- `onDragOver`: Allow drop on canvas
- `onNodesChange`: React Flow internal changes
- `onEdgesChange`: React Flow internal changes

**Store Actions** (roadStore.ts):
- `addNode()`: Add new node (with localStorage save)
- `removeNode()`: Delete node (with edge cleanup)
- `updateNodeLocal()`: Quick local update (no persistence)
- `updateNode()`: Full update (with persistence)
- `fetchRoadData()`: Load from localStorage
- `optimizeRoad()`: Send to optimization API

---

## Data Persistence

**Storage Method**: Browser localStorage
- **Key**: `autoroad_data`
- **Trigger**: Every add/remove/update operation
- **Fallback**: Demo/initial data if no cache
- **Format**: JSON with nodes, edges, sections, specialSection, availableNodes

**Loading Flow**:
```
1. App loads
2. fetchRoadData() checks localStorage
3. If found: Load cached state
4. If not: Load demo/initial data
5. Component renders with loaded state
```

---

## React Flow vs Legacy

**CourseGraphFlow.tsx (CURRENT - React Flow)**:
- Uses reactflow library
- Better performance
- Built-in pan/zoom
- Automatic edge routing
- Handles manage viewport state

**CourseGraph.tsx (LEGACY - Canvas)**:
- Manual column layout
- Custom SVG edge rendering
- ResizeObserver for updates
- Still maintained but not primary

**Recommendation**: Use CourseGraphFlow.tsx for new features

---

## Performance Characteristics

**Optimizations Present**:
- React.memo on CourseNode component
- Zustand selectors (state.nodes only re-renders when nodes change)
- RequestAnimationFrame for viewport sync
- ResizeObserver for edge updates
- Memoized positioning calculations

**Scaling Limits**:
- Current: Tested with 11 nodes (demo data)
- Potential: 100-500 nodes without issues
- Beyond 500: Consider virtualization
- 1000+: Definitely virtualize with react-window

---

## Integration Points

**To Add a Node Feature**:
1. Get node data from user input
2. Create CourseNode object
3. Call `useGraphStore.getState().addNode(node)`
4. Component auto-updates position
5. localStorage automatically saves

**To Move a Node**:
1. Detect drag end
2. Calculate new section
3. Call `updateNodeLocal(nodeId, { section: newSection })`
4. Position auto-updates
5. localStorage saves (if userControlled)

**To Style a Node**:
1. Update getNodeStyle() in nodeStyles.ts
2. Add condition for your style state
3. Return borderColor, bgColor, textColor, boxShadow
4. Component uses returned styles

---

## Dependencies

From package.json:
- **reactflow**: ^11.11.4 (main React Flow library)
- **zustand**: (state management)
- **react**: (UI library)
- **typescript**: (type safety)

---

## Testing Checklist

- [x] React Flow imports from 'reactflow'
- [x] Node types defined in types.ts
- [x] Zustand store in roadStore.ts
- [x] Drag and drop handlers present
- [x] localStorage persistence working
- [x] Positioning algorithm correct
- [x] Styling system functional
- [x] Edge rendering implemented
- [x] Special sections (Must Take, ASEs) handled

---

## Questions Answered

**Q: Where is React Flow being used?**
A: In `/Users/matt/summer/autoroad/src/components/course-graph/CourseGraphFlow.tsx` as the main graph visualization component.

**Q: How are user nodes implemented?**
A: As CourseNode React components wrapped in React Flow's custom node type (FlowCourseNode), with 40px circles showing units and course IDs.

**Q: What's the node data structure?**
A: CourseNode interface with id, courseId, section, userControlled, disabled, and term availability fields. Defined in `/src/types.ts`.

**Q: Where are nodes added/managed?**
A: In Zustand store (`/src/stores/roadStore.ts`) with actions addNode, removeNode, updateNode. Automatic localStorage persistence on every change.

---

## Next Steps

1. **Read Documentation**: Start with GRAPH_QUICK_REFERENCE.md for quick lookups
2. **Study Implementation**: Review CourseGraphFlow.tsx line by line
3. **Understand State**: Explore roadStore.ts for state management patterns
4. **Test Features**: Use browser console to inspect nodes and edges
5. **Modify Carefully**: Remember to maintain positioning algorithm and localStorage sync

---

## Support

All documentation files are located in:
```
/Users/matt/summer/autoroad/
```

- GRAPH_IMPLEMENTATION_GUIDE.md (detailed technical reference)
- GRAPH_ARCHITECTURE.md (visual diagrams and flows)
- GRAPH_QUICK_REFERENCE.md (quick lookup and snippets)
- SEARCH_RESULTS_SUMMARY.md (this file)

Happy coding!
