/**
 * Computes SVG stroke dash settings to highlight portions of a course node border
 * based on term availability.
 *
 * We highlight:
 * - Left half for Fall
 * - Right half for Spring
 * - Full ring for Fall+Spring
 * - Bottom half for IAP-only (when Fall/Spring unavailable)
 */

export interface TermAvailability {
  offeredFall?: boolean;
  offeredSpring?: boolean;
  offeredIAP?: boolean;
}

export interface TermBorderHighlight {
  dasharray: string;
  dashoffset: number;
}

type TermPattern = "fall" | "spring" | "both" | "iap";

function resolvePattern(terms: TermAvailability): TermPattern | null {
  const fall = !!terms.offeredFall;
  const spring = !!terms.offeredSpring;
  const iap = !!terms.offeredIAP;

  if (fall && spring && !iap) return "both";
  if (fall && !spring && !iap) return "fall";
  if (!fall && spring && !iap) return "spring";
  if (!fall && !spring && iap) return "iap";
  return null;
}

const HIGHLIGHT_CONFIG: Record<TermPattern, TermBorderHighlight> = {
  fall: { dasharray: "0.5 0.5", dashoffset: 0.75 },   // Left half
  spring: { dasharray: "0.5 0.5", dashoffset: 0.25 }, // Right half
  iap: { dasharray: "0.5 0.5", dashoffset: 0 },       // Bottom half
  both: { dasharray: "1 0", dashoffset: 0 },
};

export function getTermBorderHighlight(
  terms: TermAvailability
): TermBorderHighlight | null {
  const pattern = resolvePattern(terms);
  if (!pattern) return null;
  return HIGHLIGHT_CONFIG[pattern];
}
