import type { Marker, OptimizerNode } from '@/types';
import type { ObjectiveConfig, ConstraintConfig } from '@/types/models/optimizer';

// handle imports from courseroad and general .road file format, which we must use to be Compatible

export interface RoadFormatSubject {
  overrideWarnings?: boolean;
  semester: number;
  title: string;
  subject_id: string;
  units: number;
}

export interface RoadFormat {
  coursesOfStudy: string[];
  progressOverrides: Record<string, unknown>;
  selectedSubjects: RoadFormatSubject[];
  progressAssertions: Record<string, unknown>;
}

export interface AroadFormat extends RoadFormat {
  autoroad: {
    version: "1";
    objectives: ObjectiveConfig[];
    objectiveTiers: Record<string, number>;
    requirementTiers: Record<string, number>;
    requirementSources: Record<string, string>;
    hardConstraints: ConstraintConfig[];
    customEquivalencies: Record<string, string[]>;
    selectedYear: string;
    lockPastSemesters: boolean;
    mustTakeSubjects: RoadFormatSubject[];
    optimizerNodes: RoadFormatSubject[];
  };
}

export interface OptimizationStateSnapshot {
  selectedObjectives: ObjectiveConfig[];
  objectiveTiers: Record<string, number>;
  requirementTiers: Record<string, number>;
  requirementSources: Record<string, string>;
  selectedHardConstraints: ConstraintConfig[];
  customEquivalencies: Record<string, string[]>;
  selectedYear: string;
  lockPastSemesters: boolean;
}

function sectionToSemester(section: number): number {
  // ASE: section -1 -> semester 0
  // Regular: section 0-11 -> semester 1-12
  if (section === -1) return 0; // ASE
  if (section < 0) return 1; // Fallback for other negative sections
  return section + 1;
}

function semesterToSection(semester: number): number | null {
  // ASE: semester 0 -> section -1
  // Regular: semester 1-12 -> section 0-11
  if (semester === 0) return -1; // ASE
  if (semester < 0) return 0; // Fallback for invalid semesters
  if (semester > 12) return null; // Grad semesters not supported
  return semester - 1;
}

type CourseDetailsFetcher = (courseId: string) => Promise<{ title: string; total_units: number }>;

export async function exportToRoadFormat(
  markers: Marker[],
  selectedRequirements: string[],
  getCourseDetails: CourseDetailsFetcher
): Promise<RoadFormat> {
  const selectedSubjects: RoadFormatSubject[] = [];

  for (const marker of markers) {
    if (marker.status === 'banish') continue;
    if (marker.section === -2) continue; // Must Take markers don't exist in .road format

    try {
      const details = await getCourseDetails(marker.courseId);

      selectedSubjects.push({
        overrideWarnings: marker.status === 'override',
        semester: sectionToSemester(marker.section),
        title: details.title,
        subject_id: marker.courseId,
        units: details.total_units,
      });
    } catch (error) {
      console.warn(`Failed to get details for ${marker.courseId}:`, error);
      selectedSubjects.push({
        overrideWarnings: marker.status === 'override',
        semester: sectionToSemester(marker.section),
        title: marker.courseId,
        subject_id: marker.courseId,
        units: 0,
      });
    }
  }

  return {
    coursesOfStudy: selectedRequirements.length > 0 ? selectedRequirements : ['girs'],
    progressOverrides: {},
    selectedSubjects,
    progressAssertions: {},
  };
}

export async function exportToAroadFormat(
  markers: Marker[],
  optimizerNodes: OptimizerNode[],
  selectedRequirements: string[],
  optimizationState: OptimizationStateSnapshot,
  getCourseDetails: CourseDetailsFetcher
): Promise<AroadFormat> {
  // selectedSubjects = user markers only (no must-take, no banish)
  const roadBase = await exportToRoadFormat(markers, selectedRequirements, getCourseDetails);

  // Serialize must-take markers into autoroad block
  const mustTakeSubjects: RoadFormatSubject[] = [];
  for (const marker of markers) {
    if (marker.section !== -2) continue;
    if (marker.status === 'banish') continue;

    try {
      const details = await getCourseDetails(marker.courseId);
      mustTakeSubjects.push({
        overrideWarnings: marker.status === 'override',
        semester: -2,
        title: details.title,
        subject_id: marker.courseId,
        units: details.total_units,
      });
    } catch {
      mustTakeSubjects.push({
        overrideWarnings: marker.status === 'override',
        semester: -2,
        title: marker.courseId,
        subject_id: marker.courseId,
        units: 0,
      });
    }
  }

  // Serialize optimizer nodes separately
  const optimizerNodeSubjects: RoadFormatSubject[] = [];
  for (const node of optimizerNodes) {
    try {
      const details = await getCourseDetails(node.courseId);
      optimizerNodeSubjects.push({
        semester: sectionToSemester(node.section),
        title: details.title,
        subject_id: node.courseId,
        units: details.total_units,
      });
    } catch {
      optimizerNodeSubjects.push({
        semester: sectionToSemester(node.section),
        title: node.courseId,
        subject_id: node.courseId,
        units: node.units ?? 0,
      });
    }
  }

  return {
    ...roadBase,
    autoroad: {
      version: "1",
      objectives: optimizationState.selectedObjectives,
      objectiveTiers: optimizationState.objectiveTiers,
      requirementTiers: optimizationState.requirementTiers,
      requirementSources: optimizationState.requirementSources,
      hardConstraints: optimizationState.selectedHardConstraints,
      customEquivalencies: optimizationState.customEquivalencies,
      selectedYear: optimizationState.selectedYear,
      lockPastSemesters: optimizationState.lockPastSemesters,
      mustTakeSubjects,
      optimizerNodes: optimizerNodeSubjects,
    },
  };
}

