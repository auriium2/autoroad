/**
 * Data transformation utilities to convert between frontend and backend data formats.
 */

import { Section, Edge, AvailableNode } from "@/stores/roadStore";

/**
 * Transform backend optimization results to frontend road store format
 */
export function transformBackendToFrontend(backendData: unknown) {
  const data = backendData as Record<string, unknown>;
  
  // Transform the backend data structure to the frontend format
  const sections: Section[] = ((data.semesters as unknown[]) || []).map((semester: unknown, index: number) => {
    const sem = semester as Record<string, unknown>;
    return {
      id: index,
      title: String(sem.title || `Semester ${index + 1}`),
    };
  });

  const edges: Edge[] = ((data.prerequisites as unknown[]) || []).map((prereq: unknown) => {
    const p = prereq as Record<string, unknown>;
    return {
      from_id: String(p.course),
      to_id: String(p.prerequisite)
    };
  });

  const nodeDetails: Record<string, unknown> = {};
  ((data.courses as unknown[]) || []).forEach((course: unknown) => {
    const c = course as Record<string, unknown>;
    nodeDetails[String(c.subject_id)] = {
      title: c.title || c.subject_id,
      description: c.description || "",
      type: c.course_type || "Course",
      status: c.status || "Active",
      connections: c.connections || 0,
      lastUpdated: new Date().toISOString()
    };
  });

  return { sections, edges, nodeDetails };
}

/**
 * Transform frontend road data to backend format for optimization
 */
export function transformFrontendToBackend(frontendData: {
  sections: Section[];

  constraints?: unknown;
}) {
  const { sections, constraints = {} } = frontendData;

  // Convert sections to semesters
  const semesters = sections.map((section) => ({
    id: section.id,
    title: section.title,
    courses: []
  }));

  // Add special section if it exists
  const specialCourses: unknown[] = [];

  return {
    semesters,
    special_courses: specialCourses,
    constraints
  };
}

/**
 * Generates edges from prerequisites in course data
 */
export function generateEdgesFromPrerequisites(courseData: unknown[]): Edge[] {
  const edges: Edge[] = [];

  courseData.forEach(course => {
    const c = course as Record<string, unknown>;
    const sourceId = String(c.subject_id);

    // Process prerequisites if they exist
    if (c.prerequisites) {
      // Handle different prerequisite formats
      if (Array.isArray(c.prerequisites)) {
        c.prerequisites.forEach((prereq: unknown) => {
          edges.push({
            from_id: String(prereq),
            to_id: sourceId
          });
        });
      } else if (typeof c.prerequisites === 'object') {
        // Handle more complex prerequisite structure
        Object.keys(c.prerequisites as object).forEach(prereq => {
          edges.push({
            from_id: prereq,
            to_id: sourceId
          });
        });
      }
    }
  });

  return edges;
}

/**
 * Format course data from backend to frontend available nodes format
 */
export function formatAvailableNodes(courseData: unknown[]): AvailableNode[] {
  return courseData.map(course => {
    const c = course as Record<string, unknown>;
    return {
      courseId: String(c.subject_id),
      title: String(c.title || c.subject_id),
      department: String(c.department || 'Unknown'),
      units: Number(c.units || c.total_units || 12)
    };
  });
}
