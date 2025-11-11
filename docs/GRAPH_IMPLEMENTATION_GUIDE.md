# React Flow Graph Implementation Guide

## Overview
This document describes the React Flow graph/node implementation in the Autoroad codebase, including where nodes are used, how they're structured, and how they're managed in state.

---

## 1. React Flow Integration

### Package Information
- **Library**: `reactflow` v11.11.4
- **Status**: Production implementation
- **CSS**: Custom styles in `/src/components/course-graph/reactflow-custom.css`

### Main Implementation File
**Location**: `/Users/matt/summer/autoroad/src/components/course-graph/CourseGraphFlow.tsx`

This is the primary React Flow implementation with:
- ReactFlowProvider wrapper
- Custom node types and positioning
- Column headers and dividers synced with viewport
- Drag-and-drop functionality for adding nodes
- Edge rendering with bezier curves

---

## 2. Node Data Structure and Types

### Core CourseNode Interface
**Location**: `/Users/matt/summer/autoroad/src/types.ts`

```typescript
export interface CourseNode {
  id: string;                 // Unique node instance identifier (e.g., "0", "1", "6.1200_1734567890")
  courseId: string;           // Course subject ID (e.g., "6.1200", "18.01")
  section: number;            // Which semester/column this belongs to
  userControlled?: boolean;   // If true, user added/can drag this node
  disabled?: boolean;         // If true, node is disabled and cannot be taken
  offeredFall?: boolean;      // Term availability (fetched from course details)
  offeredSpring?: boolean;
  offeredIAP?: boolean;
}
```

### Related Types

**Edge Interface** (prerequisite relationship):
```typescript
export interface Edge {
  from_id: string;
  to_id: string;
}
```

**Section Interface** (semester or special section):
```typescript
export interface Section {
  id: number;
  title: string;
}
```

**Special Sections**:
- **ASEs** (id: -1) - lighter grey background
- **Must Take** (id: -2) - purple hazard overlay
- Regular sections (id: 0+) - numbered semesters

**Available Nodes** (courses from catalog):
```typescript
export interface AvailableNode {
  courseId: string;    // Course subject ID
  title: string;       // Course title
  department: string;  // Department code
  units: number;       // Credit units
}
```

---

## 3. Node Component Implementation

### Flow Node Wrapper
**Location**: `CourseGraphFlow.tsx` (lines ~30-50)

The custom `FlowCourseNode` component wraps the actual course node with React Flow handles:

```typescript
function FlowCourseNode({ data }: { data: CourseNodeType & { ... } }) {
  return (
    <div style={{ position: 'relative', transform: 'translate(-50%, 0)' }}>
      {/* Handles at edges of the circle */}
      <Handle
        type="target"
        position={Position.Left}
        style={{ background: 'transparent', border: 'none', ... }}
      />
      <Handle
        type="source"
        position={Position.Right}
        style={{ background: 'transparent', border: 'none', ... }}
      />
      <CourseNodeComponent node={data} ... />
    </div>
  );
}

const nodeTypes: NodeTypes = {
  courseNode: FlowCourseNode,
};
```

### Course Node Component
**Location**: `/Users/matt/summer/autoroad/src/components/course-graph/CourseNode.tsx`

Renders the actual visual node (circle with unit count and course ID):

```typescript
interface NodeProps {
  node: CourseNode;
  isSpecial?: boolean;
  isHovered?: boolean;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
}
```

**Features**:
- 40px circular node showing unit count
- Course ID label below
- Hover effects with shadow transitions
- Term availability indicators (SVG dashed border)
- Styling based on node state (user-controlled, disabled, special, etc.)

---

## 4. Node Styling System

### Style Configuration
**Location**: `/Users/matt/summer/autoroad/src/utils/nodeStyles.ts`

```typescript
export interface NodeStyleConfig {
  borderColor: string;
  bgColor: string;
  textColor: string;
  boxShadow: string;
}

export function getNodeStyle(node: NodeStyleProperties): NodeStyleConfig
```

### Node Style States

| State | Color | Glow | Notes |
|-------|-------|------|-------|
| **Must Take** (section -2) | Purple background | Purple glow | Hazard overlay pattern |
| **User-Controlled** | Card background | Blue glow | Draggable by user |
| **ASEs** (section -1) | Gray background | None | White/gray styling |
| **Disabled** | Red background | None | Cannot be taken |
| **Regular** | Card background | None | Standard nodes |

---

## 5. Node Management and State

