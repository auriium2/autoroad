import type { Marker, OptimizerNode } from '@/types';

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

export const DEMO_MARKERS_FIXED_SEMESTER: Marker[] = [
  // 6.120A now in Freshman Spring (correct)
  { uuid: 'demo_6.120A_spring', courseId: '6.120A', section: 2, status: 'pin' },

  // 6.1010 still has missing prereq (needs 6.1000 or 6.100A+6.100B)
  { uuid: 'demo_6.1010_spring', courseId: '6.1010', section: 2, status: 'pin' },

  { uuid: 'demo_18.01_ase', courseId: '18.01', section: -1, status: 'pin' },
  { uuid: 'demo_8.01_must', courseId: '8.01', section: -2, status: 'pin' },
];

export const DEMO_MARKERS_ALL_FIXED: Marker[] = [
  { uuid: 'demo_6.120A_spring', courseId: '6.120A', section: 2, status: 'pin' },
  // 6.1000 added in Freshman Fall to satisfy 6.1010's prereq
  { uuid: 'demo_6.1000_fall', courseId: '6.1000', section: 0, status: 'pin' },
  { uuid: 'demo_6.1010_spring', courseId: '6.1010', section: 2, status: 'pin' },
  { uuid: 'demo_18.01_ase', courseId: '18.01', section: -1, status: 'pin' },
  { uuid: 'demo_8.01_must', courseId: '8.01', section: -2, status: 'pin' },
];

export const DEMO_MARKERS_OVERRIDE_FIXED: Marker[] = [
  { uuid: 'demo_6.120A_spring', courseId: '6.120A', section: 2, status: 'pin' },
  { uuid: 'demo_6.1010_spring', courseId: '6.1010', section: 2, status: 'override' },
  { uuid: 'demo_18.01_ase', courseId: '18.01', section: -1, status: 'pin' },
  { uuid: 'demo_8.01_must', courseId: '8.01', section: -2, status: 'pin' },
];

export const DEMO_OPTIMIZER_NODES: OptimizerNode[] = [
  // ASE (section -1) - road semester 0
  { courseId: '18.01', section: -1, units: 12 },

  // Freshman Fall (section 0) - road semester 1
  { courseId: '5.111', section: 0, units: 12 },
  { courseId: '6.1000', section: 0, units: 12 },
  { courseId: '8.01', section: 0, units: 12 },

  // Freshman Spring (section 2) - road semester 3
  { courseId: '18.02A', section: 2, units: 12 },
  { courseId: '6.1010', section: 2, units: 12 },
  { courseId: '6.120A', section: 2, units: 6 },
  { courseId: '8.022', section: 2, units: 12 },

  // Sophomore Fall (section 3) - road semester 4
  { courseId: '21L.000', section: 3, units: 12 },
  { courseId: '5.611', section: 3, units: 6 },

  // Junior Fall (section 8) - road semester 9
  { courseId: '11.139', section: 8, units: 9 },
  { courseId: '12.011', section: 8, units: 9 },

  // Junior Spring (section 9) - road semester 10
  { courseId: '5.612', section: 9, units: 6 },

  // Senior Spring (section 11) - road semester 12
  { courseId: '11.026', section: 11, units: 9 },
  { courseId: '21H.321', section: 11, units: 9 },
  { courseId: '3.095', section: 11, units: 9 },
  { courseId: '7.016', section: 11, units: 12 },
];
export const DEMO_COST_BREAKDOWN: Record<string, number> = {
  'minimize_units': 12,
  'balance_workload': 5,
  'satisfy_requirements': 0,
};
export const DEMO_SIMPLE_MARKERS: Marker[] = [
  { uuid: 'demo_18.01_ase', courseId: '18.01', section: -1, status: 'pin' },
];
