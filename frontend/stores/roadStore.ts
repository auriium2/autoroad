import { create } from 'zustand';
import { storage } from '@/lib/storage';
import { fireroadApi } from '@/services/fireroad';
import type { CourseNode, Edge, Section, AvailableNode, LoadingState, Marker, OptimizerNode } from '@/types';
import { optimizerApi } from '@/services/optimizer';
import { useOptimizationStore } from '@/stores/optimizationStore';

// DEBUG: Clear localStorage on every page load (remove this in production)
if (typeof window !== 'undefined') {
  console.log('DEBUG: Clearing localStorage on module load...');
  window.localStorage.removeItem('autoroad_data');
  window.localStorage.removeItem('optimization-storage');
  window.localStorage.removeItem('autoroad_query_cache');
}

export type { CourseNode, Section, OptimizerNode, Edge, AvailableNode, Marker };

interface GraphStore {
  markers: Marker[]; // User-defined course placements (constraints)
  optimizerNodes: OptimizerNode[]; // Optimizer-suggested placements

  sections: Section[];
  availableNodes: AvailableNode[];

  loadingState: LoadingState;
  error: string | null;
  isSaving: boolean;
  isOptimizing: boolean;

  // Optimization progress tracking
  optimizationProgress: {
    step: number;
    totalSteps?: number;
    message?: string;
    solutionNumber?: number;
  } | null;

  // Cost breakdown from last optimization
  lastCostBreakdown: Record<string, number> | null;

  // Track if markers have changed since last optimization
  markersChangedSinceOptimization: boolean;

  // Track optimization result status
  lastOptimizationStatus: 'OPTIMAL' | 'FEASIBLE' | 'INFEASIBLE' | 'MODEL_INVALID' | null;

  // Optimization cancellation
  optimizationAbortController: AbortController | null;

  // User info
  userId: string | null;

  // Actions for markers
  setUserId: (userId: string | null) => void;

  addMarker: (courseId: string, section: number, status?: 'pin' | 'banish' | 'override') => void;
  removeMarker: (id: string) => void;
  updateMarker: (id: string, updates: Partial<Marker>) => void;

  loadRoadData: (data: Partial<{
    markers: Marker[];
    optimizerNodes: OptimizerNode[];
    sections: Section[];
    availableNodes: AvailableNode[];
  }>) => void;

  // API actions
  fetchRoadData: () => Promise<void>;
  saveRoadData: () => Promise<void>;
  optimizeRoad: (maxSemesters?: number, showProgress?: boolean) => Promise<{ success: boolean; error?: string }>;
  cancelOptimization: () => void;

  // Development
  loadInitialData: () => void;

  // Error handling
  clearError: () => void;
}

