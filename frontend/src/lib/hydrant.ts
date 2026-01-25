import { pack } from "msgpackr";

/**
 * Encodes data for Hydrant URL sharing using msgpack + base64.
 * Matches Hydrant's urlencode() implementation.
 */
function urlencode(obj: unknown): string {
  const packed = pack(obj);
  return btoa(String.fromCharCode(...packed));
}

/**
 * Generates a Hydrant URL for the given courses.
 *
 * @param courseIds - Array of course IDs (e.g., ["6.100A", "18.06"])
 * @param semester - Hydrant semester code (e.g., "s25", "f24")
 * @returns Full Hydrant URL with encoded schedule
 */
export function generateHydrantUrl(
  courseIds: string[],
  semester: string
): string {
  if (courseIds.length === 0) {
    return `https://hydrant.mit.edu/?t=${semester}`;
  }

  // Hydrant's deflated class format is [classNumber, ...optionalFields]
  // For a simple share without locked sections, just the class number is needed
  const deflatedClasses = courseIds.map((id) => [id]);

  // Hydrant state format: [selectedClasses, selectedNonClasses, selectedOption]
  const state = [deflatedClasses, null, 0];

  const encoded = urlencode(state);

  return `https://hydrant.mit.edu/?t=${semester}&s=${encoded}`;
}
