/**
 * Optimizer-related types
 * Types for objectives, constraints, and optimization configuration
 */

export interface ObjectiveMetadata {
  key: string;
  name: string;
  shortDescription: string;
  description: string;
  category: string;
  hasParameters: boolean;
  defaultParameters: Record<string, number>;
  parameterTypes: Record<string, string>;
  defaultTier: number;
  unremovable?: boolean;
}

export interface ObjectiveConfig {
  key: string;
  parameters: Record<string, number | boolean | Record<string, string[]> | null>;
}

export interface ObjectivesResponse {
  objectives: ObjectiveMetadata[];
  defaultConfiguration: ObjectiveConfig[];
}

export interface HardConstraintMetadata {
  key: string;
  name: string;
  shortDescription: string;
  description: string;
  category: string;
  hasParameters: boolean;
  defaultParameters: Record<string, unknown>;
  parameterTypes: Record<string, string>;
  beta: boolean;
}

export interface ConstraintConfig {
  key: string;
  parameters: Record<string, unknown>;
}

export interface HardConstraintsResponse {
  constraints: HardConstraintMetadata[];
}

export interface SearchableItem {
  type: 'degree' | 'objective' | 'constraint';
  key: string;
  displayName: string;
  metadata?: any; // Can be RequirementMetadata | ObjectiveMetadata | HardConstraintMetadata
}

export interface SearchResults {
  objectives: SearchableItem[];
  constraints: SearchableItem[];
  concentrations: SearchableItem[];
  degrees: SearchableItem[];
  totalCounts: {
    objectives: number;
    constraints: number;
    concentrations: number;
    degrees: number;
  };
}
