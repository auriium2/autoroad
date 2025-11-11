import * as React from "react";

interface DragState {
  isDragging: boolean;
  dragPosition: { x: number; y: number };
  currentSection: number;
  isOverGraph: boolean;
}

export function useCourseDrag() {
  const [state, setState] = React.useState<DragState>({
    isDragging: false,
    dragPosition: { x: 0, y: 0 },
    currentSection: -2, // Default to "Must Take" column
    isOverGraph: false,
  });

  // Track mouse movement during drag using document event listener
  React.useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!state.isDragging) return;

      const newPosition = { x: e.clientX, y: e.clientY };

      // Get the React Flow viewport to account for panning/zooming
      const flowViewport = document.querySelector('.react-flow__viewport');
      const canvas = document.querySelector('.react-flow');
      if (!canvas || !flowViewport) {
        setState(prev => ({ ...prev, dragPosition: newPosition }));
        return;
      }

      const canvasRect = canvas.getBoundingClientRect();

      // Check if cursor is actually over the graph
      const isInBounds = (
        e.clientX >= canvasRect.left &&
        e.clientX <= canvasRect.right &&
        e.clientY >= canvasRect.top &&
        e.clientY <= canvasRect.bottom
      );

      if (!isInBounds) {
        setState(prev => ({ 
          ...prev, 
          dragPosition: newPosition, 
          isOverGraph: false 
        }));
        return;
      }

      const relativeX = e.clientX - canvasRect.left;

      // Get the viewport transform to account for panning
      const transform = window.getComputedStyle(flowViewport).transform;
      let panX = 0;
      if (transform && transform !== 'none') {
        const matrix = transform.match(/matrix\(([^)]+)\)/);
        if (matrix) {
          const values = matrix[1].split(',').map(parseFloat);
          panX = values[4] || 0; // translateX is at index 4
        }
      }

      // Adjust for pan offset
      const flowX = relativeX - panX;

      // Simple column detection (200px per column)
      const COLUMN_WIDTH = 200;
      const columnIndex = Math.floor(flowX / COLUMN_WIDTH);

      // Map column index to section ID
      // Column 0: Must Take (-2), Column 1: ASEs (-1), Column 2+: semester sections (0, 1, 2, ...)
      let sectionId: number;
      if (columnIndex === 0) {
        sectionId = -2; // Must Take
      } else if (columnIndex === 1) {
        sectionId = -1; // ASEs
      } else {
        sectionId = columnIndex - 2; // Semester sections start at column 2
      }

      setState({
        isDragging: true,
        dragPosition: newPosition,
        currentSection: sectionId,
        isOverGraph: true,
      });
    };

    if (state.isDragging) {
      document.addEventListener('dragover', handleMouseMove);
      return () => {
        document.removeEventListener('dragover', handleMouseMove);
      };
    }
  }, [state.isDragging]);

  const handleDragStart = React.useCallback((e: React.DragEvent, courseData: { subject_id: string }) => {
    e.dataTransfer.setData("application/json", JSON.stringify({
      id: `${courseData.subject_id}_${Date.now()}`,
      courseId: courseData.subject_id,
      section: -2, // Default to "Must Take" column
      userControlled: true,
    }));

    // Hide the default drag image by using an empty transparent image
    const img = new Image();
    img.src = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
    e.dataTransfer.setDragImage(img, 0, 0);

    setState({
      isDragging: true,
      dragPosition: { x: e.clientX, y: e.clientY },
      currentSection: -2,
      isOverGraph: false,
    });
  }, []);

  const handleDragEnd = React.useCallback(() => {
    setState({
      isDragging: false,
      dragPosition: { x: 0, y: 0 },
      currentSection: -2,
      isOverGraph: false,
    });
  }, []);

  return {
    ...state,
    handleDragStart,
    handleDragEnd,
  };
}
