import { create } from 'zustand';
import { localStorage as localStorageApi, ApiError, roadApi } from '@/services/api';
import type { CourseNode, Edge, Section, AvailableNode, LoadingState } from '@/types';

// Re-export types for backward compatibility
export type { CourseNode, Edge, Section, AvailableNode, LoadingState };

interface GraphStore {
  // Data - user's current course selection state
  nodes: CourseNode[];
  edges: Edge[];
  sections: Section[];
  specialSection: Section | null;
  availableNodes: AvailableNode[];

  // Loading states
  loadingState: LoadingState;
  error: string | null;
  isSaving: boolean;

  // Change tracking
  hasChangesSinceOptimization: boolean;

  // User info
  userId: string | null;

  // Actions
  setUserId: (userId: string | null) => void;
  
  addNode: (node: CourseNode) => Promise<void>;
  removeNode: (id: string) => Promise<void>;
  updateNode: (id: string, updates: Partial<CourseNode>) => Promise<void>;
  updateNodeLocal: (id: string, updates: Partial<CourseNode>) => void;
  
  setEdges: (edges: Edge[]) => void;
  
  loadRoadData: (data: Partial<{
    nodes: CourseNode[];
    sections: Section[];
    edges: Edge[];
    specialSection: Section | null;
    availableNodes: AvailableNode[];
  }>) => void;
  
  // API actions
  fetchRoadData: () => Promise<void>;
  saveRoadData: () => Promise<void>;
  optimizeRoad: (constraints?: {
    maxUnitsPerSemester?: number;
    minUnitsPerSemester?: number;
    preferredTimes?: string[];
  }) => Promise<{ success: boolean; error?: string }>;

  // Development
  loadInitialData: () => void;
  
  // Error handling
  clearError: () => void;
}

