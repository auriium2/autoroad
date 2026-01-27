
import * as React from "react";
import { Users, TicketPercent, Sparkles } from "lucide-react";
import { CourseTooltip } from "@/components/CourseTooltip";
import { getTermBorderHighlight } from "@/lib/graph";
import type { FireroadCourse } from "@/services/fireroad";

interface CourseCardProps {
  course: FireroadCourse;
  onDragStart: (e: React.DragEvent, course: FireroadCourse) => void;
  onDragEnd: (e: React.DragEvent) => void;
}

export function CourseCard({ course, onDragStart, onDragEnd }: CourseCardProps) {
  if (!course || !course.subject_id || !course.title) {
    console.warn('Invalid course data:', course);
    return null;
  }

  if (course.virtual) {
    return (
      <div 
        draggable
        onDragStart={(e) => onDragStart(e, course)}
        onDragEnd={onDragEnd}
        className="relative p-4 pb-3 border border-amber-600/30 rounded-lg transition-colors overflow-hidden min-h-[80px] bg-gradient-to-br from-amber-900/20 to-amber-800/10 cursor-move hover:border-amber-500/50"
      >
        <div className="relative flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0 flex flex-col">
            <div className="font-medium text-sm mb-0.5 text-white">{course.subject_id}</div>
            <div className="text-xs text-muted-foreground line-clamp-2">
              {course.title}
            </div>
            <div className="text-[10px] text-amber-200/40 mt-2">
              Generic requirement placeholder
            </div>
          </div>
          <div className="relative w-9 h-9 rounded-full flex-shrink-0 transition-all duration-200">
            <div className="absolute inset-0 rounded-full border-2 border-amber-600/50 bg-amber-900/20 flex items-center justify-center">
              <Sparkles className="w-4 h-4 text-amber-200/80" />
            </div>
          </div>
        </div>
      </div>
    );
  }

  const termHighlight = getTermBorderHighlight({
    offeredFall: course.offered_fall,
    offeredSpring: course.offered_spring,
    offeredIAP: 'offered_IAP' in course ? course.offered_IAP : undefined,
  });

  const currentMonth = new Date().getMonth();
  const isFallSemester = currentMonth >= 8 || currentMonth <= 0;
  const currentInstructor = course.instructors && course.instructors.length > 0
    ? (isFallSemester ? course.instructors[0] : course.instructors[1] || course.instructors[0])
    : null;

  const enrollment = course.enrollment_number !== undefined && course.enrollment_number !== null
    ? Math.round(course.enrollment_number)
    : null;
  const rating = course.rating !== undefined && course.rating !== null
    ? course.rating.toFixed(1)
    : null;

  const isGraduate = course.level === 'G';

  return (
    <CourseTooltip courseId={course.subject_id}>
      <div 
        draggable
        onDragStart={(e) => onDragStart(e, course)}
        onDragEnd={onDragEnd}
        className="relative p-4 pb-2.5 border border-border rounded-lg transition-colors overflow-hidden min-h-[100px] cursor-move hover:border-primary/50"
      >
        {isGraduate && (
          <div className="absolute inset-0 pointer-events-none bg-gradient-to-tr from-transparent to-purple-500/8" />
        )}

        {currentInstructor && (
          <div className="absolute left-0 right-0 bottom-2 flex items-center pointer-events-none overflow-hidden">
            <div className="animate-marquee whitespace-nowrap">
              <span className="text-3xl font-bold text-muted-foreground/[0.15] select-none mx-8">
                {currentInstructor}
              </span>
              <span className="text-3xl font-bold text-muted-foreground/[0.15] select-none mx-8">
                {currentInstructor}
              </span>
            </div>
          </div>
        )}

        <div className="relative flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0 flex flex-col">
            <div className="font-medium text-sm mb-0.5">
              {course.has_final ? (
                <span className="bg-yellow-500/30 px-1 -mx-1 rounded-sm">{course.subject_id}</span>
              ) : (
                course.subject_id
              )}
            </div>
            <div className="text-xs text-muted-foreground line-clamp-2 mb-2">
              {course.title}
            </div>

            <div className="flex items-center gap-x-2 text-[11px] text-muted-foreground/80 mt-auto overflow-hidden">
              {(course.in_class_hours !== undefined && course.in_class_hours !== null &&
                course.out_of_class_hours !== undefined && course.out_of_class_hours !== null) ? (
                <span className="flex items-center gap-1 whitespace-nowrap">
                  <span className="font-semibold">{(course.in_class_hours + course.out_of_class_hours).toFixed(1)}h</span>
                </span>
              ) : (
                <span className="flex items-center gap-1 whitespace-nowrap text-muted-foreground/40">
                  <span className="font-semibold">—</span>
                </span>
              )}
              {enrollment ? (
                <span className="flex items-center gap-0.5 whitespace-nowrap">
                  <Users className="w-3 h-3 opacity-60" />
                  <span className="font-semibold">{enrollment}</span>
                </span>
              ) : (
                <span className="flex items-center gap-0.5 whitespace-nowrap text-muted-foreground/40">
                  <Users className="w-3 h-3 opacity-60" />
                  <span className="font-semibold">—</span>
                </span>
              )}
              {rating ? (
                <span className="flex items-center gap-0.5 whitespace-nowrap">
                  <span className="font-semibold">★{rating}</span>
                </span>
              ) : (
                <span className="flex items-center gap-0.5 whitespace-nowrap text-muted-foreground/40">
                  <span className="font-semibold">★—</span>
                </span>
              )}
              {course.imdb_rating !== undefined && course.imdb_rating !== null ? (
                <span className="flex items-center gap-0.5 whitespace-nowrap">
                  <TicketPercent className="w-3 h-3 opacity-60" />
                  <span className="font-semibold">{course.imdb_rating}</span>
                </span>
              ) : (
                <span className="flex items-center gap-0.5 text-muted-foreground/40 whitespace-nowrap">
                  <TicketPercent className="w-3 h-3 opacity-60" />
                  <span className="font-semibold">—</span>
                </span>
              )}
              {course.not_offered_year && (
                <span className="text-[10px] text-yellow-500/80 whitespace-nowrap" title={`Not offered ${course.not_offered_year}`}>
                  ⚠'{course.not_offered_year.split('-')[0].slice(-2)}-'{course.not_offered_year.split('-')[1].slice(-2)}
                </span>
              )}
            </div>
          </div>
          <div
            className="relative w-9 h-9 rounded-full flex-shrink-0 transition-all duration-200"
            data-tutorial="course-drag-handle"
          >
            <div className="absolute inset-0 rounded-full border-2 border-border bg-card flex items-center justify-center text-xs font-bold">
              {course.total_units ?? 12}
            </div>
            {termHighlight && (
              <svg
                className="pointer-events-none absolute inset-0"
                viewBox="0 0 36 36"
                preserveAspectRatio="xMidYMid meet"
              >
                <circle
                  cx="18"
                  cy="18"
                  r="16"
                  fill="none"
                  stroke="rgba(255,255,255,0.35)"
                  strokeWidth="2"
                  pathLength={1}
                  strokeDasharray={termHighlight.dasharray}
                  strokeDashoffset={termHighlight.dashoffset}
                  strokeLinecap="butt"
                />
              </svg>
            )}
          </div>
        </div>
      </div>
    </CourseTooltip>
  );
}
