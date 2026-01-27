import { useState, useEffect } from "react";

interface TimeBlockPickerProps {
  blockedSlots: number[][]; // [[day, startHour, endHour], ...]
  onChange: (slots: number[][]) => void;
}

const DAYS = ["M", "T", "W", "R", "F"] as const;
const START_HOUR = 8;
const END_HOUR = 22;
const HOURS = END_HOUR - START_HOUR;

export function TimeBlockPicker({ blockedSlots, onChange }: TimeBlockPickerProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [dragMode, setDragMode] = useState<"add" | "remove">("add");
  const [dragStart, setDragStart] = useState<{ day: number; hour: number } | null>(null);
  const [dragCurrent, setDragCurrent] = useState<{ day: number; hour: number } | null>(null);

  const isHourBlocked = (day: number, hour: number): boolean => {
    return blockedSlots.some(
      ([d, startHour, endHour]) => d === day && hour >= startHour && hour < endHour
    );
  };

  const getDragSelection = (): Set<string> => {
    if (!dragStart || !dragCurrent) return new Set();
    
    const minDay = Math.min(dragStart.day, dragCurrent.day);
    const maxDay = Math.max(dragStart.day, dragCurrent.day);
    const minHour = Math.min(dragStart.hour, dragCurrent.hour);
    const maxHour = Math.max(dragStart.hour, dragCurrent.hour);
    
    const selection = new Set<string>();
    for (let d = minDay; d <= maxDay; d++) {
      for (let h = minHour; h <= maxHour; h++) {
        selection.add(`${d}-${h}`);
      }
    }
    return selection;
  };

  const handleMouseDown = (day: number, hour: number) => {
    const currentlyBlocked = isHourBlocked(day, hour);
    setIsDragging(true);
    setDragMode(currentlyBlocked ? "remove" : "add");
    setDragStart({ day, hour });
    setDragCurrent({ day, hour });
  };

  const handleMouseEnter = (day: number, hour: number) => {
    if (isDragging) {
      setDragCurrent({ day, hour });
    }
  };

  const handleMouseUp = () => {
    if (!isDragging || !dragStart || !dragCurrent) {
      setIsDragging(false);
      setDragStart(null);
      setDragCurrent(null);
      return;
    }

    const minDay = Math.min(dragStart.day, dragCurrent.day);
    const maxDay = Math.max(dragStart.day, dragCurrent.day);
    const minHour = Math.min(dragStart.hour, dragCurrent.hour);
    const maxHour = Math.max(dragStart.hour, dragCurrent.hour) + 1; // +1 for end hour

    if (dragMode === "add") {
      // Add new blocked slots for each day in the range
      const newSlots = [...blockedSlots];
      for (let d = minDay; d <= maxDay; d++) {
        // Remove any existing slots that overlap with this day's range
        const filtered = newSlots.filter(
          ([slotDay, slotStart, slotEnd]) =>
            slotDay !== d || slotEnd <= minHour || slotStart >= maxHour
        );
        newSlots.length = 0;
        newSlots.push(...filtered);
        
        // Merge with existing slots on this day
        const daySlots = blockedSlots.filter(([slotDay]) => slotDay === d);
        let mergedStart = minHour;
        let mergedEnd = maxHour;
        
        for (const [, slotStart, slotEnd] of daySlots) {
          if (slotStart <= maxHour && slotEnd >= minHour) {
            mergedStart = Math.min(mergedStart, slotStart);
            mergedEnd = Math.max(mergedEnd, slotEnd);
          }
        }
        
        newSlots.push([d, mergedStart, mergedEnd]);
      }
      onChange(newSlots);
    } else {
      // Remove slots in the dragged range
      const newSlots: number[][] = [];
      for (const [d, slotStart, slotEnd] of blockedSlots) {
        if (d < minDay || d > maxDay) {
          newSlots.push([d, slotStart, slotEnd]);
          continue;
        }
        // This slot is on a day we're modifying
        if (slotEnd <= minHour || slotStart >= maxHour) {
          // No overlap
          newSlots.push([d, slotStart, slotEnd]);
        } else {
          // Split the slot around the removed region
          if (slotStart < minHour) {
            newSlots.push([d, slotStart, minHour]);
          }
          if (slotEnd > maxHour) {
            newSlots.push([d, maxHour, slotEnd]);
          }
        }
      }
      onChange(newSlots);
    }

    setIsDragging(false);
    setDragStart(null);
    setDragCurrent(null);
  };

  useEffect(() => {
    const handleGlobalMouseUp = () => {
      if (isDragging) {
        handleMouseUp();
      }
    };
    window.addEventListener("mouseup", handleGlobalMouseUp);
    return () => window.removeEventListener("mouseup", handleGlobalMouseUp);
  }, [isDragging, dragStart, dragCurrent, dragMode, blockedSlots]);

  const dragSelection = getDragSelection();

  return (
    <div 
      className="select-none rounded overflow-hidden bg-gray-800"
      onMouseLeave={() => {
        if (isDragging) {
          handleMouseUp();
        }
      }}
    >
      {/* Header row */}
      <div className="flex gap-px bg-gray-700">
        <div style={{ width: 24 }} />
        {DAYS.map((day) => (
          <div
            key={day}
            className="flex-1 text-[10px] text-gray-400 text-center font-medium py-0.5"
            style={{ minWidth: 24 }}
          >
            {day}
          </div>
        ))}
      </div>

      {/* Grid body */}
      <div className="flex gap-px bg-gray-700">
        {/* Time labels */}
        <div className="flex flex-col text-[9px] text-gray-500" style={{ width: 24 }}>
          {Array.from({ length: HOURS }, (_, i) => {
            const hour = START_HOUR + i;
            const displayHour = hour % 12 || 12;
            const ampm = hour < 12 ? "a" : "p";
            return (
              <div
                key={i}
                className="flex items-center justify-end pr-1"
                style={{ height: 12 }}
              >
                {displayHour}{ampm}
              </div>
            );
          })}
        </div>

        {/* Day columns */}
        {DAYS.map((_, dayIndex) => (
          <div key={dayIndex} className="flex-1 flex flex-col" style={{ minWidth: 24 }}>
            {Array.from({ length: HOURS }, (_, hourIndex) => {
              const hour = START_HOUR + hourIndex;
              const isBlocked = isHourBlocked(dayIndex, hour);
              const isInDragSelection = dragSelection.has(`${dayIndex}-${hour}`);
              const willBeBlocked = isDragging
                ? dragMode === "add"
                  ? isInDragSelection || isBlocked
                  : isBlocked && !isInDragSelection
                : isBlocked;

              return (
                <div
                  key={hourIndex}
                  className={`
                    cursor-pointer transition-colors
                    ${willBeBlocked ? "bg-red-500/60" : "bg-gray-800 hover:bg-gray-700"}
                    ${isInDragSelection && isDragging ? (dragMode === "add" ? "ring-1 ring-red-400" : "ring-1 ring-gray-400") : ""}
                  `}
                  style={{ height: 12 }}
                  onMouseDown={() => handleMouseDown(dayIndex, hour)}
                  onMouseEnter={() => handleMouseEnter(dayIndex, hour)}
                />
              );
            })}
          </div>
        ))}
      </div>

      {/* Instructions */}
      <div className="text-[9px] text-gray-500 text-center py-1 bg-gray-800/50">
        Click and drag to block/unblock time
      </div>
    </div>
  );
}
