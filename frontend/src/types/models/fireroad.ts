/**
 * Shared types for Fireroad API
 * Used by both client-side services and Next.js API routes
 */

export interface PrereqTreeNode {
  type: 'course' | 'group';
  courseId?: string;  // for type === 'course'
  threshold?: number;  // for type === 'group'
  items?: PrereqTreeNode[];  // for type === 'group'
}

export interface FireroadCourse {
  subject_id: string;
  title: string;
  total_units: number;
  description?: string;
  prerequisites?: string;
  prereqTree?: PrereqTreeNode;  // Parsed prereq tree with equivalencies injected
  corequisites?: string;
  is_variable_units?: boolean;
  is_historical?: boolean;
  offered_fall?: boolean;
  offered_spring?: boolean;
  offered_IAP?: boolean;
  offered_summer?: boolean;
  not_offered_year?: string | null;
  public?: boolean;
  level?: string;
  lecture_units?: number;
  lab_units?: number;
  preparation_units?: number;
  design_units?: number;
  in_class_hours?: number;
  out_of_class_hours?: number;
  joint_subjects?: string[];
  equivalent_subjects?: string[];
  meets_with_subjects?: string[];
  children?: string[];
  instructors?: string[];
  rating?: number;
  enrollment_number?: number;
  imdb_rating?: number | null;
  gir_attribute?: string;
  hass_attribute?: string;
  communication_requirement?: string;
  schedule?: string;
  has_final?: boolean;
  pdf_option?: boolean;
  is_half_class?: boolean;
  url?: string;
  source_semester?: string;
  virtual?: boolean;  // True for generic requirement placeholders (HASS-A, etc.)
}

export interface PaginatedCoursesResponse {
  courses: FireroadCourse[];
  total: number;
  offset: number;
  limit: number;
  has_more: boolean;
}

export interface FireroadSearchParams {
  type?: 'contains' | 'matches' | 'starts' | 'ends';
  gir?: string;
  hass?: string;
  ci?: boolean | string;
  offered?: 'fall' | 'spring' | 'IAP' | 'summer';
  level?: 'undergrad' | 'grad' | string;
  units?: string;
  term?: string;
  sort?: string;
  full?: boolean;
  offset?: number;
  limit?: number;
  department?: string;
}

export interface RequirementMetadata {
  'title-no-degree'?: string;
  title?: string;
  'short-title'?: string;
  'medium-title'?: string;
  description?: string;
  source?: 'canonical' | 'beta';
  hasBothVersions?: boolean;
}

export type RequirementsListResponse = Record<string, RequirementMetadata>;

export interface RequirementNode {
  title?: string;
  'connection-type'?: 'all' | 'any';
  'threshold-desc'?: string;
  threshold?: {
    cutoff: number;
    criterion: string;
    type: string;
  };
  desc?: string;
  reqs?: RequirementNode[];
  req?: string;
  fulfilled?: boolean;
  progress?: number;
  max?: number;
  percent_fulfilled?: number;
  sat_courses?: string[];
  is_bypassed?: boolean;
  invalid?: boolean;  // True if course doesn't exist in catalog
}

export interface RequirementTree {
  'list-id': string;
  title: string;
  'medium-title'?: string;
  'short-title'?: string;
  'title-no-degree'?: string;
  desc?: string;
  reqs: RequirementNode[];
}