### Zustand Store
**Location**: `/Users/matt/summer/autoroad/src/stores/roadStore.ts`

Central state management for all nodes:

```typescript
interface GraphStore {
  // Data
  nodes: CourseNode[];
  edges: Edge[];
  sections: Section[];
  specialSection: Section | null;
  availableNodes: AvailableNode[];
  
  // Loading states
  loadingState: LoadingState;
  error: string | null;
  isSaving: boolean;
  hasChangesSinceOptimization: boolean;
  userId: string | null;
  
  // Node actions
  addNode: (node: CourseNode) => Promise<void>;
  removeNode: (id: string) => Promise<void>;
  updateNode: (id: string, updates: Partial<CourseNode>) => Promise<void>;
  updateNodeLocal: (id: string, updates: Partial<CourseNode>) => void;
  
  // Data loading
  fetchRoadData: () => Promise<void>;
  saveRoadData: () => Promise<void>;
  optimizeRoad: (constraints?: {...}) => Promise<{...}>;
  loadInitialData: () => void;
}
```

### Key State Actions

#### Add Node
```typescript
addNode: async (node: CourseNode) => {
  // Optimistically updates state
  // Saves to localStorage
  // Marks changes if user-controlled
}
```

#### Remove Node
```typescript
removeNode: async (id: string) => {
  // Removes node and associated edges
  // Saves to localStorage
}
```

#### Update Node Local (No API call)
```typescript
updateNodeLocal: (id: string, updates: Partial<CourseNode>) => {
  // Updates only local state
  // Used for drag operations and section changes
  // Marks changes if section is updated and node is user-controlled
}
```

#### Update Node (Full update with persistence)
```typescript
updateNode: async (id: string, updates: Partial<CourseNode>) => {
  // Updates state
  // Saves to localStorage
}
```

---

## 6. Positioning and Layout System

### Column-Based Layout
**Location**: `CourseGraphFlow.tsx` (lines ~400-440)

```typescript
const COLUMN_WIDTH = 200;
const NODE_SPACING = 120;
const VIEWPORT_CENTER_Y = 400;

// Nodes positioned at:
// x: columnIndex * COLUMN_WIDTH + (COLUMN_WIDTH / 2)
// y: startY + nodeIndexInSection * NODE_SPACING
```

### Automatic Positioning Logic

1. **Section Index**: Find section in `allSections` array
2. **Nodes in Section**: Count how many nodes are in that section
3. **Total Height**: Calculate `(nodeCount - 1) * NODE_SPACING`
4. **Centering**: Position to center the group vertically
5. **Y Offset**: Apply `nodeIndexInSection * NODE_SPACING`

### Special Sections Included First
```typescript
const allSections: Section[] = React.useMemo(() => {
  const mustTakeSection: Section = { id: -2, title: 'Must Take' };
  const asesSection: Section = { id: -1, title: 'ASEs' };
  return [mustTakeSection, asesSection, ...sections];
}, [sections]);
```

---

## 7. Node Conversion to React Flow Format

**Location**: `CourseGraphFlow.tsx` (lines ~180-220)

Store nodes are converted to React Flow nodes with positioning:

```typescript
React.useEffect(() => {
  const flowNodes: Node[] = storeNodes.map((node, index) => {
    const sectionIndex = allSections.findIndex(s => s.id === node.section);
    const nodesInSection = storeNodes.filter(n => n.section === node.section);
    const nodeIndexInSection = nodesInSection.findIndex(n => n.id === node.id);
    
    const totalNodesHeight = (nodesInSection.length - 1) * NODE_SPACING;
    const startY = VIEWPORT_CENTER_Y - (totalNodesHeight / 2);

    return {
      id: node.id,
      type: 'courseNode',
      position: {
        x: sectionIndex * COLUMN_WIDTH + (COLUMN_WIDTH / 2),
        y: startY + nodeIndexInSection * NODE_SPACING,
      },
      data: { ...node, onMouseEnter: () => {}, onMouseLeave: () => {} },
      draggable: node.userControlled || false,
    };
  });

  setNodes(flowNodes);
}, [storeNodes, allSections, setNodes]);
```

---

## 8. Edge Rendering

### Edge Data Structure
Edges are converted from store format to React Flow edges:

```typescript
React.useEffect(() => {
  const flowEdges: FlowEdge[] = storeEdges.map((edge) => {
    const fromNode = storeNodes.find(n => n.id === edge.from_id);
    const toNode = storeNodes.find(n => n.id === edge.to_id);

    // Skip edges involving Must Take column (section -2)
    if (fromNode?.section === -2 || toNode?.section === -2) {
      return null;
    }

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
      markerEnd: { type: MarkerType.ArrowClosed, ... },
    };
  });

  setEdges(flowEdges);
}, [storeEdges, storeNodes, allSections, setEdges]);
```

