import type { Marker } from '@/types';

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

function sectionToSemester(section: number): number {
  // ASE: section -1 -> semester 0
  // Must Take: section -2 -> not exported (handled by filtering banish)
  // Regular: section 0-11 -> semester 1-12
  if (section === -1) return 0; // ASE
  if (section < 0) return 1; // Fallback for other negative sections
  return section + 1;
}

function semesterToSection(semester: number): number {
  // ASE: semester 0 -> section -1
  // Regular: semester 1-12 -> section 0-11
  if (semester === 0) return -1; // ASE
  if (semester < 0) return 0; // Fallback for invalid semesters
  return semester - 1;
}

export async function exportToRoadFormat(
  markers: Marker[],
  selectedRequirements: string[],
  getCourseDetails: (courseId: string) => Promise<{ name: string; units: number }>
): Promise<RoadFormat> {
  const selectedSubjects: RoadFormatSubject[] = [];

  for (const marker of markers) {
    if (marker.status === 'banish') continue;

    try {
      const details = await getCourseDetails(marker.courseId);

      selectedSubjects.push({
        overrideWarnings: marker.status === 'override',
        semester: sectionToSemester(marker.section),
        title: details.name,
        subject_id: marker.courseId,
        units: details.units,
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

export interface ImportResult {
  markers: Marker[];
  warnings: string[];
}

export function importFromRoadFormat(roadData: RoadFormat): ImportResult {
  const markers: Marker[] = [];
  const warnings: string[] = [];

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
      continue; // Skip this subject
    }

    const marker: Marker = {
      uuid: `marker_${subject.subject_id}_${Date.now()}_${Math.random()}`,
      courseId: subject.subject_id,
      section: semesterToSection(subject.semester),
      status: subject.overrideWarnings ? 'override' : 'pin',
    };

    markers.push(marker);
  }

  return { markers, warnings };
}

export function downloadRoadFile(roadData: RoadFormat, filename = 'autoroad.road'): void {
  const jsonStr = JSON.stringify(roadData);
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

export function uploadRoadFile(): Promise<RoadFormat | null> {
  return new Promise((resolve, reject) => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.road,application/json';

    input.onchange = async (e) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (!file) {
        resolve(null);
        return;
      }

      try {
        const text = await file.text();
        const data = JSON.parse(text) as RoadFormat;
        resolve(data);
      } catch (error) {
        reject(new Error('Failed to parse .road file: ' + (error instanceof Error ? error.message : 'Unknown error')));
      }
    };

    input.oncancel = () => {
      resolve(null);
    };

    input.click();
  });
}
