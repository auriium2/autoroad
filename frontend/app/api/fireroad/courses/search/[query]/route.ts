/**
 * Fireroad API Proxy - Course Search
 * Uses in-memory cached course catalog for filtering
 * Adds computed fields like IMDB-weighted rating
 */

import { NextRequest, NextResponse } from 'next/server';
import { calculateIMDBRating } from '@/lib/fireroadUtils';
import { getFullCourseCatalog } from '@/lib/cache';
import type { FireroadCourse, PaginatedCoursesResponse } from '@/types/models/fireroad';

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

    const offset = parseInt(req.nextUrl.searchParams.get('offset') || '0', 10);
    const limit = parseInt(req.nextUrl.searchParams.get('limit') || '20', 10);
    const department = req.nextUrl.searchParams.get('department');
    const searchType = req.nextUrl.searchParams.get('type') || 'contains';
    const sortParam = req.nextUrl.searchParams.get('sort');
    
    const girFilter = req.nextUrl.searchParams.get('gir');
    const hassFilter = req.nextUrl.searchParams.get('hass');
    const ciFilter = req.nextUrl.searchParams.get('ci');
    const levelFilter = req.nextUrl.searchParams.get('level');
    const unitsFilter = req.nextUrl.searchParams.get('units');
    const termFilter = req.nextUrl.searchParams.get('term');

    // Get all courses from cache
    const allCourses = await getFullCourseCatalog();

    // Filter by search query
    let filteredCourses = allCourses;

    // Skip query filtering if query is '*' (wildcard - return all courses)
    if (query !== '*') {
      const searchLower = query.toLowerCase();
      if (searchType === 'starts') {
        filteredCourses = filteredCourses.filter((course) =>
          course.subject_id?.toLowerCase().startsWith(searchLower) ||
          course.title?.toLowerCase().startsWith(searchLower)
        );
      } else if (searchType === 'contains') {
        filteredCourses = filteredCourses.filter((course) =>
          course.subject_id?.toLowerCase().includes(searchLower) ||
          course.title?.toLowerCase().includes(searchLower)
        );
      }
    }
    
    // Apply filters
    if (department && department !== 'all') {
      filteredCourses = filteredCourses.filter((course) => 
        course.subject_id?.startsWith(`${department}.`)
      );
    }
    
    if (girFilter) {
      filteredCourses = filteredCourses.filter((course) => {
        if (girFilter === 'LAB') return course.gir_attribute?.includes('LAB');
        if (girFilter === 'REST') return course.gir_attribute?.includes('REST');
        return true;
      });
    }
    
    if (hassFilter) {
      filteredCourses = filteredCourses.filter((course) => 
        course.hass_attribute?.includes(hassFilter)
      );
    }
    
    if (ciFilter) {
      filteredCourses = filteredCourses.filter((course) => {
        if (ciFilter === 'CI-H') return course.communication_requirement?.includes('CI-H');
        if (ciFilter === 'CI-HW') return course.communication_requirement?.includes('CI-HW');
        if (ciFilter === 'NONE') return !course.communication_requirement;
        return true;
      });
    }
    
    if (levelFilter) {
      filteredCourses = filteredCourses.filter((course) => {
        if (levelFilter === 'UG') return course.level === 'U';
        if (levelFilter === 'G') return course.level === 'G';
        return true;
      });
    }
    
    if (unitsFilter) {
      filteredCourses = filteredCourses.filter((course) => {
        const units = course.total_units || 0;
        if (unitsFilter === '<6') return units < 6;
        if (unitsFilter === '6') return units === 6;
        if (unitsFilter === '9') return units === 9;
        if (unitsFilter === '12') return units === 12;
        if (unitsFilter === '15') return units === 15;
        if (unitsFilter === '6+') return units >= 6;
        return true;
      });
    }
    
    if (termFilter) {
      filteredCourses = filteredCourses.filter((course) => {
        if (termFilter === 'FA') return course.offered_fall;
        if (termFilter === 'IAP') return course.offered_IAP;
        if (termFilter === 'SP') return course.offered_spring;
        return true;
      });
    }
    
    // Enrich courses with computed fields (IMDB rating)
    const enrichedCourses = filteredCourses.map(course => ({
      ...course,
      imdb_rating: course.imdb_rating ?? calculateIMDBRating(course.rating, course.enrollment_number),
    }));
    
    // Apply sorting
    let sortedCourses = enrichedCourses;
    if (sortParam) {
      sortedCourses = [...enrichedCourses].sort((a, b) => {
        switch (sortParam) {
          case 'imdb-rating-asc':
            return (a.imdb_rating ?? 0) - (b.imdb_rating ?? 0);
          case 'imdb-rating-desc':
            return (b.imdb_rating ?? 0) - (a.imdb_rating ?? 0);
          case 'units-asc':
            return (a.total_units ?? 0) - (b.total_units ?? 0);
          case 'units-desc':
            return (b.total_units ?? 0) - (a.total_units ?? 0);
          case 'enrollment-asc':
            return (a.enrollment_number ?? 0) - (b.enrollment_number ?? 0);
          case 'enrollment-desc':
            return (b.enrollment_number ?? 0) - (a.enrollment_number ?? 0);
          default:
            return 0;
        }
      });
    }
    
    // Apply pagination
    const total = sortedCourses.length;
    const paginatedCourses = sortedCourses.slice(offset, offset + limit);
    
    const responseData: PaginatedCoursesResponse = {
      courses: paginatedCourses,
      total,
      offset,
      limit,
      has_more: offset + limit < total,
    };
    
    return NextResponse.json(responseData, {
      headers: {
        'Cache-Control': 'public, s-maxage=1800, stale-while-revalidate=3600',
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
