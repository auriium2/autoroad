/**
 * Optimizer API service
 * Handles communication with the backend optimizer
 * Supports both one-shot optimization and live streaming of optimization progress
 */

import type { Marker, OptimizerNode } from '@/types';

export interface OptimizationConstraints {
  maxUnitsPerSemester?: number;
  minUnitsPerSemester?: number;
  preferredTimes?: string[];
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
}

/**
 * Mock optimizer that simulates optimization steps
 * In production, this would connect to a backend API or WebSocket
 */
class MockOptimizer {
  private mockDelay = 500; // ms between steps
  
  /**
   * Run optimization process
   * Always yields intermediate results as the optimizer works
   * The caller can choose to only use the final result or show progress
   */
  async *optimize(
    markers: Marker[],
    requiredCourses: string[],
    constraints?: OptimizationConstraints
  ): AsyncGenerator<OptimizationProgress> {
    // Simulate optimizer working through steps
    const steps = [
      {
        step: 1,
        message: "Analyzing prerequisites...",
        nodes: markers.filter(m => m.status !== 'banish').map(m => ({
          courseId: m.courseId,
          section: m.section,
        })),
      },
      {
        step: 2,
        message: "Distributing required courses...",
        nodes: [
          ...markers.filter(m => m.status !== 'banish').map(m => ({
            courseId: m.courseId,
            section: m.section,
          })),
          { courseId: "6.1010", section: 2 },
          { courseId: "6.1030", section: 3 },
        ],
      },
      {
        step: 3,
        message: "Optimizing unit distribution...",
        nodes: [
          ...markers.filter(m => m.status !== 'banish').map(m => ({
            courseId: m.courseId,
            section: m.section,
          })),
          { courseId: "6.1010", section: 2 },
          { courseId: "6.1020", section: 3 },
          { courseId: "6.1030", section: 3 },
          { courseId: "6.1040", section: 3 },
        ],
      },
      {
        step: 4,
        message: "Finalizing schedule...",
        nodes: [
          ...markers.filter(m => m.status !== 'banish').map(m => ({
            courseId: m.courseId,
            section: m.section,
          })),
          { courseId: "6.1010", section: 2 },
          { courseId: "6.1020", section: 3 },
          { courseId: "6.1030", section: 3 },
          { courseId: "6.1040", section: 3 },
          { courseId: "6.1050", section: 4 },
          { courseId: "6.1060", section: 5 },
          { courseId: "6.1070", section: 5 },
        ],
      },
    ];
    
    for (const stepData of steps) {
      await new Promise(resolve => setTimeout(resolve, this.mockDelay));
      yield {
        ...stepData,
        totalSteps: steps.length,
      };
    }
  }
}

// Export singleton instance
export const optimizerApi = new MockOptimizer();

/**
 * TODO: Real WebSocket implementation would look like:
 * 
 * class WebSocketOptimizer {
 *   private ws: WebSocket | null = null;
 *   
 *   async *streamOptimization(...) {
 *     this.ws = new WebSocket('ws://backend/optimize');
 *     
 *     // Send request
 *     this.ws.send(JSON.stringify({ markers, requiredCourses, constraints }));
 *     
 *     // Yield updates as they come
 *     for await (const message of this.iterateMessages(this.ws)) {
 *       yield JSON.parse(message) as OptimizationProgress;
 *     }
 *   }
 * }
 */
