/**
 * Service for handling optimization requests to the backend
 */

import { Section } from "@/stores/roadStore";
import { transformFrontendToBackend, transformBackendToFrontend } from "@/lib/dataTransformers";

interface OptimizationRequest {
  sections: Section[];
  specialSection?: Section;
  constraints?: {
    lockedCourses?: string[];
    preferredTimes?: string[];
    avoidProfessors?: string[];
    maxUnitsPerSemester?: number;
    minUnitsPerSemester?: number;
    priorities?: {
      [key: string]: number;
    };
  };
}

interface OptimizationResult {
  success: boolean;
  message?: string;
  data?: any;
  error?: string;
}

/**
 * Send a request to optimize the course road
 */
export async function optimizeRoad(request: OptimizationRequest): Promise<OptimizationResult> {
  try {
    // Convert frontend data to backend format
    const backendRequest = transformFrontendToBackend(request);
    
    const response = await fetch('/api/optimize', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(backendRequest),
    });
    
    if (!response.ok) {
      throw new Error(`Optimization failed: ${response.statusText}`);
    }
    
    const result = await response.json();
    
    // Transform backend result to frontend format
    const frontendData = transformBackendToFrontend(result);
    
    return {
      success: true,
      data: frontendData
    };
  } catch (error) {
    console.error('Error optimizing road:', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error occurred'
    };
  }
}

/**
 * Fetch available course data from the backend
 */
export async function fetchAvailableCourses(): Promise<OptimizationResult> {
  try {
    const response = await fetch('/api/courses');
    
    if (!response.ok) {
      throw new Error(`Failed to fetch courses: ${response.statusText}`);
    }
    
    const courseData = await response.json();
    
    return {
      success: true,
      data: courseData
    };
  } catch (error) {
    console.error('Error fetching courses:', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error occurred'
    };
  }
}

/**
 * Validate if a road is feasible without running a full optimization
 */
export async function validateRoad(request: OptimizationRequest): Promise<OptimizationResult> {
  try {
    // Convert frontend data to backend format
    const backendRequest = transformFrontendToBackend(request);
    
    const response = await fetch('/api/validate', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(backendRequest),
    });
    
    if (!response.ok) {
      throw new Error(`Validation failed: ${response.statusText}`);
    }
    
    const result = await response.json();
    
    return {
      success: true,
      data: result
    };
  } catch (error) {
    console.error('Error validating road:', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error occurred'
    };
  }
}

/**
 * Save road data to user profile (if auth implemented)
 */
export async function saveRoad(name: string, request: OptimizationRequest): Promise<OptimizationResult> {
  try {
    const response = await fetch('/api/save-road', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        name,
        roadData: request
      }),
    });
    
    if (!response.ok) {
      throw new Error(`Failed to save road: ${response.statusText}`);
    }
    
    const result = await response.json();
    
    return {
      success: true,
      message: 'Road saved successfully',
      data: result
    };
  } catch (error) {
    console.error('Error saving road:', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error occurred'
    };
  }
}