/**
 * Hydrant API Client
 * Fetches parsed schedule data from backend
 */

import { API_BASE_URL } from '@/config/api';

export interface TimeBlock {
  course_id: string;
  type: string;
  room: string;
  day: number; // 0=Monday, 1=Tuesday, 2=Wednesday, 3=Thursday, 4=Friday
  start_hour: number; // 24-hour decimal (e.g., 15.5 for 3:30pm)
  end_hour: number;
  is_required: boolean; // true if only 1 section of this type (must attend)
  section_index: number; // 0-indexed section option number
}

export interface ScheduleResponse {
  target_semester: string;
  data_semester: string;
  blocks: TimeBlock[];
  missing_courses: string[];
  has_conflicts: boolean;
}

export const hydrantApi = {
  async getSchedule(targetSemester: string, courseIds: string[]): Promise<ScheduleResponse> {
    if (courseIds.length === 0) {
      return {
        target_semester: targetSemester,
        data_semester: targetSemester,
        blocks: [],
        missing_courses: [],
        has_conflicts: false,
      };
    }

    const response = await fetch(
      `${API_BASE_URL}/api/hydrant/schedule/${targetSemester}?course_ids=${courseIds.join(",")}`
    );
    if (!response.ok) {
      throw new Error(`Failed to fetch schedule for ${targetSemester}`);
    }
    return response.json();
  },
};
