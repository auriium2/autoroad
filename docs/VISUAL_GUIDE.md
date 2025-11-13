# Visual Guide: Graph Visualization System

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      COURSE GRAPH SYSTEM                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              User Interaction Layer                       │   │
│  │  ┌─────────────────────────────────────────────────────┐ │   │
│  │  │ Add/Remove Nodes | Drag Nodes | Hover Tooltips    │ │   │
│  │  └─────────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              ↓                                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │         State Management Layer (Zustand Store)          │   │
│  │  ┌─────────────────────────────────────────────────────┐ │   │
│  │  │ nodes[] | edges[] | sections[] | loading state     │ │   │
│  │  │ (CourseNode, Edge, Section types)                  │ │   │
│  │  └─────────────────────────────────────────────────────┘ │   │
│  │ File: /stores/roadStore.ts                              │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              ↓                                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │           Rendering Layer (Two Implementations)         │   │
│  │                                                          │   │
│  │  ┌──────────────────────┐  ┌──────────────────────────┐ │   │
│  │  │  ReactFlow Version   │  │   CSS Grid Version       │ │   │
│  │  │ CourseGraphFlow.tsx  │  │  CourseGraph.tsx         │ │   │
│  │  │                      │  │                          │ │   │
│  │  │ ┌─────────────────┐  │  │ ┌──────────────────────┐ │ │   │
│  │  │ │ Node Layout     │  │  │ │ Column Grid Layout   │ │ │   │
│  │  │ │ Calculations    │  │  │ │ (Flex Container)     │ │ │   │
│  │  │ └─────────────────┘  │  │ └──────────────────────┘ │ │   │
│  │  │                      │  │                          │ │   │
│  │  │ ┌─────────────────┐  │  │ ┌──────────────────────┐ │ │   │
│  │  │ │ Edge Conversion │  │  │ │ SVG Overlay Layer    │ │ │   │
│  │  │ │ to ReactFlow    │  │  │ │ (CourseEdges.tsx)    │ │ │   │
│  │  │ │ Format          │  │  │ │                      │ │ │   │
│  │  │ └─────────────────┘  │  │ └──────────────────────┘ │ │   │
│  │  │                      │  │                          │ │   │
│  │  │ ┌─────────────────┐  │  │ ┌──────────────────────┐ │ │   │
│  │  │ │ Distance-Based  │  │  │ │ Distance-Based       │ │ │   │
│  │  │ │ Edge Coloring   │  │  │ │ Edge Styling         │ │ │   │
│  │  │ │ (Lines 334-340) │  │  │ │ (Lines 109-125)      │ │ │   │
│  │  │ └─────────────────┘  │  │ └──────────────────────┘ │ │   │
│  │  └──────────────────────┘  └──────────────────────────┘ │   │
│  │                                                          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              ↓                                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │         Styling & Effects Layer                          │   │
│  │  ┌─────────────────────────────────────────────────────┐ │   │
│  │  │ Node Styling (nodeStyles.ts)                        │ │   │
│  │  │ Term Highlighting (termBorderHighlight.ts)          │ │   │
│  │  │ Hover Effects (CourseNodeHoverCard.tsx)             │ │   │
│  │  └─────────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              ↓                                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │         DOM/Browser Rendering                            │   │
│  │  ┌─────────────────────────────────────────────────────┐ │   │
│  │  │ SVG Elements | HTML Divs | Canvas (ReactFlow)      │ │   │
│  │  └─────────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Visual Layout: Column-Based Grid

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Course Graph Viewport                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│ ┌────────┬────────┬────────┬────────┬────────┬────────┬────────┐   │
│ │ Must   │ ASEs   │ Fall   │ Spring │ Fall   │ Spring │ Fall   │   │
│ │ Take   │        │ Year 1 │ Year 1 │ Year 2 │ Year 2 │ Year 3 │   │
│ │(id=-2) │(id=-1) │(id=0)  │(id=1)  │(id=2)  │(id=3)  │(id=4)  │   │
│ ├────────┼────────┼────────┼────────┼────────┼────────┼────────┤   │
│ │        │        │        │        │        │        │        │   │
│ │ WIDTH: │ WIDTH: │ WIDTH: │ WIDTH: │ WIDTH: │ WIDTH: │ WIDTH: │   │
│ │ 180px  │ 180px  │ 180px  │ 180px  │ 180px  │ 180px  │ 180px  │   │
│ │        │        │        │        │        │        │        │   │
│ │  ┌──┐  │  ┌──┐  │  ┌──┐  │  ┌──┐  │  ┌──┐  │  ┌──┐  │  ┌──┐  │   │
│ │  │18│  │  │  │  │  │6 │  │  │6 │  │  │6 │  │  │6 │  │  │6 │  │   │
│ │  │  │  │  │  │  │  │1 │  │  │1 │  │  │1 │  │  │1 │  │  │1 │  │   │
│ │  │.0│  │  │  │  │  │0 │  │  │2 │  │  │0 │  │  │0 │  │  │0 │  │   │
│ │  │1 │  │  │  │  │  │0 │  │  │0 │  │  │1 │  │  │2 │  │  │7 │  │   │
│ │  └──┘  │  └──┘  │  └──┘  │  └──┘  │  └──┘  │  └──┘  │  └──┘  │   │
│ │  (ASE) │ (ASE)  │ (USER) │(USER)  │ (AUTO) │ (AUTO) │ (AUTO) │   │
│ │        │        │        │        │        │        │        │   │
│ │  VERT  │  VERT  │  VERT  │  VERT  │  VERT  │  VERT  │  VERT  │   │
│ │  GAP:  │  GAP:  │  GAP:  │  GAP:  │  GAP:  │  GAP:  │  GAP:  │   │
│ │  64px  │  64px  │  64px  │  64px  │  64px  │  64px  │  64px  │   │
│ │  (gap- │  (gap- │  (gap- │  (gap- │  (gap- │  (gap- │  (gap- │   │
│ │   16)  │   16)  │   16)  │   16)  │   16)  │   16)  │   16)  │   │
│ │        │        │        │        │        │        │        │   │
│ │  ┌──┐  │        │  ┌──┐  │        │  ┌──┐  │  ┌──┐  │        │   │
│ │  │18│  │        │  │6 │  │        │  │6 │  │  │6 │  │        │   │
│ │  │  │  │        │  │1 │  │        │  │1 │  │  │1 │  │        │   │
│ │  │.0│  │        │  │2 │  │        │  │0 │  │  │0 │  │        │   │
│ │  │2 │  │        │  │0 │  │        │  │3 │  │  │4 │  │        │   │
│ │  └──┘  │        │  └──┘  │        │  └──┘  │  └──┘  │        │   │
│ │        │        │        │        │        │        │        │   │
│ │        │        │        │        │  ┌──┐  │        │  ┌──┐  │   │
│ │        │        │        │        │  │6 │  │        │  │6 │  │   │
│ │        │        │        │        │  │1 │  │        │  │1 │  │   │
│ │        │        │        │        │  │0 │  │        │  │0 │  │   │
│ │        │        │        │        │  │5 │  │        │  │6 │  │   │
│ │        │        │        │        │  └──┘  │        │  └──┘  │   │
│ │        │        │        │        │        │        │        │   │
│ └────────┴────────┴────────┴────────┴────────┴────────┴────────┘   │
│                                                                      │
│ KEY:                                                                 │
│  - Column WIDTH: 180-200px (CSS Flex: 0 0 180px)                  │
│  - Node HEIGHT: 40px (h-10)                                       │
│  - Vertical SPACING: 64px (gap-16) or 120px (NODE_SPACING)        │
│  - Nodes centered vertically in viewport                          │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

