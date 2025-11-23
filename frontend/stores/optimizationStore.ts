// DEBUG: Clear optimization storage FIRST before any imports (remove this in production)
if (typeof window !== 'undefined') {
  console.log('DEBUG: Clearing optimization-storage BEFORE imports...');
  window.localStorage.removeItem('optimization-storage');
  window.localStorage.removeItem('autoroad_query_cache');
}

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { ObjectiveConfig } from '@/services/optimizer';
import { useGraphStore } from './roadStore';

interface OptimizationState {
  selectedObjectives: ObjectiveConfig[];
  selectedRequirements: string[];
  selectedYear?: string;
  lockPastSemesters: boolean;
  selectedHardConstraints: string[];
  expandedRequirements: string[];
  expandedRequirementNodes: Record<string, Set<string>>;
  requirementTiers: Record<string, number>;
  objectiveTiers: Record<string, number>;
  customEquivalencies: Record<string, string[]>;
  
  setObjectives: (objectives: ObjectiveConfig[]) => void;
  setRequirements: (requirements: string[]) => void;
  setYear: (year?: string) => void;
  setLockPastSemesters: (lock: boolean) => void;
  setHardConstraints: (constraints: string[]) => void;
  toggleHardConstraint: (constraintKey: string) => void;
  
  addRequirement: (requirement: string) => void;
  removeRequirement: (requirement: string) => void;
  
  toggleRequirementExpanded: (requirement: string) => void;
  toggleRequirementNodeExpanded: (requirement: string, nodePath: string) => void;
  
  setRequirementTier: (requirement: string, tier: number) => void;
  setObjectiveTier: (objectiveKey: string, tier: number) => void;
  
  addCustomEquivalency: (courseA: string, courseB: string) => void;
  removeCustomEquivalency: (courseA: string, courseB: string) => void;
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

export const useOptimizationStore = create<OptimizationState>()(
  persist(
    (set) => ({
  selectedObjectives: [],
  selectedRequirements: [],
  selectedYear: getDefaultYear(),
  lockPastSemesters: false,
  selectedHardConstraints: [],
  expandedRequirements: [],
  expandedRequirementNodes: {},
  requirementTiers: {},
  objectiveTiers: {},
  customEquivalencies: {},
  
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
  setHardConstraints: (constraints) => {
    markOptimizationAsStale();
    set({ selectedHardConstraints: constraints });
  },
  toggleHardConstraint: (constraintKey) => {
    markOptimizationAsStale();
    set((state) => {
      const isEnabled = state.selectedHardConstraints.includes(constraintKey);
      if (isEnabled) {
        return {
          selectedHardConstraints: state.selectedHardConstraints.filter(k => k !== constraintKey)
        };
      } else {
        return {
          selectedHardConstraints: [...state.selectedHardConstraints, constraintKey]
        };
      }
    });
  },
  
  addRequirement: (requirement) => {
    markOptimizationAsStale();
    set((state) => {
      // Don't add duplicates
      if (state.selectedRequirements.includes(requirement)) {
        return state;
      }
      return {
        selectedRequirements: [...state.selectedRequirements, requirement],
      };
    });
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
  
  addCustomEquivalency: (courseA, courseB) => {
    markOptimizationAsStale();
    set((state) => {
      const newEquivalencies = { ...state.customEquivalencies };
      
      if (!newEquivalencies[courseA]) {
        newEquivalencies[courseA] = [];
      }
      if (!newEquivalencies[courseB]) {
        newEquivalencies[courseB] = [];
      }
      
      if (!newEquivalencies[courseA].includes(courseB)) {
        newEquivalencies[courseA] = [...newEquivalencies[courseA], courseB];
      }
      if (!newEquivalencies[courseB].includes(courseA)) {
        newEquivalencies[courseB] = [...newEquivalencies[courseB], courseA];
      }
      
      return { customEquivalencies: newEquivalencies };
    });
  },
  
  removeCustomEquivalency: (courseA, courseB) => {
    markOptimizationAsStale();
    set((state) => {
      const newEquivalencies = { ...state.customEquivalencies };
      
      if (newEquivalencies[courseA]) {
        newEquivalencies[courseA] = newEquivalencies[courseA].filter((c) => c !== courseB);
        if (newEquivalencies[courseA].length === 0) {
          delete newEquivalencies[courseA];
        }
      }
      
      if (newEquivalencies[courseB]) {
        newEquivalencies[courseB] = newEquivalencies[courseB].filter((c) => c !== courseA);
        if (newEquivalencies[courseB].length === 0) {
          delete newEquivalencies[courseB];
        }
      }
      
      return { customEquivalencies: newEquivalencies };
    });
  },
}),
    {
      name: 'optimization-storage',
      partialize: (state) => ({
        selectedObjectives: state.selectedObjectives,
        selectedRequirements: state.selectedRequirements,
        selectedYear: state.selectedYear,
        lockPastSemesters: state.lockPastSemesters,
        selectedHardConstraints: state.selectedHardConstraints,
        requirementTiers: state.requirementTiers,
        objectiveTiers: state.objectiveTiers,
        customEquivalencies: state.customEquivalencies,
      }),
    }
  )
);
