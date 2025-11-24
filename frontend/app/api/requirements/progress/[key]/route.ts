/**
 * Requirement Progress API Proxy
 * Proxies progress requests to Fireroad API or serves custom requirements from files
 */

import { NextRequest, NextResponse } from 'next/server';
import { loadCustomRequirement } from '@/lib/requirementFileParser';
import { buildRequirementTree } from '@/lib/requirementTreeBuilder';
import type { RequirementTree } from '@/types/models/fireroad';

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
    const source = url.searchParams.get('source') || 'canonical'; // 'canonical' or 'beta'

    // If beta version is requested, serve custom requirement
    if (source === 'beta') {
      let customRequirement = null;
      try {
        customRequirement = loadCustomRequirement(key);
      } catch (error) {
        console.error(`Failed to load custom requirement ${key}:`, error);
      }

      if (customRequirement) {
        try {
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
              'Cache-Control': 'public, s-maxage=300, stale-while-revalidate=600',
            },
          });
        } catch (error) {
          console.error(`Failed to build requirement tree for ${key}:`, error);
          return NextResponse.json(
            { error: error instanceof Error ? error.message : 'Failed to build requirement tree' },
            { status: 500 }
          );
        }
      }
      // If beta requested but no custom file, fall through to Fireroad
    }

    // For canonical version, try Fireroad (and fall back to custom if Fireroad fails)
    try {
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
          'Cache-Control': 'public, s-maxage=300, stale-while-revalidate=600',
        },
      });
    } catch (fireroadError) {
      // Fireroad failed, try custom requirement as fallback
      console.log(`Fireroad failed for ${key}, trying custom requirement`);
      
      let customRequirement = null;
      try {
        customRequirement = loadCustomRequirement(key);
      } catch (error) {
        console.error(`Failed to load custom requirement ${key}:`, error);
      }

      if (customRequirement) {
        try {
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
              'Cache-Control': 'public, s-maxage=300, stale-while-revalidate=600',
            },
          });
        } catch (error) {
          console.error(`Failed to build requirement tree for ${key}:`, error);
        }
      }

      // Both Fireroad and custom failed
      console.error('Requirement progress proxy error:', fireroadError);
      return NextResponse.json(
        { error: fireroadError instanceof Error ? fireroadError.message : 'Failed to fetch requirement progress' },
        { status: 500 }
      );
    }
  } catch (error) {
    console.error('Unexpected error in requirement progress:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Unexpected error' },
      { status: 500 }
    );
  }
}