export const useGraphStore = create<GraphStore>((set, get) => ({
  // Initial state
  markers: [],
  optimizerNodes: [],
  sections: [],
  availableNodes: [],
  loadingState: 'loading',
  error: null,
  isSaving: false,
  isOptimizing: false,
  lastCostBreakdown: null,
  optimizationProgress: null,
  markersChangedSinceOptimization: false,
  lastOptimizationStatus: null,
  optimizationAbortController: null,
  userId: null,

  // User actions
  setUserId: (userId) => set({ userId }),

  clearError: () => set({ error: null }),

  // Marker management
  addMarker: (courseId, section, status = 'pin') => {
    const { markers, optimizerNodes } = get();

    const newMarker: Marker = {
      uuid: `marker_${courseId}_${Date.now()}`,
      courseId,
      section,
      status,
    };

    set({
      markers: [...markers, newMarker],
      markersChangedSinceOptimization: optimizerNodes.length > 0,
      lastOptimizationStatus: null,
    });
  },

  removeMarker: (uuid) => {
    const { markers, optimizerNodes } = get();

    set({
      markers: markers.filter(m => m.uuid !== uuid),
      markersChangedSinceOptimization: optimizerNodes.length > 0,
      lastOptimizationStatus: null,
    });
  },

  updateMarker: (uuid, updates) => {
    const { markers, optimizerNodes } = get();

    set({
      markers: markers.map(m => m.uuid === uuid ? { ...m, ...updates } : m),
      markersChangedSinceOptimization: optimizerNodes.length > 0,
      lastOptimizationStatus: null,
    });
  },

  loadRoadData: (data) => {
    if (data.markers) set({ markers: data.markers });
    if (data.optimizerNodes) set({ optimizerNodes: data.optimizerNodes });
    if (data.sections) set({ sections: data.sections });
    if (data.availableNodes) set({ availableNodes: data.availableNodes });
  },

  // Load road data from localStorage
  fetchRoadData: async () => {
    set({ loadingState: 'loading', error: null });

    // DEBUG: Clear localStorage on every page load (remove this in production)
    const DEBUG_CLEAR_ON_RELOAD = true;
    if (DEBUG_CLEAR_ON_RELOAD && typeof window !== 'undefined') {
      console.log('DEBUG: Clearing localStorage on page reload...');
      window.localStorage.removeItem('autoroad_data');
      window.localStorage.removeItem('optimization-storage');
      window.localStorage.removeItem('autoroad_query_cache');
    }

    // Load from localStorage
    const cached = storage.load();

    if (cached) {
      // Convert old format if needed
      const markers = cached.nodes
        ?.filter((n: CourseNode) => n.userControlled)
        .map((n: CourseNode) => ({
          uuid: n.uuid,
          courseId: n.courseId,
          section: n.section,
          status: n.nodeStatus || 'pin',
        })) || [];

      set({
        markers,
        optimizerNodes: [],
        sections: cached.sections,
        availableNodes: cached.availableNodes,
        loadingState: 'success',
      });
    } else {
      // If no cached data, load initial/demo data
      get().loadInitialData();
      set({ loadingState: 'success' });
    }
  },

  // Save is no longer needed - state is ephemeral or will be saved via API
  saveRoadData: async () => {
    // TODO: Save to backend API when available
    // For now, this is a no-op since we don't persist to localStorage anymore
  },

  // Optimization - always streams progress
  optimizeRoad: async (maxSemesters = 12, showProgress = true) => {
    const { markers } = get();

    // Get objectives, requirements, year, lockPastSemesters, hard constraints, and tiers from optimization store
    const selectedObjectives = useOptimizationStore.getState().selectedObjectives;
    const selectedRequirements = useOptimizationStore.getState().selectedRequirements;
    const selectedYear = useOptimizationStore.getState().selectedYear;
    const lockPastSemesters = useOptimizationStore.getState().lockPastSemesters;
    const selectedHardConstraints = useOptimizationStore.getState().selectedHardConstraints;
    const requirementTiers = useOptimizationStore.getState().requirementTiers;
    const objectiveTiers = useOptimizationStore.getState().objectiveTiers;

    // Create AbortController for this optimization
    const abortController = new AbortController();

    set({
      loadingState: 'loading',
      error: null,
      isOptimizing: true,
      optimizationProgress: showProgress ? { step: 0 } : null,
      markersChangedSinceOptimization: false,
      optimizationAbortController: abortController,
      lastOptimizationStatus: null,  // Reset status so toast will trigger again
    });

    try {
      let lastRenderTime = 0;
      const RENDER_THROTTLE_MS = 800;
      let latestNodes: OptimizerNode[] = [];
      let lastProgressUpdate = 0;
      const PROGRESS_THROTTLE_MS = 100;

      // Convert graduation year to planning year if selected
      let planningYear: string | undefined;
      if (selectedYear) {
        const { graduationYearToPlanningYear } = await import('@/lib/yearUtils');
        planningYear = graduationYearToPlanningYear(selectedYear);
      }

      // Fetch course categories for displaying category tier stars
      try {
        console.log('[Optimizer] Fetching course categories...');
        const courseCategories = await optimizerApi.getCourseCategories(
          markers,
          selectedRequirements,
          maxSemesters,
          planningYear
        );
        console.log(`[Optimizer] Fetched categories for ${Object.keys(courseCategories).length} courses`);
        useOptimizationStore.getState().setCourseCategories(courseCategories);
      } catch (error) {
        console.error('[Optimizer] Failed to fetch course categories:', error);
      }

      // Pass objectives as-is
      const objectivesWithParams = selectedObjectives.length > 0 ? selectedObjectives : undefined;

      // Stream optimization progress
      for await (const progress of optimizerApi.optimize(
        markers,
        selectedRequirements,
        maxSemesters,
        abortController.signal,
        objectivesWithParams,
        selectedHardConstraints,
        planningYear,
        lockPastSemesters,
        requirementTiers,
        objectiveTiers
      )) {
        // Handle completion status
        if (progress.isComplete && progress.status) {
          set({ lastOptimizationStatus: progress.status });
          continue;
        }

        if (progress.nodes.length > 0) {
          latestNodes = progress.nodes;

          // Store cost breakdown if available
          if (progress.costBreakdown) {
            set({ lastCostBreakdown: progress.costBreakdown });
          }

          // Throttle UI updates to reduce rendering lag
          const now = Date.now();
          const timeSinceLastRender = now - lastRenderTime;
          const timeSinceLastProgress = now - lastProgressUpdate;

          if (timeSinceLastRender >= RENDER_THROTTLE_MS) {
            lastRenderTime = now;
            lastProgressUpdate = now;

            set({
              optimizerNodes: latestNodes,
              optimizationProgress: showProgress ? {
                step: progress.step,
                totalSteps: progress.totalSteps,
                message: progress.message,
                solutionNumber: progress.solutionNumber,
              } : null,
            });
          } else if (showProgress && timeSinceLastProgress >= PROGRESS_THROTTLE_MS) {
            // Update progress without nodes for smoother progress indicator
            lastProgressUpdate = now;
            set({
              optimizationProgress: {
                step: progress.step,
                totalSteps: progress.totalSteps,
                message: progress.message,
                solutionNumber: progress.solutionNumber,
              },
            });
          }
        } else {
          // Progress messages without nodes (e.g., "Initializing...")
          set({
            optimizationProgress: showProgress ? {
              step: progress.step,
              totalSteps: progress.totalSteps,
              message: progress.message,
              solutionNumber: progress.solutionNumber,
            } : null,
          });
        }
      }

      // Final update with the latest solution (in case it was throttled)
      if (latestNodes.length > 0) {
        set({
          optimizerNodes: latestNodes,
        });
      }

      // Finalize
      set({
        loadingState: 'success',
        isOptimizing: false,
        optimizationProgress: null,
        optimizationAbortController: null,
      });

      return { success: true };
    } catch (error) {
      // Check if it was cancelled
      if (error instanceof Error && error.name === 'AbortError') {
        set({
          loadingState: 'idle',
          isOptimizing: false,
          optimizationProgress: null,
          optimizationAbortController: null,
        });
        return { success: false, error: 'Optimization cancelled' };
      }

      const errorMessage = error instanceof Error ? error.message : 'Optimization failed';
      set({
        loadingState: 'error',
        error: errorMessage,
        isOptimizing: false,
        optimizationProgress: null,
        optimizationAbortController: null,
      });
      return { success: false, error: errorMessage };
    }
  },

  cancelOptimization: () => {
    const { optimizationAbortController } = get();
    if (optimizationAbortController) {
      optimizationAbortController.abort();
    }
  },

  // Load sample data for development/demo
  loadInitialData: () => {

  },
}));
