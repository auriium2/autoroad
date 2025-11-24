"use client";

import * as React from "react";
import { Skeleton } from "@/components/ui/skeleton";
import type { SearchableItem, ObjectiveMetadata } from "@/types/models/optimizer";

interface ParameterSearchDropdownProps {
  searchResults?: {
    objectives: SearchableItem[];
    constraints: SearchableItem[];
    concentrations: SearchableItem[];
    degrees: SearchableItem[];
    totalCounts: {
      objectives: number;
      constraints: number;
      concentrations: number;
      degrees: number;
    };
  };
  isLoading: boolean;
  searchTerm: string;
  onSelectObjective: (objective: ObjectiveMetadata) => void;
  onSelectConstraint: (key: string) => void;
  onSelectRequirement: (key: string) => void;
}

export function ParameterSearchDropdown({
  searchResults,
  isLoading,
  searchTerm,
  onSelectObjective,
  onSelectConstraint,
  onSelectRequirement,
}: ParameterSearchDropdownProps) {
  if (isLoading) {
    return (
      <div className="absolute z-20 w-full mt-1 bg-gray-900 border border-gray-700 rounded shadow-xl max-h-80 overflow-y-auto backdrop-blur-sm">
        <div className="p-3 space-y-2">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="space-y-1">
              <Skeleton className="h-4 w-32 bg-muted" />
              <Skeleton className="h-3 w-full bg-muted/50" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (!searchResults) return null;

  const hasNoResults =
    searchResults.objectives.length === 0 &&
    searchResults.constraints.length === 0 &&
    searchResults.concentrations.length === 0 &&
    searchResults.degrees.length === 0;

  return (
    <div className="absolute z-20 w-full mt-1 bg-gray-900 border border-gray-700 rounded shadow-xl max-h-80 overflow-y-auto backdrop-blur-sm">
      {searchResults.objectives.length > 0 && (
        <div>
          <div className="sticky top-0 bg-gray-900/95 backdrop-blur-sm px-3 py-1.5 text-[10px] font-semibold text-purple-400 uppercase tracking-wider border-b border-gray-700/50">
            Objectives ({searchResults.totalCounts.objectives})
          </div>
          {searchResults.objectives.map((item) => (
            <button
              key={`search-${item.type}-${item.key}`}
              onClick={() => {
                if (item.metadata && 'key' in item.metadata) {
                  onSelectObjective(item.metadata as ObjectiveMetadata);
                }
              }}
              className="w-full px-3 py-2.5 text-left text-sm hover:bg-gray-800 transition-colors border-b border-gray-800/50 last:border-b-0"
            >
              <div className="font-medium">{item.displayName}</div>
              {item.metadata && 'description' in item.metadata && item.metadata.description && (
                <div className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
                  {item.metadata.description}
                </div>
              )}
            </button>
          ))}
        </div>
      )}

      {searchResults.constraints.length > 0 && (
        <div>
          <div className="sticky top-0 bg-gray-900/95 backdrop-blur-sm px-3 py-1.5 text-[10px] font-semibold text-orange-400 uppercase tracking-wider border-b border-gray-700/50">
            Hard Constraints ({searchResults.totalCounts.constraints})
          </div>
          {searchResults.constraints.map((item) => (
            <button
              key={`search-${item.type}-${item.key}`}
              onClick={() => onSelectConstraint(item.key)}
              className="w-full px-3 py-2.5 text-left text-sm hover:bg-gray-800 transition-colors border-b border-gray-800/50 last:border-b-0"
            >
              <div className="font-medium">{item.displayName}</div>
              {item.metadata && 'description' in item.metadata && item.metadata.description && (
                <div className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
                  {item.metadata.description}
                </div>
              )}
            </button>
          ))}
        </div>
      )}

      {searchResults.concentrations.length > 0 && (
        <div>
          <div className="sticky top-0 bg-gray-900/95 backdrop-blur-sm px-3 py-1.5 text-[10px] font-semibold text-cyan-400 uppercase tracking-wider border-b border-gray-700/50">
            Concentrations ({searchResults.totalCounts.concentrations})
          </div>
          {searchResults.concentrations.map((item) => (
            <button
              key={`search-${item.type}-${item.key}`}
              onClick={() => onSelectRequirement(item.key)}
              className="w-full px-3 py-2.5 text-left text-sm hover:bg-gray-800 transition-colors border-b border-gray-800/50 last:border-b-0"
            >
              <div className="flex items-center gap-2">
                <span className="font-medium">{item.displayName}</span>
                <span className="px-1.5 py-0.5 text-[9px] font-medium bg-cyan-500/10 text-cyan-400/60 rounded">BETA</span>
              </div>
              {item.metadata && 'title_no_degree' in item.metadata && (item.metadata.title_no_degree || item.metadata.title) && (
                <div className="text-xs text-muted-foreground mt-0.5">
                  {item.metadata.title_no_degree || item.metadata.title}
                </div>
              )}
            </button>
          ))}
        </div>
      )}

      {searchResults.degrees.length > 0 && (
        <div>
          <div className="sticky top-0 bg-gray-900/95 backdrop-blur-sm px-3 py-1.5 text-[10px] font-semibold text-blue-400 uppercase tracking-wider border-b border-gray-700/50">
            Degrees ({searchResults.totalCounts.degrees})
          </div>
          {searchResults.degrees.map((item) => (
            <button
              key={`search-${item.type}-${item.key}`}
              onClick={() => onSelectRequirement(item.key)}
              className="w-full px-3 py-2.5 text-left text-sm hover:bg-gray-800 transition-colors border-b border-gray-800/50 last:border-b-0"
            >
              <div className="font-medium">{item.displayName}</div>
              {item.metadata && 'title_no_degree' in item.metadata && (item.metadata.title_no_degree || item.metadata.title) && (
                <div className="text-xs text-muted-foreground mt-0.5">
                  {item.metadata.title_no_degree || item.metadata.title}
                </div>
              )}
            </button>
          ))}
        </div>
      )}

      {hasNoResults && (
        <div className="px-3 py-6 text-sm text-muted-foreground text-center">
          No results found for &quot;{searchTerm}&quot;
        </div>
      )}
    </div>
  );
}
