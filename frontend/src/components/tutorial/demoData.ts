import type { Marker, OptimizerNode } from '@/types';

// ===========================================
// STAGE 1: Initial markers with problems to fix
// ===========================================

// Start with some markers that have issues the user needs to fix
export const DEMO_MARKERS_WITH_PROBLEMS: Marker[] = [
  // 6.120A in IAP (section 1) - but 6.120A is NOT offered in IAP! Yellow warning
  { uuid: 'demo_6.120A_iap', courseId: '6.120A', section: 1, status: 'pin' },

  // 6.1010 in Freshman Spring - missing prereq (needs 6.1000 or 6.100A+6.100B)
  { uuid: 'demo_6.1010_spring', courseId: '6.1010', section: 2, status: 'pin' },

  // 18.01 ASE'd (this is fine)
  { uuid: 'demo_18.01_ase', courseId: '18.01', section: -1, status: 'pin' },

  // 8.01 in Must Take (this is fine)
  { uuid: 'demo_8.01_must', courseId: '8.01', section: -2, status: 'pin' },
];

// ===========================================
// STAGE 2: After fixing the wrong semester (6.100A moved to Fall)
// ===========================================

export const DEMO_MARKERS_FIXED_SEMESTER: Marker[] = [
  // 6.120A now in Freshman spring (correct)
  { uuid: 'demo_6.120A_fall', courseId: '6.120A', section: 2, status: 'pin' },

  // 6.1010 still has missing prereq (needs 6.1000 or 6.100A+6.100B)
  { uuid: 'demo_6.1010_spring', courseId: '6.1010', section: 2, status: 'pin' },

  { uuid: 'demo_18.01_ase', courseId: '18.01', section: -1, status: 'pin' },
  { uuid: 'demo_8.01_must', courseId: '8.01', section: -2, status: 'pin' },
];

// ===========================================
// STAGE 3: After adding 6.1000 to fix prereqs
// ===========================================

export const DEMO_MARKERS_ALL_FIXED: Marker[] = [
  { uuid: 'demo_6.120A_fall', courseId: '6.120A', section: 2, status: 'pin' },
  // 6.1000 added in IAP to satisfy 6.1010's prereq
  { uuid: 'demo_6.1000_iap', courseId: '6.1000', section: 0, status: 'pin' },
  { uuid: 'demo_6.1010_spring', courseId: '6.1010', section: 2, status: 'pin' },
  { uuid: 'demo_18.01_ase', courseId: '18.01', section: -1, status: 'pin' },
  { uuid: 'demo_8.01_must', courseId: '8.01', section: -2, status: 'pin' },
];

// ===========================================
// STAGE 4: Optimization result
// ===========================================

export const DEMO_OPTIMIZER_NODES: OptimizerNode[] = [
  // User's pinned courses (optimizer agrees with all of them)
  { courseId: '6.120A', section: 0, units: 12 },
  { courseId: '6.1000', section: 1, units: 6 },
  { courseId: '6.1010', section: 2, units: 12 },

  // 8.01 placed by optimizer in Freshman Fall
  { courseId: '8.01', section: 0, units: 12 },

  // GIRs the optimizer filled in
  { courseId: '5.111', section: 0, units: 12 }, // Chemistry
  { courseId: '8.02', section: 2, units: 12 }, // Physics II

  // More CS courses for later semesters
  { courseId: '6.1900', section: 3, units: 12 }, // Sophomore Fall
  { courseId: '6.006', section: 5, units: 12 }, // Sophomore Spring
];

// Cost breakdown for demo
export const DEMO_COST_BREAKDOWN: Record<string, number> = {
  'minimize_units': 12,
  'balance_workload': 5,
  'satisfy_requirements': 0,
};

// ===========================================
// Simple demo for post-tutorial state
// ===========================================

export const DEMO_SIMPLE_MARKERS: Marker[] = [
  { uuid: 'demo_18.01_ase', courseId: '18.01', section: -1, status: 'pin' },
];
