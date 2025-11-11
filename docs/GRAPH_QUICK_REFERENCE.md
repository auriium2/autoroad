# Graph Implementation Quick Reference

## File Locations

```
src/
├── components/course-graph/
│   ├── CourseGraphFlow.tsx          ← MAIN React Flow implementation
│   ├── CourseGraph.tsx              ← Legacy canvas-based version
│   ├── CourseNode.tsx               ← Individual node component
│   ├── CourseNodeHoverCard.tsx      ← Hover tooltip
│   ├── CourseEdges.tsx              ← Edge rendering
│   ├── ColumnContextMenu.tsx        ← Right-click menu
│   ├── types.ts                     ← Graph-specific types
│   ├── index.ts                     ← Exports
│   └── reactflow-custom.css         ← Custom styles
│
├── stores/
│   ├── roadStore.ts                 ← Zustand state (NODES, EDGES, SECTIONS)
│   └── index.ts                     ← Store exports
│
├── types.ts                         ← Global type definitions (CourseNode, Edge, Section)
│
└── utils/
    ├── nodeStyles.ts                ← Node styling logic
    └── termBorderHighlight.ts       ← Term availability indicators
```

---

## Core Types

### CourseNode (stored in Zustand)
```typescript
interface CourseNode {
  id: string;              // Unique instance ID
  courseId: string;        // Display name (e.g., "6.1200")
  section: number;         // -2=MustTake, -1=ASEs, 0+=semesters
  userControlled?: boolean;// User can drag
  disabled?: boolean;      // Cannot be taken
  offeredFall?: boolean;   // Term availability
  offeredSpring?: boolean;
  offeredIAP?: boolean;
}
```

### Edge
```typescript
interface Edge {
  from_id: string;  // Source node ID
  to_id: string;    // Target node ID
}
```

### Section
```typescript
interface Section {
  id: number;       // -2=MustTake, -1=ASEs, 0+=semesters
  title: string;    // Display name
}
```

---

## State Management (Zustand)

### Access Store
```typescript
import { useGraphStore } from '@/stores/roadStore';

// In component
const nodes = useGraphStore(state => state.nodes);
const edges = useGraphStore(state => state.edges);
```

### Add Node
```typescript
const newNode: CourseNode = {
  id: `node_${Date.now()}`,
  courseId: '6.1200',
  section: 0,
  userControlled: true,
};
await useGraphStore.getState().addNode(newNode);
```

### Update Node
```typescript
// Local only (no persistence)
useGraphStore.getState().updateNodeLocal(nodeId, { section: 1 });

// Full update with persistence
await useGraphStore.getState().updateNode(nodeId, { disabled: true });
```

### Remove Node
```typescript
await useGraphStore.getState().removeNode(nodeId);
```

### Load/Save
```typescript
// Load from localStorage/API
await useGraphStore.getState().fetchRoadData();

// Manual save to localStorage
await useGraphStore.getState().saveRoadData();
```

---

## Positioning Constants

```typescript
const COLUMN_WIDTH = 200;        // Width of each section column
const NODE_SPACING = 120;        // Vertical spacing between nodes
const VIEWPORT_CENTER_Y = 400;   // Center Y for centering node groups
const NODE_RADIUS = 20;          // Node circle radius (40px total)
```

### Position Formula
```typescript
// For a node in section at sectionIndex:
x = sectionIndex * COLUMN_WIDTH + (COLUMN_WIDTH / 2)    // 100, 300, 500...

// For node at nodeIndexInSection in a section with N total nodes:
totalHeight = (N - 1) * NODE_SPACING
startY = VIEWPORT_CENTER_Y - (totalHeight / 2)
y = startY + nodeIndexInSection * NODE_SPACING
```

---

## React Flow Node Types

### FlowCourseNode (Wrapper)
- Adds React Flow Handles (target left, source right)
- Wraps CourseNode component
- Transparent, borderless handles
- Auto-positioned at node edges

### CourseNode (Visual)
- 40px circle with unit count
- Course ID label below
- Hover effects
- Styling based on state

---

