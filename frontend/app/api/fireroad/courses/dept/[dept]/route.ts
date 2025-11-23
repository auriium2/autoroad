/**
 * Fireroad API Proxy - Department Courses
 * Proxies department course listing requests with pagination support
 * Adds enrichment. I need a baddie
 */

import { NextRequest, NextResponse } from 'next/server';
import { enrichCourse, type FireroadCourse } from '@/lib/fireroad-utils';

const FIREROAD_API_URL = 'https://fireroad.mit.edu';

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ dept: string }> }
) {
  try {
    const { dept } = await params;

    if (!dept) {
      return NextResponse.json(
        { error: 'Department is required' },
        { status: 400 }
      );
    }

    // Get pagination params
    const offset = parseInt(req.nextUrl.searchParams.get('offset') || '0', 10);
    const limit = parseInt(req.nextUrl.searchParams.get('limit') || '20', 10);

    // Always request full data from Fireroad
    const url = `${FIREROAD_API_URL}/courses/dept/${dept}?full=true`;

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
    const filteredCourses = allCourses.filter((course) => !course.is_historical);

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
        'Cache-Control': 'public, s-maxage=3600, stale-while-revalidate=7200', // Cache for 1 hour, serve stale for 2 hours
      },
    });
  } catch (error) {
    console.error('Fireroad dept proxy error:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to fetch department courses' },
      { status: 500 }
    );
  }
}
