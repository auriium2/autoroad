/**
 * Requirements List API Proxy
 * Proxies requests to the Python backend which handles merging Fireroad + local requirements
 */

import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

export async function GET() {
  try {
    const response = await fetch(`${BACKEND_URL}/api/requirements/list`, {
      headers: {
        'Accept': 'application/json',
      },
      // next: {
      //   revalidate: 24 * 60 * 60, // Cache for 24 hours (requirements rarely change)
      // },
      //
      cache: 'no-store', // DEBUGGING
    });

    if (!response.ok) {
      throw new Error(`Backend API error: ${response.statusText}`);
    }

    const requirements = await response.json();

    return NextResponse.json(requirements, {
      headers: {
        'Cache-Control': 'no-store',
        //'Cache-Control': 'public, s-maxage=86400, stale-while-revalidate=172800', // 24h cache, 48h stale
      },
    });
  } catch (error) {
    console.error('Requirements list proxy error:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to fetch requirements list' },
      { status: 500 }
    );
  }
}
