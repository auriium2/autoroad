/**
 * Fireroad API Client
 * Interface to MIT's Fireroad course catalog API
 */

import { API_BASE_URL } from '@/config/api';
import type {
  FireroadCourse,
  PaginatedCoursesResponse,
  FireroadSearchParams,
  RequirementMetadata,
  RequirementsListResponse,
  RequirementNode,
  RequirementTree,
} from '@/types/models/fireroad';

export class ApiError extends Error {
  constructor(
    message: string,
    public statusCode?: number,
    public details?: unknown
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function apiFetch<T>(
  url: string,
  options: RequestInit = {}
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${url}`, {
    ...options,
    headers: {
      // Only add Accept header - don't add Content-Type for GET requests
      // to avoid CORS preflight requests
      'Accept': 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new ApiError(
      errorData.error || `HTTP ${response.status}: ${response.statusText}`,
      response.status,
      errorData
    );
  }

  return await response.json();
}

export type {
  FireroadCourse,
  PaginatedCoursesResponse,
  FireroadSearchParams,
  RequirementMetadata,
  RequirementsListResponse,
  RequirementNode,
  RequirementTree,
};

export const fireroadApi = {
  async checkHealth(): Promise<{ status: string; service: string }> {
    return apiFetch<{ status: string; service: string }>(
      '/api/health',
      { signal: AbortSignal.timeout(3000) }
    );
  },

  async getRequirementsList(): Promise<RequirementsListResponse> {
    return apiFetch<RequirementsListResponse>('/api/requirements/list');
  },

  async getRequirementProgress(
    key: string,
    courseIds: string[],
    source: 'canonical' | 'beta' = 'canonical'
  ): Promise<RequirementTree> {
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

    const url = `/api/requirements/progress/${encodeURIComponent(key)}?source=${source}`;

    return apiFetch<RequirementTree>(
      url,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(roadData),
      }
    );
  },

  async searchCourses(
    query: string,
    params?: FireroadSearchParams
  ): Promise<PaginatedCoursesResponse> {
    const searchParams = new URLSearchParams();
    searchParams.append('q', query);
    if (params?.type) searchParams.append('search_type', params.type);
    if (params?.gir) searchParams.append('gir', params.gir);
    if (params?.hass) searchParams.append('hass', params.hass);
    if (params?.ci) searchParams.append('ci', typeof params.ci === 'string' ? params.ci : 'true');
    if (params?.level) searchParams.append('level', params.level);
    if (params?.units) searchParams.append('units', params.units);
    if (params?.term) searchParams.append('term', params.term);
    if (params?.sort) searchParams.append('sort', params.sort);
    if (params?.offset !== undefined) searchParams.append('offset', params.offset.toString());
    if (params?.limit !== undefined) searchParams.append('limit', params.limit.toString());
    if (params?.department) searchParams.append('department', params.department);

    return apiFetch<PaginatedCoursesResponse>(`/api/courses/search?${searchParams}`);
  },

  async getCoursesByDepartment(dept: string, offset = 0, limit = 20): Promise<PaginatedCoursesResponse> {
    const params = new URLSearchParams();
    params.append('offset', offset.toString());
    params.append('limit', limit.toString());
    return apiFetch<PaginatedCoursesResponse>(`/api/courses/dept/${dept}?${params}`);
  },

  async getCourseDetails(subjectId: string): Promise<FireroadCourse> {
    return apiFetch<FireroadCourse>(`/api/courses/lookup/${encodeURIComponent(subjectId)}`);
  },
};
