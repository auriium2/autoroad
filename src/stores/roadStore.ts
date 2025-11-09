import { create } from 'zustand';
import { roadApi, localStorage as localStorageApi, ApiError } from '@/services/api';

// Course node representing a single class
export interface CourseNode {
  id: string;
  label: string;
  section: number; // Which semester/section this belongs to
  locked?: boolean;
  disabled?: boolean;
  user_added?: boolean;
}

// Edge between two courses (prerequisite relationship)
export interface Edge {
  from_id: string;
  to_id: string;
}

// Section (semester)
export interface Section {
  id: number;
  title: string;
}

// Available node for adding
export interface AvailableNode {
  id: string;
  name: string;
  category: string;
  description: string;
}

// Loading state
export type LoadingState = 'idle' | 'loading' | 'success' | 'error';

interface GraphStore {
  // Data
  nodes: CourseNode[];
  edges: Edge[];
  sections: Section[];
  specialSection: Section | null;
  availableNodes: AvailableNode[];

  // Loading states
  loadingState: LoadingState;
  error: string | null;
  isSaving: boolean;

  // User info
  userId: string | null;

  // Actions
  setUserId: (userId: string | null) => void;
  
  addNode: (node: CourseNode) => Promise<void>;
  removeNode: (id: string) => Promise<void>;
  updateNode: (id: string, updates: Partial<CourseNode>) => Promise<void>;
  
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
  loadingState: 'idle',
  error: null,
  isSaving: false,
  userId: null,

  // User actions
  setUserId: (userId) => set({ userId }),

  clearError: () => set({ error: null }),

  // Node actions with optimistic updates
  addNode: async (node) => {
    const { userId, nodes } = get();
    
    // Optimistic update
    set({ nodes: [...nodes, node] });

    try {
      await roadApi.addNode(node, userId || undefined);
      // Save to localStorage as backup
      localStorageApi.save({
        nodes: get().nodes,
        edges: get().edges,
        sections: get().sections,
        specialSection: get().specialSection,
        availableNodes: get().availableNodes,
      });
    } catch (error) {
      // Rollback on error
      set({ nodes: nodes.filter(n => n.id !== node.id) });
      set({ error: error instanceof ApiError ? error.message : 'Failed to add node' });
      throw error;
    }
  },

  removeNode: async (id) => {
    const { userId, nodes, edges } = get();
    
    // Store for rollback
    const previousNodes = nodes;
    const previousEdges = edges;

    // Optimistic update
    set({
      nodes: nodes.filter(n => n.id !== id),
      edges: edges.filter(e => e.from_id !== id && e.to_id !== id),
    });

    try {
      await roadApi.removeNode(id, userId || undefined);
      localStorageApi.save({
        nodes: get().nodes,
        edges: get().edges,
        sections: get().sections,
        specialSection: get().specialSection,
        availableNodes: get().availableNodes,
      });
    } catch (error) {
      // Rollback on error
      set({ nodes: previousNodes, edges: previousEdges });
      set({ error: error instanceof ApiError ? error.message : 'Failed to remove node' });
      throw error;
    }
  },

  updateNode: async (id, updates) => {
    const { userId, nodes } = get();
    
    // Store for rollback
    const previousNodes = nodes;

    // Optimistic update
    set({
      nodes: nodes.map(n => n.id === id ? { ...n, ...updates } : n),
    });

    try {
      await roadApi.updateNode(id, updates, userId || undefined);
      localStorageApi.save({
        nodes: get().nodes,
        edges: get().edges,
        sections: get().sections,
        specialSection: get().specialSection,
        availableNodes: get().availableNodes,
      });
    } catch (error) {
      // Rollback on error
      set({ nodes: previousNodes });
      set({ error: error instanceof ApiError ? error.message : 'Failed to update node' });
      throw error;
    }
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

  // Fetch road data from API with localStorage fallback
  fetchRoadData: async () => {
    const { userId } = get();
    
    set({ loadingState: 'loading', error: null });

    try {
      // Try to fetch from API
      const data = await roadApi.fetchRoadData(userId || undefined);
      
      set({
        nodes: data.nodes,
        edges: data.edges,
        sections: data.sections,
        specialSection: data.specialSection,
        availableNodes: data.availableNodes,
        loadingState: 'success',
      });

      // Save to localStorage
      localStorageApi.save(data);
    } catch (error) {
      console.error('Failed to fetch from API, trying localStorage...', error);
      
      // Fallback to localStorage
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
        set({
          loadingState: 'error',
          error: error instanceof ApiError ? error.message : 'Failed to load road data',
        });
      }
    }
  },

  // Save road data to API
  saveRoadData: async () => {
    const { userId, nodes, edges, sections, specialSection, availableNodes } = get();
    
    set({ isSaving: true, error: null });

    try {
      await roadApi.saveRoadData(
        { nodes, edges, sections, specialSection, availableNodes },
        userId || undefined
      );

      // Also save to localStorage
      localStorageApi.save({ nodes, edges, sections, specialSection, availableNodes });
      
      set({ isSaving: false });
    } catch (error) {
      set({
        isSaving: false,
        error: error instanceof ApiError ? error.message : 'Failed to save road data',
      });
      throw error;
    }
  },

  // Optimize road schedule
  optimizeRoad: async (constraints) => {
    const { sections, specialSection } = get();
    
    set({ loadingState: 'loading', error: null });

    try {
      const result = await roadApi.optimizeRoad({
        sections,
        specialSection,
        constraints: constraints || {},
      });

      if (result.success && result.data) {
        set({
          nodes: result.data.nodes,
          edges: result.data.edges,
          sections: result.data.sections,
          specialSection: result.data.specialSection,
          loadingState: 'success',
        });

        // Save to localStorage
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
        { id: "0", label: "18.01", section: -1 },
        { id: "1", label: "6.100", section: 0 },
        { id: "2", label: "6.1200", section: 1 },
        { id: "3", label: "6.120a", section: 1, locked: true },
        { id: "4", label: "6.1010", section: 2 },
        { id: "5", label: "6.1020", section: 3 },
        { id: "6", label: "6.1030", section: 3 },
        { id: "7", label: "6.1040", section: 3 },
        { id: "8", label: "6.1050", section: 4 },
        { id: "9", label: "6.1060", section: 5 },
        { id: "10", label: "6.1070", section: 5 },
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
      availableNodes: [
        {
          id: "auth-1",
          name: "OAuth Authentication",
          category: "Authentication",
          description: "Implement OAuth 2.0 authentication flow",
        },
        {
          id: "auth-2",
          name: "JWT Validation",
          category: "Authentication",
          description: "Validate JSON Web Tokens",
        },
      ],
    };

    set(data);
  },
}));
