/**
 * Fireroad API Proxy - Course Search
 * Proxies search requests to Fireroad API with pagination support
 * Adds computed fields like IMDB-weighted rating
 */

import { NextRequest, NextResponse } from 'next/server';
import { enrichCourse, type FireroadCourse } from '@/lib/fireroad-utils';

const FIREROAD_API_URL = 'https://fireroad.mit.edu';

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ query: string }> }
) {
  try {
    const { query } = await params;
    
    if (!query) {
      return NextResponse.json(
        { error: 'Search query is required' },
        { status: 400 }
      );
    }

    // Get pagination params
    const offset = parseInt(req.nextUrl.searchParams.get('offset') || '0', 10);
    const limit = parseInt(req.nextUrl.searchParams.get('limit') || '20', 10);
    const department = req.nextUrl.searchParams.get('department');
    
    // Forward other query parameters to Fireroad (always request full data)
    const fireroadParams = new URLSearchParams();
    req.nextUrl.searchParams.forEach((value, key) => {
      if (key !== 'offset' && key !== 'limit' && key !== 'department') {
        fireroadParams.append(key, value);
      }
    });
    fireroadParams.set('full', 'true'); // Always get full course data

    const url = `${FIREROAD_API_URL}/courses/search/${encodeURIComponent(query)}?${fireroadParams}`;
    
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

    const allCourses: FireroadCourse[] = await response.json();
    
    // Filter out historical courses
    let filteredCourses = allCourses.filter((course) => !course.is_historical);
    
    // Filter by department if specified
    if (department && department !== 'all') {
      filteredCourses = filteredCourses.filter((course) => 
        course.subject_id?.startsWith(`${department}.`)
      );
    }
    
    // Enrich courses with computed fields (IMDB rating)
    const enrichedCourses = filteredCourses.map(enrichCourse);
    
    // Apply pagination
    const total = enrichedCourses.length;
    const paginatedCourses = enrichedCourses.slice(offset, offset + limit);
    
    return NextResponse.json({
      courses: paginatedCourses,
      total,
      offset,
      limit,
      has_more: offset + limit < total,
    }, {
      headers: {
        'Cache-Control': 'public, s-maxage=1800, stale-while-revalidate=3600', // Cache for 30 min, serve stale for 1 hour
      },
    });
  } catch (error) {
    console.error('Fireroad search proxy error:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to search courses' },
      { status: 500 }
    );
  }
}
