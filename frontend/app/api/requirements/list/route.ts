/**
 * Requirements List API Proxy
 * Proxies requests to Fireroad API and loads custom requirements from files
 */

import { NextResponse } from 'next/server';
import { loadCustomRequirements } from '@/lib/requirementFileParser';
import type { RequirementsListResponse } from '@/types/fireroad';

export async function GET() {
  try {
    // Fetch from Fireroad
    const response = await fetch('https://fireroad.mit.edu/requirements/list_reqs', {
      headers: {
        'Accept': 'application/json',
      },
      next: {
        revalidate: 24 * 60 * 60, // Cache for 24 hours (requirements rarely change)
      },
    });

    if (!response.ok) {
      throw new Error(`Fireroad API error: ${response.statusText}`);
    }

    const fireroadRequirements = await response.json();

    // Load custom requirements from filesystem
    const customRequirements = loadCustomRequirements();

    // Merge Fireroad requirements with custom requirements from files
    // Custom requirements override Fireroad if there are conflicts
    const allRequirements: RequirementsListResponse = {
      ...fireroadRequirements,
      ...customRequirements,
    };

    return NextResponse.json(allRequirements, {
      headers: {
        'Cache-Control': 'public, s-maxage=86400, stale-while-revalidate=172800', // 24h cache, 48h stale
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
