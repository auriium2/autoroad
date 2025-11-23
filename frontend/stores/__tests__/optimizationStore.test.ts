/**
 * Tests for optimization store, focusing on:
 * 1. Category rewards decay rate configuration
 * 2. Requirement expansion on add
 * 3. State persistence and updates
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { create } from 'zustand';

// Mock the roadStore to avoid dependencies
vi.mock('../roadStore', () => ({
  useGraphStore: {
    getState: () => ({ optimizerNodes: [] }),
    setState: vi.fn(),
  },
}));

// Import after mocking
import { useOptimizationStore } from '../optimizationStore';

describe('OptimizationStore', () => {
  beforeEach(() => {
    // Reset store before each test
    useOptimizationStore.setState({
      selectedObjectives: [],
      selectedRequirements: [],
      selectedYear: '2029',
      lockPastSemesters: false,
      selectedHardConstraints: [],
      expandedRequirements: [],
      expandedRequirementNodes: {},
      requirementTiers: {},
      objectiveTiers: {},
      customEquivalencies: {},
      courseCategories: {},
    });
  });

  describe('Requirement Expansion', () => {
    it('should expand requirement when added', () => {
      const { addRequirement } = useOptimizationStore.getState();
      
      addRequirement('6-3');
      
      const state = useOptimizationStore.getState();
      expect(state.selectedRequirements).toContain('6-3');
      expect(state.expandedRequirements).toContain('6-3');
    });

    it('should not add duplicate requirements', () => {
      const { addRequirement } = useOptimizationStore.getState();
      
      addRequirement('6-3');
      addRequirement('6-3');
      
      const state = useOptimizationStore.getState();
      expect(state.selectedRequirements).toEqual(['6-3']);
      expect(state.expandedRequirements).toEqual(['6-3']);
    });

    it('should expand multiple requirements independently', () => {
      const { addRequirement } = useOptimizationStore.getState();
      
      addRequirement('6-3');
      addRequirement('6-2');
      
      const state = useOptimizationStore.getState();
      expect(state.selectedRequirements).toEqual(['6-3', '6-2']);
      expect(state.expandedRequirements).toEqual(['6-3', '6-2']);
    });

    it('should toggle requirement expansion correctly', () => {
      const { addRequirement, toggleRequirementExpanded } = useOptimizationStore.getState();
      
      addRequirement('6-3');
      expect(useOptimizationStore.getState().expandedRequirements).toContain('6-3');
      
      // Collapse
      toggleRequirementExpanded('6-3');
      expect(useOptimizationStore.getState().expandedRequirements).not.toContain('6-3');
      
      // Expand again
      toggleRequirementExpanded('6-3');
      expect(useOptimizationStore.getState().expandedRequirements).toContain('6-3');
    });

    it('should remove requirement correctly', () => {
      const { addRequirement, removeRequirement } = useOptimizationStore.getState();
      
      addRequirement('6-3');
      addRequirement('6-2');
      
      removeRequirement('6-3');
      
      const state = useOptimizationStore.getState();
      expect(state.selectedRequirements).toEqual(['6-2']);
      // Note: expandedRequirements may still contain '6-3' - this is OK
    });
  });

  describe('Requirement Node Expansion', () => {
    it('should expand requirement nodes', () => {
      const { toggleRequirementNodeExpanded } = useOptimizationStore.getState();
      
      toggleRequirementNodeExpanded('6-3', 'root.0.1');
      
      const state = useOptimizationStore.getState();
      expect(state.expandedRequirementNodes['6-3']).toBeDefined();
      expect(state.expandedRequirementNodes['6-3'].has('root.0.1')).toBe(true);
    });

    it('should toggle requirement nodes correctly', () => {
      const { toggleRequirementNodeExpanded } = useOptimizationStore.getState();
      
      // Expand
      toggleRequirementNodeExpanded('6-3', 'root.0.1');
      expect(useOptimizationStore.getState().expandedRequirementNodes['6-3'].has('root.0.1')).toBe(true);
      
      // Collapse
      toggleRequirementNodeExpanded('6-3', 'root.0.1');
      expect(useOptimizationStore.getState().expandedRequirementNodes['6-3'].has('root.0.1')).toBe(false);
    });

    it('should handle multiple nodes for same requirement', () => {
      const { toggleRequirementNodeExpanded } = useOptimizationStore.getState();
      
      toggleRequirementNodeExpanded('6-3', 'root.0.1');
      toggleRequirementNodeExpanded('6-3', 'root.0.2');
      
      const state = useOptimizationStore.getState();
      expect(state.expandedRequirementNodes['6-3'].has('root.0.1')).toBe(true);
      expect(state.expandedRequirementNodes['6-3'].has('root.0.2')).toBe(true);
    });
  });

  describe('Requirement Tiers', () => {
    it('should set requirement tier', () => {
      const { setRequirementTier } = useOptimizationStore.getState();
      
      setRequirementTier('root.6.0.1.2', 3);
      
      const state = useOptimizationStore.getState();
      expect(state.requirementTiers['root.6.0.1.2']).toBe(3);
    });

    it('should update existing requirement tier', () => {
      const { setRequirementTier } = useOptimizationStore.getState();
      
      setRequirementTier('root.6.0.1.2', 2);
      setRequirementTier('root.6.0.1.2', 3);
      
      const state = useOptimizationStore.getState();
      expect(state.requirementTiers['root.6.0.1.2']).toBe(3);
    });

    it('should handle multiple requirement tiers', () => {
      const { setRequirementTier } = useOptimizationStore.getState();
      
      setRequirementTier('root.6.0.1.2', 3);
      setRequirementTier('root.6.0.2.1', 2);
      
      const state = useOptimizationStore.getState();
      expect(state.requirementTiers['root.6.0.1.2']).toBe(3);
      expect(state.requirementTiers['root.6.0.2.1']).toBe(2);
    });
  });

  describe('Course Category Tiers', () => {
    it('should get course category tier from highest starred category', () => {
      const { setCourseCategories, setRequirementTier, getCourseCategoryTier } = useOptimizationStore.getState();
      
      setCourseCategories({
        '6.2050': ['root.6.0.1.2', 'root.6.0.2.1']
      });
      
      setRequirementTier('root.6.0.1.2', 3);
      setRequirementTier('root.6.0.2.1', 2);
      
      const tier = getCourseCategoryTier('6.2050');
      expect(tier).toBe(3);
    });

    it('should return 0 for courses not in any category', () => {
      const { getCourseCategoryTier } = useOptimizationStore.getState();
      
      const tier = getCourseCategoryTier('6.9999');
      expect(tier).toBe(0);
    });

    it('should return 0 for courses in unstarred categories', () => {
      const { setCourseCategories, getCourseCategoryTier } = useOptimizationStore.getState();
      
      setCourseCategories({
        '6.2050': ['root.6.0.1.2']
      });
      
      const tier = getCourseCategoryTier('6.2050');
      expect(tier).toBe(0);
    });
  });

  describe('Lock Past Semesters', () => {
    it('should have default value of false', () => {
      const state = useOptimizationStore.getState();
      expect(state.lockPastSemesters).toBe(false);
    });

    it('should toggle lock past semesters', () => {
      const { setLockPastSemesters } = useOptimizationStore.getState();
      
      setLockPastSemesters(true);
      expect(useOptimizationStore.getState().lockPastSemesters).toBe(true);
      
      setLockPastSemesters(false);
      expect(useOptimizationStore.getState().lockPastSemesters).toBe(false);
    });
  });

  describe('Custom Equivalencies', () => {
    it('should add custom equivalency', () => {
      const { addCustomEquivalency } = useOptimizationStore.getState();
      
      addCustomEquivalency('6.100A', '6.100B');
      
      const state = useOptimizationStore.getState();
      expect(state.customEquivalencies['6.100A']).toContain('6.100B');
      expect(state.customEquivalencies['6.100B']).toContain('6.100A');
    });

    it('should remove custom equivalency', () => {
      const { addCustomEquivalency, removeCustomEquivalency } = useOptimizationStore.getState();
      
      addCustomEquivalency('6.100A', '6.100B');
      removeCustomEquivalency('6.100A', '6.100B');
      
      const state = useOptimizationStore.getState();
      expect(state.customEquivalencies['6.100A']).toBeUndefined();
      expect(state.customEquivalencies['6.100B']).toBeUndefined();
    });

    it('should handle multiple equivalencies for same course', () => {
      const { addCustomEquivalency } = useOptimizationStore.getState();
      
      addCustomEquivalency('6.100A', '6.100B');
      addCustomEquivalency('6.100A', '6.100C');
      
      const state = useOptimizationStore.getState();
      expect(state.customEquivalencies['6.100A']).toContain('6.100B');
      expect(state.customEquivalencies['6.100A']).toContain('6.100C');
      expect(state.customEquivalencies['6.100B']).toContain('6.100A');
      expect(state.customEquivalencies['6.100C']).toContain('6.100A');
    });
  });

  describe('Hard Constraints', () => {
    it('should toggle hard constraint on', () => {
      const { toggleHardConstraint } = useOptimizationStore.getState();
      
      toggleHardConstraint('no_fall_sixth_semester');
      
      const state = useOptimizationStore.getState();
      expect(state.selectedHardConstraints).toContain('no_fall_sixth_semester');
    });

    it('should toggle hard constraint off', () => {
      const { toggleHardConstraint } = useOptimizationStore.getState();
      
      toggleHardConstraint('no_fall_sixth_semester');
      toggleHardConstraint('no_fall_sixth_semester');
      
      const state = useOptimizationStore.getState();
      expect(state.selectedHardConstraints).not.toContain('no_fall_sixth_semester');
    });
  });
});
