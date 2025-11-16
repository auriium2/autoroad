/**
 * Optimizer API Client
 * Interface to the backend optimization service
 */

import type { Marker, OptimizerNode } from '@/types';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

export interface OptimizationConstraints {
  maxSemesters?: number;
  maxUnitsPerSemester?: number;
  maxUnitsIAP?: number;
  maxHoursPerSemester?: number;
}

export interface OptimizationProgress {
  nodes: OptimizerNode[];
  step: number;
  totalSteps?: number;
  message?: string;
  objectiveValue?: number;
  solutionNumber?: number;
}

export interface ObjectiveMetadata {
  key: string;
  name: string;
  description: string;
  category: string;
  hasParameters: boolean;
  defaultParameters: Record<string, any>;
  parameterTypes: Record<string, string>;
}

export interface ObjectiveConfig {
  key: string;
  weight: number;
  parameters: Record<string, any>;
}

export interface ObjectivesResponse {
  objectives: ObjectiveMetadata[];
  defaultConfiguration: ObjectiveConfig[];
}

export interface RequirementMetadata {
  title_no_degree?: string;
  title?: string;
  short?: string;
  medium?: string;
}

export type RequirementsListResponse = Record<string, RequirementMetadata>;

export interface RequirementNode {
  title?: string;
  'connection-type'?: 'all' | 'any';
  'threshold-desc'?: string;
  threshold?: {
    cutoff: number;
    criterion: string;
    type: string;
  };
  desc?: string;
  reqs?: RequirementNode[];
  req?: string;
  fulfilled?: boolean;
  progress?: number;
  max?: number;
  percent_fulfilled?: number;
  sat_courses?: string[];
  is_bypassed?: boolean;
}

export interface RequirementTree {
  'list-id': string;
  title: string;
  'medium-title'?: string;
  'short-title'?: string;
  'title-no-degree'?: string;
  desc?: string;
  reqs: RequirementNode[];
}

export const optimizerApi = {
  async getObjectives(): Promise<ObjectivesResponse> {
    const response = await fetch(`${BACKEND_URL}/api/optimize/objectives`);
    if (!response.ok) {
      throw new Error(`Failed to fetch objectives: ${response.statusText}`);
    }
    return response.json();
  },

  async getRequirementsList(): Promise<RequirementsListResponse> {
    const response = await fetch(`${BACKEND_URL}/api/optimize/requirements`);
    if (!response.ok) {
      throw new Error(`Failed to fetch requirements: ${response.statusText}`);
    }
    return response.json();
  },

  async getRequirement(key: string): Promise<RequirementTree> {
    const response = await fetch(`https://fireroad.mit.edu/requirements/get_json/${key}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch requirement ${key}: ${response.statusText}`);
    }
    return response.json();
  },

  async getRequirementProgress(key: string, courseIds: string[]): Promise<RequirementTree> {
    const roadData = {
      coursesOfStudy: [key],
      selectedSubjects: courseIds.map((courseId, index) => ({
        subject_id: courseId,
        title: courseId,
        units: 12,
        semester: index % 8,
      })),
      progressAssertions: {},
    };

    const response = await fetch(
      `https://fireroad.mit.edu/requirements/progress/${key}/`,
      {
        headers: {
          'Accept': 'application/json',
        },
        method: 'POST',
        body: JSON.stringify(roadData),
      }
    );
    if (!response.ok) {
      throw new Error(`Failed to fetch requirement progress for ${key}: ${response.statusText}`);
    }
    return response.json();
  },

  async *optimize(
    markers: Marker[],
    requiredCourses: string[],
    constraints?: OptimizationConstraints,
    objectives?: ObjectiveConfig[]
  ): AsyncGenerator<OptimizationProgress> {
    const requestBody = {
      markers: markers.map(m => ({
        courseId: m.courseId,
        section: m.section,
        status: m.status,
      })),
      requirements: requiredCourses.length > 0 ? requiredCourses : ['girs', 'major6-3new'],
      constraints: {
        maxSemesters: constraints?.maxSemesters || 12,
        maxUnitsPerSemester: constraints?.maxUnitsPerSemester || 60,
        maxUnitsIAP: constraints?.maxUnitsIAP || 12,
        maxHoursPerSemester: constraints?.maxHoursPerSemester || 60,
      },
      objectives: objectives || undefined,
    };

    const response = await fetch(`${BACKEND_URL}/api/optimize`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestBody),
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

              if (message.type === 'progress') {
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
                };
              } else if (message.type === 'complete') {
                return;
              } else if (message.type === 'error') {
                throw new Error(message.error || 'Optimization failed');
              }
            } catch (e) {
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