export const useGraphStore = create<GraphStore>((set, get) => ({
  // Initial state
  nodes: [],
  edges: [],
  sections: [],
  specialSection: null,
  availableNodes: [],
  loadingState: 'loading',
  error: null,
  isSaving: false,
  hasChangesSinceOptimization: false,
  userId: null,

  // User actions
  setUserId: (userId) => set({ userId }),

  clearError: () => set({ error: null }),

  // Node actions with optimistic updates
  addNode: async (node) => {
    const { nodes } = get();
    
    // Update state and mark changes if user-controlled
    set({ 
      nodes: [...nodes, node],
      hasChangesSinceOptimization: node.userControlled ? true : get().hasChangesSinceOptimization
    });

    // Save to localStorage
    localStorageApi.save({
      nodes: get().nodes,
      edges: get().edges,
      sections: get().sections,
      specialSection: get().specialSection,
      availableNodes: get().availableNodes,
    });
  },

  removeNode: async (id) => {
    const { nodes, edges } = get();

    // Update state
    set({
      nodes: nodes.filter(n => n.id !== id),
      edges: edges.filter(e => e.from_id !== id && e.to_id !== id),
    });

    // Save to localStorage
    localStorageApi.save({
      nodes: get().nodes,
      edges: get().edges,
      sections: get().sections,
      specialSection: get().specialSection,
      availableNodes: get().availableNodes,
    });
  },

  updateNode: async (id, updates) => {
    const { nodes } = get();

    // Update state
    set({
      nodes: nodes.map(n => n.id === id ? { ...n, ...updates } : n),
    });

    // Save to localStorage
    localStorageApi.save({
      nodes: get().nodes,
      edges: get().edges,
      sections: get().sections,
      specialSection: get().specialSection,
      availableNodes: get().availableNodes,
    });
  },

  updateNodeLocal: (id, updates) => {
    const { nodes } = get();
    const node = nodes.find(n => n.id === id);
    
    // If updating section (moving node) and node is user-controlled, mark changes
    const isMoving = updates.section !== undefined && node?.section !== updates.section;
    const shouldMarkChanges = isMoving && node?.userControlled;
    
    // Update only local state, no API call
    set({
      nodes: nodes.map(n => n.id === id ? { ...n, ...updates } : n),
      hasChangesSinceOptimization: shouldMarkChanges ? true : get().hasChangesSinceOptimization,
    });

    // Save to localStorage
    localStorageApi.save({
      nodes: get().nodes,
      edges: get().edges,
      sections: get().sections,
      specialSection: get().specialSection,
      availableNodes: get().availableNodes,
    });
  },

  setEdges: (edges) => set({ edges }),

  loadRoadData: (data) => {
    set((state) => ({
      nodes: data.nodes ?? state.nodes,
      sections: data.sections ?? state.sections,
      edges: data.edges ?? state.edges,
      specialSection: data.specialSection ?? state.specialSection,
      availableNodes: data.availableNodes ?? state.availableNodes,
    }));

    // Save to localStorage
    localStorageApi.save({
      nodes: get().nodes,
      edges: get().edges,
      sections: get().sections,
      specialSection: get().specialSection,
      availableNodes: get().availableNodes,
    });
  },

  // Load road data from localStorage
  fetchRoadData: async () => {
    set({ loadingState: 'loading', error: null });

    // TEMPORARY: Clear old localStorage data with old schema
    if (typeof window !== 'undefined') {
      const stored = window.localStorage.getItem('autoroad_data');
      if (stored && stored.includes('"locked"')) {
        console.log('Clearing old localStorage data with outdated schema...');
        window.localStorage.removeItem('autoroad_data');
      }
    }

    // Load from localStorage
    const cached = localStorageApi.load();
    
    if (cached) {
      set({
        nodes: cached.nodes,
        edges: cached.edges,
        sections: cached.sections,
        specialSection: cached.specialSection,
        availableNodes: cached.availableNodes,
        loadingState: 'success',
      });
    } else {
      // If no cached data, load initial/demo data
      get().loadInitialData();
      set({ loadingState: 'success' });
    }
  },

  // Save is automatic through localStorage in add/remove/update methods
  saveRoadData: async () => {
    const { nodes, edges, sections, specialSection, availableNodes } = get();
    
    // Just save to localStorage
    localStorageApi.save({ nodes, edges, sections, specialSection, availableNodes });
  },

  // Optimize road schedule - sends current state to API for optimization
  optimizeRoad: async (constraints) => {
    const { nodes, edges, sections, specialSection, availableNodes } = get();
    
    set({ loadingState: 'loading', error: null });

    try {
      // Send current state to optimizer
      const currentState = { nodes, edges, sections, specialSection, availableNodes };
      const result = await roadApi.optimizeRoad(currentState, constraints);

      if (result.success && result.data) {
        set({
          nodes: result.data.nodes,
          edges: result.data.edges,
          sections: result.data.sections,
          specialSection: result.data.specialSection,
          loadingState: 'success',
          hasChangesSinceOptimization: false, // Reset tracking after successful optimization
        });

        // Save optimized result to localStorage
        localStorageApi.save(result.data);

        return { success: true };
      } else {
        set({
          loadingState: 'error',
          error: result.error || 'Optimization failed',
        });
        return { success: false, error: result.error };
      }
    } catch (error) {
      const errorMessage = error instanceof ApiError ? error.message : 'Optimization failed';
      set({
        loadingState: 'error',
        error: errorMessage,
      });
      return { success: false, error: errorMessage };
    }
  },

  // Load sample data for development/demo
  loadInitialData: () => {
    const data = {
      sections: [
        { id: 0, title: "Freshman Fall" },
        { id: 1, title: "Freshman Spring" },
        { id: 2, title: "Sophomore Fall" },
        { id: 3, title: "Sophomore Spring" },
        { id: 4, title: "Junior Fall" },
        { id: 5, title: "Junior Spring" },
      ],
      specialSection: {
        id: -1,
        title: "ASEs",
      },
      nodes: [
        { id: "0", courseId: "18.01", section: -1 },
        { id: "1", courseId: "6.100", section: 0 },
        { id: "2", courseId: "6.1200", section: 1 },
        { id: "3", courseId: "6.120a", section: 1, userControlled: true },
        { id: "4", courseId: "6.1010", section: 2 },
        { id: "5", courseId: "6.1020", section: 3 },
        { id: "6", courseId: "6.1030", section: 3 },
        { id: "7", courseId: "6.1040", section: 3 },
        { id: "8", courseId: "6.1050", section: 4 },
        { id: "9", courseId: "6.1060", section: 5 },
        { id: "10", courseId: "6.1070", section: 5 },
      ],
      edges: [
        { from_id: "1", to_id: "2" },
        { from_id: "2", to_id: "4" },
        { from_id: "3", to_id: "4" },
        { from_id: "4", to_id: "5" },
        { from_id: "5", to_id: "8" },
        { from_id: "6", to_id: "8" },
        { from_id: "8", to_id: "9" },
        { from_id: "1", to_id: "8" },
        { from_id: "3", to_id: "9" },
        { from_id: "2", to_id: "9" },
      ],
      availableNodes: [],
    };

    set(data);
  },
}));
