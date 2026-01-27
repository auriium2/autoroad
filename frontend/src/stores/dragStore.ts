import { create } from "zustand";

interface DragState {
  isDragging: boolean;
  courseId: string | null;
  offeredFall: boolean;
  offeredSpring: boolean;
  offeredIAP: boolean;
  notOfferedYear: string | null;
  hoveredSection: number | null;
  
  startDrag: (courseId: string, offered: { fall: boolean; spring: boolean; iap: boolean; notOfferedYear: string | null }) => void;
  endDrag: () => void;
  setHoveredSection: (section: number | null) => void;
}

export const useDragStore = create<DragState>((set) => ({
  isDragging: false,
  courseId: null,
  offeredFall: false,
  offeredSpring: false,
  offeredIAP: false,
  notOfferedYear: null,
  hoveredSection: null,
  
  startDrag: (courseId, offered) => set({
    isDragging: true,
    courseId,
    offeredFall: offered.fall,
    offeredSpring: offered.spring,
    offeredIAP: offered.iap,
    notOfferedYear: offered.notOfferedYear,
    hoveredSection: null,
  }),
  
  endDrag: () => set({
    isDragging: false,
    courseId: null,
    offeredFall: false,
    offeredSpring: false,
    offeredIAP: false,
    notOfferedYear: null,
    hoveredSection: null,
  }),
  
  setHoveredSection: (section) => set({ hoveredSection: section }),
}));
