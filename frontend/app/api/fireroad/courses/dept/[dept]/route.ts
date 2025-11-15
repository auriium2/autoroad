/**
 * Fireroad API Proxy - Department Courses
 * Proxies department course listing requests to Fireroad API
 */

import { NextRequest, NextResponse } from 'next/server';

const FIREROAD_API_URL = 'https://fireroad.mit.edu';

export async function GET(
  req: NextRequest,
  { params }: { params: { dept: string } }
) {
  try {
    const { dept } = params;
    
    if (!dept) {
      return NextResponse.json(
        { error: 'Department is required' },
        { status: 400 }
      );
    }

    // Forward query parameters from the client request
    const searchParams = new URLSearchParams();
    req.nextUrl.searchParams.forEach((value, key) => {
      searchParams.append(key, value);
    });

    const url = `${FIREROAD_API_URL}/courses/dept/${dept}${searchParams.toString() ? '?' + searchParams : ''}`;
    
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

    const data = await response.json();
    
    return NextResponse.json(data, {
      headers: {
        'Cache-Control': 'public, max-age=3600', // Cache for 1 hour
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
