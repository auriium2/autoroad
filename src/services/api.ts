import { CourseNode, Edge, Section, AvailableNode } from '@/stores/roadStore';

// API Configuration
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '/api';

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

// Generic fetch wrapper with error handling and retries
async function fetchWithRetry<T>(
  url: string,
  options: RequestInit = {},
  retries = 3,
  delay = 1000
): Promise<T> {
  for (let i = 0; i < retries; i++) {
    try {
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
    } catch (error) {
      // If it's the last retry or not a network error, throw
      if (i === retries - 1 || !(error instanceof TypeError)) {
        throw error;
      }
      
      // Wait before retrying
      await new Promise(resolve => setTimeout(resolve, delay * Math.pow(2, i)));
    }
  }

  throw new Error('Max retries exceeded');
}

// API methods
export const roadApi = {
  /**
   * Fetch road data for a user
   */
  async fetchRoadData(userId?: string): Promise<RoadData> {
    const url = userId 
      ? `${API_BASE_URL}/road?userId=${userId}`
      : `${API_BASE_URL}/road`;
    
    return fetchWithRetry<RoadData>(url);
  },

  /**
   * Save road data
   */
  async saveRoadData(data: Partial<RoadData>, userId?: string): Promise<ApiResponse<RoadData>> {
    const url = userId
      ? `${API_BASE_URL}/road?userId=${userId}`
      : `${API_BASE_URL}/road`;

    return fetchWithRetry<ApiResponse<RoadData>>(url, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  /**
   * Optimize road schedule
   */
  async optimizeRoad(request: OptimizeRequest): Promise<ApiResponse<RoadData>> {
    return fetchWithRetry<ApiResponse<RoadData>>(`${API_BASE_URL}/optimize`, {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },

  /**
   * Fetch available courses
   */
  async fetchAvailableCourses(): Promise<AvailableNode[]> {
    return fetchWithRetry<AvailableNode[]>(`${API_BASE_URL}/courses`);
  },

  /**
   * Add a node to the road
   */
  async addNode(node: CourseNode, userId?: string): Promise<ApiResponse<CourseNode>> {
    const url = userId
      ? `${API_BASE_URL}/nodes?userId=${userId}`
      : `${API_BASE_URL}/nodes`;

    return fetchWithRetry<ApiResponse<CourseNode>>(url, {
      method: 'POST',
      body: JSON.stringify(node),
    });
  },

  /**
   * Remove a node from the road
   */
  async removeNode(nodeId: string, userId?: string): Promise<ApiResponse<void>> {
    const url = userId
      ? `${API_BASE_URL}/nodes/${nodeId}?userId=${userId}`
      : `${API_BASE_URL}/nodes/${nodeId}`;

    return fetchWithRetry<ApiResponse<void>>(url, {
      method: 'DELETE',
    });
  },

  /**
   * Update a node
   */
  async updateNode(
    nodeId: string,
    updates: Partial<CourseNode>,
    userId?: string
  ): Promise<ApiResponse<CourseNode>> {
    const url = userId
      ? `${API_BASE_URL}/nodes/${nodeId}?userId=${userId}`
      : `${API_BASE_URL}/nodes/${nodeId}`;

    return fetchWithRetry<ApiResponse<CourseNode>>(url, {
      method: 'PATCH',
      body: JSON.stringify(updates),
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
