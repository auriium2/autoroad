import { CourseNode, Edge, Section, AvailableNode } from '@/stores/roadStore';

// API Configuration
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '/api';
const FIREROAD_API_URL = 'https://fireroad.mit.edu';

// Types for API responses
export interface RoadData {
  nodes: CourseNode[];
  edges: Edge[];
  sections: Section[];
  specialSection: Section | null;
  availableNodes: AvailableNode[];
}

export interface OptimizeRequest {
  sections: Section[];
  specialSection: Section | null;
  constraints: {
    maxUnitsPerSemester?: number;
    minUnitsPerSemester?: number;
    preferredTimes?: string[];
  };
}

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
}

// Error classes
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

// Generic fetch wrapper with error handling
// Note: Retries are handled by TanStack Query when these functions are called from hooks
async function apiFetch<T>(
  url: string,
  options: RequestInit = {}
): Promise<T> {
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
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

// Fireroad API types
export interface FireroadCourse {
  subject_id: string;
  title: string;
  total_units: number;
  description?: string;
  prerequisites?: string;
  corequisites?: string;
  is_variable_units?: boolean;
  offered_fall?: boolean;
  offered_spring?: boolean;
  offered_IAP?: boolean;
  offered_summer?: boolean;
  public?: boolean;
  level?: string;
  // Full response fields
  lecture_units?: number;
  lab_units?: number;
  preparation_units?: number;
  in_class_hours?: number;
  out_of_class_hours?: number;
  joint_subjects?: string[];
  equivalent_subjects?: string[];
  meets_with_subjects?: string[];
  instructors?: string[];
  // Ratings
  rating?: number[];
  enrollment?: number[];
  // Attributes
  gir_attribute?: string;
  hass_attribute?: string;
  communication_requirement?: string;
}

export interface FireroadSearchParams {
  type?: 'contains' | 'matches' | 'starts' | 'ends';
  gir?: string;
  hass?: string;
  ci?: boolean;
  offered?: 'fall' | 'spring' | 'IAP' | 'summer';
  level?: 'undergrad' | 'grad';
  full?: boolean;
}

// Course details interface (normalized from Fireroad)
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
  offered_fall?: boolean;
  offered_spring?: boolean;
  offered_IAP?: boolean;
}

// Helper to normalize Fireroad course to our format
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
    offered_fall: course.offered_fall,
    offered_spring: course.offered_spring,
    offered_IAP: course.offered_IAP,
  };
}

// Fireroad API methods
export const fireroadApi = {
  /**
   * Search for courses using Fireroad API
   */
  async searchCourses(
    query: string,
    params?: FireroadSearchParams
  ): Promise<FireroadCourse[]> {
    const searchParams = new URLSearchParams();
    if (params?.type) searchParams.append('type', params.type);
    if (params?.gir) searchParams.append('gir', params.gir);
    if (params?.hass) searchParams.append('hass', params.hass);
    if (params?.ci) searchParams.append('ci', 'true');
    if (params?.offered) searchParams.append('offered', params.offered);
    if (params?.level) searchParams.append('level', params.level);
    if (params?.full) searchParams.append('full', 'true');

    const url = `${FIREROAD_API_URL}/courses/search/${encodeURIComponent(query)}?${searchParams}`;
    return apiFetch<FireroadCourse[]>(url);
  },

  /**
   * Get all courses in a department
   */
  async getCoursesByDepartment(dept: string, full = false): Promise<FireroadCourse[]> {
    const params = full ? '?full=true' : '';
    return apiFetch<FireroadCourse[]>(`${FIREROAD_API_URL}/courses/dept/${dept}${params}`);
  },

  /**
   * Get detailed course information
   */
  async getCourseDetails(subjectId: string): Promise<CourseDetails> {
    const course = await apiFetch<FireroadCourse>(
      `${FIREROAD_API_URL}/courses/lookup/${encodeURIComponent(subjectId)}`
    );
    return normalizeFireroadCourse(course);
  },

  /**
   * Get all courses (use sparingly, returns entire catalog)
   */
  async getAllCourses(full = false): Promise<FireroadCourse[]> {
    const params = full ? '?full=true' : '';
    return apiFetch<FireroadCourse[]>(`${FIREROAD_API_URL}/courses/all${params}`);
  },
};

// API methods for our backend
export const roadApi = {
  /**
   * Optimize road schedule - takes current user state and returns optimized arrangement
   */
  async optimizeRoad(currentState: RoadData, constraints?: {
    maxUnitsPerSemester?: number;
    minUnitsPerSemester?: number;
    preferredTimes?: string[];
  }): Promise<ApiResponse<RoadData>> {
    return apiFetch<ApiResponse<RoadData>>(`${API_BASE_URL}/optimize`, {
      method: 'POST',
      body: JSON.stringify({
        currentState,
        constraints: constraints || {},
      }),
    });
  },
};

// LocalStorage fallback with versioning
const STORAGE_KEY = 'autoroad_data';
const STORAGE_VERSION = 1;

interface StorageData {
  version: number;
  data: RoadData;
  timestamp: number;
}

export const localStorage = {
  /**
   * Save road data to localStorage
   */
  save(data: RoadData): void {
    if (typeof window === 'undefined') return;

    const storageData: StorageData = {
      version: STORAGE_VERSION,
      data,
      timestamp: Date.now(),
    };

    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(storageData));
    } catch (error) {
      console.error('Failed to save to localStorage:', error);
    }
  },

  /**
   * Load road data from localStorage
   */
  load(): RoadData | null {
    if (typeof window === 'undefined') return null;

    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (!stored) return null;

      const parsed: StorageData = JSON.parse(stored);

      // Check version compatibility
      if (parsed.version !== STORAGE_VERSION) {
        console.warn('LocalStorage data version mismatch, clearing...');
        this.clear();
        return null;
      }

      // Check if data is stale (older than 7 days)
      const sevenDays = 7 * 24 * 60 * 60 * 1000;
      if (Date.now() - parsed.timestamp > sevenDays) {
        console.warn('LocalStorage data is stale, clearing...');
        this.clear();
        return null;
      }

      return parsed.data;
    } catch (error) {
      console.error('Failed to load from localStorage:', error);
      return null;
    }
  },

  /**
   * Clear localStorage
   */
  clear(): void {
    if (typeof window === 'undefined') return;
    window.localStorage.removeItem(STORAGE_KEY);
  },
};
