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
    
    // Get filter params (these are handled server-side, not forwarded to Fireroad)
    const girFilter = req.nextUrl.searchParams.get('gir');
    const hassFilter = req.nextUrl.searchParams.get('hass');
    const ciFilter = req.nextUrl.searchParams.get('ci');
    const levelFilter = req.nextUrl.searchParams.get('level');
    const unitsFilter = req.nextUrl.searchParams.get('units');
    const termFilter = req.nextUrl.searchParams.get('term');
    
    // Forward other query parameters to Fireroad (always request full data)
    const fireroadParams = new URLSearchParams();
    const filterParams = new Set(['offset', 'limit', 'department', 'gir', 'hass', 'ci', 'level', 'units', 'term']);
    req.nextUrl.searchParams.forEach((value, key) => {
      if (!filterParams.has(key)) {
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
    
    // Apply server-side filters
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
