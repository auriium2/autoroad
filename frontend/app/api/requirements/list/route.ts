/**
 * Requirements List API Proxy
 * Proxies requests to Fireroad API and loads custom requirements from files
 */

import { NextResponse } from 'next/server';
import { loadCustomRequirements } from '@/lib/requirementFileParser';
import type { RequirementsListResponse, RequirementMetadata } from '@/types/models/fireroad';

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

    const fireroadRequirements = await response.json() as RequirementsListResponse;

    // Load custom requirements from filesystem
    let customRequirements: RequirementsListResponse = {};
    try {
      customRequirements = loadCustomRequirements();
    } catch (error) {
      console.error('Failed to load custom requirements:', error);
      // Continue without custom requirements
    }

    // Build the merged list with source metadata
    const allRequirements: RequirementsListResponse = {};

    // Add all Fireroad requirements, marking which have beta versions
    for (const [key, metadata] of Object.entries(fireroadRequirements)) {
      allRequirements[key] = {
        ...metadata,
        source: 'canonical' as const,
        hasBothVersions: key in customRequirements,
      };
    }

    // Add custom-only requirements (those not in Fireroad)
    for (const [key, metadata] of Object.entries(customRequirements)) {
      if (!(key in fireroadRequirements)) {
        allRequirements[key] = {
          ...metadata,
          source: 'beta' as const,
          hasBothVersions: false,
        };
      }
    }

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
