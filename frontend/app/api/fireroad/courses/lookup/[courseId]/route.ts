/**
 * Fireroad API Proxy - Course Lookup
 * Fetches individual course details with enrichment (IMDB rating)
 */

import { NextRequest, NextResponse } from 'next/server';
import { calculateIMDBRating } from '@/lib/fireroad-utils';
import type { FireroadCourse } from '@/types/fireroad';

const FIREROAD_API_URL = 'https://fireroad.mit.edu';

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

    const course: FireroadCourse = await response.json();
    
    // Add IMDB rating if not already present
    const imdb_rating = course.imdb_rating ?? calculateIMDBRating(course.rating, course.enrollment_number);
    
    return NextResponse.json({ ...course, imdb_rating }, {
      headers: {
        'Cache-Control': 'public, s-maxage=3600, stale-while-revalidate=7200', // Cache for 1 hour
      },
    });
  } catch (error) {
    console.error('Fireroad lookup proxy error:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to fetch course data' },
      { status: 500 }
    );
  }
}
