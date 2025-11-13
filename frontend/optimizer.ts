import { create } from "zustand";

interface OptimizationState {
  optimizationIntensity: number[];
  setOptimizationIntensity: (value: number[]) => void;
  convergenceThreshold: number[];
  setConvergenceThreshold: (value: number[]) => void;
}

export const useOptimizationStore = create<OptimizationState>((set) => ({
  optimizationIntensity: [75],
  setOptimizationIntensity: (value: number[]) =>
    set({ optimizationIntensity: value }),
  convergenceThreshold: [85],
  setConvergenceThreshold: (value: number[]) =>
    set({ convergenceThreshold: value }),
}));
