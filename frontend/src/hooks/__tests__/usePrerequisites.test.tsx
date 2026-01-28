/**
 * Tests for usePrerequisites hooks
 * Tests prerequisite fetching, edge computation, and missing prerequisite detection
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import * as React from 'react';
import {
  usePrerequisiteCourseIds,
  usePrerequisiteString,
  useCheckCoursePlacement,
  usePrerequisiteEdges,
  useMissingPrerequisites,
} from '../usePrerequisites';
import type { CourseNode } from '@/types';

// Mock dependencies
vi.mock('@/services/fireroad', () => ({
  fireroadApi: {
    getCourseDetails: vi.fn(),
  },
}));

vi.mock('@/lib/cache', () => ({
  getCachedPrereqTree: vi.fn((str: string) => {
    // Simple mock parser that returns the string as a course reference
    if (!str) return { type: 'course', id: '' };
    if (str.includes('/')) {
      const parts = str.split('/');
      return { type: 'or', children: parts.map(p => ({ type: 'course', id: p.trim() })) };
    }
    if (str.includes(',')) {
      const parts = str.split(',');
      return { type: 'and', children: parts.map(p => ({ type: 'course', id: p.trim() })) };
    }
    return { type: 'course', id: str.trim() };
  }),
}));

vi.mock('@/lib/prerequisites', () => ({
  extractCourseIds: vi.fn((tree: any) => {
    if (!tree) return [];
    if (tree.type === 'course' && tree.id) return [tree.id];
    if (tree.children) {
      return tree.children.flatMap((c: any) => {
        if (c.type === 'course' && c.id) return [c.id];
        return [];
      });
    }
    return [];
  }),
  evaluatePrerequisites: vi.fn((tree: any, taken: string[], _detailed?: boolean, _checkGir?: boolean, _tags?: Map<string, string[]>, _equivalencies?: Map<string, string[]>) => {
    if (!tree || tree.type === 'course' && !tree.id) {
      return { satisfied: true, unsatisfiedReasons: [], matchedCourses: [] };
    }
    
    if (tree.type === 'course') {
      const satisfied = taken.includes(tree.id);
      return {
        satisfied,
        unsatisfiedReasons: satisfied ? [] : [tree.id],
        matchedCourses: satisfied ? [tree.id] : [],
      };
    }
    
    if (tree.type === 'and') {
      const results = tree.children.map((c: any) => {
        if (c.type === 'course') {
          return taken.includes(c.id);
        }
        return true;
      });
      const satisfied = results.every(Boolean);
      const missing = tree.children
        .filter((c: any) => c.type === 'course' && !taken.includes(c.id))
        .map((c: any) => c.id);
      const matched = tree.children
        .filter((c: any) => c.type === 'course' && taken.includes(c.id))
        .map((c: any) => c.id);
      return { satisfied, unsatisfiedReasons: missing, matchedCourses: matched };
    }
    
    if (tree.type === 'or') {
      const matched = tree.children
        .filter((c: any) => c.type === 'course' && taken.includes(c.id))
        .map((c: any) => c.id);
      const satisfied = matched.length > 0;
      const missing = satisfied ? [] : tree.children.map((c: any) => c.id);
      return { satisfied, unsatisfiedReasons: missing, matchedCourses: matched };
    }
    
    return { satisfied: true, unsatisfiedReasons: [], matchedCourses: [] };
  }),
}));

import { fireroadApi } from '@/services/fireroad';

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe('usePrerequisiteCourseIds', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should return prerequisite course IDs', async () => {
    vi.mocked(fireroadApi.getCourseDetails).mockResolvedValue({
      subject_id: '6.006',
      title: 'Intro to Algorithms',
      prerequisites: '6.100A',
    } as any);

    const { result } = renderHook(() => usePrerequisiteCourseIds('6.006'), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toContain('6.100A');
  });

  it('should return empty array when no prerequisites', async () => {
    vi.mocked(fireroadApi.getCourseDetails).mockResolvedValue({
      subject_id: '18.01',
      title: 'Calculus',
      prerequisites: '',
    } as any);

    const { result } = renderHook(() => usePrerequisiteCourseIds('18.01'), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([]);
  });

  it('should handle API errors gracefully', async () => {
    vi.mocked(fireroadApi.getCourseDetails).mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(() => usePrerequisiteCourseIds('invalid'), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([]);
  });
});

describe('usePrerequisiteString', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should return prerequisite string', async () => {
    vi.mocked(fireroadApi.getCourseDetails).mockResolvedValue({
      subject_id: '6.006',
      prerequisites: '6.100A, 6.042',
    } as any);

    const { result } = renderHook(() => usePrerequisiteString('6.006'), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toBe('6.100A, 6.042');
  });

  it('should return empty string for null courseId', async () => {
    const { result } = renderHook(() => usePrerequisiteString(null), {
      wrapper: createWrapper(),
    });

    expect(result.current.data).toBeUndefined();
    expect(fireroadApi.getCourseDetails).not.toHaveBeenCalled();
  });
});

describe('useCheckCoursePlacement', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should return satisfied when prerequisites are met', async () => {
    vi.mocked(fireroadApi.getCourseDetails).mockResolvedValue({
      subject_id: '6.006',
      prerequisites: '6.100A',
    } as any);

    const allNodes: CourseNode[] = [
      { uuid: 'node_1', courseId: '6.100A', section: 1, userControlled: true },
      { uuid: 'node_2', courseId: '6.006', section: 3, userControlled: true },
    ];

    const { result } = renderHook(
      () => useCheckCoursePlacement('6.006', 3, allNodes),
      { wrapper: createWrapper() }
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.satisfied).toBe(true);
    expect(result.current.data?.missing).toEqual([]);
  });

  it('should return unsatisfied when prerequisites are not met', async () => {
    vi.mocked(fireroadApi.getCourseDetails).mockResolvedValue({
      subject_id: '6.006',
      prerequisites: '6.100A',
    } as any);

    const allNodes: CourseNode[] = [
      { uuid: 'node_1', courseId: '6.006', section: 1, userControlled: true },
    ];

    const { result } = renderHook(
      () => useCheckCoursePlacement('6.006', 1, allNodes),
      { wrapper: createWrapper() }
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.satisfied).toBe(false);
    expect(result.current.data?.missing).toContain('6.100A');
  });

  it('should return satisfied when no prerequisites', async () => {
    vi.mocked(fireroadApi.getCourseDetails).mockResolvedValue({
      subject_id: '18.01',
      prerequisites: '',
    } as any);

    const { result } = renderHook(
      () => useCheckCoursePlacement('18.01', 1, []),
      { wrapper: createWrapper() }
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.satisfied).toBe(true);
  });
});

describe('usePrerequisiteEdges', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should compute edges between courses with prerequisites', async () => {
    vi.mocked(fireroadApi.getCourseDetails)
      .mockResolvedValueOnce({
        subject_id: '6.100A',
        prerequisites: '',
      } as any)
      .mockResolvedValueOnce({
        subject_id: '6.006',
        prerequisites: '6.100A',
      } as any);

    const nodes: CourseNode[] = [
      { uuid: 'node_1', courseId: '6.100A', section: 1, userControlled: true },
      { uuid: 'node_2', courseId: '6.006', section: 3, userControlled: true },
    ];

    const { result } = renderHook(() => usePrerequisiteEdges(nodes), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    
    const edges = result.current.data?.edges ?? [];
    expect(edges).toHaveLength(1);
    expect(edges[0]).toEqual({ fromUuid: 'node_1', toUuid: 'node_2' });
  });

  it('should return empty edges for empty nodes', async () => {
    const { result } = renderHook(() => usePrerequisiteEdges([]), {
      wrapper: createWrapper(),
    });

    // Query is disabled for empty nodes
    expect(result.current.data).toBeUndefined();
  });

  it('should not create edges for courses in same or earlier section', async () => {
    vi.mocked(fireroadApi.getCourseDetails)
      .mockResolvedValueOnce({
        subject_id: '6.100A',
        prerequisites: '',
      } as any)
      .mockResolvedValueOnce({
        subject_id: '6.006',
        prerequisites: '6.100A',
      } as any);

    const nodes: CourseNode[] = [
      { uuid: 'node_1', courseId: '6.100A', section: 3, userControlled: true },
      { uuid: 'node_2', courseId: '6.006', section: 1, userControlled: true }, // Earlier section
    ];

    const { result } = renderHook(() => usePrerequisiteEdges(nodes), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    
    const edges = result.current.data?.edges ?? [];
    expect(edges).toHaveLength(0);
  });
});

describe('useMissingPrerequisites', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should identify missing prerequisites', async () => {
    vi.mocked(fireroadApi.getCourseDetails)
      .mockResolvedValueOnce({
        subject_id: '6.006',
        prerequisites: '6.100A',
      } as any);

    const nodes: CourseNode[] = [
      { uuid: 'node_1', courseId: '6.006', section: 1, userControlled: true },
    ];

    const { result } = renderHook(() => useMissingPrerequisites(nodes), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    
    const missing = result.current.data?.get('node_1') ?? [];
    expect(missing).toContain('6.100A');
  });

  it('should return empty array when prerequisites are satisfied', async () => {
    vi.mocked(fireroadApi.getCourseDetails)
      .mockResolvedValueOnce({
        subject_id: '6.100A',
        prerequisites: '',
      } as any)
      .mockResolvedValueOnce({
        subject_id: '6.006',
        prerequisites: '6.100A',
      } as any);

    const nodes: CourseNode[] = [
      { uuid: 'node_1', courseId: '6.100A', section: 1, userControlled: true },
      { uuid: 'node_2', courseId: '6.006', section: 3, userControlled: true },
    ];

    const { result } = renderHook(() => useMissingPrerequisites(nodes), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    
    const missing = result.current.data?.get('node_2') ?? [];
    expect(missing).toEqual([]);
  });

  it('should skip prerequisite check for override nodes', async () => {
    vi.mocked(fireroadApi.getCourseDetails)
      .mockResolvedValueOnce({
        subject_id: '6.006',
        prerequisites: '6.100A',
      } as any);

    const nodes: CourseNode[] = [
      { uuid: 'node_1', courseId: '6.006', section: 1, userControlled: true, nodeStatus: 'override' },
    ];

    const { result } = renderHook(() => useMissingPrerequisites(nodes), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    
    const missing = result.current.data?.get('node_1') ?? [];
    expect(missing).toEqual([]);
  });

  it('should skip prerequisite check for ASE section (-1)', async () => {
    vi.mocked(fireroadApi.getCourseDetails)
      .mockResolvedValueOnce({
        subject_id: '6.006',
        prerequisites: '6.100A',
      } as any);

    const nodes: CourseNode[] = [
      { uuid: 'node_1', courseId: '6.006', section: -1, userControlled: true },
    ];

    const { result } = renderHook(() => useMissingPrerequisites(nodes), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    
    const missing = result.current.data?.get('node_1') ?? [];
    expect(missing).toEqual([]);
  });

  it('should skip prerequisite check for Must Take section (-2)', async () => {
    vi.mocked(fireroadApi.getCourseDetails)
      .mockResolvedValueOnce({
        subject_id: '6.006',
        prerequisites: '6.100A',
      } as any);

    const nodes: CourseNode[] = [
      { uuid: 'node_1', courseId: '6.006', section: -2, userControlled: true },
    ];

    const { result } = renderHook(() => useMissingPrerequisites(nodes), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    
    const missing = result.current.data?.get('node_1') ?? [];
    expect(missing).toEqual([]);
  });

  it('should return empty map for empty nodes', async () => {
    const { result } = renderHook(() => useMissingPrerequisites([]), {
      wrapper: createWrapper(),
    });

    // Query is disabled for empty nodes
    expect(result.current.data).toBeUndefined();
  });
});
