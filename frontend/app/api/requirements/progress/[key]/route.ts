/**
 * Requirement Progress API Proxy
 * Proxies progress requests to the Python backend which handles parsing and evaluation
 */

import { NextRequest, NextResponse } from 'next/server';
import type { RequirementTree } from '@/types/models/fireroad';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ key: string }> }
) {
  try {
    const { key } = await params;

    if (!key) {
      return NextResponse.json(
        { error: 'Requirement key is required' },
        { status: 400 }
      );
    }

    const body = await req.json();
    
    // Check if beta version is requested via query parameter
    const url = new URL(req.url);
    const source = url.searchParams.get('source') || 'canonical';

    const response = await fetch(
      `${BACKEND_URL}/api/requirements/progress/${encodeURIComponent(key)}?source=${source}`,
      {
        method: 'POST',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      }
    );

    if (!response.ok) {
      throw new Error(`Backend API error: ${response.statusText}`);
    }

    const progressData: RequirementTree = await response.json();

    return NextResponse.json(progressData, {
      headers: {
        'Cache-Control': 'public, s-maxage=300, stale-while-revalidate=600',
      },
    });
  } catch (error) {
    console.error('Requirement progress proxy error:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to fetch requirement progress' },
      { status: 500 }
    );
  }
}
