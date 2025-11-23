import { create } from 'zustand';
import { storage } from '@/lib/storage';
import { ApiError, fireroadApi } from '@/services/fireroad';
import type { CourseNode, Edge, Section, AvailableNode, LoadingState, Marker, OptimizerNode } from '@/types';
import { optimizerApi, type OptimizationConstraints, type OptimizationProgress, type ObjectiveConfig } from '@/services/optimizer';
import { useOptimizationStore } from '@/stores/optimizationStore';

export type { CourseNode, Section, OptimizerNode, Edge, AvailableNode };

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
  } | null;

  // Track if markers have changed since last optimization
  markersChangedSinceOptimization: boolean;

  // Track optimization result status
  lastOptimizationStatus: 'OPTIMAL' | 'FEASIBLE' | 'INFEASIBLE' | 'MODEL_INVALID' | null;

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
  optimizeRoad: (constraints?: OptimizationConstraints, showProgress?: boolean) => Promise<{ success: boolean; error?: string }>;

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
  optimizationProgress: null,
  markersChangedSinceOptimization: false,
  lastOptimizationStatus: null,
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
  optimizeRoad: async (constraints, showProgress = true) => {
    const { markers } = get();
    
    // Get objectives, requirements, year, and lockPastSemesters from optimization store
    const selectedObjectives = useOptimizationStore.getState().selectedObjectives;
    const selectedRequirements = useOptimizationStore.getState().selectedRequirements;
    const selectedYear = useOptimizationStore.getState().selectedYear;
    const lockPastSemesters = useOptimizationStore.getState().lockPastSemesters;

    set({
      loadingState: 'loading',
      error: null,
      isOptimizing: true,
      optimizationProgress: showProgress ? { step: 0 } : null,
      markersChangedSinceOptimization: false,
    });

    try {
      let lastRenderTime = 0;
      const RENDER_THROTTLE_MS = 500;
      let latestNodes: OptimizerNode[] = [];

      // Convert graduation year to planning year if selected
      let planningYear: string | undefined;
      if (selectedYear) {
        const { graduationYearToPlanningYear } = await import('@/lib/yearUtils');
        planningYear = graduationYearToPlanningYear(selectedYear);
      }

      // Stream optimization progress
      for await (const progress of optimizerApi.optimize(
        markers,
        selectedRequirements,
        constraints,
        selectedObjectives.length > 0 ? selectedObjectives : undefined,
        planningYear,
        lockPastSemesters
      )) {
        // Handle completion status
        if (progress.isComplete && progress.status) {
          set({ lastOptimizationStatus: progress.status });
          continue;
        }
        
        if (progress.nodes.length > 0) {
          latestNodes = progress.nodes;

          // Throttle UI updates to reduce rendering lag
          const now = Date.now();
          const timeSinceLastRender = now - lastRenderTime;
          if (timeSinceLastRender >= RENDER_THROTTLE_MS) {
            lastRenderTime = now;

            set({
              optimizerNodes: latestNodes,
              optimizationProgress: showProgress ? {
                step: progress.step,
                totalSteps: progress.totalSteps,
                message: progress.message,
              } : null,
            });
          }
        } else {
          // Progress messages without nodes (e.g., "Initializing...")
          set({
            optimizationProgress: showProgress ? {
              step: progress.step,
              totalSteps: progress.totalSteps,
              message: progress.message,
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
      });

      return { success: true };
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Optimization failed';
      set({
        loadingState: 'error',
        error: errorMessage,
        isOptimizing: false,
        optimizationProgress: null,
      });
      return { success: false, error: errorMessage };
    }
  },

  // Load sample data for development/demo
  loadInitialData: () => {

  },
}));
