import { create } from 'zustand';
import { localStorage as localStorageApi, ApiError, roadApi } from '@/services/api';
import type { CourseNode, Edge, Section, AvailableNode, LoadingState, Marker, OptimizerNode } from '@/types';
import { optimizerApi, type OptimizationConstraints, type OptimizationProgress } from '@/services/optimizerApi';
import { computePrerequisiteEdges } from '@/lib/prerequisites';

// Re-export types for backward compatibility
export type { CourseNode, Edge, Section, AvailableNode, LoadingState, Marker, OptimizerNode };

interface GraphStore {
  // Data - separated into markers (user-defined) and optimizer results
  markers: Marker[]; // User-defined course placements (constraints)
  optimizerNodes: OptimizerNode[]; // Optimizer-suggested placements
  
  // Computed/derived data
  nodes: CourseNode[]; // Unified view for rendering (computed from markers + optimizerNodes)
  edges: Edge[]; // Computed prerequisite edges
  
  sections: Section[];
  specialSection: Section | null;
  availableNodes: AvailableNode[];

  // Loading states
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
  
  // Computed node management (backward compat with old API)
  addNode: (node: CourseNode) => Promise<void>;
  removeNode: (id: string) => Promise<void>;
  updateNode: (id: string, updates: Partial<CourseNode>) => Promise<void>;
  updateNodeLocal: (id: string, updates: Partial<CourseNode>) => void;
  
  setEdges: (edges: Edge[]) => void;
  
  loadRoadData: (data: Partial<{
    markers: Marker[];
    optimizerNodes: OptimizerNode[];
    sections: Section[];
    specialSection: Section | null;
    availableNodes: AvailableNode[];
  }>) => void;
  
  // API actions
  fetchRoadData: () => Promise<void>;
  saveRoadData: () => Promise<void>;
  optimizeRoad: (constraints?: OptimizationConstraints, showProgress?: boolean) => Promise<{ success: boolean; error?: string }>;

  // Internal helpers
  computeNodes: () => CourseNode[];
  computeEdges: () => Edge[];
  
  // Development
  loadInitialData: () => void;
  
  // Error handling
  clearError: () => void;
}

