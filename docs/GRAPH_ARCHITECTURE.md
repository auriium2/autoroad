# Graph Architecture Diagrams

## 1. Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER ACTIONS                             │
└─────────────┬──────────────────────────────────────────┬─────────┘
              │                                          │
              ▼                                          ▼
        ┌──────────────┐                        ┌─────────────────┐
        │  Drop Node   │                        │  Drag Node      │
        │  from Search │                        │  Between Columns│
        └──────┬───────┘                        └────────┬────────┘
               │                                         │
               ▼                                         ▼
        ┌──────────────────────────────────────────────────────────┐
        │          React Flow Event Handlers                       │
        │  onDrop() → addNode()                                   │
        │  onNodeDragStop() → updateNodeLocal()                   │
        └──────────────┬───────────────────────────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────────────────────────────────┐
        │       Zustand GraphStore State Update                    │
        │  - nodes: CourseNode[]                                  │
        │  - edges: Edge[]                                         │
        │  - sections: Section[]                                   │
        │  - specialSection: Section | null                        │
        └──────────────┬───────────────────────────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────────────────────────────────┐
        │     Automatic localStorage Save                          │
        │  localStorage.save(nodes, edges, sections, ...)         │
        └──────────────┬───────────────────────────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────────────────────────────────┐
        │       Component Render (React.useEffect)                │
        │  1. Convert store nodes → React Flow nodes              │
        │  2. Apply positioning logic                             │
        │  3. Update node positions on canvas                     │
        └──────────────────────────────────────────────────────────┘
```

---

## 2. Component Hierarchy

```
CourseGraphFlow (ReactFlowProvider wrapper)
│
├── CourseGraphFlowInner
│   │
│   ├── <ReactFlow> (main canvas)
│   │   │
│   │   ├── FlowCourseNode (custom node type)
│   │   │   └── CourseNode (visual node)
│   │   │       ├── CourseTooltip
│   │   │       │   └── CourseNodeHoverCard
│   │   │       ├── Circle with unit count
│   │   │       ├── Course ID label
│   │   │       └── Term availability indicator (SVG)
│   │   │
│   │   └── Edges (bezier curves, auto-styled)
│   │
│   ├── <Background> (dotted pattern)
│   │
│   └── ColumnHeaders (positioned overlay)
│       ├── Column backgrounds (purple/gray)
│       ├── Column dividers
│       └── Section title headers

SearchSidebar (drag source)
│
├── CourseSearchTab
│   └── Drag-to-add course
│       ├── onDragStart → serialize node data
│       └── Drop onto graph → onDrop handler
```

---

## 3. Node Data Structure

```
CourseNode (Zustand Store)
│
├── id: string
│   └── Unique instance identifier (e.g., "0", "6.1200_1734567890")
│
├── courseId: string
│   └── Display name (e.g., "6.1200", "18.01")
│
├── section: number
│   ├── -2 → "Must Take" column (purple)
│   ├── -1 → "ASEs" column (gray)
│   └── 0+ → Regular semester columns
│
├── userControlled?: boolean
│   └── true → User can drag (blue glow)
│
├── disabled?: boolean
│   └── true → Cannot be taken (red styling)
│
└── Term availability (from course details API)
    ├── offeredFall?: boolean
    ├── offeredSpring?: boolean
    └── offeredIAP?: boolean


React Flow Node (Converted at render time)
│
├── id: string (matches CourseNode.id)
│
├── type: 'courseNode'
│   └── Uses FlowCourseNode custom component
│
├── position: { x: number, y: number }
│   ├── x = columnIndex * 200 + 100
│   └── y = centerY + nodeIndexInSection * 120
│
├── data: CourseNode
│   └── All CourseNode properties + handlers
│
└── draggable: boolean
    └── true if userControlled
```

---

## 4. Positioning Algorithm

```
INPUTS:
- allSections: Section[] (Must Take, ASEs, Semester 1-6)
- storeNodes: CourseNode[]
- Constants:
  - COLUMN_WIDTH = 200px
  - NODE_SPACING = 120px
  - VIEWPORT_CENTER_Y = 400px