## Node Styling States

| State | Colors | Glow | Notes |
|-------|--------|------|-------|
| **Must Take** (section -2) | Purple bg | Purple | Hazard pattern |
| **User-Controlled** | Card bg | Blue | Draggable |
| **ASEs** (section -1) | Gray bg | None | Fixed |
| **Disabled** | Red bg | None | Cannot take |
| **Regular** | Card bg | None | Normal |

---

## Drag & Drop

### Drag from Sidebar
```typescript
// In CourseSearchTab.tsx
onDragStart: (e) => {
  e.dataTransfer.setData('application/json', JSON.stringify(nodeData));
}

// In CourseGraphFlow.tsx
onDrop: (e) => {
  const nodeData = JSON.parse(e.dataTransfer.getData('application/json'));
  const position = screenToFlowPosition({ x: e.clientX, y: e.clientY });
  const sectionId = determineSection(position.x);
  addNode({ ...nodeData, section: sectionId });
}
```

### Drag Within Canvas
```typescript
// In CourseGraphFlow.tsx
onNodeDragStop: (event, node) => {
  const newSectionId = determineSection(node.position.x);
  if (newSectionId !== node.data.section) {
    updateNodeLocal(node.id, { section: newSectionId });
  }
}
```

---

## Edge Rendering

### Short Distance (Adjacent Columns)
- Solid line
- strokeWidth: 2
- opacity: 0.6-0.7
- Color: `rgba(156, 163, 175, 0.7)`

### Long Distance (>1 Column)
- Dashed line (5px dash, 5px gap)
- strokeWidth: 1.5
- opacity: 0.4
- Color: `rgba(209, 213, 219, 0.4)`

### Filtered
- Edges from/to "Must Take" (section -2) are hidden

---

## Common Tasks

### Find Node by ID
```typescript
const node = useGraphStore.getState().nodes.find(n => n.id === nodeId);
```

### Find Nodes in Section
```typescript
const sectionNodes = useGraphStore.getState().nodes.filter(n => n.section === sectionId);
```

### Get Section Title
```typescript
const section = useGraphStore.getState().sections.find(s => s.id === sectionId);
const title = section?.title || 'Unknown';
```

### Check if Node is User-Added
```typescript
const isUserAdded = node.userControlled === true;
```

### Get All Prerequisite Edges
```typescript
const prereqs = useGraphStore.getState().edges.filter(e => e.to_id === nodeId);
```

### Get All Dependent Edges
```typescript
const dependents = useGraphStore.getState().edges.filter(e => e.from_id === nodeId);
```

---

## localStorage Format

```typescript
// Key: 'autoroad_data'
// Value:
{
  nodes: CourseNode[],
  edges: Edge[],
  sections: Section[],
  specialSection: Section | null,
  availableNodes: AvailableNode[]
}

// Access in browser console:
JSON.parse(localStorage.getItem('autoroad_data'))
```

---

## ReactFlow Configuration

```typescript
<ReactFlow
  nodes={nodes}                          // React Flow Node[]
  edges={edges}                          // React Flow Edge[]
  nodeTypes={{ courseNode: FlowCourseNode }}
  onNodeDragStop={onNodeDragStop}       // Move node between columns
  onDrop={onDrop}                       // Add new node from sidebar
  onDragOver={onDragOver}               // Allow drop
  nodesDraggable={true}                 // Enable dragging
  nodesConnectable={false}              // Edges are read-only
  elementsSelectable={true}             // Can select nodes
  zoomOnScroll={false}                  // Disable zoom with scroll
  panOnScroll={true}                    // Pan with scroll
  panOnDrag={true}                      // Pan with middle-click drag
  minZoom={0.8}                         // Minimum zoom level
  maxZoom={1.5}                         // Maximum zoom level
  defaultViewport={{ x: 0, y: 20, zoom: 1 }}
  proOptions={{ hideAttribution: true }}
>
  <Background variant={BackgroundVariant.Dots} gap={20} size={1} />
</ReactFlow>
```

---

## Special Sections

