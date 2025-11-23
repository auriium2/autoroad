export const ASE: string = "ASEs";

export interface Marker {
  uuid: string;
  courseId: string;
  section: number;
  status: 'pin' | 'banish' | 'override';
}

export interface OptimizerNode {
  courseId: string;
  section: number;
  units?: number;
}

export interface CourseNode {
  uuid: string;
  courseId: string;
  section: number;
  userControlled?: boolean;
  disabled?: boolean;
  nodeStatus?: 'pin' | 'banish' | 'override';
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
