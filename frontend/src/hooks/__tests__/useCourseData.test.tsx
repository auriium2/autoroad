/**
 * Tests for useCourseData hooks
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useSearchCourses, useCourseDetails } from '../useCourseData';
import type { FireroadCourse, PaginatedCoursesResponse } from '@/types/models/fireroad';
import * as React from 'react';

// Mock the fireroad service
vi.mock('@/services/fireroad', () => ({
  fireroadApi: {
    searchCourses: vi.fn(),
    getCourseDetails: vi.fn(),
  },
}));

import { fireroadApi } from '@/services/fireroad';

const mockCourses: FireroadCourse[] = [
  {
    subject_id: '6.100A',
    title: 'Introduction to Computer Science',
    total_units: 12,
    level: 'U',
    offered_fall: true,
    offered_spring: false,
    offered_IAP: false,
    is_historical: false,
  },
  {
    subject_id: '6.1200',
    title: 'Mathematics for Computer Science',
    total_units: 12,
    level: 'U',
    offered_fall: true,
    offered_spring: true,
    offered_IAP: false,
    is_historical: false,
  },
  {
    subject_id: '18.01',
    title: 'Single Variable Calculus',
    total_units: 12,
    level: 'U',
    offered_fall: true,
    offered_spring: true,
    offered_IAP: false,
    is_historical: false,
  },
];

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

describe('useSearchCourses', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should return empty array for empty query', async () => {
    const { result } = renderHook(() => useSearchCourses('', 'all', undefined), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([]);
    expect(fireroadApi.searchCourses).not.toHaveBeenCalled();
  });

  it('should search with text query using contains type', async () => {
    const mockResponse: PaginatedCoursesResponse = {
      courses: mockCourses,
      total: 3,
      offset: 0,
      limit: 2000,
      has_more: false,
    };
    
    vi.mocked(fireroadApi.searchCourses).mockResolvedValue(mockResponse);

    const { result } = renderHook(() => useSearchCourses('computer', 'all', undefined), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    
    expect(fireroadApi.searchCourses).toHaveBeenCalledWith('computer', {
      type: 'contains',
      department: undefined,
      offset: 0,
      limit: 2000,
    });
    expect(result.current.data).toEqual(mockCourses);
  });

  it('should search with course ID using starts type', async () => {
    const mockResponse: PaginatedCoursesResponse = {
      courses: [mockCourses[0], mockCourses[1]],
      total: 2,
      offset: 0,
      limit: 2000,
      has_more: false,
    };
    
    vi.mocked(fireroadApi.searchCourses).mockResolvedValue(mockResponse);

    const { result } = renderHook(() => useSearchCourses('6.1', 'all', undefined), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    
    expect(fireroadApi.searchCourses).toHaveBeenCalledWith('6.1', {
      type: 'starts',
      department: undefined,
      offset: 0,
      limit: 2000,
    });
  });

  it('should sort results to prioritize exact department matches', async () => {
    const unsortedCourses: FireroadCourse[] = [
      {
        subject_id: '18.06',
        title: 'Linear Algebra',
        total_units: 12,
        level: 'U',
        offered_fall: true,
        offered_spring: false,
        offered_IAP: false,
        is_historical: false,
      },
      {
        subject_id: '6.1200',
        title: 'Mathematics for Computer Science',
        total_units: 12,
        level: 'U',
        offered_fall: true,
        offered_spring: true,
        offered_IAP: false,
        is_historical: false,
      },
      {
        subject_id: '6.100A',
        title: 'Introduction to Computer Science',
        total_units: 12,
        level: 'U',
        offered_fall: true,
        offered_spring: false,
        offered_IAP: false,
        is_historical: false,
      },
    ];

    const mockResponse: PaginatedCoursesResponse = {
      courses: unsortedCourses,
      total: 3,
      offset: 0,
      limit: 2000,
      has_more: false,
    };
    
    vi.mocked(fireroadApi.searchCourses).mockResolvedValue(mockResponse);

    const { result } = renderHook(() => useSearchCourses('6.1', 'all', undefined), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    
    // Should prioritize courses starting with 6. and sort alphabetically
    expect(result.current.data?.[0].subject_id).toBe('6.100A');
    expect(result.current.data?.[1].subject_id).toBe('6.1200');
    expect(result.current.data?.[2].subject_id).toBe('18.06');
  });

  it('should pass department filter to API', async () => {
    const mockResponse: PaginatedCoursesResponse = {
      courses: [mockCourses[0]],
      total: 1,
      offset: 0,
      limit: 2000,
      has_more: false,
    };
    
    vi.mocked(fireroadApi.searchCourses).mockResolvedValue(mockResponse);

    const { result } = renderHook(() => useSearchCourses('intro', '6', undefined), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    
    expect(fireroadApi.searchCourses).toHaveBeenCalledWith('intro', {
      type: 'contains',
      department: '6',
      offset: 0,
      limit: 2000,
    });
  });

  it('should treat "all" department as undefined', async () => {
    const mockResponse: PaginatedCoursesResponse = {
      courses: mockCourses,
      total: 3,
      offset: 0,
      limit: 2000,
      has_more: false,
    };
    
    vi.mocked(fireroadApi.searchCourses).mockResolvedValue(mockResponse);

    const { result } = renderHook(() => useSearchCourses('intro', 'all', undefined), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    
    expect(fireroadApi.searchCourses).toHaveBeenCalledWith('intro', {
      type: 'contains',
      department: undefined,
      offset: 0,
      limit: 2000,
    });
  });

  it('should pass filters to API', async () => {
    const mockResponse: PaginatedCoursesResponse = {
      courses: mockCourses,
      total: 3,
      offset: 0,
      limit: 2000,
      has_more: false,
    };
    
    vi.mocked(fireroadApi.searchCourses).mockResolvedValue(mockResponse);

    const filters = { level: 'UG', gir: 'LAB' };
    const { result } = renderHook(() => useSearchCourses('*', 'all', filters), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    
    expect(fireroadApi.searchCourses).toHaveBeenCalledWith('*', {
      type: 'contains',
      department: undefined,
      offset: 0,
      limit: 2000,
      level: 'UG',
      gir: 'LAB',
    });
  });

  it('should handle wildcard search with filters', async () => {
    const mockResponse: PaginatedCoursesResponse = {
      courses: mockCourses,
      total: 3,
      offset: 0,
      limit: 2000,
      has_more: false,
    };
    
    vi.mocked(fireroadApi.searchCourses).mockResolvedValue(mockResponse);

    const filters = { level: 'UG' };
    const { result } = renderHook(() => useSearchCourses('*', '6', filters), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    
    expect(fireroadApi.searchCourses).toHaveBeenCalledWith('*', {
      type: 'contains',
      department: '6',
      offset: 0,
      limit: 2000,
      level: 'UG',
    });
  });
});

describe('useCourseDetails', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should fetch course details when courseId is provided', async () => {
    const mockCourse = mockCourses[0];
    vi.mocked(fireroadApi.getCourseDetails).mockResolvedValue(mockCourse);

    const { result } = renderHook(() => useCourseDetails('6.100A'), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    
    expect(fireroadApi.getCourseDetails).toHaveBeenCalledWith('6.100A');
    expect(result.current.data).toEqual(mockCourse);
  });

  it('should not fetch when courseId is null', async () => {
    const { result } = renderHook(() => useCourseDetails(null), {
      wrapper: createWrapper(),
    });

    expect(result.current.isLoading).toBe(false);
    expect(fireroadApi.getCourseDetails).not.toHaveBeenCalled();
  });

  it('should return null when courseId is null', async () => {
    const { result } = renderHook(() => useCourseDetails(null), {
      wrapper: createWrapper(),
    });

    expect(result.current.data).toBeUndefined();
  });
});
