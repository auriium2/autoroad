/**
 * Parser for Fireroad-format requirement files
 * 
 * File format:
 * Line 1: Metadata (short#,#medium#,#full title#,#thresholds)
 * Line 2: Description
 * Lines 3+: Requirement definitions
 */

import fs from 'fs';
import path from 'path';

export interface RequirementMetadata {
  title_no_degree?: string;
  title: string;
  short: string;
  medium: string;
}

export interface RequirementFile {
  metadata: RequirementMetadata;
  description: string;
  content: string;
}

const REQUIREMENTS_DIR = path.join(process.cwd(), 'requirements');

/**
 * Parse a requirement file in Fireroad format
 */
export function parseRequirementFile(content: string): RequirementFile {
  const lines = content.split('\n');
  
  if (lines.length < 2) {
    throw new Error('Invalid requirement file: must have at least 2 lines');
  }

  // Parse metadata from first line
  const metadataLine = lines[0];
  const parts = metadataLine.split('#,#');
  
  const metadata: RequirementMetadata = {
    short: parts[0] || '',
    medium: parts[1] || parts[0] || '',
    title: parts[2] || parts[1] || parts[0] || '',
    title_no_degree: parts[0] || '',
  };

  // Find the description (skip empty lines after metadata)
  let descriptionIndex = 1;
  while (descriptionIndex < lines.length && lines[descriptionIndex].trim() === '') {
    descriptionIndex++;
  }
  
  const description = descriptionIndex < lines.length 
    ? lines[descriptionIndex].replace(/\\n\\n/g, '\n\n')
    : '';

  // Rest is the requirement content (skip empty lines after description)
  let contentStartIndex = descriptionIndex + 1;
  while (contentStartIndex < lines.length && lines[contentStartIndex].trim() === '') {
    contentStartIndex++;
  }
  
  const requirementContent = lines.slice(contentStartIndex).join('\n');

  return {
    metadata,
    description,
    content: requirementContent,
  };
}

/**
 * Load all custom requirement files from the requirements directory
 * Returns a map of requirement key -> metadata
 */
export function loadCustomRequirements(): Record<string, RequirementMetadata> {
  const requirements: Record<string, RequirementMetadata> = {};

  // Check if requirements directory exists
  if (!fs.existsSync(REQUIREMENTS_DIR)) {
    return requirements;
  }

  // Read all .txt and .fireroad files in the requirements directory
  const files = fs.readdirSync(REQUIREMENTS_DIR)
    .filter(file => file.endsWith('.txt') || file.endsWith('.fireroad'));

  for (const file of files) {
    try {
      const filePath = path.join(REQUIREMENTS_DIR, file);
      const content = fs.readFileSync(filePath, 'utf-8');
      const parsed = parseRequirementFile(content);
      
      // Use filename without extension as the key
      const key = file.endsWith('.fireroad') 
        ? path.basename(file, '.fireroad')
        : path.basename(file, '.txt');
      requirements[key] = parsed.metadata;
    } catch (error) {
      console.error(`Error loading requirement file ${file}:`, error);
    }
  }

  return requirements;
}

/**
 * Load a specific custom requirement file
 */
export function loadCustomRequirement(key: string): RequirementFile | null {
  // Try both .fireroad and .txt extensions
  const fireroadPath = path.join(REQUIREMENTS_DIR, `${key}.fireroad`);
  const txtPath = path.join(REQUIREMENTS_DIR, `${key}.txt`);
  
  const filePath = fs.existsSync(fireroadPath) ? fireroadPath : 
                   fs.existsSync(txtPath) ? txtPath : null;
  
  if (!filePath) {
    return null;
  }

  try {
    const content = fs.readFileSync(filePath, 'utf-8');
    return parseRequirementFile(content);
  } catch (error) {
    console.error(`Error loading requirement file ${key}:`, error);
    return null;
  }
}
