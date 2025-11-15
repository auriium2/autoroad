/**
 * LocalStorage utilities for persisting road data
 */

import { CourseNode, Edge, Section, AvailableNode } from '@/stores/roadStore';

export interface RoadData {
  nodes: CourseNode[];
  edges: Edge[];
  sections: Section[];
  availableNodes: AvailableNode[];
}

const STORAGE_KEY = 'autoroad_data';
const STORAGE_VERSION = 1;

interface StorageData {
  version: number;
  data: RoadData;
  timestamp: number;
}

export const storage = {
  save(data: RoadData): void {
    if (typeof window === 'undefined') return;

    const storageData: StorageData = {
      version: STORAGE_VERSION,
      data,
      timestamp: Date.now(),
    };

    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(storageData));
    } catch (error) {
      console.error('Failed to save to localStorage:', error);
    }
  },

  load(): RoadData | null {
    if (typeof window === 'undefined') return null;

    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (!stored) return null;

      const parsed: StorageData = JSON.parse(stored);

      if (parsed.version !== STORAGE_VERSION) {
        console.warn('LocalStorage data version mismatch, clearing...');
        this.clear();
        return null;
      }

      const sevenDays = 7 * 24 * 60 * 60 * 1000;
      if (Date.now() - parsed.timestamp > sevenDays) {
        console.warn('LocalStorage data is stale, clearing...');
        this.clear();
        return null;
      }

      return parsed.data;
    } catch (error) {
      console.error('Failed to load from localStorage:', error);
      return null;
    }
  },

  clear(): void {
    if (typeof window === 'undefined') return;
    window.localStorage.removeItem(STORAGE_KEY);
  },
};
