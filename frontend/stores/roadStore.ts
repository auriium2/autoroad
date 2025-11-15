import { create } from 'zustand';
import { storage } from '@/lib/storage';
import { ApiError } from '@/services/fireroad';
import type { CourseNode, Edge, Section, AvailableNode, LoadingState, Marker, OptimizerNode } from '@/types';
import { optimizerApi, type OptimizationConstraints, type OptimizationProgress } from '@/services/optimizer';

// Re-export types for backward compatibility
export type { CourseNode, Edge, Section, AvailableNode, LoadingState, Marker, OptimizerNode };

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

  // User info
  userId: string | null;

  // Actions for markers
  setUserId: (userId: string | null) => void;

  addMarker: (courseId: string, section: number, status?: 'pin' | 'banish' | 'solo') => void;
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
  userId: null,

  // User actions
  setUserId: (userId) => set({ userId }),

  clearError: () => set({ error: null }),

  // Marker management
  addMarker: (courseId, section, status = 'pin') => {
    const { markers } = get();

    const newMarker: Marker = {
      uuid: `marker_${courseId}_${Date.now()}`,
      courseId,
      section,
      status,
    };

    set({
      markers: [...markers, newMarker],
    });
  },

  removeMarker: (uuid) => {
    const { markers } = get();

    set({
      markers: markers.filter(m => m.uuid !== uuid),
    });
  },

  updateMarker: (uuid, updates) => {
    const { markers } = get();

    set({
      markers: markers.map(m => m.uuid === uuid ? { ...m, ...updates } : m),
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

    set({
      loadingState: 'loading',
      error: null,
      isOptimizing: true,
      optimizationProgress: showProgress ? {} as any : null,
    });

    try {
      // Stream optimization progress
      for await (const progress of optimizerApi.optimize(
        markers,
        [], // TODO: pass required courses
        constraints
      )) {

        set({
          optimizerNodes: progress.nodes,
          optimizationProgress: showProgress ? {
            step: progress.step,
            totalSteps: progress.totalSteps,
            message: progress.message,
          } : null,
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
    const markers: Marker[] = [
      { uuid: "marker_1", courseId: "6.120a", section: 1, status: 'pin' },
    ];

    set({
      sections: [
        { id: 0, title: "Freshman Fall" },
        { id: 1, title: "Freshman Spring" },
        { id: 2, title: "Sophomore Fall" },
        { id: 3, title: "Sophomore Spring" },
        { id: 4, title: "Junior Fall" },
        { id: 5, title: "Junior Spring" },
      ],
      markers,
      optimizerNodes: [
        { courseId: "18.01", section: -1 },
        { courseId: "6.100", section: 0 },
        { courseId: "6.1200", section: 1 },
        { courseId: "6.1010", section: 2 },
        { courseId: "6.1020", section: 3 },
        { courseId: "6.1030", section: 3 },
        { courseId: "6.1040", section: 3 },
        { courseId: "6.1050", section: 4 },
        { courseId: "6.1060", section: 5 },
        { courseId: "6.1070", section: 5 },
      ] as OptimizerNode[],
      availableNodes: [],
    });
  },
}));
