/**
 * Fireroad API Client
 * Interface to MIT's Fireroad course catalog API
 */

import type {
  FireroadCourse,
  PaginatedCoursesResponse,
  FireroadSearchParams,
  RequirementMetadata,
  RequirementsListResponse,
  RequirementNode,
  RequirementTree,
} from '@/types/fireroad';

const FIREROAD_PROXY_URL = '/api/fireroad';

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
  const response = await fetch(url, {
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
      '/api/health/fireroad',
      { signal: AbortSignal.timeout(3000) }
    );
  },

  async getRequirementsList(): Promise<RequirementsListResponse> {
    return apiFetch<RequirementsListResponse>('/api/requirements/list');
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

    return apiFetch<RequirementTree>(
      `/api/requirements/progress/${encodeURIComponent(key)}`,
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
    if (params?.type) searchParams.append('type', params.type);
    if (params?.gir) searchParams.append('gir', params.gir);
    if (params?.hass) searchParams.append('hass', params.hass);
    if (params?.ci) searchParams.append('ci', typeof params.ci === 'string' ? params.ci : 'true');
    if (params?.offered) searchParams.append('offered', params.offered);
    if (params?.level) searchParams.append('level', params.level);
    if (params?.units) searchParams.append('units', params.units);
    if (params?.term) searchParams.append('term', params.term);
    if (params?.offset !== undefined) searchParams.append('offset', params.offset.toString());
    if (params?.limit !== undefined) searchParams.append('limit', params.limit.toString());
    if (params?.department) searchParams.append('department', params.department);

    // paginated search
    const url = `${FIREROAD_PROXY_URL}/courses/search/${encodeURIComponent(query)}?${searchParams}`;
    return apiFetch<PaginatedCoursesResponse>(url);
  },

  async getCoursesByDepartment(dept: string, offset = 0, limit = 20): Promise<PaginatedCoursesResponse> {
    const params = new URLSearchParams();
    params.append('offset', offset.toString());
    params.append('limit', limit.toString());
    // Always use proxy for paginated department search (has full course data)
    return apiFetch<PaginatedCoursesResponse>(`${FIREROAD_PROXY_URL}/courses/dept/${dept}?${params}`);
  },

  async getCourseDetails(subjectId: string): Promise<FireroadCourse> {
    return apiFetch<FireroadCourse>(
      `${FIREROAD_PROXY_URL}/courses/lookup/${encodeURIComponent(subjectId)}`
    );
  },

  async getAllCourses(full = false): Promise<FireroadCourse[]> {
    // Note: This endpoint returns the entire catalog and can be very large
    // Consider implementing pagination or not exposing this endpoint
    const params = full ? '?full=true' : '';
    return apiFetch<FireroadCourse[]>(`${FIREROAD_PROXY_URL}/courses/all${params}`);
  },
};
