/**
 * Tests for cache utilities
 * Tests prerequisite caching, course prefetching, and requirement extraction
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { QueryClient } from '@tanstack/react-query';
import {
  getCachedPrereqTree,
  clearPrereqCache,
  getPrereqCacheStats,
  prefetchCourses,
  extractCoursesFromRequirement,
} from '../cache';

// Mock dependencies
vi.mock('@/services/fireroad', () => ({
  fireroadApi: {
    getCourseDetails: vi.fn(),
    getRequirementProgress: vi.fn(),
  },
}));

vi.mock('@/lib/prerequisites', () => ({
  parseFireroad: vi.fn((str: string) => {
    // Simple mock parser
    if (!str) return { type: 'group', threshold: 0, items: [] };
    return { type: 'course', id: str };
  }),
}));

import { fireroadApi } from '@/services/fireroad';
import { parseFireroad } from '@/lib/prerequisites';

describe('Prerequisite Cache', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    clearPrereqCache();
  });

  describe('getCachedPrereqTree', () => {
    it('should return empty group for empty string', () => {
      const result = getCachedPrereqTree('');
      expect(result).toEqual({ type: 'group', threshold: 0, items: [] });
      expect(parseFireroad).not.toHaveBeenCalled();
    });

    it('should return empty group for whitespace string', () => {
      const result = getCachedPrereqTree('   ');
      expect(result).toEqual({ type: 'group', threshold: 0, items: [] });
    });

    it('should parse and cache prerequisite string', () => {
      const result = getCachedPrereqTree('6.100A');
      
      expect(parseFireroad).toHaveBeenCalledWith('6.100A');
      expect(result).toEqual({ type: 'course', id: '6.100A' });
    });

    it('should return cached result on second call', () => {
      getCachedPrereqTree('6.100A');
      getCachedPrereqTree('6.100A');
      
      // Parser should only be called once
      expect(parseFireroad).toHaveBeenCalledTimes(1);
    });

    it('should cache different strings separately', () => {
      getCachedPrereqTree('6.100A');
      getCachedPrereqTree('18.01');
      
      expect(parseFireroad).toHaveBeenCalledTimes(2);
    });
  });

  describe('clearPrereqCache', () => {
    it('should clear the cache', () => {
      getCachedPrereqTree('6.100A');
      expect(getPrereqCacheStats().size).toBe(1);
      
      clearPrereqCache();
      
      expect(getPrereqCacheStats().size).toBe(0);
    });

    it('should require re-parsing after clear', () => {
      getCachedPrereqTree('6.100A');
      clearPrereqCache();
      getCachedPrereqTree('6.100A');
      
      expect(parseFireroad).toHaveBeenCalledTimes(2);
    });
  });

  describe('getPrereqCacheStats', () => {
    it('should return cache size and max size', () => {
      const stats = getPrereqCacheStats();
      
      expect(stats).toHaveProperty('size');
      expect(stats).toHaveProperty('maxSize');
      expect(stats.maxSize).toBe(500);
    });

    it('should track cache size correctly', () => {
      expect(getPrereqCacheStats().size).toBe(0);
      
      getCachedPrereqTree('6.100A');
      expect(getPrereqCacheStats().size).toBe(1);
      
      getCachedPrereqTree('18.01');
      expect(getPrereqCacheStats().size).toBe(2);
    });
  });
});

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
    it('should prefetch course details for valid course IDs', async () => {
      vi.mocked(fireroadApi.getCourseDetails).mockResolvedValue({
        subject_id: '6.100A',
        title: 'Intro to CS',
      } as any);

      await prefetchCourses(queryClient, ['6.100A', '18.01']);

      expect(fireroadApi.getCourseDetails).toHaveBeenCalledTimes(2);
      expect(fireroadApi.getCourseDetails).toHaveBeenCalledWith('6.100A');
      expect(fireroadApi.getCourseDetails).toHaveBeenCalledWith('18.01');
    });

    it('should deduplicate course IDs', async () => {
      vi.mocked(fireroadApi.getCourseDetails).mockResolvedValue({} as any);

      await prefetchCourses(queryClient, ['6.100A', '6.100A', '18.01', '18.01']);

      expect(fireroadApi.getCourseDetails).toHaveBeenCalledTimes(2);
    });

    it('should filter out GIR placeholders', async () => {
      vi.mocked(fireroadApi.getCourseDetails).mockResolvedValue({} as any);

      await prefetchCourses(queryClient, ['GIR:CAL1', '6.100A', 'GIR:BIOL']);

      expect(fireroadApi.getCourseDetails).toHaveBeenCalledTimes(1);
      expect(fireroadApi.getCourseDetails).toHaveBeenCalledWith('6.100A');
    });

    it('should filter out HASS placeholders', async () => {
      vi.mocked(fireroadApi.getCourseDetails).mockResolvedValue({} as any);

      await prefetchCourses(queryClient, ['HASS-A', 'HASS-S', '6.100A']);

      expect(fireroadApi.getCourseDetails).toHaveBeenCalledTimes(1);
    });

    it('should filter out CI placeholders', async () => {
      vi.mocked(fireroadApi.getCourseDetails).mockResolvedValue({} as any);

      await prefetchCourses(queryClient, ['CI-H', 'CI-M', '6.100A']);

      expect(fireroadApi.getCourseDetails).toHaveBeenCalledTimes(1);
    });

    it('should filter out REST placeholder', async () => {
      vi.mocked(fireroadApi.getCourseDetails).mockResolvedValue({} as any);

      await prefetchCourses(queryClient, ['REST', '6.100A']);

      expect(fireroadApi.getCourseDetails).toHaveBeenCalledTimes(1);
    });

    it('should silently handle prefetch failures', async () => {
      vi.mocked(fireroadApi.getCourseDetails)
        .mockResolvedValueOnce({} as any)
        .mockRejectedValueOnce(new Error('Network error'));

      // Should not throw
      await expect(prefetchCourses(queryClient, ['6.100A', '18.01'])).resolves.toBeUndefined();
    });

    it('should handle empty array', async () => {
      await prefetchCourses(queryClient, []);

      expect(fireroadApi.getCourseDetails).not.toHaveBeenCalled();
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
