/**
 * Optimizer API Client
 * Interface to the backend optimization service
 */

import type { Marker, OptimizerNode } from '@/types';
import type { ObjectivesResponse, HardConstraintsResponse, ObjectiveConfig } from '@/types/models/optimizer';

async function optimizerFetch<T>(
  url: string,
  options: RequestInit = {}
): Promise<T> {
  const response = await fetch(url, {
    ...options,
    headers: {
      'Accept': 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(
      errorData.error || `HTTP ${response.status}: ${response.statusText}`
    );
  }

  return await response.json();
}



export interface OptimizationProgress {
  nodes: OptimizerNode[];
  step: number;
  totalSteps?: number;
  message?: string;
  objectiveValue?: number;
  solutionNumber?: number;
  costBreakdown?: Record<string, number>;
  status?: 'OPTIMAL' | 'FEASIBLE' | 'INFEASIBLE' | 'MODEL_INVALID';
  isComplete?: boolean;
  // Queue info
  jobId?: string;
  tier?: 'fast' | 'slow';
  queuePosition?: number;
  queueLength?: number;
  // Rate limit info
  fastRequestsUsed?: number;
  fastRequestsRemaining?: number;
  fastRequestsLimit?: number;
}

export const optimizerApi = {
  async checkHealth(): Promise<{ status: string; service: string }> {
    return optimizerFetch<{ status: string; service: string }>(
      '/api/optimize/health',
      { signal: AbortSignal.timeout(3000) }
    );
  },

  async getCourseCategories(
    markers: Marker[],
    requiredCourses: string[],
    maxSemesters: number,
    planningYear?: string
  ): Promise<Record<string, string[]>> {
    const requestBody = {
      markers: markers.map(m => ({
        courseId: m.courseId,
        section: m.section,
        status: m.status,
      })),
      requirements: requiredCourses.length > 0 ? requiredCourses : ['girs', 'major6-3new'],
      maxSemesters: maxSemesters || 12,
      planningYear: planningYear || undefined,
    };

    return optimizerFetch<Record<string, string[]>>(
      '/api/optimize/course-categories',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      }
    );
  },

  async getObjectives(): Promise<ObjectivesResponse> {
    return optimizerFetch<ObjectivesResponse>('/api/optimize/objectives');
  },

  async getHardConstraints(): Promise<HardConstraintsResponse> {
    return optimizerFetch<HardConstraintsResponse>('/api/optimize/constraints');
  },

  async *optimize(
    markers: Marker[],
    requiredCourses: string[],
    maxSemesters: number,
    signal?: AbortSignal,
    objectives?: ObjectiveConfig[],
    hardConstraints?: string[],
    planningYear?: string,
    lockPastSemesters?: boolean,
    requirementTiers?: Record<string, number>,
    objectiveTiers?: Record<string, number>,
    requirementSources?: Record<string, 'canonical' | 'beta'>
  ): AsyncGenerator<OptimizationProgress> {
    const requestBody = {
      markers: markers.map(m => ({
        courseId: m.courseId,
        section: m.section,
        status: m.status,
      })),
      requirements: requiredCourses.length > 0 ? requiredCourses : ['girs', 'major6-3new'],
      maxSemesters: maxSemesters || 12,
      objectives: objectives || undefined,
      hardConstraints: hardConstraints || [],
      planningYear: planningYear || undefined,
      lockPastSemesters: lockPastSemesters || false,
      requirementTiers: requirementTiers || {},
      objectiveTiers: objectiveTiers || {},
      requirementSources: requirementSources || {},
    };

    const response = await fetch('/api/optimize', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestBody),
      signal,
    });

    if (!response.ok) {
      throw new Error(`Optimization request failed: ${response.statusText}`);
    }

    if (!response.body) {
      throw new Error('Response body is null');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    try {
      while (true) {
        const { done, value } = await reader.read();

        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);

            try {
              const message = JSON.parse(data);

              if (message.type === 'job_created') {
                yield {
                  nodes: [],
                  step: 0,
                  message: message.tier === 'fast' ? 'Job queued (fast tier)...' : 'Job queued (slow tier)...',
                  jobId: message.jobId,
                  tier: message.tier,
                  fastRequestsUsed: message.fast_requests_used,
                  fastRequestsRemaining: message.fast_requests_remaining,
                  fastRequestsLimit: message.fast_requests_limit,
                };
              } else if (message.type === 'queued') {
                yield {
                  nodes: [],
                  step: 0,
                  message: message.message || (message.position === 1 ? 'Starting worker...' : `Position ${message.position} of ${message.queueLength} in queue`),
                  queuePosition: message.position,
                  queueLength: message.queueLength,
                };
              } else if (message.type === 'worker_started') {
                yield {
                  nodes: [],
                  step: 0,
                  message: 'Worker started, optimizing...',
                };
              } else if (message.type === 'progress') {
                yield {
                  nodes: [],
                  step: message.step || 0,
                  totalSteps: message.totalSteps,
                  message: message.message,
                };
              } else if (message.type === 'solution') {
                yield {
                  nodes: message.nodes || [],
                  step: message.step || 0,
                  totalSteps: message.totalSteps,
                  message: message.message,
                  objectiveValue: message.objectiveValue,
                  solutionNumber: message.solutionNumber,
                  costBreakdown: message.costBreakdown,
                };
              } else if (message.type === 'complete') {
                // Check if optimization failed or has warnings
                if (message.status === 'INFEASIBLE') {
                  const errorMsg = message.warnings?.join('. ') || 'No feasible solution found. Markers or constraints may be too strict or impossible to complete! ';
                  throw new Error(errorMsg);
                } else if (message.status === 'MODEL_INVALID') {
                  throw new Error('Invalid optimization model - please report this bug');
                } else if (message.warnings && message.warnings.length > 0) {
                  console.warn('[Optimizer] Warnings:', message.warnings);
                }

                // Yield final completion message with status
                yield {
                  nodes: [],
                  step: 0,
                  status: message.status,
                  isComplete: true,
                };

                return;
              } else if (message.type === 'error') {
                throw new Error(message.error || 'Optimization failed');
              }
            } catch (e) {
              // Re-throw intentional errors (optimization failures)
              if (e instanceof Error) {
                throw e;
              }
              // Only log actual parse errors
              console.error('Failed to parse SSE message:', data, e);
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  },
};
