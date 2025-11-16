/**
 * Optimizer API service
 * Handles communication with the backend optimizer
 * Supports both one-shot optimization and live streaming of optimization progress
 */

import type { Marker, OptimizerNode } from '@/types';

export interface OptimizationConstraints {
  maxSemesters?: number;
  maxUnitsPerSemester?: number;
  maxUnitsIAP?: number;
  maxHoursPerSemester?: number;
}

export interface OptimizationResult {
  nodes: OptimizerNode[]; // List of (semester, courseId) pairs
  success: boolean;
  error?: string;
}

export interface OptimizationProgress {
  nodes: OptimizerNode[]; // Current state
  step: number;
  totalSteps?: number;
  message?: string;
  objectiveValue?: number; // Objective value for this solution (lower is better)
  solutionNumber?: number; // Sequence number to ensure proper ordering
}

/**
 * Real optimizer that connects to backend API via Server-Sent Events (SSE)
 */
class BackendOptimizer {
  private baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  /**
   * Run optimization process with real-time streaming via SSE
   * Always yields intermediate results as the optimizer works
   */
  async *optimize(
    markers: Marker[],
    requiredCourses: string[],
    constraints?: OptimizationConstraints
  ): AsyncGenerator<OptimizationProgress> {
    // Prepare request body
    const requestBody = {
      markers: markers.map(m => ({
        courseId: m.courseId,
        section: m.section,
        status: m.status,
      })),
      requirements: requiredCourses.length > 0 ? requiredCourses : ['girs', 'major6-3new'],
      constraints: {
        maxSemesters: constraints?.maxSemesters || 12,
        maxUnitsPerSemester: constraints?.maxUnitsPerSemester || 60,
        maxUnitsIAP: constraints?.maxUnitsIAP || 12,
        maxHoursPerSemester: constraints?.maxHoursPerSemester || 60,
      },
    };

    // Make POST request to start optimization
    const response = await fetch(`${this.baseUrl}/api/optimize`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestBody),
    });

    if (!response.ok) {
      throw new Error(`Optimization request failed: ${response.statusText}`);
    }

    if (!response.body) {
      throw new Error('Response body is null');
    }

    // Parse SSE stream
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    try {
      while (true) {
        const { done, value } = await reader.read();
        
        if (done) break;

        // Decode chunk and add to buffer
        buffer += decoder.decode(value, { stream: true });

        // Process complete SSE messages
        const lines = buffer.split('\n');
        buffer = lines.pop() || ''; // Keep incomplete line in buffer

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6); // Remove 'data: ' prefix
            
            try {
              const message = JSON.parse(data);

              // Handle different message types
              if (message.type === 'progress') {
                yield {
                  nodes: [],
                  step: message.step || 0,
                  totalSteps: message.totalSteps,
                  message: message.message,
                };
              } else if (message.type === 'solution') {
                yield {
                  nodes: message.nodes || [],
                  step: message.step || 0,
                  totalSteps: message.totalSteps,
                  message: message.message,
                  objectiveValue: message.objectiveValue,
                  solutionNumber: message.solutionNumber,
                };
              } else if (message.type === 'complete') {
                // Final message - stop iteration
                return;
              } else if (message.type === 'error') {
                throw new Error(message.error || 'Optimization failed');
              }
            } catch (e) {
              console.error('Failed to parse SSE message:', data, e);
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  }
}

// Export singleton instance
export const optimizerApi = new BackendOptimizer();