SVG Overlay (CourseEdges):
  ○ ─────────────────────────── ○  (Close edge, solid, gray #9ca3af)
    \                           /
     \         ╱───────╲       /
      \       ╱         ╲     /
       ° ───╱           ╲─── °   (Long edge, dashed, light gray #d1d5db)
         /                 \
        /                   \
       ○ ───────────────────── ○
```

---

## Edge Color Decision Flow Chart

```
                          ┌─ EDGE DETECTED ─┐
                          │                   │
                          └─────────┬─────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │   GET HORIZONTAL DISTANCE     │
                    │   (fromNode.x - toNode.x)     │
                    └───────────────┬───────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
             ┌──────┴──────┐              ┌─────────┴────────┐
             │             │              │                  │
        distance ≤ 300px   │              │         distance > 300px
             │             │              │                  │
        ┌────┴────┐        │         ┌────┴────┐            │
        │          │        │         │          │            │
        ↓          ↓        │         ↓          ↓            │
   COLOR: #9ca3af │         │    COLOR: #d1d5db │            │
   WIDTH: 2px     │         │    WIDTH: 1.5px   │            │
   OPACITY: 0.6   │         │    OPACITY: 0.4   │            │
   STYLE: SOLID   │         │    STYLE: DASHED  │            │
        │         │         │         │         │            │
        └────┬────┘         │         └────┬────┘            │
             │              │              │                 │
             └──────────────┼──────────────┘                 │
                            │                               │
                   ┌────────┴────────┐                       │
                   │                 │                       │
                   ↓                 ↓                       │
            SVG PATH STYLE   (used by both)                  │
            ┌─────────────────────────────┐                  │
            │ strokeDasharray:             │                 │
            │   - solid: "none"            │                 │
            │   - dashed: "8 4"            │                 │
            │ strokeLinecap: "round"       │                 │
            │ fill: "none"                 │                 │
            └──────────────┬───────────────┘                 │
                           │                                │
                           ↓                                │
                    ┌──────────────┐                        │
                    │ RENDER EDGE  │                        │
                    │ SVG <path>   │                        │
                    └──────────────┘                        │
```

---

## Node Styling Decision Tree

```
START: CourseNode Created
│
└─► INPUT: { section, userControlled, disabled, isSpecial }
    │
    ├─► IS section === -2 (Must Take)?
    │   YES ──► bgColor: "bg-purple-950/40"
    │   YES ──► textColor: "text-purple-300"
    │   YES ──► boxShadow: "0 0 20px rgba(168, 85, 247, 0.6)"
    │   │
    │   NO ──► IS userControlled === true?
    │         YES ──► bgColor: "bg-card"
    │         YES ──► boxShadow: "0 0 20px rgba(59, 130, 246, 0.5)"
    │         │
    │         NO ──► IS section === -1 (ASEs)?
    │               YES ──► bgColor: "bg-gray-50 dark:bg-gray-900/40"
    │               YES ──► textColor: "text-gray-300"
    │               YES ──► borderColor: "border-gray-300"
    │               │
    │               NO ──► IS disabled === true?
    │                     YES ──► bgColor: "bg-red-50 dark:bg-red-950/20"
    │                     YES ──► textColor: "text-red-400"
    │                     YES ──► borderColor: "border-red-500"
    │                     │
    │                     NO ──► DEFAULT STYLING
    │                           bgColor: "bg-card"
    │                           textColor: "text-foreground"
    │                           borderColor: "border-border"
    │
    └─► OUTPUT: NodeStyleConfig
        {
          borderColor: string,
          bgColor: string,
          textColor: string,
          boxShadow: string
        }
```

---

## SVG Bezier Curve Visualization

```
Scenario 1: Vertical Gap (Different Y positions)

From Node (Y=100)
    ○
    │
    │ offsetFromX, offsetFromY + controlFactor
    │
    ├──────╮
    │      │ Control point 1
    │      ├─╮
    │       ╲ │ Bezier curve
    │        ╲├─╯
    │         │
    │    ╭────┤
    │    │ Control point 2
    │    ├─╯
    │  ╱
    ├─╯
    │
    ○ To Node (Y=250)

Formula:
  controlY1 = offsetFromY + (dy * 0.3)
  controlY2 = offsetToY - (dy * 0.3)
  path = M fromX fromY C midX controlY1, midX controlY2, toX toY


Scenario 2: Horizontal Distance (Same Y position)

From Node ─────────┐
  (100, 200)        │
                    │ bezier curve through middle
                    │
                   ─┴─ To Node
                    (700, 200)


Bezier Control:
  ┌─────────────┬─────────────┐
  │ From        │ To          │
  ├─────────────┼─────────────┤
  │ dy = 0      │ factor=0.3  │
  │ control1 Y: │ 200 + 0*0.3 │ = 200 (straight)
  │ control2 Y: │ 200 - 0*0.3 │ = 200 (straight)
  │             │             │
  │ Result: Straight path (no curve when dy=0)
  └─────────────┴─────────────┘
```

---

## Term Availability Highlighting

```
SVG Circle Node with Term Availability Pattern

Fall Only:                Spring Only:              IAP Only:
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   ╭─────╮       │    │       ╭─────╮   │    │   ╭─────╮       │
│  ╱       ╲      │    │      ╱       ╲  │    │  ╱       ╲      │
│ │ ··· 12  │     │    │    12  ··· │   │    │ │  12  ··· │     │
│ │ ····   │     │    │    │  ·····  │   │    │ │ ·······  │     │
│  ╲ ·····╱      │    │      ╲·····╱  │    │  ╲ ······╱      │
│   ╰─────╯       │    │       ╰─────╯   │    │   ╰─────╯       │
│ Left: dashed    │    │ Right: dashed   │    │ Bottom: dashed  │
│ (dashoffset:    │    │ (dashoffset:    │    │ (dashoffset:    │
│  0.25)          │    │  0.75)          │    │  0.5)           │
└─────────────────┘    └─────────────────┘    └─────────────────┘

Fall + Spring (Both):
┌─────────────────┐
│   ╭─────╮       │
│  ╱       ╲      │
│ │         12    │
│ │         ─────│
│  ╲       ╱      │
│   ╰─────╯       │
│ Full: solid     │
│ (dasharray: 1 0)│
└─────────────────┘

Implementation:
<svg className="absolute inset-0" viewBox="0 0 40 40">
  <circle
    cx="20" cy="20" r="18"
    stroke="rgba(255,255,255,0.25)"
    strokeDasharray={termHighlight.dasharray}    // "0.5 0.5" or "1 0"
    strokeDashoffset={termHighlight.dashoffset}  // 0.25, 0.75, 0.5, or 0
  />
</svg>
```

---

## Component Hierarchy

```
App
└── CourseGraphFlow (or CourseGraph as alternative)
    │
    ├── ColumnHeaders
    │   ├── Column Background (hazard overlay, gradient)
    │   ├── Column Dividers (vertical lines)
    │   └── Column Titles (sticky)
    │
    ├── FlowCourseNode (repeated per node)
    │   ├── Handle.target (left side)
    │   ├── Handle.source (right side)
    │   └── CourseNode
    │       ├── Circle (40px)
    │       │   ├── Border (colored based on status)
    │       │   ├── Background (colored based on status)
    │       │   └── Units (12-unit count)
    │       │
    │       ├── Term Highlight SVG (optional)
    │       │   └── Circle stroke with dash pattern
    │       │
    │       └── Course ID Label
    │           └── Below circle, "6.1200" etc.
    │
    ├── SVG Edges (Overlay)
    │   ├── <g> container
    │   └── <path> (repeated per edge)
    │       ├── d="M ... C ... ..." (cubic bezier)
    │       ├── stroke (color based on distance)
    │       ├── strokeWidth (2px or 1.5px)
    │       ├── opacity (0.6 or 0.4)
    │       └── strokeDasharray ("8 4" or none)
    │
    └── ContextMenu (on right-click)
        ├── Pin
        ├── Banish
        └── Remove Node
```

---

## Performance Optimization Points

```
┌─────────────────────────────────────┐
│  RENDERING PERFORMANCE              │
├─────────────────────────────────────┤
│                                     │
│ Expensive Operations:               │
│ ├─ SVG path calculation per edge   │
│ ├─ Node position recalculation     │
│ ├─ Edge re-rendering on scroll     │
│ └─ Bezier curve generation         │
│                                     │
│ Optimizations:                      │
│ ├─ Memoize node positions          │
│ ├─ Throttle scroll/resize events   │
│ ├─ Use requestAnimationFrame       │
│ ├─ Lazy-load edge rendering       │
│ └─ Cache path strings             │
│                                     │
│ Current Implementation:             │
│ ├─ React.useReducer for force      │
│ │  updates (CourseEdges.tsx)       │
│ ├─ ResizeObserver for layout       │
│ │  changes                         │
│ ├─ ReactFlow's built-in            │
│ │  rendering optimization         │
│ └─ localStorage caching            │
│                                     │
└─────────────────────────────────────┘
```

