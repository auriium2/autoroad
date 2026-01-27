import { create } from "zustand";

export interface CourseOfferings {
  fall: boolean;
  spring: boolean;
  iap: boolean;
  notOfferedYear: string | null;
}

interface DragState {
  isDragging: boolean;
  courseId: string | null;
  offeredFall: boolean;
  offeredSpring: boolean;
  offeredIAP: boolean;
  notOfferedYear: string | null;
  hoveredSection: number | null;
  
  startDrag: (courseId: string, offered: CourseOfferings) => void;
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

/**
 * Extract course offerings from any object with offering fields.
 * Works with FireroadCourse or partial course data.
 */
export function extractCourseOfferings(course: {
  offered_fall?: boolean;
  offered_spring?: boolean;
  offered_IAP?: boolean;
  not_offered_year?: string | null;
} | null | undefined): CourseOfferings {
  return {
    fall: course?.offered_fall ?? true,
    spring: course?.offered_spring ?? true,
    iap: course?.offered_IAP ?? false,
    notOfferedYear: course?.not_offered_year ?? null,
  };
}