FOR EACH node IN storeNodes:
  1. Find sectionIndex in allSections
     sectionIndex = allSections.findIndex(s => s.id === node.section)
  
  2. Count nodes in same section
     nodesInSection = storeNodes.filter(n => n.section === node.section)
  
  3. Find node's index within section
     nodeIndexInSection = nodesInSection.findIndex(n => n.id === node.id)
  
  4. Calculate total height of all nodes in section
     totalHeight = (nodesInSection.length - 1) * NODE_SPACING
  
  5. Calculate start Y (centered vertically)
     startY = VIEWPORT_CENTER_Y - (totalHeight / 2)
  
  6. Final position
     position.x = sectionIndex * COLUMN_WIDTH + (COLUMN_WIDTH / 2)
     position.y = startY + nodeIndexInSection * NODE_SPACING

EXAMPLE:
  3 nodes in section 1 (Freshman Fall):
  - Node 0: y = 400 - (2*120/2) + 0*120 = 280
  - Node 1: y = 400 - (2*120/2) + 1*120 = 400
  - Node 2: y = 400 - (2*120/2) + 2*120 = 520
  
  All centered around y=400 (viewport center)
```

---

## 5. State Management (Zustand Store)

```
useGraphStore (Zustand)
│
├── STATE
│   ├── nodes: CourseNode[]
│   │   └── Current user's course selection
│   │
│   ├── edges: Edge[]
│   │   └── Prerequisite relationships
│   │
│   ├── sections: Section[]
│   │   └── Semester definitions
│   │
│   ├── specialSection: Section | null
│   │   └── ASEs or other special section
│   │
│   ├── availableNodes: AvailableNode[]
│   │   └── Full course catalog
│   │
│   ├── loadingState: 'idle' | 'loading' | 'success' | 'error'
│   │
│   ├── error: string | null
│   │
│   ├── isSaving: boolean
│   │
│   ├── hasChangesSinceOptimization: boolean
│   │
│   └── userId: string | null
│
├── ACTIONS (synchronous)
│   ├── addNode(node: CourseNode)
│   │   ├── Add to nodes array
│   │   ├── Save to localStorage
│   │   └── Mark changes if userControlled
│   │
│   ├── removeNode(id: string)
│   │   ├── Remove from nodes
│   │   ├── Remove associated edges
│   │   └── Save to localStorage
│   │
│   ├── updateNode(id: string, updates: Partial<CourseNode>)
│   │   ├── Update node properties
│   │   └── Save to localStorage
│   │
│   ├── updateNodeLocal(id: string, updates: Partial<CourseNode>)
│   │   ├── Update local state only (no persistence)
│   │   └── Used during drag operations
│   │
│   ├── setEdges(edges: Edge[])
│   │   └── Replace entire edge list
│   │
│   ├── loadRoadData(data: Partial<GraphStore>)
│   │   ├── Load from API/localStorage
│   │   └── Save to localStorage
│   │
│   ├── fetchRoadData()
│   │   ├── Load from localStorage
│   │   ├── Fallback to loadInitialData()
│   │   └── Set loadingState
│   │
│   ├── saveRoadData()
│   │   └── Manual save to localStorage
│   │
│   ├── optimizeRoad(constraints)
│   │   ├── Send to optimization API
│   │   ├── Load optimized result
│   │   └── Reset change tracking
│   │
│   └── clearError()
│       └── Reset error state
│
└── SELECTORS (optimized for performance)
    ├── const nodes = useGraphStore(state => state.nodes)
    ├── const edges = useGraphStore(state => state.edges)
    └── All properties accessible via selector pattern
```

---

## 6. Node Styling State Machine

```
CourseNode State → Styling

