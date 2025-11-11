/**
 * Shared utility for computing node styling based on node properties
 * Used by both CourseNode component and drag preview
 */

export interface NodeStyleConfig {
  borderColor: string;
  bgColor: string;
  textColor: string;
  boxShadow: string;
}

export interface NodeProperties {
  section: number;
  userControlled?: boolean;
  disabled?: boolean;
  isSpecial?: boolean;
}

/**
 * Computes the styling for a course node based on its properties
 * @param node - The node properties to compute styling for
 * @returns The computed style configuration
 */
export function getNodeStyle(node: NodeProperties): NodeStyleConfig {
  const { section, userControlled, disabled, isSpecial } = node;

  // Check if node is in "Must Take" column (section -2)
  const isMustTake = section === -2;
  
  // Check if node is in "ASEs" column (section -1)
  const isASE = section === -1;

  let borderColor = "border-border";
  let bgColor = "bg-card";
  let textColor = "text-foreground";
  let boxShadow = "none";

  if (isMustTake) {
    // Must Take nodes: purple glow
    borderColor = "border-purple-500";
    bgColor = "bg-purple-950/40";
    textColor = "text-purple-300";
    boxShadow = "0 0 20px rgba(168, 85, 247, 0.6), 0 0 40px rgba(168, 85, 247, 0.3)";
  } else if (isASE) {
    // ASEs nodes: white/gray styling
    borderColor = "border-gray-300 dark:border-gray-600";
    bgColor = "bg-gray-50 dark:bg-gray-900/40";
    textColor = "text-gray-700 dark:text-gray-300";
    boxShadow = "none";
  } else if (isSpecial) {
    // Special nodes: primary color
    borderColor = "border-primary";
    bgColor = "bg-primary/10";
    textColor = "text-foreground";
    boxShadow = "none";
  } else if (disabled) {
    // Disabled nodes: red styling
    borderColor = "border-red-500";
    bgColor = "bg-red-50 dark:bg-red-950/20";
    textColor = "text-red-700 dark:text-red-400";
    boxShadow = "none";
  } else if (userControlled) {
    // User-controlled nodes: yellow border
    borderColor = "border-yellow-500";
    bgColor = "bg-yellow-950/20";
    textColor = "text-yellow-200";
    boxShadow = "none";
  }

  return {
    borderColor,
    bgColor,
    textColor,
    boxShadow,
  };
}
