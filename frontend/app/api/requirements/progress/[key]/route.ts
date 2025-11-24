/**
 * Requirement Progress API Proxy
 * Proxies progress requests to Fireroad API or serves custom requirements from files
 */

import { NextRequest, NextResponse } from 'next/server';
import { loadCustomRequirement } from '@/lib/requirementFileParser';
import { buildRequirementTree } from '@/lib/requirementTreeBuilder';
import type { RequirementTree } from '@/types/fireroad';

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

    // Check if this is a custom requirement file
    const customRequirement = loadCustomRequirement(key);
    if (customRequirement) {
      // Parse custom requirement locally using our tree builder
      const selectedSubjects = body.selectedSubjects || [];
      
      const requirementTree = buildRequirementTree(
        key,
        customRequirement.metadata,
        customRequirement.description,
        customRequirement.content,
        selectedSubjects
      );

      return NextResponse.json(requirementTree, {
        headers: {
          'Cache-Control': 'public, s-maxage=300, stale-while-revalidate=600', // 5min cache, 10min stale
        },
      });
    }

    // Otherwise, proxy to Fireroad
    
    const response = await fetch(
      `https://fireroad.mit.edu/requirements/progress/${encodeURIComponent(key)}/`,
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
      throw new Error(`Fireroad API error: ${response.statusText}`);
    }

    const progressData: RequirementTree = await response.json();

    return NextResponse.json(progressData, {
      headers: {
        'Cache-Control': 'public, s-maxage=300, stale-while-revalidate=600', // 5min cache, 10min stale
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
