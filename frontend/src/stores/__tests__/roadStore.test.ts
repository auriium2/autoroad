/**
 * Tests for roadStore (useGraphStore)
 * Core state management for markers, optimizer nodes, and optimization flow
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useGraphStore } from '../roadStore';
import { useOptimizationStore } from '../optimizationStore';
import type { Marker, OptimizerNode } from '@/types';

// Mock dependencies
vi.mock('@/services/optimizer', () => ({
  optimizerApi: {
    optimize: vi.fn(),
    getCourseCategories: vi.fn().mockResolvedValue({}),
  },
}));

vi.mock('@/services/fireroad', () => ({
  fireroadApi: {},
}));

vi.mock('@/lib/storage', () => ({
  storage: {
    load: vi.fn(),
    save: vi.fn(),
  },
}));

import { optimizerApi } from '@/services/optimizer';
import { storage } from '@/lib/storage';

// Helper to reset store state
function resetStore() {
  useGraphStore.setState({
    markers: [],
    optimizerNodes: [],
    sections: [],
    availableNodes: [],
    loadingState: 'idle',
    error: null,
    isSaving: false,
    isOptimizing: false,
    optimizationProgress: null,
    lastCostBreakdown: null,
    markersChangedSinceOptimization: false,
    lastOptimizationStatus: null,
    optimizationAbortController: null,
    userId: null,
  });
}

describe('useGraphStore', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetStore();
  });

  describe('Marker Management', () => {
    describe('addMarker', () => {
      it('should add a new marker with default pin status', () => {
        const { addMarker } = useGraphStore.getState();
        
        addMarker('6.100A', 3);
        
        const { markers } = useGraphStore.getState();
        expect(markers).toHaveLength(1);
        expect(markers[0]).toMatchObject({
          courseId: '6.100A',
          section: 3,
          status: 'pin',
        });
        expect(markers[0].uuid).toMatch(/^marker_6\.100A_\d+$/);
      });

      it('should add a marker with custom status', () => {
        const { addMarker } = useGraphStore.getState();
        
        addMarker('18.01', 1, 'banish');
        
        const { markers } = useGraphStore.getState();
        expect(markers[0].status).toBe('banish');
      });

      it('should add a marker with override status', () => {
        const { addMarker } = useGraphStore.getState();
        
        addMarker('8.01', 2, 'override');
        
        const { markers } = useGraphStore.getState();
        expect(markers[0].status).toBe('override');
      });

      it('should allow multiple markers for different courses', () => {
        const { addMarker } = useGraphStore.getState();
        
        addMarker('6.100A', 3);
        addMarker('18.01', 1);
        addMarker('8.01', 2);
        
        const { markers } = useGraphStore.getState();
        expect(markers).toHaveLength(3);
        expect(markers.map(m => m.courseId)).toEqual(['6.100A', '18.01', '8.01']);
      });

      it('should set markersChangedSinceOptimization when optimizer nodes exist', () => {
        useGraphStore.setState({
          optimizerNodes: [{ courseId: '6.042', section: 4, units: 12 }],
        });
        
        const { addMarker } = useGraphStore.getState();
        addMarker('6.100A', 3);
        
        const { markersChangedSinceOptimization } = useGraphStore.getState();
        expect(markersChangedSinceOptimization).toBe(true);
      });

      it('should not set markersChangedSinceOptimization when no optimizer nodes', () => {
        const { addMarker } = useGraphStore.getState();
        addMarker('6.100A', 3);
        
        const { markersChangedSinceOptimization } = useGraphStore.getState();
        expect(markersChangedSinceOptimization).toBe(false);
      });

      it('should reset lastOptimizationStatus when adding marker', () => {
        useGraphStore.setState({ lastOptimizationStatus: 'OPTIMAL' });
        
        const { addMarker } = useGraphStore.getState();
        addMarker('6.100A', 3);
        
        const { lastOptimizationStatus } = useGraphStore.getState();
        expect(lastOptimizationStatus).toBeNull();
      });
    });

    describe('removeMarker', () => {
      it('should remove a marker by uuid', () => {
        useGraphStore.setState({
          markers: [
            { uuid: 'marker_1', courseId: '6.100A', section: 3, status: 'pin' },
            { uuid: 'marker_2', courseId: '18.01', section: 1, status: 'pin' },
          ],
        });
        
        const { removeMarker } = useGraphStore.getState();
        removeMarker('marker_1');
        
        const { markers } = useGraphStore.getState();
        expect(markers).toHaveLength(1);
        expect(markers[0].uuid).toBe('marker_2');
      });

      it('should do nothing when removing non-existent marker', () => {
        useGraphStore.setState({
          markers: [{ uuid: 'marker_1', courseId: '6.100A', section: 3, status: 'pin' }],
        });
        
        const { removeMarker } = useGraphStore.getState();
        removeMarker('non_existent');
        
        const { markers } = useGraphStore.getState();
        expect(markers).toHaveLength(1);
      });

      it('should set markersChangedSinceOptimization when optimizer nodes exist', () => {
        useGraphStore.setState({
          markers: [{ uuid: 'marker_1', courseId: '6.100A', section: 3, status: 'pin' }],
          optimizerNodes: [{ courseId: '6.042', section: 4, units: 12 }],
        });
        
        const { removeMarker } = useGraphStore.getState();
        removeMarker('marker_1');
        
        const { markersChangedSinceOptimization } = useGraphStore.getState();
        expect(markersChangedSinceOptimization).toBe(true);
      });

      it('should reset lastOptimizationStatus when removing marker', () => {
        useGraphStore.setState({
          markers: [{ uuid: 'marker_1', courseId: '6.100A', section: 3, status: 'pin' }],
          lastOptimizationStatus: 'FEASIBLE',
        });
        
        const { removeMarker } = useGraphStore.getState();
        removeMarker('marker_1');
        
        const { lastOptimizationStatus } = useGraphStore.getState();
        expect(lastOptimizationStatus).toBeNull();
      });
    });

    describe('updateMarker', () => {
      it('should update marker section', () => {
        useGraphStore.setState({
          markers: [{ uuid: 'marker_1', courseId: '6.100A', section: 3, status: 'pin' }],
        });
        
        const { updateMarker } = useGraphStore.getState();
        updateMarker('marker_1', { section: 5 });
        
        const { markers } = useGraphStore.getState();
        expect(markers[0].section).toBe(5);
      });

      it('should update marker status', () => {
        useGraphStore.setState({
          markers: [{ uuid: 'marker_1', courseId: '6.100A', section: 3, status: 'pin' }],
        });
        
        const { updateMarker } = useGraphStore.getState();
        updateMarker('marker_1', { status: 'banish' });
        
        const { markers } = useGraphStore.getState();
        expect(markers[0].status).toBe('banish');
      });

      it('should update multiple fields at once', () => {
        useGraphStore.setState({
          markers: [{ uuid: 'marker_1', courseId: '6.100A', section: 3, status: 'pin' }],
        });
        
        const { updateMarker } = useGraphStore.getState();
        updateMarker('marker_1', { section: 7, status: 'override' });
        
        const { markers } = useGraphStore.getState();
        expect(markers[0]).toMatchObject({ section: 7, status: 'override' });
      });

      it('should not modify other markers', () => {
        useGraphStore.setState({
          markers: [
            { uuid: 'marker_1', courseId: '6.100A', section: 3, status: 'pin' },
            { uuid: 'marker_2', courseId: '18.01', section: 1, status: 'pin' },
          ],
        });
        
        const { updateMarker } = useGraphStore.getState();
        updateMarker('marker_1', { section: 5 });
        
        const { markers } = useGraphStore.getState();
        expect(markers[1]).toMatchObject({ section: 1, status: 'pin' });
      });

      it('should do nothing when updating non-existent marker', () => {
        useGraphStore.setState({
          markers: [{ uuid: 'marker_1', courseId: '6.100A', section: 3, status: 'pin' }],
        });
        
        const { updateMarker } = useGraphStore.getState();
        updateMarker('non_existent', { section: 5 });
        
        const { markers } = useGraphStore.getState();
        expect(markers[0].section).toBe(3);
      });

      it('should set markersChangedSinceOptimization when optimizer nodes exist', () => {
        useGraphStore.setState({
          markers: [{ uuid: 'marker_1', courseId: '6.100A', section: 3, status: 'pin' }],
          optimizerNodes: [{ courseId: '6.042', section: 4, units: 12 }],
        });
        
        const { updateMarker } = useGraphStore.getState();
        updateMarker('marker_1', { section: 5 });
        
        const { markersChangedSinceOptimization } = useGraphStore.getState();
        expect(markersChangedSinceOptimization).toBe(true);
      });
    });
  });

  describe('loadRoadData', () => {
    it('should load markers', () => {
      const markers: Marker[] = [
        { uuid: 'marker_1', courseId: '6.100A', section: 3, status: 'pin' },
        { uuid: 'marker_2', courseId: '18.01', section: 1, status: 'banish' },
      ];
      
      const { loadRoadData } = useGraphStore.getState();
      loadRoadData({ markers });
      
      expect(useGraphStore.getState().markers).toEqual(markers);
    });

    it('should load optimizer nodes', () => {
      const optimizerNodes: OptimizerNode[] = [
        { courseId: '6.042', section: 4, units: 12 },
        { courseId: '6.006', section: 5, units: 12 },
      ];
      
      const { loadRoadData } = useGraphStore.getState();
      loadRoadData({ optimizerNodes });
      
      expect(useGraphStore.getState().optimizerNodes).toEqual(optimizerNodes);
    });

    it('should load partial data without overwriting other fields', () => {
      useGraphStore.setState({
        markers: [{ uuid: 'marker_1', courseId: '6.100A', section: 3, status: 'pin' }],
        optimizerNodes: [{ courseId: '6.042', section: 4, units: 12 }],
      });
      
      const { loadRoadData } = useGraphStore.getState();
      loadRoadData({ markers: [] });
      
      const state = useGraphStore.getState();
      expect(state.markers).toEqual([]);
      expect(state.optimizerNodes).toHaveLength(1);
    });

    it('should load sections and available nodes', () => {
      const sections = [{ id: 1, title: 'Fall 1' }];
      const availableNodes = [{ courseId: '6.100A', title: 'Intro to CS', department: 'EECS', units: 12 }];
      
      const { loadRoadData } = useGraphStore.getState();
      loadRoadData({ sections, availableNodes });
      
      const state = useGraphStore.getState();
      expect(state.sections).toEqual(sections);
      expect(state.availableNodes).toEqual(availableNodes);
    });
  });

  describe('fetchRoadData', () => {
    it('should set success state after fetching with no cached data', async () => {
      vi.mocked(storage.load).mockReturnValue(null);
      
      await useGraphStore.getState().fetchRoadData();
      
      expect(useGraphStore.getState().loadingState).toBe('success');
    });

    it('should load cached data from storage', async () => {
      const cachedData = {
        nodes: [
          { uuid: 'node_1', courseId: '6.100A', section: 3, userControlled: true, nodeStatus: 'pin' },
          { uuid: 'node_2', courseId: '18.01', section: 1, userControlled: true },
        ],
        sections: [{ id: 1, title: 'Fall 1' }],
        availableNodes: [],
      };
      vi.mocked(storage.load).mockReturnValue(cachedData as any);
      
      await useGraphStore.getState().fetchRoadData();
      
      const state = useGraphStore.getState();
      expect(state.markers).toHaveLength(2);
      expect(state.markers[0]).toMatchObject({
        uuid: 'node_1',
        courseId: '6.100A',
        section: 3,
        status: 'pin',
      });
      expect(state.markers[1].status).toBe('pin'); // Default when nodeStatus not set
      expect(state.loadingState).toBe('success');
    });

    it('should set success state when no cached data', async () => {
      vi.mocked(storage.load).mockReturnValue(null);
      
      await useGraphStore.getState().fetchRoadData();
      
      expect(useGraphStore.getState().loadingState).toBe('success');
    });

    it('should clear error state when fetching', async () => {
      useGraphStore.setState({ error: 'Previous error' });
      vi.mocked(storage.load).mockReturnValue(null);
      
      await useGraphStore.getState().fetchRoadData();
      
      expect(useGraphStore.getState().error).toBeNull();
    });
  });

  describe('optimizeRoad', () => {
    beforeEach(() => {
      // Setup optimization store with defaults
      useOptimizationStore.setState({
        selectedObjectives: [],
        selectedRequirements: ['girs'],
        selectedYear: undefined,
        lockPastSemesters: false,
        selectedHardConstraints: [],
        requirementTiers: {},
        objectiveTiers: {},
        requirementSources: {},
      });
    });

    it('should set isOptimizing true during optimization', async () => {
      // Mock streaming generator that completes immediately
      vi.mocked(optimizerApi.optimize).mockImplementation(async function* () {
        yield { nodes: [], step: 1, isComplete: true, status: 'OPTIMAL' };
      });
      
      const promise = useGraphStore.getState().optimizeRoad();
      expect(useGraphStore.getState().isOptimizing).toBe(true);
      
      await promise;
      expect(useGraphStore.getState().isOptimizing).toBe(false);
    });

    it('should update optimizer nodes from stream', async () => {
      const mockNodes: OptimizerNode[] = [
        { courseId: '6.100A', section: 3, units: 12 },
        { courseId: '18.01', section: 1, units: 12 },
      ];
      
      vi.mocked(optimizerApi.optimize).mockImplementation(async function* () {
        yield { nodes: mockNodes, step: 1 };
        yield { nodes: [], step: 2, isComplete: true, status: 'OPTIMAL' };
      });
      
      await useGraphStore.getState().optimizeRoad();
      
      expect(useGraphStore.getState().optimizerNodes).toEqual(mockNodes);
    });

    it('should set lastOptimizationStatus on completion', async () => {
      vi.mocked(optimizerApi.optimize).mockImplementation(async function* () {
        yield { nodes: [], step: 1, isComplete: true, status: 'FEASIBLE' };
      });
      
      await useGraphStore.getState().optimizeRoad();
      
      expect(useGraphStore.getState().lastOptimizationStatus).toBe('FEASIBLE');
    });

    it('should store cost breakdown when available', async () => {
      const mockCostBreakdown = { 'total_units': 48, 'difficulty': 10 };
      
      vi.mocked(optimizerApi.optimize).mockImplementation(async function* () {
        yield { nodes: [{ courseId: '6.100A', section: 3, units: 12 }], step: 1, costBreakdown: mockCostBreakdown };
        yield { nodes: [], step: 2, isComplete: true, status: 'OPTIMAL' };
      });
      
      await useGraphStore.getState().optimizeRoad();
      
      expect(useGraphStore.getState().lastCostBreakdown).toEqual(mockCostBreakdown);
    });

    it('should return success true on successful optimization', async () => {
      vi.mocked(optimizerApi.optimize).mockImplementation(async function* () {
        yield { nodes: [], step: 1, isComplete: true, status: 'OPTIMAL' };
      });
      
      const result = await useGraphStore.getState().optimizeRoad();
      
      expect(result).toEqual({ success: true });
    });

    it('should handle optimization error', async () => {
      vi.mocked(optimizerApi.optimize).mockImplementation(async function* () {
        throw new Error('Optimization failed: infeasible');
      });
      
      const result = await useGraphStore.getState().optimizeRoad();
      
      expect(result).toEqual({ success: false, error: 'Optimization failed: infeasible' });
      expect(useGraphStore.getState().error).toBe('Optimization failed: infeasible');
      expect(useGraphStore.getState().loadingState).toBe('error');
    });

    it('should reset markersChangedSinceOptimization', async () => {
      useGraphStore.setState({ markersChangedSinceOptimization: true });
      
      vi.mocked(optimizerApi.optimize).mockImplementation(async function* () {
        yield { nodes: [], step: 1, isComplete: true, status: 'OPTIMAL' };
      });
      
      await useGraphStore.getState().optimizeRoad();
      
      expect(useGraphStore.getState().markersChangedSinceOptimization).toBe(false);
    });

    it('should pass markers to optimizer', async () => {
      const markers: Marker[] = [
        { uuid: 'marker_1', courseId: '6.100A', section: 3, status: 'pin' },
      ];
      useGraphStore.setState({ markers });
      
      vi.mocked(optimizerApi.optimize).mockImplementation(async function* () {
        yield { nodes: [], step: 1, isComplete: true, status: 'OPTIMAL' };
      });
      
      await useGraphStore.getState().optimizeRoad();
      
      // Check that optimize was called with the markers as first argument
      expect(optimizerApi.optimize).toHaveBeenCalled();
      const callArgs = vi.mocked(optimizerApi.optimize).mock.calls[0];
      expect(callArgs[0]).toEqual(markers);
    });
  });

  describe('cancelOptimization', () => {
    it('should abort the optimization controller', async () => {
      const abortSpy = vi.fn();
      const mockController = { abort: abortSpy, signal: new AbortController().signal };
      useGraphStore.setState({ optimizationAbortController: mockController as any });
      
      useGraphStore.getState().cancelOptimization();
      
      expect(abortSpy).toHaveBeenCalled();
    });

    it('should do nothing when no optimization in progress', () => {
      useGraphStore.setState({ optimizationAbortController: null });
      
      // Should not throw
      expect(() => useGraphStore.getState().cancelOptimization()).not.toThrow();
    });

    it('should return cancelled error when optimization is aborted', async () => {
      const abortError = new Error('Aborted');
      abortError.name = 'AbortError';
      
      vi.mocked(optimizerApi.optimize).mockImplementation(async function* () {
        throw abortError;
      });
      
      const result = await useGraphStore.getState().optimizeRoad();
      
      expect(result).toEqual({ success: false, error: 'Optimization cancelled' });
      expect(useGraphStore.getState().loadingState).toBe('idle');
    });
  });

  describe('clearError', () => {
    it('should clear the error state', () => {
      useGraphStore.setState({ error: 'Some error' });
      
      useGraphStore.getState().clearError();
      
      expect(useGraphStore.getState().error).toBeNull();
    });
  });

  describe('setUserId', () => {
    it('should set the user ID', () => {
      useGraphStore.getState().setUserId('user_123');
      
      expect(useGraphStore.getState().userId).toBe('user_123');
    });

    it('should allow setting null', () => {
      useGraphStore.setState({ userId: 'user_123' });
      
      useGraphStore.getState().setUserId(null);
      
      expect(useGraphStore.getState().userId).toBeNull();
    });
  });
});
