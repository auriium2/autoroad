"use client";

import React, { useState, useRef, useEffect } from "react";
import { ChevronDown, Check } from "lucide-react";
import { cn } from "@/lib/utils";

interface SimpleSelectOption {
  value: string;
  label: string;
}

interface SimpleSelectProps {
  options: SimpleSelectOption[];
  value?: string;
  placeholder?: string;
  onValueChange?: (value: string) => void;
  className?: string;
  disabled?: boolean;
}

export function SimpleSelect({
  options,
  value,
  placeholder = "Select an option",
  onValueChange,
  className,
  disabled = false,
}: SimpleSelectProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedValue, setSelectedValue] = useState(value || "");
  const containerRef = useRef<HTMLDivElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [isOpen]);

  // Close dropdown on escape key
  useEffect(() => {
    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsOpen(false);
      }
    }

    if (isOpen) {
      document.addEventListener("keydown", handleEscape);
      return () => document.removeEventListener("keydown", handleEscape);
    }
  }, [isOpen]);

  const handleSelect = (optionValue: string) => {
    setSelectedValue(optionValue);
    setIsOpen(false);
    onValueChange?.(optionValue);
  };

  const selectedOption = options.find(opt => opt.value === selectedValue);
  const displayValue = selectedOption?.label || placeholder;

  return (
    <div ref={containerRef} className={cn("relative", className)}>
      {/* Trigger */}
      <button
        type="button"
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled}
        className={cn(
          "flex w-full items-center justify-between gap-2 rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs transition-colors",
          "hover:bg-accent hover:text-accent-foreground",
          "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
          "disabled:cursor-not-allowed disabled:opacity-50",
          "h-9", // Same height as shadcn select
          isOpen && "ring-2 ring-ring ring-offset-2"
        )}
      >
        <span className={cn(
          "truncate",
          !selectedOption && "text-muted-foreground"
        )}>
          {displayValue}
        </span>
        <ChevronDown className={cn(
          "h-4 w-4 shrink-0 opacity-50 transition-transform",
          isOpen && "rotate-180"
        )} />
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div
          ref={dropdownRef}
          className={cn(
            "absolute top-full z-50 mt-1 w-full rounded-md border bg-popover p-1 text-popover-foreground shadow-lg",
            "animate-in fade-in-0 zoom-in-95",
            "min-w-[8rem] overflow-hidden"
          )}
        >
          <div className="max-h-60 overflow-y-auto">
            {options.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => handleSelect(option.value)}
                className={cn(
                  "relative flex w-full cursor-pointer items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors",
                  "hover:bg-accent hover:text-accent-foreground",
                  "focus:bg-accent focus:text-accent-foreground",
                  selectedValue === option.value && "bg-accent text-accent-foreground"
                )}
              >
                <span className="truncate">{option.label}</span>
                {selectedValue === option.value && (
                  <Check className="ml-auto h-4 w-4 shrink-0" />
                )}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}