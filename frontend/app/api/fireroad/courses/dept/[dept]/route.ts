import { NextRequest, NextResponse } from 'next/server';
import { calculateIMDBRating } from '@/lib/fireroadUtils';
import { getFullCourseCatalog } from '@/lib/cache';
import type { PaginatedCoursesResponse } from '@/types/models/fireroad';

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

    const offset = parseInt(req.nextUrl.searchParams.get('offset') || '0', 10);
    const limit = parseInt(req.nextUrl.searchParams.get('limit') || '20', 10);

    // Get all courses from cache
    const allCourses = await getFullCourseCatalog();

    // Filter by department
    const deptCourses = allCourses.filter((course) =>
      course.subject_id?.startsWith(`${dept}.`)
    );

    // Enrich with IMDB rating
    const enrichedCourses = deptCourses.map(course => ({
      ...course,
      imdb_rating: course.imdb_rating ?? calculateIMDBRating(course.rating, course.enrollment_number),
    }));

    // Apply pagination
    const total = enrichedCourses.length;
    const paginatedCourses = enrichedCourses.slice(offset, offset + limit);

    const responseData: PaginatedCoursesResponse = {
      courses: paginatedCourses,
      total,
      offset,
      limit,
      has_more: offset + limit < total,
    };

    return NextResponse.json(responseData, {
      headers: {
        'Cache-Control': 'public, s-maxage=3600, stale-while-revalidate=7200',
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