export interface ImportResult {
  markers: Marker[];
  warnings: string[];
  coursesOfStudy: string[];
}

export interface AroadImportResult extends ImportResult {
  optimizationState?: OptimizationStateSnapshot;
  optimizerNodes?: OptimizerNode[];
}

export function importFromRoadFormat(roadData: RoadFormat): ImportResult {
  const markers: Marker[] = [];
  const warnings: string[] = [];
  const coursesOfStudy = roadData.coursesOfStudy || [];

  for (const subject of roadData.selectedSubjects) {
    // Check for generic HASS or GIR placeholders
    const subjectId = subject.subject_id;
    const isGenericGIR = /^GIR:/i.test(subjectId);
    const isGenericHASS = /^HASS[-\s]?[AHSE]/i.test(subjectId);
    const isGenericCI = /^CI-[HM]/i.test(subjectId);
    // Plain GIR codes used by CourseRoad (CAL1, CAL2, BIOL, CHEM, PHY1, PHY2, REST)
    const isPlainGIR = /^(CAL1|CAL2|BIOL|CHEM|PHY1|PHY2|REST)$/i.test(subjectId);

    if (isGenericGIR || isGenericHASS || isGenericCI || isPlainGIR) {
      warnings.push(
        `Generic requirement "${subjectId}" (${subject.title}) cannot be imported. ` +
        `Please select a specific course that fulfills this requirement.`
      );
      continue;
    }

    // Skip grad semesters (13+)
    const section = semesterToSection(subject.semester);
    if (section === null) {
      warnings.push(
        `"${subjectId}" (${subject.title}) is in a grad semester and was skipped.`
      );
      continue;
    }

    const marker: Marker = {
      uuid: `marker_${subject.subject_id}_${Date.now()}_${Math.random()}`,
      courseId: subject.subject_id,
      section,
      status: subject.overrideWarnings ? 'override' : 'pin',
    };

    markers.push(marker);
  }

  return { markers, warnings, coursesOfStudy };
}

export function importFromAroadFormat(data: AroadFormat): AroadImportResult {
  const baseResult = importFromRoadFormat(data);

  if (!data.autoroad) {
    return baseResult;
  }

  const aroad = data.autoroad;

  // Reconstruct must-take markers
  if (aroad.mustTakeSubjects) {
    for (const subject of aroad.mustTakeSubjects) {
      baseResult.markers.push({
        uuid: `marker_${subject.subject_id}_${Date.now()}_${Math.random()}`,
        courseId: subject.subject_id,
        section: -2,
        status: subject.overrideWarnings ? 'override' : 'pin',
      });
    }
  }

  // Reconstruct optimizer nodes
  const optimizerNodes: OptimizerNode[] = [];
  if (aroad.optimizerNodes) {
    for (const subject of aroad.optimizerNodes) {
      const section = semesterToSection(subject.semester);
      if (section === null) continue;
      optimizerNodes.push({
        courseId: subject.subject_id,
        section,
        units: subject.units,
      });
    }
  }

  return {
    ...baseResult,
    optimizerNodes,
    optimizationState: {
      selectedObjectives: aroad.objectives || [],
      objectiveTiers: aroad.objectiveTiers || {},
      requirementTiers: aroad.requirementTiers || {},
      requirementSources: (aroad.requirementSources || {}) as Record<string, string>,
      selectedHardConstraints: aroad.hardConstraints || [],
      customEquivalencies: aroad.customEquivalencies || {},
      selectedYear: aroad.selectedYear || String(new Date().getFullYear() + 4),
      lockPastSemesters: aroad.lockPastSemesters ?? false,
    },
  };
}

export function downloadFile(data: RoadFormat | AroadFormat, filename: string): void {
  const jsonStr = JSON.stringify(data);
  const blob = new Blob([jsonStr], { type: 'application/json' });
  const url = URL.createObjectURL(blob);

  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);

  URL.revokeObjectURL(url);
}

// Keep old name for backwards compat with any other callers
export const downloadRoadFile = downloadFile;

export function uploadFile(): Promise<RoadFormat | AroadFormat | null> {
  return new Promise((resolve, reject) => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.road,.aroad,application/json';

    input.onchange = async (e) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (!file) {
        resolve(null);
        return;
      }

      try {
        const text = await file.text();
        const data = JSON.parse(text);
        resolve(data);
      } catch (error) {
        reject(new Error('Failed to parse file: ' + (error instanceof Error ? error.message : 'Unknown error')));
      }
    };

    input.oncancel = () => {
      resolve(null);
    };

    input.click();
  });
}

// Keep old name for backwards compat
export const uploadRoadFile = uploadFile;
