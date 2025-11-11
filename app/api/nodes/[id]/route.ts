import { NextRequest, NextResponse } from 'next/server';
import { CourseDetails } from '@/services/api';

// Mock course data matching Fireroad API structure
const mockCourseData: Record<string, CourseDetails> = {
  "0": {
    id: "18.01",
    name: "Single Variable Calculus",
    description: "Differentiation and integration of functions of one variable, with applications.",
    units: 12,
    prerequisites: "",
    corequisites: "",
    terms_offered: ["Fall", "Spring"],
    instructors: [],
    offered_fall: true,
    offered_spring: true,
  },
  "1": {
    id: "6.100A",
    name: "Introduction to CS and Programming in Python",
    description: "Introduction to computer science and programming for students with little or no programming experience.",
    units: 6,
    prerequisites: "",
    corequisites: "",
    terms_offered: ["Fall"],
    instructors: [],
    offered_fall: true,
  },
  "2": {
    id: "6.1200",
    name: "Mathematics for Computer Science",
    description: "Elementary discrete mathematics for science and engineering, with applications to computer science.",
    units: 12,
    prerequisites: "Calculus I (GIR)",
    corequisites: "",
    terms_offered: ["Fall", "Spring"],
    instructors: [],
    offered_fall: true,
    offered_spring: true,
  },
  "3": {
    id: "6.120A",
    name: "Discrete Mathematics and Proof for Computer Science",
    description: "Discrete mathematics with a focus on computer science applications.",
    units: 12,
    prerequisites: "",
    corequisites: "",
    terms_offered: ["Spring"],
    instructors: [],
    offered_spring: true,
  },
};

/**
 * Fetch course data from FireRoad API (or return mock data)
 */
async function fetchCourseData(courseId: string): Promise<CourseDetails> {
  // For now, return mock data
  if (mockCourseData[courseId]) {
    return mockCourseData[courseId];
  }
  
  // Return generic course data matching Fireroad structure
  return {
    id: courseId,
    name: `Course ${courseId}`,
    description: "No description available",
    units: 12,
    prerequisites: "",
    corequisites: "",
    terms_offered: [],
    instructors: [],
  };
}

export async function GET(
  req: NextRequest,
  context: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await context.params;
    
    // Fetch course data (either from mock data or API)
    const courseData = await fetchCourseData(id);
    
    return NextResponse.json(courseData);
  } catch (error) {
    console.error('Error fetching node details:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to fetch node details' },
      { status: 500 }
    );
  }
}
