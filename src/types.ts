/**
 * Centralized type definitions for the Autoroad application
 */

// Constants
export const ASE: string = "ASEs";

// ============================================================================
// Core Node Types
// ============================================================================

/**
 * Course node representing a single class in the schedule
 * 
 * Field naming:
 * - `id`: Unique identifier for this specific node instance in the graph (e.g., "0", "1", "6.1200_1734567890")
 * - `courseId`: The course subject ID displayed to the user (e.g., "6.1200", "18.01")
 * - `section`: Which semester/column this course belongs to
 */
export interface CourseNode {
  id: string; // Unique node instance identifier
  courseId: string; // Course subject ID (e.g., "6.1200", "18.01")
  section: number; // Which semester/section this belongs to
  userControlled?: boolean; // If true, user added/can drag this node
  disabled?: boolean; // If true, node is disabled and cannot be taken
}

/**
 * Available course that can be added to the schedule
 * Represents courses from the catalog that the user can search and add
 */
export interface AvailableNode {
  courseId: string; // Course subject ID (e.g., "6.1200", "18.01")
  title: string; // Course title (e.g., "Mathematics for Computer Science")
  department: string; // Department code (e.g., "6", "18")
  units: number; // Credit units
}

// ============================================================================
// Graph Relationship Types
// ============================================================================

/**
 * Edge between two courses (prerequisite relationship)
 */
export interface Edge {
  from_id: string;
  to_id: string;
}

/**
 * Section (semester or special section like "Must Take" or "ASEs")
 */
export interface Section {
  id: number;
  title: string;
}

// ============================================================================
// Styling Types
// ============================================================================

/**
 * Node style configuration for rendering
 */
export interface NodeStyleConfig {
  borderColor: string;
  bgColor: string;
  textColor: string;
  boxShadow: string;
}

/**
 * Node properties used to compute styling
 * This is a subset of CourseNode with additional rendering properties
 */
export interface NodeStyleProperties {
  section: number;
  userControlled?: boolean;
  disabled?: boolean;
  isSpecial?: boolean;
}

// ============================================================================
// Loading and State Types
// ============================================================================

/**
 * Loading state for async operations
 */
export type LoadingState = 'idle' | 'loading' | 'success' | 'error';
