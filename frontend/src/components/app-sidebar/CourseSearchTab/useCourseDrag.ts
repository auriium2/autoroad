import * as React from "react";
import { useDragStore, extractCourseOfferings } from "@/stores/dragStore";

interface CourseData {
  subject_id: string;
  virtual?: boolean;
  offered_fall?: boolean;
  offered_spring?: boolean;
  offered_IAP?: boolean;
  not_offered_year?: string | null;
}

export function useCourseDrag() {
  const [draggedCourseId, setDraggedCourseId] = React.useState<string | null>(null);
  const startDrag = useDragStore((state) => state.startDrag);
  const endDrag = useDragStore((state) => state.endDrag);

  const handleDragStart = (e: React.DragEvent, courseData: CourseData) => {
    // Virtual markers (HASS-A, etc.) cannot go in Must Take, default to first semester
    const defaultSection = courseData.virtual ? 0 : -2;

    // Set the data for React Flow to pick up
    e.dataTransfer.setData("application/reactflow", "node");
    e.dataTransfer.setData("application/json", JSON.stringify({
      id: `${courseData.subject_id}_${Date.now()}`,
      courseId: courseData.subject_id,
      section: defaultSection,
      userControlled: true,
    }));
    
    e.dataTransfer.effectAllowed = 'move';
    
    setDraggedCourseId(courseData.subject_id);
    startDrag(courseData.subject_id, extractCourseOfferings(courseData));
  };

  const handleDragEnd = () => {
    setDraggedCourseId(null);
    endDrag();
  };

  return {
    draggedCourseId,
    handleDragStart,
    handleDragEnd,
  };
}
