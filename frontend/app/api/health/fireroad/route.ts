/**
 * Fireroad Health Check Proxy
 * Proxies health checks to Fireroad API so clients don't directly hit it
 */

import { NextResponse } from 'next/server';

const FIREROAD_API_URL = 'https://fireroad.mit.edu';

export async function GET() {
  try {
    const response = await fetch(`${FIREROAD_API_URL}/courses/all?limit=1`, {
      signal: AbortSignal.timeout(3000),
      headers: {
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      return NextResponse.json(
        { status: 'unhealthy', service: 'fireroad', error: 'Health check failed' },
        { status: 503 }
      );
    }

    return NextResponse.json(
      { status: 'healthy', service: 'fireroad' },
      {
        headers: {
          'Cache-Control': 'public, s-maxage=10, stale-while-revalidate=30',
        },
      }
    );
  } catch (error) {
    console.error('Fireroad health check failed:', error);
    return NextResponse.json(
      { status: 'unhealthy', service: 'fireroad', error: 'Service unavailable' },
      { status: 503 }
    );
  }
}