**Edge Styling**:
- **Short distance** (adjacent columns): Solid line, opacity 0.7, strokeWidth 2
- **Long distance** (>1 column): Dashed line, opacity 0.4, strokeWidth 1.5

---

## 9. Drag and Drop System

### Node Dragging (within React Flow)
**Location**: `CourseGraphFlow.tsx` (lines ~290-310)

```typescript
const onNodeDragStop = React.useCallback((_event, node) => {
  if (!node.data.userControlled) return;

  // Determine target section based on x position
  const sectionIndex = Math.round((node.position.x - COLUMN_WIDTH / 2) / COLUMN_WIDTH);
  const clampedIndex = Math.max(0, Math.min(sectionIndex, allSections.length - 1));
  const section = allSections[clampedIndex];

  if (section && node.data.section !== section.id) {
    // Update section and snap to center
    updateNodeLocal(node.id, { section: section.id });
  }
}, [allSections, updateNodeLocal]);
```

### Adding Nodes (Drag from Sidebar)
**Location**: `CourseGraphFlow.tsx` (lines ~315-360)

```typescript
const onDrop = React.useCallback(async (event) => {
  event.preventDefault();

  const nodeData = JSON.parse(event.dataTransfer.getData('application/json'));
  const position = screenToFlowPosition({ x: event.clientX, y: event.clientY });

  // Determine section based on drop position
  const sectionIndex = Math.round((position.x - COLUMN_WIDTH / 2) / COLUMN_WIDTH);
  const clampedIndex = Math.max(0, Math.min(sectionIndex, allSections.length - 1));
  const section = allSections[clampedIndex];

  const newNode = { ...nodeData, section: section.id };
  await addNode(newNode);
}, [addNode, screenToFlowPosition, allSections]);
```

---

## 10. Column Headers and Overlays

### Synchronized Column Headers
**Location**: `CourseGraphFlow.tsx` (lines ~70-140)

Column headers, dividers, and backgrounds move with viewport using RAF:

```typescript
React.useEffect(() => {
  let rafId: number;
  
  const updateViewport = () => {
    const viewport = getViewport();
    
    // Update transform for sync with viewport
    if (backgroundRef.current) {
      backgroundRef.current.style.transform = `translate(${viewport.x}px, 0) scale(${viewport.zoom})`;
    }
    if (dividersRef.current) {
      dividersRef.current.style.transform = `translate(${viewport.x}px, 0) scale(${viewport.zoom})`;
    }
    if (headersRef.current) {
      headersRef.current.style.transform = `translate(${viewport.x}px, 0) scale(${viewport.zoom})`;
    }
    
    rafId = requestAnimationFrame(updateViewport);
  };
  
  rafId = requestAnimationFrame(updateViewport);
  return () => cancelAnimationFrame(rafId);
}, [getViewport]);
```

### Section Backgrounds
- **Must Take** (id: -2): Purple hazard stripe pattern with 45° gradient
- **ASEs** (id: -1): Subtle white semi-transparent overlay
- **Regular sections**: No background

---

## 11. Data Loading and Persistence

### Fetch Flow
```
fetchRoadData() → Check localStorage → Load cached data OR loadInitialData()
  ↓
updateNodeLocal() / addNode() / removeNode() → Save to localStorage
  ↓
localStorage.save() called on every state change
```

### Storage API
**Location**: `/Users/matt/summer/autoroad/src/services/api.ts`

```typescript
// Saves nodes, edges, sections, specialSection, availableNodes to localStorage
localStorage.save({ nodes, edges, sections, specialSection, availableNodes });

// Loads from localStorage
const cached = localStorage.load();
```

### Initial Data (Demo/Fallback)
When no cached data exists, `loadInitialData()` provides:
- 6 semester sections (Freshman through Junior)
- ASEs special section
- 11 demo nodes
- 10 prerequisite edges

---

## 12. Alternative Graph Component (Legacy)

### CourseGraph.tsx
**Location**: `/Users/matt/summer/autoroad/src/components/course-graph/CourseGraph.tsx`

This is an older implementation without React Flow (custom canvas-based graph). Key differences:
- Manual column layout with flex
- Custom edge rendering with SVG overlay
- Context menu for adding nodes
- Simpler drag/drop implementation

