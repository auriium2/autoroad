import { create } from 'zustand';

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

interface GraphStore {
  // Data
  nodes: CourseNode[];
  edges: Edge[];
  sections: Section[];
  specialSection: Section | null;
  availableNodes: AvailableNode[];

  // Actions
  addNode: (node: CourseNode) => void;
  removeNode: (id: string) => void;
  updateNode: (id: string, updates: Partial<CourseNode>) => void;
  setEdges: (edges: Edge[]) => void;
  loadRoadData: (data: {
    nodes?: CourseNode[];
    sections?: Section[];
    edges?: Edge[];
    specialSection?: Section | null;
    availableNodes?: AvailableNode[];
  }) => void;
  loadInitialData: () => void;
}

export const useGraphStore = create<GraphStore>((set) => ({
  // Initial state
  nodes: [],
  edges: [],
  sections: [],
  specialSection: null,
  availableNodes: [],

  // Actions
  addNode: (node) => set((state) => ({ 
    nodes: [...state.nodes, node] 
  })),

  removeNode: (id) => set((state) => ({
    nodes: state.nodes.filter(n => n.id !== id),
    edges: state.edges.filter(e => e.from_id !== id && e.to_id !== id)
  })),

  updateNode: (id, updates) => set((state) => ({
    nodes: state.nodes.map(n => n.id === id ? { ...n, ...updates } : n)
  })),

  setEdges: (edges) => set({ edges }),

  loadRoadData: (data) => set((state) => ({
    nodes: data.nodes ?? state.nodes,
    sections: data.sections ?? state.sections,
    edges: data.edges ?? state.edges,
    specialSection: data.specialSection ?? state.specialSection,
    availableNodes: data.availableNodes ?? state.availableNodes,
  })),

  // Load sample data for development
  loadInitialData: () => set({
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
  }),
}));
