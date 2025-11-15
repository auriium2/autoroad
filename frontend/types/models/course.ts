export const ASE: string = "ASEs";

export interface Marker {
  id: string;
  courseId: string;
  section: number;
  status: 'pin' | 'banish' | 'solo';
}

export interface OptimizerNode {
  courseId: string;
  section: number;
}

export interface CourseNode {
  id: string;
  courseId: string;
  section: number;
  userControlled?: boolean;
  disabled?: boolean;
  nodeStatus?: 'pin' | 'banish' | 'solo';
  offeredFall?: boolean;
  offeredSpring?: boolean;
  offeredIAP?: boolean;
}

export interface AvailableNode {
  courseId: string;
  title: string;
  department: string;
  units: number;
}
