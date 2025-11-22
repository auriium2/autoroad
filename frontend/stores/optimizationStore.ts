import { create } from 'zustand';
import type { ObjectiveConfig } from '@/services/optimizer';

interface OptimizationState {
  selectedObjectives: ObjectiveConfig[];
  selectedRequirements: string[];
  selectedYear?: string;
  lockPastSemesters: boolean;
  expandedRequirements: string[];
  expandedRequirementNodes: Record<string, Set<string>>;
  
  setObjectives: (objectives: ObjectiveConfig[]) => void;
  setRequirements: (requirements: string[]) => void;
  setYear: (year?: string) => void;
  setLockPastSemesters: (lock: boolean) => void;
  
  addRequirement: (requirement: string) => void;
  removeRequirement: (requirement: string) => void;
  
  toggleRequirementExpanded: (requirement: string) => void;
  toggleRequirementNodeExpanded: (requirement: string, nodePath: string) => void;
}

function getDefaultYear(): string {
  const currentDate = new Date();
  const currentYear = currentDate.getFullYear();
  const currentMonth = currentDate.getMonth();
  const academicYearStart = currentMonth >= 8 ? currentYear : currentYear - 1;
  const freshmanGradYear = academicYearStart + 4;
  return String(freshmanGradYear);
}

export const useOptimizationStore = create<OptimizationState>((set) => ({
  selectedObjectives: [],
  selectedRequirements: [],
  selectedYear: getDefaultYear(),
  lockPastSemesters: false,
  expandedRequirements: [],
  expandedRequirementNodes: {},
  
  setObjectives: (objectives) => set({ selectedObjectives: objectives }),
  setRequirements: (requirements) => set({ selectedRequirements: requirements }),
  setYear: (year) => set({ selectedYear: year }),
  setLockPastSemesters: (lock) => set({ lockPastSemesters: lock }),
  
  addRequirement: (requirement) =>
    set((state) => ({
      selectedRequirements: [...state.selectedRequirements, requirement],
    })),
  
  removeRequirement: (requirement) =>
    set((state) => ({
      selectedRequirements: state.selectedRequirements.filter((r) => r !== requirement),
    })),
  
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
}));
