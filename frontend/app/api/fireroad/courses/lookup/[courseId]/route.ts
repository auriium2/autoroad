/**
 * Fireroad API Proxy - Course Lookup
 * Proxies requests to Fireroad API to avoid CORS issues
 * Toggle USE_FIREROAD to switch between real API and fake data
 */

import { NextRequest, NextResponse } from 'next/server';

const USE_FIREROAD = false; // Toggle to switch between fake and real Fireroad API
const FIREROAD_API_URL = 'https://fireroad.mit.edu';

interface FakeCourse {
  subject_id: string;
  title: string;
  total_units: number;
  description: string;
  prerequisites: string;
  corequisites: string;
  offered_fall?: boolean;
  offered_spring?: boolean;
  gir_attribute?: string;
  communication_requirement?: string;
}

// Fake course data for development/testing
const FAKE_COURSES: Record<string, FakeCourse> = {
  '18.01': {
    subject_id: '18.01',
    title: 'Single Variable Calculus',
    total_units: 12,
    description: 'Differentiation and integration of functions of one variable, with applications.',
    prerequisites: '',
    corequisites: '',
    offered_fall: true,
    offered_spring: true,
    gir_attribute: 'REST',
  },
  '6.100': {
    subject_id: '6.100',
    title: 'Introduction to Computer Science Programming in Python',
    total_units: 12,
    description: 'Introduction to computer science and programming using Python.',
    prerequisites: '',
    corequisites: '',
    offered_fall: true,
    offered_spring: true,
  },
  '6.1200': {
    subject_id: '6.1200',
    title: 'Mathematics for Computer Science',
    total_units: 12,
    description: 'Elementary discrete mathematics for science and engineering.',
    prerequisites: '6.100',
    corequisites: '',
    offered_fall: true,
    offered_spring: true,
  },
  '6.120a': {
    subject_id: '6.120a',
    title: 'Discrete Mathematics and Proof for Computer Science',
    total_units: 6,
    description: 'Introduction to discrete mathematics and proof techniques.',
    prerequisites: '',
    corequisites: '',
    offered_fall: true,
  },
  '6.1010': {
    subject_id: '6.1010',
    title: 'Fundamentals of Programming',
    total_units: 12,
    description: 'Introduction to programming in Python.',
    prerequisites: '6.100/6.120a',
    corequisites: '',
    offered_fall: true,
    offered_spring: true,
  },
  '6.1020': {
    subject_id: '6.1020',
    title: 'Software Construction',
    total_units: 12,
    description: 'Introduces fundamental principles and techniques of software development.',
    prerequisites: '6.1010',
    corequisites: '',
    offered_spring: true,
    communication_requirement: 'CI-M',
  },
  '6.1030': {
    subject_id: '6.1030',
    title: 'Introduction to Algorithms',
    total_units: 12,
    description: 'Introduction to mathematical modeling of computational problems.',
    prerequisites: '6.1200,6.1010',
    corequisites: '',
    offered_fall: true,
    offered_spring: true,
  },
  '6.1040': {
    subject_id: '6.1040',
    title: 'Software Design',
    total_units: 12,
    description: 'Learn to design software applications from scratch.',
    prerequisites: '6.1020',
    corequisites: '',
    offered_fall: true,
    offered_spring: true,
  },
  '6.1050': {
    subject_id: '6.1050',
    title: 'Computer Systems Engineering',
    total_units: 12,
    description: 'Topics on the engineering of computer software and hardware systems.',
    prerequisites: '6.1020,6.1030',
    corequisites: '',
    offered_fall: true,
  },
  '6.1060': {
    subject_id: '6.1060',
    title: 'Performance Engineering of Software Systems',
    total_units: 12,
    description: 'Project-based introduction to building efficient software systems.',
    prerequisites: '6.1050',
    corequisites: '',
    offered_spring: true,
  },
  '6.1070': {
    subject_id: '6.1070',
    title: 'Introduction to Robotics',
    total_units: 12,
    description: 'Introduces students to the fundamentals of robotics.',
    prerequisites: '6.1010',
    corequisites: '',
    offered_fall: true,
  },
  '6.3700': {
    subject_id: '6.3700',
    title: 'Introduction to Probability',
    total_units: 12,
    description: 'Introduction to probability theory and applications.',
    prerequisites: '18.01',
    corequisites: '',
    offered_fall: true,
    offered_spring: true,
    gir_attribute: 'REST',
  },
  '18.02': {
    subject_id: '18.02',
    title: 'Multivariable Calculus',
    total_units: 12,
    description: 'Calculus of several variables.',
    prerequisites: '18.01',
    corequisites: '',
    offered_fall: true,
    offered_spring: true,
    gir_attribute: 'REST',
  },
  '18.03': {
    subject_id: '18.03',
    title: 'Differential Equations',
    total_units: 12,
    description: 'Study of ordinary differential equations.',
    prerequisites: '18.02',
    corequisites: '',
    offered_fall: true,
    offered_spring: true,
    gir_attribute: 'REST',
  },
  '6.1800': {
    subject_id: '6.1800',
    title: 'Computer Systems Engineering',
    total_units: 12,
    description: 'Topics on the engineering of computer software and hardware systems.',
    prerequisites: '6.1020',
    corequisites: '',
    offered_fall: true,
  },
};

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ courseId: string }> }
) {
  try {
    const { courseId } = await params;
    
    if (!courseId) {
      return NextResponse.json(
        { error: 'Course ID is required' },
        { status: 400 }
      );
    }

    let data;

    if (USE_FIREROAD) {
      // Use real Fireroad API
      const url = `${FIREROAD_API_URL}/courses/lookup/${encodeURIComponent(courseId)}`;
      
      const response = await fetch(url, {
        headers: {
          'Accept': 'application/json',
        },
      });

      if (!response.ok) {
        return NextResponse.json(
          { error: `Fireroad API error: ${response.statusText}` },
          { status: response.status }
        );
      }

      data = await response.json();
    } else {
      // Use fake data
      data = FAKE_COURSES[courseId];
      
      if (!data) {
        return NextResponse.json(
          { error: `Course ${courseId} not found in fake data` },
          { status: 404 }
        );
      }
    }
    
    return NextResponse.json(data, {
      headers: {
        'Cache-Control': 'public, max-age=3600', // Cache for 1 hour
      },
    });
  } catch (error) {
    console.error('Fireroad proxy error:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to fetch course data' },
      { status: 500 }
    );
  }
}
