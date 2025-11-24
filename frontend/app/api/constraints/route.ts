/**
 * Hard Constraints API Proxy
 * Proxies requests to backend optimizer service
 */

import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

export async function GET() {
  try {
    const response = await fetch(`${BACKEND_URL}/api/optimize/constraints`, {
      headers: {
        'Accept': 'application/json',
      },
      next: {
        revalidate: 24 * 60 * 60, // Cache for 24 hours (constraints are static)
      },
    });

    if (!response.ok) {
      throw new Error(`Backend API error: ${response.statusText}`);
    }

    const data = await response.json();

    return NextResponse.json(data, {
      headers: {
        'Cache-Control': 'public, s-maxage=86400, stale-while-revalidate=172800',
      },
    });
  } catch (error) {
    console.error('Constraints proxy error:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to fetch constraints' },
      { status: 500 }
    );
  }
}
