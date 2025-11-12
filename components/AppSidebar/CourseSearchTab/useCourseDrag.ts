import * as React from "react";

export function useCourseDrag() {
  const [draggedCourseId, setDraggedCourseId] = React.useState<string | null>(null);

  const handleDragStart = (e: React.DragEvent, courseData: { subject_id: string }) => {
    // Set the data for React Flow to pick up
    e.dataTransfer.setData("application/reactflow", "node");
    e.dataTransfer.setData("application/json", JSON.stringify({
      id: `${courseData.subject_id}_${Date.now()}`,
      courseId: courseData.subject_id,
      section: -2, // Default to "Must Take" column
      userControlled: true,
    }));
    
    e.dataTransfer.effectAllowed = 'move';
    
    setDraggedCourseId(courseData.subject_id);
  };

  const handleDragEnd = () => {
    setDraggedCourseId(null);
  };

  return {
    draggedCourseId,
    handleDragStart,
    handleDragEnd,
  };
}
