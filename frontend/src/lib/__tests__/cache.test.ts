/**
 * Tests for cache utilities
 * Tests course prefetching
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { QueryClient } from '@tanstack/react-query';
import { prefetchCourses } from '../cache';

// Mock dependencies
vi.mock('@/services/fireroad', () => ({
  fireroadApi: {
    getCourseDetails: vi.fn(),
    getCourseDetailsBatch: vi.fn(),
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
