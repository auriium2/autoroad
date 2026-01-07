/**
 * Unified Parameter Search API
 * Handles searching and filtering of requirements, objectives, and constraints on the server
 */

import { NextRequest, NextResponse } from 'next/server';
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

    // Fetch all data sources in parallel (requirements now from backend)
    const [requirementsResponse, objectivesResponse, constraintsResponse] = await Promise.all([
      fetch(`${BACKEND_URL}/api/requirements/list`, {
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

    if (!requirementsResponse.ok || !objectivesResponse.ok || !constraintsResponse.ok) {
      throw new Error('Failed to fetch data from upstream services');
    }

    const allRequirements = await requirementsResponse.json() as RequirementsListResponse;
    const objectivesData = await objectivesResponse.json() as ObjectivesResponse;
    const constraintsData = await constraintsResponse.json() as HardConstraintsResponse;

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

      const displayName = metadata['medium-title'] || metadata['title-no-degree'] || metadata['short-title'] || key;
      const searchableText = [
        key,
        metadata.title,
        metadata['title-no-degree'],
        metadata['medium-title'],
        metadata['short-title'],
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