export const useGraphStore = create<GraphStore>((set, get) => ({
  // Initial state
  markers: [],
  optimizerNodes: [],
  nodes: [],
  edges: [],
  sections: [],
  specialSection: null,
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

  // Compute unified node list from markers + optimizer nodes
  computeNodes: () => {
    const { markers, optimizerNodes } = get();
    
    // Build a map of optimizer nodes by (courseId, section) for overlap detection
    const optimizerMap = new Map<string, OptimizerNode>();
    for (const on of optimizerNodes) {
      const key = `${on.courseId}_${on.section}`;
      optimizerMap.set(key, on);
    }
    
    // Markers become nodes with userControlled=true
    // Check if there's an overlapping optimizer node
    const markerNodes: CourseNode[] = markers.map((marker) => {
      const key = `${marker.courseId}_${marker.section}`;
      const hasOptimizerOverlap = optimizerMap.has(key) && marker.status !== 'banish';
      
      return {
        id: marker.id,
        courseId: marker.courseId,
        section: marker.section,
        userControlled: true,
        nodeStatus: marker.status,
        // Add flag to indicate optimizer agreement
        ...(hasOptimizerOverlap ? { optimizerAgreed: true } : {}),
      } as CourseNode & { optimizerAgreed?: boolean };
    });
    
    // Optimizer nodes become regular nodes
    // Filter out optimizer nodes that overlap with non-banish markers
    const markerKeys = new Set(
      markers
        .filter(m => m.status !== 'banish')
        .map(m => `${m.courseId}_${m.section}`)
    );
    
    const optimizerOnlyNodes: CourseNode[] = optimizerNodes
      .filter(on => {
        const key = `${on.courseId}_${on.section}`;
        return !markerKeys.has(key);
      })
      .map((on, index) => ({
        id: `optimizer_${on.courseId}_${on.section}_${index}`,
        courseId: on.courseId,
        section: on.section,
        userControlled: false,
      }));
    
    return [...markerNodes, ...optimizerOnlyNodes];
  },

  // Compute prerequisite edges
  computeEdges: () => {
    const { nodes } = get();
    
    // This is async but we can't await in Zustand
    // We'll trigger async computation and update state when done
    computePrerequisiteEdges(nodes).then(edges => {
      set({ edges });
    });
    
    // Return current edges immediately
    return get().edges;
  },

  // Marker management
  addMarker: (courseId, section, status = 'pin') => {
    const { markers } = get();
    
    const newMarker: Marker = {
      id: `marker_${courseId}_${Date.now()}`,
      courseId,
      section,
      status,
    };
    
    set({ 
      markers: [...markers, newMarker],
    });
    
    // Recompute nodes and edges
    set({ 
      nodes: get().computeNodes(),
      edges: get().computeEdges(),
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

  removeMarker: (id) => {
    const { markers } = get();

    set({
      markers: markers.filter(m => m.id !== id),
    });
    
    // Recompute nodes and edges
    set({ 
      nodes: get().computeNodes(),
      edges: get().computeEdges(),
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

  updateMarker: (id, updates) => {
    const { markers } = get();

    set({
      markers: markers.map(m => m.id === id ? { ...m, ...updates } : m),
    });
    
    // Recompute nodes and edges
    set({ 
      nodes: get().computeNodes(),
      edges: get().computeEdges(),
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

  // Backward compatibility - wrap marker operations
  addNode: async (node) => {
    if (node.userControlled) {
      get().addMarker(node.courseId, node.section, node.nodeStatus || 'pin');
    }
  },

  removeNode: async (id) => {
    // Check if it's a marker
    const marker = get().markers.find(m => m.id === id);
    if (marker) {
      get().removeMarker(id);
    }
  },

  updateNode: async (id, updates) => {
    const marker = get().markers.find(m => m.id === id);
    if (marker && updates.nodeStatus) {
      get().updateMarker(id, { status: updates.nodeStatus });
    }
  },

  updateNodeLocal: (id, updates) => {
    const marker = get().markers.find(m => m.id === id);
    if (marker) {
      const markerUpdates: Partial<Marker> = {};
      if (updates.section !== undefined) markerUpdates.section = updates.section;
      if (updates.nodeStatus !== undefined) markerUpdates.status = updates.nodeStatus;
      get().updateMarker(id, markerUpdates);
    }
  },

  setEdges: (edges) => set({ edges }),

  loadRoadData: (data) => {
    if (data.markers) set({ markers: data.markers });
    if (data.optimizerNodes) set({ optimizerNodes: data.optimizerNodes });
    if (data.sections) set({ sections: data.sections });
    if (data.specialSection) set({ specialSection: data.specialSection });
    if (data.availableNodes) set({ availableNodes: data.availableNodes });
    
    // Recompute nodes and edges
    set({ 
      nodes: get().computeNodes(),
      edges: get().computeEdges(),
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
    const cached = localStorageApi.load();
    
    if (cached) {
      // Convert old format if needed
      const markers = cached.nodes
        ?.filter((n: CourseNode) => n.userControlled)
        .map((n: CourseNode) => ({
          id: n.id,
          courseId: n.courseId,
          section: n.section,
          status: n.nodeStatus || 'pin',
        })) || [];
      
      set({
        markers,
        optimizerNodes: [],
        sections: cached.sections,
        specialSection: cached.specialSection,
        availableNodes: cached.availableNodes,
      });
      
      // Recompute
      set({ 
        nodes: get().computeNodes(),
        edges: get().computeEdges(),
        loadingState: 'success',
      });
    } else {
      // If no cached data, load initial/demo data
      get().loadInitialData();
      set({ loadingState: 'success' });
    }
  },

  // Save is automatic through localStorage
  saveRoadData: async () => {
    const { nodes, edges, sections, specialSection, availableNodes } = get();
    localStorageApi.save({ nodes, edges, sections, specialSection, availableNodes });
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
      let lastProgress: OptimizationProgress | null = null;
      
      for await (const progress of optimizerApi.optimize(
        markers,
        [], // TODO: pass required courses
        constraints
      )) {
        lastProgress = progress;
        
        // Update with intermediate results
        set({
          optimizerNodes: progress.nodes,
          optimizationProgress: showProgress ? {
            step: progress.step,
            totalSteps: progress.totalSteps,
            message: progress.message,
          } : null,
        });
        
        // Recompute nodes for live preview
        set({ 
          nodes: get().computeNodes(),
          edges: get().computeEdges(),
        });
      }

      // Finalize
      set({
        loadingState: 'success',
        isOptimizing: false,
        optimizationProgress: null,
      });

      // Save final result
      localStorageApi.save({
        nodes: get().nodes,
        edges: get().edges,
        sections: get().sections,
        specialSection: get().specialSection,
        availableNodes: get().availableNodes,
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
      { id: "marker_1", courseId: "6.120a", section: 1, status: 'pin' },
    ];
    
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
    };

    set(data);
    
    // Recompute
    set({ 
      nodes: get().computeNodes(),
      edges: get().computeEdges(),
    });
  },
}));
