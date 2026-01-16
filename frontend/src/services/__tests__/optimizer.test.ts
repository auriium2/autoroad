/**
 * Tests for optimizer API client
 * Tests streaming responses, API calls, and error handling
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { optimizerApi, type OptimizationProgress } from '../optimizer';
import type { Marker } from '@/types';

// Mock global fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

// Helper to create a mock readable stream from SSE data
function createMockSSEStream(events: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  let index = 0;
  
  return new ReadableStream({
    pull(controller) {
      if (index < events.length) {
        controller.enqueue(encoder.encode(events[index] + '\n'));
        index++;
      } else {
        controller.close();
      }
    },
  });
}

// Helper to create mock response
function createMockResponse(options: {
  ok?: boolean;
  status?: number;
  statusText?: string;
  json?: any;
  body?: ReadableStream<Uint8Array>;
}): Response {
  return {
    ok: options.ok ?? true,
    status: options.status ?? 200,
    statusText: options.statusText ?? 'OK',
    json: vi.fn().mockResolvedValue(options.json ?? {}),
    body: options.body ?? null,
    headers: new Headers(),
  } as unknown as Response;
}

describe('optimizerApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('checkHealth', () => {
    it('should return health status', async () => {
      const healthResponse = { status: 'healthy', service: 'optimizer' };
      mockFetch.mockResolvedValue(createMockResponse({ json: healthResponse }));
      
      const result = await optimizerApi.checkHealth();
      
      expect(result).toEqual(healthResponse);
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/optimize/health',
        expect.objectContaining({
          headers: expect.objectContaining({ Accept: 'application/json' }),
        })
      );
    });

    it('should throw on HTTP error', async () => {
      mockFetch.mockResolvedValue(createMockResponse({
        ok: false,
        status: 503,
        statusText: 'Service Unavailable',
        json: { error: 'Service down' },
      }));
      
      await expect(optimizerApi.checkHealth()).rejects.toThrow('Service down');
    });
  });

  describe('getObjectives', () => {
    it('should fetch objectives', async () => {
      const objectivesResponse = {
        objectives: [
          { key: 'minimize_units', name: 'Minimize Units', hasParameters: false },
        ],
        defaultConfiguration: [{ key: 'minimize_units', parameters: {} }],
      };
      mockFetch.mockResolvedValue(createMockResponse({ json: objectivesResponse }));
      
      const result = await optimizerApi.getObjectives();
      
      expect(result).toEqual(objectivesResponse);
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/optimize/objectives',
        expect.any(Object)
      );
    });
  });

  describe('getHardConstraints', () => {
    it('should fetch hard constraints', async () => {
      const constraintsResponse = {
        constraints: [
          { key: 'no_fall_classes', name: 'No Fall Classes', category: 'scheduling' },
        ],
      };
      mockFetch.mockResolvedValue(createMockResponse({ json: constraintsResponse }));
      
      const result = await optimizerApi.getHardConstraints();
      
      expect(result).toEqual(constraintsResponse);
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/optimize/constraints',
        expect.any(Object)
      );
    });
  });

  describe('getCourseCategories', () => {
    it('should fetch course categories with correct request body', async () => {
      const markers: Marker[] = [
        { uuid: 'marker_1', courseId: '6.100A', section: 3, status: 'pin' },
      ];
      const categoriesResponse = { '6.100A': ['major6-3new/core'] };
      mockFetch.mockResolvedValue(createMockResponse({ json: categoriesResponse }));
      
      const result = await optimizerApi.getCourseCategories(
        markers,
        ['girs', 'major6-3new'],
        12,
        '2024-2025'
      );
      
      expect(result).toEqual(categoriesResponse);
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/optimize/course-categories',
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
          body: JSON.stringify({
            markers: [{ courseId: '6.100A', section: 3, status: 'pin' }],
            requirements: ['girs', 'major6-3new'],
            maxSemesters: 12,
            planningYear: '2024-2025',
          }),
        })
      );
    });

    it('should use default requirements when none provided', async () => {
      mockFetch.mockResolvedValue(createMockResponse({ json: {} }));
      
      await optimizerApi.getCourseCategories([], [], 12);
      
      const callBody = JSON.parse(mockFetch.mock.calls[0][1].body);
      expect(callBody.requirements).toEqual(['girs', 'major6-3new']);
    });
  });

  describe('optimize', () => {
    it('should stream progress updates', async () => {
      const sseEvents = [
        'data: {"type":"progress","step":1,"message":"Initializing..."}',
        'data: {"type":"progress","step":2,"message":"Building model..."}',
        'data: {"type":"complete","status":"OPTIMAL"}',
      ];
      
      mockFetch.mockResolvedValue(createMockResponse({
        body: createMockSSEStream(sseEvents),
      }));
      
      const markers: Marker[] = [];
      const progress: OptimizationProgress[] = [];
      
      for await (const p of optimizerApi.optimize(markers, ['girs'], 12)) {
        progress.push(p);
      }
      
      expect(progress).toHaveLength(3);
      expect(progress[0]).toMatchObject({ step: 1, message: 'Initializing...' });
      expect(progress[1]).toMatchObject({ step: 2, message: 'Building model...' });
      expect(progress[2]).toMatchObject({ status: 'OPTIMAL', isComplete: true });
    });

    it('should yield solution nodes', async () => {
      const sseEvents = [
        'data: {"type":"solution","step":1,"nodes":[{"courseId":"6.100A","section":3,"units":12}],"solutionNumber":1}',
        'data: {"type":"complete","status":"OPTIMAL"}',
      ];
      
      mockFetch.mockResolvedValue(createMockResponse({
        body: createMockSSEStream(sseEvents),
      }));
      
      const progress: OptimizationProgress[] = [];
      
      for await (const p of optimizerApi.optimize([], ['girs'], 12)) {
        progress.push(p);
      }
      
      expect(progress[0].nodes).toHaveLength(1);
      expect(progress[0].nodes[0]).toMatchObject({
        courseId: '6.100A',
        section: 3,
        units: 12,
      });
      expect(progress[0].solutionNumber).toBe(1);
    });

    it('should include cost breakdown in solution', async () => {
      const costBreakdown = { total_units: 48, difficulty: 10 };
      const sseEvents = [
        `data: {"type":"solution","step":1,"nodes":[],"costBreakdown":${JSON.stringify(costBreakdown)}}`,
        'data: {"type":"complete","status":"OPTIMAL"}',
      ];
      
      mockFetch.mockResolvedValue(createMockResponse({
        body: createMockSSEStream(sseEvents),
      }));
      
      const progress: OptimizationProgress[] = [];
      
      for await (const p of optimizerApi.optimize([], ['girs'], 12)) {
        progress.push(p);
      }
      
      expect(progress[0].costBreakdown).toEqual(costBreakdown);
    });

    it('should throw on INFEASIBLE status', async () => {
      const sseEvents = [
        'data: {"type":"complete","status":"INFEASIBLE","warnings":["No solution possible"]}',
      ];
      
      mockFetch.mockResolvedValue(createMockResponse({
        body: createMockSSEStream(sseEvents),
      }));
      
      await expect(async () => {
        for await (const _ of optimizerApi.optimize([], ['girs'], 12)) {
          // consume
        }
      }).rejects.toThrow('No solution possible');
    });

    it('should throw on MODEL_INVALID status', async () => {
      const sseEvents = [
        'data: {"type":"complete","status":"MODEL_INVALID"}',
      ];
      
      mockFetch.mockResolvedValue(createMockResponse({
        body: createMockSSEStream(sseEvents),
      }));
      
      await expect(async () => {
        for await (const _ of optimizerApi.optimize([], ['girs'], 12)) {
          // consume
        }
      }).rejects.toThrow('Invalid optimization model');
    });

    it('should throw on error message', async () => {
      const sseEvents = [
        'data: {"type":"error","error":"Internal server error"}',
      ];
      
      mockFetch.mockResolvedValue(createMockResponse({
        body: createMockSSEStream(sseEvents),
      }));
      
      await expect(async () => {
        for await (const _ of optimizerApi.optimize([], ['girs'], 12)) {
          // consume
        }
      }).rejects.toThrow('Internal server error');
    });

    it('should throw on HTTP error', async () => {
      mockFetch.mockResolvedValue(createMockResponse({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
      }));
      
      await expect(async () => {
        for await (const _ of optimizerApi.optimize([], ['girs'], 12)) {
          // consume
        }
      }).rejects.toThrow('Optimization request failed');
    });

    it('should throw when response body is null', async () => {
      mockFetch.mockResolvedValue(createMockResponse({ body: null }));
      
      await expect(async () => {
        for await (const _ of optimizerApi.optimize([], ['girs'], 12)) {
          // consume
        }
      }).rejects.toThrow('Response body is null');
    });

    it('should send correct request body', async () => {
      const sseEvents = ['data: {"type":"complete","status":"OPTIMAL"}'];
      mockFetch.mockResolvedValue(createMockResponse({
        body: createMockSSEStream(sseEvents),
      }));
      
      const markers: Marker[] = [
        { uuid: 'marker_1', courseId: '6.100A', section: 3, status: 'pin' },
        { uuid: 'marker_2', courseId: '18.01', section: 1, status: 'banish' },
      ];
      
      for await (const _ of optimizerApi.optimize(
        markers,
        ['girs', 'major6-3new'],
        12,
        undefined,
        [{ key: 'minimize_units', parameters: {} }],
        ['no_fall'],
        '2024-2025',
        true,
        { 'girs': 2 },
        { 'minimize_units': 1 },
        { 'girs': 'beta' }
      )) {
        // consume
      }
      
      const callBody = JSON.parse(mockFetch.mock.calls[0][1].body);
      expect(callBody).toEqual({
        markers: [
          { courseId: '6.100A', section: 3, status: 'pin' },
          { courseId: '18.01', section: 1, status: 'banish' },
        ],
        requirements: ['girs', 'major6-3new'],
        maxSemesters: 12,
        objectives: [{ key: 'minimize_units', parameters: {} }],
        hardConstraints: ['no_fall'],
        planningYear: '2024-2025',
        lockPastSemesters: true,
        requirementTiers: { 'girs': 2 },
        objectiveTiers: { 'minimize_units': 1 },
        requirementSources: { 'girs': 'beta' },
      });
    });

    it('should use default values for optional parameters', async () => {
      const sseEvents = ['data: {"type":"complete","status":"OPTIMAL"}'];
      mockFetch.mockResolvedValue(createMockResponse({
        body: createMockSSEStream(sseEvents),
      }));
      
      for await (const _ of optimizerApi.optimize([], [], 0)) {
        // consume
      }
      
      const callBody = JSON.parse(mockFetch.mock.calls[0][1].body);
      expect(callBody.requirements).toEqual(['girs', 'major6-3new']);
      expect(callBody.maxSemesters).toBe(12);
      expect(callBody.hardConstraints).toEqual([]);
      expect(callBody.lockPastSemesters).toBe(false);
      expect(callBody.requirementTiers).toEqual({});
      expect(callBody.objectiveTiers).toEqual({});
      expect(callBody.requirementSources).toEqual({});
    });

    it('should pass abort signal to fetch', async () => {
      const sseEvents = ['data: {"type":"complete","status":"OPTIMAL"}'];
      mockFetch.mockResolvedValue(createMockResponse({
        body: createMockSSEStream(sseEvents),
      }));
      
      const abortController = new AbortController();
      
      for await (const _ of optimizerApi.optimize([], ['girs'], 12, abortController.signal)) {
        // consume
      }
      
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/optimize',
        expect.objectContaining({
          signal: abortController.signal,
        })
      );
    });

    it('should handle multi-chunk SSE data', async () => {
      // Simulate data split across multiple chunks
      const encoder = new TextEncoder();
      let chunkIndex = 0;
      const chunks = [
        'data: {"type":"pro',  // partial
        'gress","step":1}\n',  // continuation
        'data: {"type":"complete","status":"OPTIMAL"}\n',
      ];
      
      const stream = new ReadableStream({
        pull(controller) {
          if (chunkIndex < chunks.length) {
            controller.enqueue(encoder.encode(chunks[chunkIndex]));
            chunkIndex++;
          } else {
            controller.close();
          }
        },
      });
      
      mockFetch.mockResolvedValue(createMockResponse({ body: stream }));
      
      const progress: OptimizationProgress[] = [];
      
      for await (const p of optimizerApi.optimize([], ['girs'], 12)) {
        progress.push(p);
      }
      
      expect(progress).toHaveLength(2);
      expect(progress[0]).toMatchObject({ step: 1 });
    });
  });
});
