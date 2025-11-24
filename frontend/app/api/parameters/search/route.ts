/**
 * Unified Parameter Search API
 * Handles searching and filtering of requirements, objectives, and constraints on the server
 */

import { NextRequest, NextResponse } from 'next/server';
import { loadCustomRequirements } from '@/lib/requirementFileParser';
import type { RequirementsListResponse } from '@/types/models/fireroad';
import type {
  ObjectivesResponse,
  HardConstraintsResponse,
  SearchableItem,
  SearchResults,
} from '@/types/models/optimizer';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const query = searchParams.get('q')?.toLowerCase() || '';
    const limit = parseInt(searchParams.get('limit') || '30', 10);
    const excludeRequirements = searchParams.get('excludeRequirements')?.split(',') || [];
    const excludeObjectives = searchParams.get('excludeObjectives')?.split(',') || [];
    const excludeConstraints = searchParams.get('excludeConstraints')?.split(',') || [];

    // Fetch all data sources in parallel
    const [fireroadResponse, objectivesResponse, constraintsResponse] = await Promise.all([
      fetch('https://fireroad.mit.edu/requirements/list_reqs', {
        headers: { 'Accept': 'application/json' },
        next: { revalidate: 24 * 60 * 60 },
      }),
      fetch(`${BACKEND_URL}/api/optimize/objectives`, {
        next: { revalidate: 24 * 60 * 60 },
      }),
      fetch(`${BACKEND_URL}/api/optimize/constraints`, {
        next: { revalidate: 24 * 60 * 60 },
      }),
    ]);

    if (!fireroadResponse.ok || !objectivesResponse.ok || !constraintsResponse.ok) {
      throw new Error('Failed to fetch data from upstream services');
    }

    const fireroadRequirements = await fireroadResponse.json() as RequirementsListResponse;
    const objectivesData = await objectivesResponse.json() as ObjectivesResponse;
    const constraintsData = await constraintsResponse.json() as HardConstraintsResponse;

    // Load custom requirements
    let customRequirements: RequirementsListResponse = {};
    try {
      customRequirements = loadCustomRequirements();
    } catch (error) {
      console.error('Failed to load custom requirements:', error);
    }

    // Merge requirements with source metadata
    const allRequirements: RequirementsListResponse = {};
    for (const [key, metadata] of Object.entries(fireroadRequirements)) {
      allRequirements[key] = {
        ...metadata,
        source: 'canonical' as const,
        hasBothVersions: key in customRequirements,
      };
    }
    for (const [key, metadata] of Object.entries(customRequirements)) {
      if (!(key in fireroadRequirements)) {
        allRequirements[key] = {
          ...metadata,
          source: 'beta' as const,
          hasBothVersions: false,
        };
      }
    }

    // Build searchable items
    const objectives: SearchableItem[] = [];
    const constraints: SearchableItem[] = [];
    const concentrations: SearchableItem[] = [];
    const degrees: SearchableItem[] = [];

    // Process objectives
    objectivesData.objectives.forEach(objective => {
      if (excludeObjectives.includes(objective.key)) return;

      const searchableText = [
        objective.key,
        objective.name,
        objective.description,
        objective.category,
      ].join(' ').toLowerCase();

      if (!query || searchableText.includes(query)) {
        objectives.push({
          type: 'objective',
          key: objective.key,
          displayName: objective.name,
          metadata: objective,
        });
      }
    });

    // Process constraints
    constraintsData.constraints.forEach(constraint => {
      if (excludeConstraints.includes(constraint.key)) return;

      const searchableText = [
        constraint.key,
        constraint.name,
        constraint.description,
        constraint.category,
      ].join(' ').toLowerCase();

      if (!query || searchableText.includes(query)) {
        constraints.push({
          type: 'constraint',
          key: constraint.key,
          displayName: constraint.name,
          metadata: constraint,
        });
      }
    });

    // Process requirements
    Object.entries(allRequirements).forEach(([key, metadata]) => {
      if (excludeRequirements.includes(key)) return;

      const displayName = metadata.short || metadata.medium || key;
      const searchableText = [
        key,
        metadata.title,
        metadata.title_no_degree,
        metadata.medium,
        metadata.short,
      ].filter(Boolean).join(' ').toLowerCase();

      if (!query || searchableText.includes(query)) {
        const item: SearchableItem = {
          type: 'degree',
          key,
          displayName,
          metadata,
        };

        const isConcentration = metadata.source === 'beta' && !metadata.hasBothVersions;
        if (isConcentration) {
          concentrations.push(item);
        } else {
          degrees.push(item);
        }
      }
    });

    // Apply limit to results
    const results: SearchResults = {
      objectives: objectives.slice(0, limit),
      constraints: constraints.slice(0, limit),
      concentrations: concentrations.slice(0, limit),
      degrees: degrees.slice(0, limit),
      totalCounts: {
        objectives: objectives.length,
        constraints: constraints.length,
        concentrations: concentrations.length,
        degrees: degrees.length,
      },
    };

    return NextResponse.json(results, {
      headers: {
        'Cache-Control': 'public, s-maxage=3600, stale-while-revalidate=7200',
      },
    });
  } catch (error) {
    console.error('Parameter search error:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Search failed' },
      { status: 500 }
    );
  }
}
