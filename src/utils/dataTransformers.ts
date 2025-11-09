/**
 * Data transformation utilities to convert between frontend and backend data formats.
 */

import { Section, CourseNode, Edge, NodeDetail, AvailableNode } from "@/stores/roadStore";

/**
 * Transform backend optimization results to frontend road store format
 */
export function transformBackendToFrontend(backendData: any) {
  // Transform the backend data structure to the frontend format
  const sections: Section[] = backendData.semesters?.map((semester: any, index: number) => ({
    id: index,
    title: semester.title,
    nodes: semester.courses.map((course: any) => ({
      id: course.subject_id,
      label: course.subject_id,
      locked: course.locked || false,
      disabled: course.disabled || false,
      section: index,
      user_added: course.user_added || false
    }))
  })) || [];

  const edges: Edge[] = backendData.prerequisites?.map((prereq: any) => ({
    from: String(prereq.course),
    to: String(prereq.prerequisite)
  })) || [];

  const nodeDetails: Record<string, NodeDetail> = {};
  backendData.courses?.forEach((course: any) => {
    nodeDetails[course.subject_id] = {
      title: course.title || course.subject_id,
      description: course.description || "",
      type: course.course_type || "Course",
      status: course.status || "Active",
      connections: course.connections || 0,
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
  specialSection?: Section;
  constraints?: any;
}) {
  const { sections, specialSection, constraints = {} } = frontendData;

  // Convert sections to semesters
  const semesters = sections.map((section) => ({
    id: section.id,
    title: section.title,
    courses: section.nodes.map((node) => ({
      subject_id: node.id,
      locked: node.locked || false,
      disabled: node.disabled || false,
      user_added: node.user_added || false
    }))
  }));

  // Add special section if it exists
  const specialCourses = specialSection?.nodes.map((node) => ({
    subject_id: node.id,
    special_type: "ASE", // Assuming special section is for ASEs
    locked: node.locked || false,
    disabled: node.disabled || false,
    user_added: node.user_added || false
  })) || [];

  return {
    semesters,
    special_courses: specialCourses,
    constraints
  };
}

/**
 * Generates edges from prerequisites in course data
 */
export function generateEdgesFromPrerequisites(courseData: any[]): Edge[] {
  const edges: Edge[] = [];

  courseData.forEach(course => {
    const sourceId = course.subject_id;

    // Process prerequisites if they exist
    if (course.prerequisites) {
      // Handle different prerequisite formats
      if (Array.isArray(course.prerequisites)) {
        course.prerequisites.forEach((prereq: string) => {
          edges.push({
            from_id: prereq,
            to_id: sourceId
          });
        });
      } else if (typeof course.prerequisites === 'object') {
        // Handle more complex prerequisite structure
        Object.keys(course.prerequisites).forEach(prereq => {
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
export function formatAvailableNodes(courseData: any[]): AvailableNode[] {
  return courseData.map(course => ({
    id: course.subject_id,
    name: course.title || course.subject_id,
    category: course.department || 'Unknown',
    description: course.description || `Course ${course.subject_id}`
  }));
}
