/**
 * Backend Health Check Proxy
 * Proxies health checks to the Python backend so clients don't directly hit it
 */

import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

export async function GET() {
  try {
    const response = await fetch(`${BACKEND_URL}/api/optimize/health`, {
      signal: AbortSignal.timeout(3000),
      headers: {
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      return NextResponse.json(
        { status: 'unhealthy', service: 'backend', error: 'Health check failed' },
        { status: 503 }
      );
    }

    const data = await response.json();
    return NextResponse.json(data, {
      headers: {
        'Cache-Control': 'public, s-maxage=10, stale-while-revalidate=30',
      },
    });
  } catch (error) {
    console.error('Backend health check failed:', error);
    return NextResponse.json(
      { status: 'unhealthy', service: 'backend', error: 'Service unavailable' },
      { status: 503 }
    );
  }
}