### Must Take Column (section: -2)
- First column
- Purple striped background (45° diagonal)
- Purple text color
- Purple glow effect
- Edges to/from this column are hidden
- Used for required courses that don't need positioning

### ASEs Column (section: -1)
- Second column
- Gray background
- Gray text color
- No glow effect
- Used for Additional Subjects for Electives

### Regular Sections (section: 0+)
- Normal styling
- Transparent background
- Positioned based on array index

---

## Debugging

### Check All Nodes
```typescript
console.log(useGraphStore.getState().nodes);
```

### Check All Edges
```typescript
console.log(useGraphStore.getState().edges);
```

### Check All Sections
```typescript
console.log(useGraphStore.getState().sections);
```

### Check Node Position (React Flow)
```typescript
// In React component
const nodes = useNodesState(...)[0];
const node = nodes.find(n => n.id === nodeId);
console.log(node.position);  // { x: 300, y: 400 }
```

### Monitor Store Changes
```typescript
useGraphStore.subscribe((state) => {
  console.log('Store updated:', {
    nodeCount: state.nodes.length,
    edgeCount: state.edges.length,
  });
});
```

### Check localStorage
```typescript
// Browser console
const data = JSON.parse(localStorage.getItem('autoroad_data'));
console.log('Nodes:', data.nodes.length);
console.log('Edges:', data.edges.length);
```

---

## Performance Tips

1. **Use Selectors**: `useGraphStore(state => state.nodes)` (not full state)
2. **Memoize Components**: CourseNode is React.memo'd
3. **RequestAnimationFrame**: Column headers use RAF for smooth scrolling
4. **ResizeObserver**: Edge paths update on resize
5. **Avoid**: Don't virtualize nodes unless 1000+ nodes

---

## Common Patterns

### Get Node with Course Details
```typescript
const node = useGraphStore.getState().nodes.find(n => n.id === nodeId);
const courseDetails = await fetchCourseDetails(node.courseId);
```

### Update Multiple Nodes
```typescript
nodeIds.forEach(id => {
  updateNodeLocal(id, { disabled: true });
});
```

### Bulk Add Nodes
```typescript
const newNodes = courseIds.map((id, idx) => ({
  id: `node_${id}_${idx}`,
  courseId: id,
  section: 0,
}));

newNodes.forEach(node => addNode(node));
```

### Move Node to Section
```typescript
const nodeId = 'some_node_id';
const newSectionId = 2;  // Sophomore Fall
updateNodeLocal(nodeId, { section: newSectionId });
```

---

## Gotchas

1. **Node ID vs Course ID**: `id` is unique instance, `courseId` is display name
2. **Section Numbering**: -2=MustTake, -1=ASEs, 0+=Semesters
3. **Must Take Edges Hidden**: Edges involving section -2 don't render
4. **Positions Auto-Calculate**: Don't manually set node positions
5. **localStorage Used**: No API calls for persistence (yet)
6. **Memoization Important**: React.useCallback dependencies matter
7. **Column Width Fixed**: 200px, adjust COLUMN_WIDTH constant if needed
8. **Special Sections First**: allSections array has [-2, -1, ...sections]

---

## Version Info

- **React Flow**: v11.11.4
- **Zustand**: (check package.json)
- **React**: (check package.json)
- **TypeScript**: Yes

---

## Related Files

- **Styling**: `/src/utils/nodeStyles.ts` - getNodeStyle()
- **Styling**: `/src/utils/termBorderHighlight.ts` - term availability
- **API**: `/src/services/api.ts` - localStorage.save/load
- **Types**: `/src/types.ts` - Global type definitions
- **Hooks**: `/src/hooks/useCourseData.ts` - Fetch course details

---

## Next Steps for Development

1. Review `CourseGraphFlow.tsx` for React Flow setup
2. Check `roadStore.ts` for state management
3. Look at `CourseNode.tsx` for node rendering
4. Study positioning algorithm in CourseGraphFlow.tsx (lines ~400-440)
5. Understand drag handlers (lines ~290-360)
6. Test with browser localStorage inspection

Good luck with your development!
