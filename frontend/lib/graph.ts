/**
 * Graph Visualization Utilities
 * Handles node styling and term border highlights for the course graph
 */

import type { NodeStyleConfig, NodeStyleProperties } from '@/types';

// ============================================================================
// Node Styling
// ============================================================================

export function getNodeStyle(node: NodeStyleProperties): NodeStyleConfig {
  const { section, userControlled, disabled } = node;

  const isMustTake = section === -2;
  const isASE = section === -1;

  let borderColor = "border-border";
  let bgColor = "bg-card";
  let textColor = "text-foreground";
  let boxShadow = "none";

  if (isMustTake) {
    bgColor = "bg-purple-950/40";
    textColor = "text-purple-300";
    boxShadow = "0 0 20px rgba(168, 85, 247, 0.6), 0 0 40px rgba(168, 85, 247, 0.3)";
  } else if (userControlled) {
    borderColor = "border-blue-700";
    bgColor = "bg-blue-950/50";
    textColor = "text-blue-300";
    boxShadow = "none";
  } else if (isASE) {
    borderColor = "border-gray-300 dark:border-gray-600";
    bgColor = "bg-gray-50 dark:bg-gray-900/40";
    textColor = "text-gray-700 dark:text-gray-300";
    boxShadow = "none";
  } else if (disabled) {
    borderColor = "border-red-500";
    bgColor = "bg-red-50 dark:bg-red-950/20";
    textColor = "text-red-700 dark:text-red-400";
    boxShadow = "none";
  }

  return {
    borderColor,
    bgColor,
    textColor,
    boxShadow,
  };
}

// ============================================================================
// Term Border Highlights
// ============================================================================

export interface TermAvailability {
  offeredFall?: boolean;
  offeredSpring?: boolean;
  offeredIAP?: boolean;
}

export interface TermBorderHighlight {
  dasharray: string;
  dashoffset: number;
}

type TermPattern = "fall" | "spring" | "both" | "iap" | "fall-iap" | "spring-iap";

function resolvePattern(terms: TermAvailability): TermPattern | null {
  const fall = !!terms.offeredFall;
  const spring = !!terms.offeredSpring;
  const iap = !!terms.offeredIAP;

  if (fall && spring && !iap) return "both";
  if (fall && !spring && !iap) return "fall";
  if (!fall && spring && !iap) return "spring";
  if (!fall && !spring && iap) return "iap";
  if (fall && !spring && iap) return "fall-iap";
  if (!fall && spring && iap) return "spring-iap";
  return null;
}

const HIGHLIGHT_CONFIG: Record<TermPattern, TermBorderHighlight> = {
  fall: { dasharray: "0.5 0.5", dashoffset: 0.75 },
  spring: { dasharray: "0.5 0.5", dashoffset: 0.25 },
  iap: { dasharray: "0.5 0.5", dashoffset: 0 },
  both: { dasharray: "1 0", dashoffset: 0 },
  "fall-iap": { dasharray: "0.75 0.25", dashoffset: 0.75 },
  "spring-iap": { dasharray: "0.75 0.25", dashoffset: 0.25 },
};

export function getTermBorderHighlight(
  terms: TermAvailability
): TermBorderHighlight | null {
  const pattern = resolvePattern(terms);
  if (!pattern) return null;
  return HIGHLIGHT_CONFIG[pattern];
}
