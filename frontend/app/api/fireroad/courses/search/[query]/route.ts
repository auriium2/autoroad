/**
 * Fireroad API Proxy - Course Search
 * Proxies search requests to Fireroad API to avoid CORS issues
 */

import { NextRequest, NextResponse } from 'next/server';

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

    // Forward query parameters from the client request
    const searchParams = new URLSearchParams();
    req.nextUrl.searchParams.forEach((value, key) => {
      searchParams.append(key, value);
    });

    const url = `${FIREROAD_API_URL}/courses/search/${encodeURIComponent(query)}?${searchParams}`;
    
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
        'Cache-Control': 'public, max-age=1800', // Cache for 30 minutes
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