**Status**: Appears to be replaced by `CourseGraphFlow.tsx` but still maintained.

---

## 13. Key Files Summary

| File | Purpose |
|------|---------|
| `CourseGraphFlow.tsx` | Main React Flow implementation |
| `CourseGraph.tsx` | Legacy canvas-based graph |
| `CourseNode.tsx` | Individual node component |
| `CourseEdges.tsx` | Edge rendering overlay |
| `roadStore.ts` | Zustand state management |
| `types.ts` | TypeScript type definitions |
| `nodeStyles.ts` | Node styling utility |
| `reactflow-custom.css` | Custom React Flow styles |
| `CourseNodeHoverCard.tsx` | Hover tooltip component |
| `AddNodeDropdown.tsx` | Course search/selection dropdown |
| `useCourseDrag.ts` | Drag handling from sidebar |

---

## 14. React Flow Configuration

### ReactFlow Component Props
**Location**: `CourseGraphFlow.tsx` (lines ~375-420)

```typescript
<ReactFlow
  nodes={nodes}
  edges={edges}
  onNodesChange={onNodesChange}
  onEdgesChange={onEdgesChange}
  onNodeDragStop={onNodeDragStop}
  onDrop={onDrop}
  onDragOver={onDragOver}
  nodeTypes={nodeTypes}
  fitView={false}
  minZoom={0.8}
  maxZoom={1.5}
  nodesDraggable
  nodesConnectable={false}
  elementsSelectable={true}
  zoomOnScroll={false}
  panOnScroll
  panOnDrag
  translateExtent={[[0, -Infinity], [numColumns * COLUMN_WIDTH, Infinity]]}
  defaultViewport={{ x: 0, y: 20, zoom: 1 }}
  proOptions={{ hideAttribution: true }}
  style={{ background: 'transparent' }}
>
  <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="rgba(255, 255, 255, 0.1)" />
</ReactFlow>
```

**Key Settings**:
- Edges not connectable (read-only visualization)
- Pan on drag/scroll enabled
- Zoom constrained to 0.8-1.5x
- Pan translation limited horizontally
- Dotted background pattern

---

## 15. Common Operations

### Adding a Node
```typescript
const newNode: CourseNode = {
  id: `node_${Date.now()}`,
  courseId: '6.1200',
  section: 0,
  userControlled: true,
};
await useGraphStore.getState().addNode(newNode);
```

### Moving a Node (Drag)
```typescript
useGraphStore.getState().updateNodeLocal(nodeId, { section: newSectionId });
```

### Removing a Node
```typescript
await useGraphStore.getState().removeNode(nodeId);
```

### Updating Node Properties
```typescript
await useGraphStore.getState().updateNode(nodeId, { disabled: true });
```

### Loading Data
```typescript
await useGraphStore.getState().fetchRoadData();
```

### Optimizing Schedule
```typescript
const result = await useGraphStore.getState().optimizeRoad({
  maxUnitsPerSemester: 24,
  minUnitsPerSemester: 12,
});
```

---

## 16. Debugging Tips

### Check Store State
```typescript
import { useGraphStore } from '@/stores/roadStore';

// In component
const state = useGraphStore();
console.log('Nodes:', state.nodes);
console.log('Edges:', state.edges);
console.log('Sections:', state.sections);
```

### Monitor Node Positioning
Look at React Flow's node `position` field after conversion - should align with column layout.

### localStorage State
```typescript
// In browser console
JSON.parse(localStorage.getItem('autoroad_data'))
```

### Flow Node Conversion
Verify that store nodes are being converted correctly in the `React.useEffect` in `CourseGraphFlow.tsx` that updates `setNodes()`.

---

## 17. Performance Considerations

1. **Memoization**: CourseNode component is React.memo'd
2. **Zustand Selectors**: Store uses selector pattern for performance
3. **RAF Animation**: Column headers use requestAnimationFrame
4. **ResizeObserver**: Edge paths update on container resize
5. **Virtualization**: Not implemented (consider for 1000+ nodes)

---

## Summary

The graph implementation uses:
- **React Flow** for visualization and interaction
- **Zustand** for state management
- **localStorage** for persistence
- **Custom node components** for styling
- **Column-based layout** with automatic positioning
- **Edge visualization** with bezier curves
- **Drag-and-drop** for adding and moving nodes
- **Synchronized headers** that move with viewport

All nodes are stored in a central Zustand store and converted to React Flow format on render, enabling seamless real-time updates and persistence.
