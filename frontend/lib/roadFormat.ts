import type { Marker } from '@/types';

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
  if (section < 0) return 1;
  return section + 1;
}

function semesterToSection(semester: number): number {
  return Math.max(0, semester - 1);
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

export function importFromRoadFormat(roadData: RoadFormat): Marker[] {
  const markers: Marker[] = [];

  for (const subject of roadData.selectedSubjects) {
    const marker: Marker = {
      uuid: `marker_${subject.subject_id}_${Date.now()}_${Math.random()}`,
      courseId: subject.subject_id,
      section: semesterToSection(subject.semester),
      status: subject.overrideWarnings ? 'override' : 'pin',
    };
    
    markers.push(marker);
  }

  return markers;
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
