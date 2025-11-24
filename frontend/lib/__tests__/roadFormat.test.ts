import { describe, it, expect } from 'vitest';
import { exportToRoadFormat, importFromRoadFormat, type RoadFormat } from '../roadFormat';
import type { Marker } from '@/types';

describe('roadFormat', () => {
  describe('exportToRoadFormat', () => {
    it('should export markers to .road format', async () => {
      const markers: Marker[] = [
        {
          uuid: 'marker_1',
          courseId: '18.02',
          section: 1,
          status: 'pin',
        },
        {
          uuid: 'marker_2',
          courseId: '6.100A',
          section: 0,
          status: 'override',
        },
      ];

      const mockGetCourseDetails = async (courseId: string) => {
        const mockData: Record<string, { title: string; total_units: number }> = {
          '18.02': { title: 'Calculus', total_units: 12 },
          '6.100A': { title: 'Introduction to CS', total_units: 6 },
        };
        return mockData[courseId];
      };

      const result = await exportToRoadFormat(markers, ['girs'], mockGetCourseDetails);

      expect(result.coursesOfStudy).toEqual(['girs']);
      expect(result.selectedSubjects).toHaveLength(2);
      expect(result.selectedSubjects[0]).toEqual({
        overrideWarnings: false,
        semester: 2,
        title: 'Calculus',
        subject_id: '18.02',
        units: 12,
      });
      expect(result.selectedSubjects[1]).toEqual({
        overrideWarnings: true,
        semester: 1,
        title: 'Introduction to CS',
        subject_id: '6.100A',
        units: 6,
      });
    });

    it('should skip banished markers', async () => {
      const markers: Marker[] = [
        {
          uuid: 'marker_1',
          courseId: '18.02',
          section: 0,
          status: 'pin',
        },
        {
          uuid: 'marker_2',
          courseId: '6.100A',
          section: 0,
          status: 'banish',
        },
      ];

      const mockGetCourseDetails = async (courseId: string) => {
        return { title: 'Test Course', total_units: 12 };
      };

      const result = await exportToRoadFormat(markers, [], mockGetCourseDetails);

      expect(result.selectedSubjects).toHaveLength(1);
      expect(result.selectedSubjects[0].subject_id).toBe('18.02');
    });

    it('should use girs as default coursesOfStudy', async () => {
      const markers: Marker[] = [];
      const mockGetCourseDetails = async () => ({ title: '', total_units: 0 });

      const result = await exportToRoadFormat(markers, [], mockGetCourseDetails);

      expect(result.coursesOfStudy).toEqual(['girs']);
    });
  });

  describe('importFromRoadFormat', () => {
    it('should import .road format to markers', () => {
      const roadData: RoadFormat = {
        coursesOfStudy: ['girs'],
        progressOverrides: {},
        selectedSubjects: [
          {
            overrideWarnings: true,
            semester: 1,
            title: 'Calculus',
            subject_id: '18.02',
            units: 12,
          },
          {
            semester: 2,
            title: 'Introduction to CS',
            subject_id: '6.100A',
            units: 6,
          },
        ],
        progressAssertions: {},
      };

      const result = importFromRoadFormat(roadData);

      expect(result.markers).toHaveLength(2);
      expect(result.warnings).toHaveLength(0);
      expect(result.markers[0]).toMatchObject({
        courseId: '18.02',
        section: 0,
        status: 'override',
      });
      expect(result.markers[1]).toMatchObject({
        courseId: '6.100A',
        section: 1,
        status: 'pin',
      });
    });

    it('should convert semester to section correctly', () => {
      const roadData: RoadFormat = {
        coursesOfStudy: ['girs'],
        progressOverrides: {},
        selectedSubjects: [
          {
            semester: 1,
            title: 'Freshman Fall',
            subject_id: '18.01',
            units: 12,
          },
          {
            semester: 12,
            title: 'Senior Spring',
            subject_id: '6.UAT',
            units: 12,
          },
        ],
        progressAssertions: {},
      };

      const result = importFromRoadFormat(roadData);

      expect(result.markers[0].section).toBe(0);
      expect(result.markers[1].section).toBe(11);
    });

    it('should handle ASE semester (semester 0)', () => {
      const roadData: RoadFormat = {
        coursesOfStudy: ['girs'],
        progressOverrides: {},
        selectedSubjects: [
          {
            semester: 0,
            title: 'ASE Course',
            subject_id: '18.01',
            units: 12,
          },
        ],
        progressAssertions: {},
      };

      const result = importFromRoadFormat(roadData);

      expect(result.markers[0].section).toBe(-1);
    });

    it('should default to pin status when overrideWarnings is not set', () => {
      const roadData: RoadFormat = {
        coursesOfStudy: ['girs'],
        progressOverrides: {},
        selectedSubjects: [
          {
            semester: 1,
            title: 'Test',
            subject_id: '18.01',
            units: 12,
          },
        ],
        progressAssertions: {},
      };

      const result = importFromRoadFormat(roadData);

      expect(result.markers[0].status).toBe('pin');
    });

    it('should warn about generic GIR courses', () => {
      const roadData: RoadFormat = {
        coursesOfStudy: ['girs'],
        progressOverrides: {},
        selectedSubjects: [
          {
            semester: 1,
            title: 'Calculus I GIR',
            subject_id: 'GIR:CAL1',
            units: 12,
          },
          {
            semester: 2,
            title: 'Real Course',
            subject_id: '18.01',
            units: 12,
          },
        ],
        progressAssertions: {},
      };

      const result = importFromRoadFormat(roadData);

      expect(result.markers).toHaveLength(1);
      expect(result.markers[0].courseId).toBe('18.01');
      expect(result.warnings).toHaveLength(1);
      expect(result.warnings[0]).toContain('GIR:CAL1');
    });

    it('should warn about generic HASS courses', () => {
      const roadData: RoadFormat = {
        coursesOfStudy: ['girs'],
        progressOverrides: {},
        selectedSubjects: [
          {
            semester: 1,
            title: 'HASS Arts',
            subject_id: 'HASS-A',
            units: 12,
          },
          {
            semester: 2,
            title: 'HASS Elective',
            subject_id: 'HASS E',
            units: 12,
          },
        ],
        progressAssertions: {},
      };

      const result = importFromRoadFormat(roadData);

      expect(result.markers).toHaveLength(0);
      expect(result.warnings).toHaveLength(2);
      expect(result.warnings[0]).toContain('HASS-A');
      expect(result.warnings[1]).toContain('HASS E');
    });

    it('should warn about CI-H and CI-M placeholders', () => {
      const roadData: RoadFormat = {
        coursesOfStudy: ['girs'],
        progressOverrides: {},
        selectedSubjects: [
          {
            semester: 1,
            title: 'Communication Intensive HASS',
            subject_id: 'CI-H',
            units: 12,
          },
        ],
        progressAssertions: {},
      };

      const result = importFromRoadFormat(roadData);

      expect(result.markers).toHaveLength(0);
      expect(result.warnings).toHaveLength(1);
      expect(result.warnings[0]).toContain('CI-H');
    });

    it('should warn about plain GIR codes from CourseRoad', () => {
      const roadData: RoadFormat = {
        coursesOfStudy: ['girs'],
        progressOverrides: {},
        selectedSubjects: [
          {
            semester: 0,
            title: 'Generic Calculus I GIR',
            subject_id: 'CAL1',
            units: 12,
          },
          {
            semester: 0,
            title: 'Generic Biology GIR',
            subject_id: 'BIOL',
            units: 12,
          },
          {
            semester: 0,
            title: 'Real ASE Course',
            subject_id: '6.100A',
            units: 6,
          },
        ],
        progressAssertions: {},
      };

      const result = importFromRoadFormat(roadData);

      expect(result.markers).toHaveLength(1);
      expect(result.markers[0].courseId).toBe('6.100A');
      expect(result.markers[0].section).toBe(-1); // ASE
      expect(result.warnings).toHaveLength(2);
      expect(result.warnings[0]).toContain('CAL1');
      expect(result.warnings[1]).toContain('BIOL');
    });
  });
});