┌─────────────────────────────────────────────┐
│ Must Take (section === -2)                  │
├─────────────────────────────────────────────┤
│ bgColor: "bg-purple-950/40"                │
│ textColor: "text-purple-300"                │
│ boxShadow: Purple glow (20px, 40px)        │
│ Pattern: 45° diagonal stripes               │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ User-Controlled (userControlled === true)   │
├─────────────────────────────────────────────┤
│ bgColor: "bg-card"                         │
│ textColor: "text-foreground"                │
│ boxShadow: Blue glow (20px, 40px)          │
│ Draggable: true                             │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ ASEs (section === -1)                       │
├─────────────────────────────────────────────┤
│ borderColor: "border-gray-300"              │
│ bgColor: "bg-gray-50 dark:bg-gray-900/40"  │
│ textColor: "text-gray-700 dark:text-gray-300"│
│ boxShadow: "none"                          │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ Disabled (disabled === true)                │
├─────────────────────────────────────────────┤
│ borderColor: "border-red-500"               │
│ bgColor: "bg-red-50 dark:bg-red-950/20"    │
│ textColor: "text-red-700 dark:text-red-400"│
│ boxShadow: "none"                          │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ Regular (default)                           │
├─────────────────────────────────────────────┤
│ borderColor: "border-border"                │
│ bgColor: "bg-card"                         │
│ textColor: "text-foreground"                │
│ boxShadow: "none"                          │
└─────────────────────────────────────────────┘
```

---

## 7. Edge Rendering Pipeline

```
Store Edges (Edge[])
  └── from_id: string
  └── to_id: string

    ▼

React Flow Edges (FlowEdge[])
  └── id: string
  └── source: string (from_id)
  └── target: string (to_id)
  └── type: 'default' (bezier curves)

    ▼

Styled Based on Distance
  │
  ├── Short distance (adjacent columns)
  │   ├── stroke: "rgba(156, 163, 175, 0.7)"
  │   ├── strokeWidth: 2
  │   ├── opacity: 0.6
  │   └── strokeDasharray: undefined (solid)
  │
  └── Long distance (>1 column)
      ├── stroke: "rgba(209, 213, 219, 0.4)"
      ├── strokeWidth: 1.5
      ├── opacity: 0.4
      └── strokeDasharray: "5 5" (dashed)

    ▼

Filtered Edges
  └── No edges from/to Must Take column (section -2)

    ▼

Rendered in ReactFlow Canvas
  └── Bezier curves with arrow markers
```

---

## 8. Drag and Drop Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    DRAG FROM SIDEBAR                             │
└─────────────────────────────────────────────────────────────────┘

User selects course from search
  │
  ▼
CourseSearchTab.tsx
  ├── onDragStart handler
  ├── Serialize CourseNode data
  └── Set dataTransfer type: 'application/json'
      
    ▼

CourseGraphFlow.tsx
  └── onDragOver handler
      └── event.preventDefault()
      └── Set dropEffect = 'move'

    ▼

User drops on canvas
  │
  ▼
CourseGraphFlow.tsx
  └── onDrop handler
      1. Get drop position: screenToFlowPosition()
      2. Determine target section from x position
      3. Create new CourseNode
      4. Call addNode(newNode)
      
      ▼
      
    Zustand Store
      ├── nodes.push(newNode)
      ├── Save to localStorage
      └── Trigger component re-render
      
      ▼
      
    React.useEffect (store nodes change)
      ├── Convert to React Flow format
      ├── Apply positioning algorithm
      └── setNodes(flowNodes)
      
      ▼
      
    ReactFlow Canvas
      └── Node appears at drop location

┌─────────────────────────────────────────────────────────────────┐
│                  DRAG WITHIN CANVAS                              │
└─────────────────────────────────────────────────────────────────┘

User drags node in canvas
  │
  ▼
ReactFlow (nodesDraggable = true)
  │
  ▼
onNodeDragStop handler
  1. Calculate target section from x position
  2. If section changed:
     └── Call updateNodeLocal(nodeId, { section: newSectionId })
       │
       ▼
       Zustand Store
         ├── Update node.section in nodes array
         ├── Mark changes if userControlled
         └── Trigger re-render
       
       ▼
       
       React.useEffect (store nodes change)
         ├── Recalculate positions
         ├── Apply positioning algorithm
         └── Snap node to center of new column
```

---

## 9. Column Layout Structure

