/**
 * Tests for cache utilities
 * Tests course prefetching and requirement extraction
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { QueryClient } from '@tanstack/react-query';
import {
  prefetchCourses,
  extractCoursesFromRequirement,
} from '../cache';

// Mock dependencies
vi.mock('@/services/fireroad', () => ({
  fireroadApi: {
    getCourseDetails: vi.fn(),
    getCourseDetailsBatch: vi.fn(),
    getRequirementProgress: vi.fn(),
  },
}));

import { fireroadApi } from '@/services/fireroad';

describe('Course Prefetching', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });
  });

  afterEach(() => {
    queryClient.clear();
  });

  describe('prefetchCourses', () => {
    it('should prefetch course details for valid course IDs using batch endpoint', async () => {
      vi.mocked(fireroadApi.getCourseDetailsBatch).mockResolvedValue({
        '6.100A': { subject_id: '6.100A', title: 'Intro to CS' } as any,
        '18.01': { subject_id: '18.01', title: 'Calculus' } as any,
      });

      await prefetchCourses(queryClient, ['6.100A', '18.01']);

      expect(fireroadApi.getCourseDetailsBatch).toHaveBeenCalledTimes(1);
      expect(fireroadApi.getCourseDetailsBatch).toHaveBeenCalledWith(['6.100A', '18.01']);
    });

    it('should deduplicate course IDs', async () => {
      vi.mocked(fireroadApi.getCourseDetailsBatch).mockResolvedValue({});

      await prefetchCourses(queryClient, ['6.100A', '6.100A', '18.01', '18.01']);

      expect(fireroadApi.getCourseDetailsBatch).toHaveBeenCalledTimes(1);
      expect(vi.mocked(fireroadApi.getCourseDetailsBatch).mock.calls[0][0]).toHaveLength(2);
    });

    it('should filter out GIR placeholders', async () => {
      vi.mocked(fireroadApi.getCourseDetailsBatch).mockResolvedValue({});

      await prefetchCourses(queryClient, ['GIR:CAL1', '6.100A', 'GIR:BIOL']);

      expect(fireroadApi.getCourseDetailsBatch).toHaveBeenCalledWith(['6.100A']);
    });

    it('should filter out HASS placeholders', async () => {
      vi.mocked(fireroadApi.getCourseDetailsBatch).mockResolvedValue({});

      await prefetchCourses(queryClient, ['HASS-A', 'HASS-S', '6.100A']);

      expect(fireroadApi.getCourseDetailsBatch).toHaveBeenCalledWith(['6.100A']);
    });

    it('should filter out CI placeholders', async () => {
      vi.mocked(fireroadApi.getCourseDetailsBatch).mockResolvedValue({});

      await prefetchCourses(queryClient, ['CI-H', 'CI-M', '6.100A']);

      expect(fireroadApi.getCourseDetailsBatch).toHaveBeenCalledWith(['6.100A']);
    });

    it('should filter out REST placeholder', async () => {
      vi.mocked(fireroadApi.getCourseDetailsBatch).mockResolvedValue({});

      await prefetchCourses(queryClient, ['REST', '6.100A']);

      expect(fireroadApi.getCourseDetailsBatch).toHaveBeenCalledWith(['6.100A']);
    });

    it('should silently handle prefetch failures', async () => {
      vi.mocked(fireroadApi.getCourseDetailsBatch).mockRejectedValue(new Error('Network error'));

      // Should not throw
      await expect(prefetchCourses(queryClient, ['6.100A', '18.01'])).resolves.toBeUndefined();
    });

    it('should handle empty array', async () => {
      await prefetchCourses(queryClient, []);

      expect(fireroadApi.getCourseDetailsBatch).not.toHaveBeenCalled();
    });

    it('should populate individual query cache entries', async () => {
      vi.mocked(fireroadApi.getCourseDetailsBatch).mockResolvedValue({
        '6.100A': { subject_id: '6.100A', title: 'Intro to CS' } as any,
        '18.01': { subject_id: '18.01', title: 'Calculus' } as any,
      });

      await prefetchCourses(queryClient, ['6.100A', '18.01']);

      // Check that individual cache entries are populated
      expect(queryClient.getQueryData(['courses', 'details', '6.100A'])).toEqual({
        subject_id: '6.100A',
        title: 'Intro to CS',
      });
      expect(queryClient.getQueryData(['courses', 'details', '18.01'])).toEqual({
        subject_id: '18.01',
        title: 'Calculus',
      });
    });
  });
});

describe('extractCoursesFromRequirement', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should extract courses from requirement tree', async () => {
    vi.mocked(fireroadApi.getRequirementProgress).mockResolvedValue({
      reqs: [
        { req: '6.100A' },
        { req: '6.042' },
        {
          reqs: [
            { req: '6.006' },
            { req: '6.046' },
          ],
        },
      ],
    } as any);

    const result = await extractCoursesFromRequirement('major6-3new');

    expect(result).toContain('6.100A');
    expect(result).toContain('6.042');
    expect(result).toContain('6.006');
    expect(result).toContain('6.046');
    expect(fireroadApi.getRequirementProgress).toHaveBeenCalledWith('major6-3new', []);
  });

  it('should deduplicate courses', async () => {
    vi.mocked(fireroadApi.getRequirementProgress).mockResolvedValue({
      reqs: [
        { req: '6.100A' },
        { req: '6.100A' },
        { req: '6.042' },
      ],
    } as any);

    const result = await extractCoursesFromRequirement('test');

    expect(result.filter(c => c === '6.100A')).toHaveLength(1);
  });

  it('should handle nested requirement trees', async () => {
    vi.mocked(fireroadApi.getRequirementProgress).mockResolvedValue({
      reqs: [
        {
          reqs: [
            {
              reqs: [
                { req: '6.100A' },
              ],
            },
          ],
        },
      ],
    } as any);

    const result = await extractCoursesFromRequirement('test');

    expect(result).toContain('6.100A');
  });

  it('should return empty array on error', async () => {
    vi.mocked(fireroadApi.getRequirementProgress).mockRejectedValue(
      new Error('Network error')
    );

    const result = await extractCoursesFromRequirement('invalid');

    expect(result).toEqual([]);
  });

  it('should handle empty requirement tree', async () => {
    vi.mocked(fireroadApi.getRequirementProgress).mockResolvedValue({
      reqs: [],
    } as any);

    const result = await extractCoursesFromRequirement('empty');

    expect(result).toEqual([]);
  });
});
