"use client";

import * as React from "react";
import { Plus } from "lucide-react";

interface ColumnContextMenuProps {
  x: number;
  y: number;
  sectionId: number;
  sectionTitle: string;
  onAddNode: () => void;
  onClose: () => void;
}

export function ColumnContextMenu({
  x,
  y,
  sectionId,
  sectionTitle,
  onAddNode,
  onClose,
}: ColumnContextMenuProps) {
  const menuRef = React.useRef<HTMLDivElement>(null);

  // Close on click outside
  React.useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        onClose();
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [onClose]);

  // Close on escape key
  React.useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [onClose]);

  return (
    <div
      ref={menuRef}
      className="fixed z-50 min-w-[200px] glass-card rounded-lg shadow-lg py-1"
      style={{
        left: `${x}px`,
        top: `${y}px`,
      }}
    >
      <div className="px-3 py-2 text-xs font-semibold text-muted-foreground border-b border-border/50">
        {sectionTitle}
      </div>
      <button
        className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-accent/50 transition-colors cursor-pointer"
        onClick={() => {
          onAddNode();
          onClose();
        }}
      >
        <Plus className="h-4 w-4" />
        Add Course
      </button>
    </div>
  );
}