```
ReactFlow Canvas
│
├── <Background> (dots pattern)
│
├── <ReactFlow viewport>
│   └── Nodes positioned in grid:
│       
│       Section 0        Section 1        Section 2
│       (Must Take)      (ASEs)          (Freshman Fall)
│       x=100            x=300            x=500
│       ┌─────┐         ┌─────┐         ┌─────┐
│       │  12 │         │  12 │         │   6 │  ◄─ Node at y=280
│       │ UNI │         │ 18. │         │ 6.1 │
│       └─────┘         └─────┘         └─────┘
│       ┌─────┐         ┌─────┐         ┌─────┐
│       │  12 │         │  12 │         │   9 │  ◄─ Node at y=400
│       │ COD │         │ 6.1 │         │ 6.0 │
│       └─────┘         └─────┘         └─────┘
│       ┌─────┐         ┌─────┐         ┌─────┐
│       │  12 │         │  18 │         │  12 │  ◄─ Node at y=520
│       │ INT │         │ 6.1 │         │ 6.1 │
│       └─────┘         └─────┘         └─────┘
│       
│       ◄─ 200px ─►   ◄─ 200px ─►   ◄─ 200px ─►
│
│
└── <ColumnHeaders overlay>
    ├── Background colors (section-specific)
    ├── Column dividers (vertical lines)
    └── Section titles
        ├── "Must Take" (glass card)
        ├── "ASEs" (glass card)
        └── "Freshman Fall" (glass card)


Key Constants:
- COLUMN_WIDTH = 200px
- NODE_SPACING = 120px
- NODE_RADIUS = 20px (40px total diameter)
- VIEWPORT_CENTER_Y = 400px
```

---

## 10. State Persistence Flow

```
User Action
  │
  ├─ addNode()
  ├─ removeNode()
  ├─ updateNode()
  ├─ updateNodeLocal()
  └─ setEdges()
    │
    ▼
  Zustand Store Updates
    │
    ▼
  All mutations call:
  └─ localStorage.save({
       nodes,
       edges,
       sections,
       specialSection,
       availableNodes
     })
    │
    ▼
  Browser localStorage
  └─ Key: 'autoroad_data'
    │
    ▼
  App Reload
    │
    ├─ fetchRoadData()
    │   │
    │   ├─ Load from localStorage
    │   │   └─ setLoadingState('success')
    │   │
    │   └─ If no cache:
    │       └─ loadInitialData() (demo data)
    │
    └─ State restored
```

---

## 11. Type Conversion Flow

```
Raw Store Data
└── CourseNode[]
    ├── id: "0"
    ├── courseId: "6.1200"
    ├── section: 1
    ├── userControlled: true
    └── [...]

    ▼ (React.useEffect when store nodes change)

Positioning Calculation
└── For each node:
    1. Find sectionIndex
    2. Count nodes in section
    3. Calculate centering Y
    4. Apply NODE_SPACING
    5. Get column X

    ▼

React Flow Nodes
└── Node[]
    ├── id: "0"
    ├── type: "courseNode"
    ├── position: { x: 300, y: 400 }
    ├── data: CourseNode
    │   └── All original properties
    │   └── Plus event handlers
    │
    └── draggable: true

    ▼

Custom Component
└── FlowCourseNode
    ├── Wraps with React Flow Handles
    ├── Renders CourseNode component
    └── Shows 40px circle with units

    ▼

Rendered on Canvas
└── Visual node with:
    ├── Circle (40px)
    ├── Unit count (center)
    ├── Course ID label (below)
    └── Hover effects
```

---

## Summary

The graph implementation follows a clear data flow:
1. **Data**: Store nodes (CourseNode[]) in Zustand
2. **Conversion**: Transform to React Flow format with positioning
3. **Rendering**: Display on canvas with custom components
4. **Interaction**: Handle drag/drop via React Flow handlers
5. **Persistence**: Auto-save to localStorage on every change
6. **Styling**: Apply dynamic styles based on node state

All positioning is automatic and centered, with special handling for Must Take and ASEs columns.
