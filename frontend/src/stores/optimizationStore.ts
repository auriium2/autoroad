import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { ObjectiveConfig, ConstraintConfig } from '@/types/models/optimizer';
import { useGraphStore } from './roadStore';

interface OptimizationState {
  selectedObjectives: ObjectiveConfig[];
  selectedRequirements: string[];
  selectedYear?: string;
  lockPastSemesters: boolean;
  selectedHardConstraints: ConstraintConfig[];
  expandedRequirements: string[];
  expandedRequirementNodes: Record<string, Set<string>>;
  requirementTiers: Record<string, number>;
  objectiveTiers: Record<string, number>;
  customEquivalencies: Record<string, string[]>;
  courseCategories: Record<string, string[]>; // Maps course ID to requirement paths it satisfies
  requirementSources: Record<string, 'canonical' | 'beta'>; // Maps requirement key to its source

  setObjectives: (objectives: ObjectiveConfig[]) => void;
  setRequirements: (requirements: string[]) => void;
  setYear: (year?: string) => void;
  setLockPastSemesters: (lock: boolean) => void;
  setHardConstraints: (constraints: ConstraintConfig[]) => void;
  toggleHardConstraint: (constraintKey: string, defaultParameters?: Record<string, unknown>) => void;
  updateConstraintParameters: (constraintKey: string, parameters: Record<string, unknown>) => void;

  addRequirement: (requirement: string) => void;
  removeRequirement: (requirement: string) => void;

  toggleRequirementExpanded: (requirement: string) => void;
  toggleRequirementNodeExpanded: (requirement: string, nodePath: string) => void;

  setRequirementTier: (requirement: string, tier: number) => void;
  setObjectiveTier: (objectiveKey: string, tier: number) => void;

  setRequirementSource: (requirement: string, source: 'canonical' | 'beta') => void;

  addCustomEquivalency: (courseA: string, courseB: string) => void;
  removeCustomEquivalency: (courseA: string, courseB: string) => void;

  setCourseCategories: (categories: Record<string, string[]>) => void;
  getCourseCategoryTier: (courseId: string) => number;

  loadOptimizationState: (state: {
    selectedObjectives?: ObjectiveConfig[];
    objectiveTiers?: Record<string, number>;
    requirementTiers?: Record<string, number>;
    requirementSources?: Record<string, string>;
    selectedHardConstraints?: ConstraintConfig[];
    customEquivalencies?: Record<string, string[]>;
    selectedYear?: string;
    lockPastSemesters?: boolean;
    selectedRequirements?: string[];
  }) => void;
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
  courseCategories: {},
  requirementSources: {},

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
  toggleHardConstraint: (constraintKey, defaultParameters = {}) => {
    markOptimizationAsStale();
    set((state) => {
      const existingIdx = state.selectedHardConstraints.findIndex(c => c.key === constraintKey);
      if (existingIdx >= 0) {
        return {
          selectedHardConstraints: state.selectedHardConstraints.filter(c => c.key !== constraintKey)
        };
      } else {
        return {
          selectedHardConstraints: [...state.selectedHardConstraints, { key: constraintKey, parameters: defaultParameters }]
        };
      }
    });
  },
  updateConstraintParameters: (constraintKey, parameters) => {
    markOptimizationAsStale();
    set((state) => ({
      selectedHardConstraints: state.selectedHardConstraints.map(c =>
        c.key === constraintKey ? { ...c, parameters } : c
      )
    }));
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
        expandedRequirements: [...state.expandedRequirements, requirement],
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
      const currentNodes = state.expandedRequirementNodes[requirement] || new Set<string>();
      const hasNode = currentNodes.has(nodePath);

      const newNodes = hasNode // Create new Set immutably by spreading and filtering/adding
        ? new Set([...currentNodes].filter(n => n !== nodePath))
        : new Set([...currentNodes, nodePath]);

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

  setRequirementSource: (requirement, source) => {
    markOptimizationAsStale();
    set((state) => ({
      requirementSources: {
        ...state.requirementSources,
        [requirement]: source,
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

  setCourseCategories: (categories) => {
    set({ courseCategories: categories });
  },

  getCourseCategoryTier: (courseId) => {
    const state = useOptimizationStore.getState();
    const categories = state.courseCategories[courseId] || [];
    const requirementTiers = state.requirementTiers;

    // Find the highest tier among all requirement categories this course belongs to
    let maxTier = 0;
    for (const reqPath of categories) {
      const tier = requirementTiers[reqPath] || 0;
      if (tier > maxTier) {
        maxTier = tier;
      }
    }

    return maxTier;
  },

  loadOptimizationState: (incoming) => {
    markOptimizationAsStale();
    set({
      ...(incoming.selectedObjectives !== undefined && { selectedObjectives: incoming.selectedObjectives }),
      ...(incoming.objectiveTiers !== undefined && { objectiveTiers: incoming.objectiveTiers }),
      ...(incoming.requirementTiers !== undefined && { requirementTiers: incoming.requirementTiers }),
      ...(incoming.requirementSources !== undefined && { requirementSources: incoming.requirementSources as Record<string, 'canonical' | 'beta'> }),
      ...(incoming.selectedHardConstraints !== undefined && { selectedHardConstraints: incoming.selectedHardConstraints }),
      ...(incoming.customEquivalencies !== undefined && { customEquivalencies: incoming.customEquivalencies }),
      ...(incoming.selectedYear !== undefined && { selectedYear: incoming.selectedYear }),
      ...(incoming.lockPastSemesters !== undefined && { lockPastSemesters: incoming.lockPastSemesters }),
      ...(incoming.selectedRequirements !== undefined && { selectedRequirements: incoming.selectedRequirements }),
    });
  },
}),
    {
      name: 'optimization_storage',
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
