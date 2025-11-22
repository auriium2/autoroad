import { create } from 'zustand';
import type { ObjectiveConfig } from '@/services/optimizer';
import { useGraphStore } from './roadStore';

interface OptimizationState {
  selectedObjectives: ObjectiveConfig[];
  selectedRequirements: string[];
  selectedYear?: string;
  lockPastSemesters: boolean;
  expandedRequirements: string[];
  expandedRequirementNodes: Record<string, Set<string>>;
  requirementTiers: Record<string, number>;
  objectiveTiers: Record<string, number>;
  
  setObjectives: (objectives: ObjectiveConfig[]) => void;
  setRequirements: (requirements: string[]) => void;
  setYear: (year?: string) => void;
  setLockPastSemesters: (lock: boolean) => void;
  
  addRequirement: (requirement: string) => void;
  removeRequirement: (requirement: string) => void;
  
  toggleRequirementExpanded: (requirement: string) => void;
  toggleRequirementNodeExpanded: (requirement: string, nodePath: string) => void;
  
  setRequirementTier: (requirement: string, tier: number) => void;
  setObjectiveTier: (objectiveKey: string, tier: number) => void;
}

function getDefaultYear(): string {
  const currentDate = new Date();
  const currentYear = currentDate.getFullYear();
  const currentMonth = currentDate.getMonth();
  const academicYearStart = currentMonth >= 8 ? currentYear : currentYear - 1;
  const freshmanGradYear = academicYearStart + 4;
  return String(freshmanGradYear);
}

function markOptimizationAsStale() {
  const graphStore = useGraphStore.getState();
  // Only mark as stale if there's an existing optimization result
  if (graphStore.optimizerNodes.length > 0) {
    useGraphStore.setState({ markersChangedSinceOptimization: true });
  }
}

export const useOptimizationStore = create<OptimizationState>((set) => ({
  selectedObjectives: [],
  selectedRequirements: [],
  selectedYear: getDefaultYear(),
  lockPastSemesters: false,
  expandedRequirements: [],
  expandedRequirementNodes: {},
  requirementTiers: {},
  objectiveTiers: {},
  
  setObjectives: (objectives) => {
    markOptimizationAsStale();
    set({ selectedObjectives: objectives });
  },
  setRequirements: (requirements) => {
    markOptimizationAsStale();
    set({ selectedRequirements: requirements });
  },
  setYear: (year) => {
    markOptimizationAsStale();
    set({ selectedYear: year });
  },
  setLockPastSemesters: (lock) => {
    markOptimizationAsStale();
    set({ lockPastSemesters: lock });
  },
  
  addRequirement: (requirement) => {
    markOptimizationAsStale();
    set((state) => ({
      selectedRequirements: [...state.selectedRequirements, requirement],
    }));
  },
  
  removeRequirement: (requirement) => {
    markOptimizationAsStale();
    set((state) => ({
      selectedRequirements: state.selectedRequirements.filter((r) => r !== requirement),
    }));
  },
  
  toggleRequirementExpanded: (requirement) =>
    set((state) => ({
      expandedRequirements: state.expandedRequirements.includes(requirement)
        ? state.expandedRequirements.filter((r) => r !== requirement)
        : [...state.expandedRequirements, requirement],
    })),
  
  toggleRequirementNodeExpanded: (requirement, nodePath) =>
    set((state) => {
      const currentNodes = state.expandedRequirementNodes[requirement] || new Set();
      const newNodes = new Set(currentNodes);
      
      if (newNodes.has(nodePath)) {
        newNodes.delete(nodePath);
      } else {
        newNodes.add(nodePath);
      }
      
      return {
        expandedRequirementNodes: {
          ...state.expandedRequirementNodes,
          [requirement]: newNodes,
        },
      };
    }),
  
  setRequirementTier: (requirement, tier) => {
    markOptimizationAsStale();
    set((state) => ({
      requirementTiers: {
        ...state.requirementTiers,
        [requirement]: tier,
      },
    }));
  },
  
  setObjectiveTier: (objectiveKey, tier) => {
    markOptimizationAsStale();
    set((state) => ({
      objectiveTiers: {
        ...state.objectiveTiers,
        [objectiveKey]: tier,
      },
    }));
  },
}));
