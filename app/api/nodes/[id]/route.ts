import { NextRequest, NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';
import * as path from 'path';

const execAsync = promisify(exec);

// Mock course data for development (in production this would come from a database or external API)
const mockCourseData: Record<string, any> = {
  "0": {
    title: "18.01 - Calculus",
    description: "Single Variable Calculus",
    type: "ASE",
    status: "Active",
    connections: 1,
    lastUpdated: "2 minutes ago",
    units: 12,
    prerequisites: [],
  },
  "1": {
    title: "6.100A - Introduction to Programming",
    description: "Introduction to computer programming and algorithm development",
    type: "Course",
    status: "Active", 
    connections: 1,
    lastUpdated: "1 minute ago",
    units: 12,
    prerequisites: [],
  },
  "2": {
    title: "6.1200 - Mathematics for Computer Science",
    description: "Elementary discrete mathematics for science and engineering",
    type: "Course",
    status: "Active",
    connections: 2,
    lastUpdated: "30 seconds ago",
    units: 12,
    prerequisites: ["1"],
  },
  "3": {
    title: "6.120A - Discrete Mathematics",
    description: "Advanced discrete mathematics topics",
    type: "Course",
    status: "Locked",
    connections: 1,
    lastUpdated: "45 seconds ago",
    units: 12,
    prerequisites: ["1"],
  },
};

/**
 * Fetch course data from FireRoad API (or return mock data)
 */
async function fetchCourseData(courseId: string): Promise<any> {
  // For now, return mock data
  if (mockCourseData[courseId]) {
    return mockCourseData[courseId];
  }
  
  // In a production environment, this would call the FireRoad API
  try {
    // This is a placeholder for a real API call
    // const response = await fetch(`https://fireroad.mit.edu/courses/${courseId}`);
    // const data = await response.json();
    // return data;
    
    // For now, return a generic response for unknown courses
    return {
      title: `Course ${courseId}`,
      description: "No description available",
      type: "Course",
      status: "Unknown",
      connections: 0,
      lastUpdated: "Unknown",
      units: 12,
      prerequisites: [],
    };
  } catch (error) {
    console.error(`Error fetching data for course ${courseId}:`, error);
    throw error;
  }
}

export async function GET(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const { id } = params;
    
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