/**
 * Fireroad API Client
 * Interface to MIT's Fireroad course catalog API
 */

import type { FireroadCourse } from '@/lib/fireroad-utils';

// Toggle between direct API calls and proxy
const USE_DIRECT_API = true;
const FIREROAD_API_URL = 'https://fireroad.mit.edu';
const FIREROAD_PROXY_URL = '/api/fireroad';

const BASE_URL = USE_DIRECT_API ? FIREROAD_API_URL : FIREROAD_PROXY_URL;

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

export type { FireroadCourse };

export interface FireroadSearchParams {
  type?: 'contains' | 'matches' | 'starts' | 'ends';
  gir?: string;
  hass?: string;
  ci?: boolean;
  offered?: 'fall' | 'spring' | 'IAP' | 'summer';
  level?: 'undergrad' | 'grad';
  full?: boolean;
  offset?: number;
  limit?: number;
  department?: string;
}

export interface PaginatedCoursesResponse {
  courses: FireroadCourse[];
  total: number;
  offset: number;
  limit: number;
  has_more: boolean;
}

export interface CourseDetails {
  id: string;
  name: string;
  description: string;
  units: number;
  prerequisites: string;
  corequisites: string;
  terms_offered: string[];
  instructors: string[];
  level?: string;
  gir_attribute?: string;
  hass_attribute?: string;
  communication_requirement?: string;
  offered_fall?: boolean;
  offered_spring?: boolean;
  offered_IAP?: boolean;
  rating?: number;
  enrollment_number?: number;
  imdb_rating?: number | null;
  in_class_hours?: number;
  out_of_class_hours?: number;
}

function normalizeFireroadCourse(course: FireroadCourse): CourseDetails {
  const terms_offered = [];
  if (course.offered_fall) terms_offered.push('Fall');
  if (course.offered_spring) terms_offered.push('Spring');
  if (course.offered_IAP) terms_offered.push('IAP');

  return {
    id: course.subject_id,
    name: course.title,
    description: course.description || '',
    units: course.total_units,
    prerequisites: course.prerequisites || '',
    corequisites: course.corequisites || '',
    terms_offered,
    instructors: course.instructors || [],
    level: course.level,
    gir_attribute: course.gir_attribute,
    hass_attribute: course.hass_attribute,
    communication_requirement: course.communication_requirement,
    offered_fall: course.offered_fall,
    offered_spring: course.offered_spring,
    offered_IAP: course.offered_IAP,
    rating: course.rating,
    enrollment_number: course.enrollment_number,
    imdb_rating: course.imdb_rating,
    in_class_hours: course.in_class_hours,
    out_of_class_hours: course.out_of_class_hours,
  };
}

export const fireroadApi = {
  async checkHealth(): Promise<{ status: string; service: string }> {
    try {
      const response = await fetch(`${FIREROAD_API_URL}/requirements/list_reqs`, {
        method: 'HEAD', // Just check if the endpoint is reachable
        signal: AbortSignal.timeout(3000), // 3 second timeout
      });
      if (!response.ok) {
        throw new Error('Fireroad health check failed');
      }
      return {
        status: 'healthy',
        service: 'fireroad'
      };
    } catch (error) {
      throw new Error('Fireroad service unavailable');
    }
  },

  async searchCourses(
    query: string,
    params?: FireroadSearchParams
  ): Promise<PaginatedCoursesResponse> {
    const searchParams = new URLSearchParams();
    if (params?.type) searchParams.append('type', params.type);
    if (params?.gir) searchParams.append('gir', params.gir);
    if (params?.hass) searchParams.append('hass', params.hass);
    if (params?.ci) searchParams.append('ci', 'true');
    if (params?.offered) searchParams.append('offered', params.offered);
    if (params?.level) searchParams.append('level', params.level);
    if (params?.offset !== undefined) searchParams.append('offset', params.offset.toString());
    if (params?.limit !== undefined) searchParams.append('limit', params.limit.toString());
    if (params?.department) searchParams.append('department', params.department);

    // Always use proxy for paginated search (has full course data)
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

  async getCourseDetails(subjectId: string): Promise<CourseDetails> {
    // Always use proxy for lookup to get enriched data with IMDB rating
    const course = await apiFetch<FireroadCourse>(
      `${FIREROAD_PROXY_URL}/courses/lookup/${encodeURIComponent(subjectId)}`
    );
    return normalizeFireroadCourse(course);
  },

  async getAllCourses(full = false): Promise<FireroadCourse[]> {
    // Note: This endpoint returns the entire catalog and can be very large
    // Consider implementing pagination or not exposing this endpoint
    const params = full ? '?full=true' : '';
    return apiFetch<FireroadCourse[]>(`${BASE_URL}/courses/all${params}`);
  },
};
