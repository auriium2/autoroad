/**
 * Computes SVG stroke dash settings to highlight portions of a course node border
 * based on term availability.
 *
 * We highlight:
 * - Left half for Fall
 * - Right half for Spring
 * - Full ring for Fall+Spring
 * - Bottom half for IAP-only
 * - Left half + bottom half for Fall+IAP
 * - Right half + bottom half for Spring+IAP
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
  fall: { dasharray: "0.5 0.5", dashoffset: 0.75 },      // Left half
  spring: { dasharray: "0.5 0.5", dashoffset: 0.25 },    // Right half
  iap: { dasharray: "0.5 0.5", dashoffset: 0 },          // Bottom half
  both: { dasharray: "1 0", dashoffset: 0 },             // Full ring
  "fall-iap": { dasharray: "0.75 0.25", dashoffset: 0.75 }, // Left half + bottom half
  "spring-iap": { dasharray: "0.75 0.25", dashoffset: 0.25 }, // Right half + bottom half
};

export function getTermBorderHighlight(
  terms: TermAvailability
): TermBorderHighlight | null {
  const pattern = resolvePattern(terms);
  if (!pattern) return null;
  return HIGHLIGHT_CONFIG[pattern];
}
