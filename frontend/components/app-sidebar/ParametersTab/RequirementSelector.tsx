"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { optimizerApi } from "@/services/optimizer";
import { X, ChevronDown, ChevronRight } from "lucide-react";
import { useOptimizationStore } from "@/stores/optimizationStore";
import { RequirementTreeView } from "./RequirementTreeView";

export function RequirementSelector() {
  const [searchTerm, setSearchTerm] = React.useState("");
  const [showSearchResults, setShowSearchResults] = React.useState(false);

  const selectedRequirements = useOptimizationStore((state) => state.selectedRequirements);
  const addRequirement = useOptimizationStore((state) => state.addRequirement);
  const removeRequirement = useOptimizationStore((state) => state.removeRequirement);
  const expandedRequirements = useOptimizationStore((state) => state.expandedRequirements);
  const toggleRequirementExpanded = useOptimizationStore((state) => state.toggleRequirementExpanded);

  const { data: requirementsList, isLoading } = useQuery({
    queryKey: ['requirements-list'],
    queryFn: () => optimizerApi.getRequirementsList(),
    staleTime: 60 * 60 * 1000,
  });

  // Initialize with GIRs by default
  React.useEffect(() => {
    if (requirementsList && selectedRequirements.length === 0) {
      addRequirement('girs');
    }
  }, [requirementsList, selectedRequirements.length, addRequirement]);

  const handleAddRequirement = (key: string) => {
    console.log('[RequirementSelector] Adding requirement:', key);
    console.log('[RequirementSelector] Current requirements:', selectedRequirements);
    if (!selectedRequirements.includes(key)) {
      console.log('[RequirementSelector] Calling addRequirement');
      addRequirement(key);
    }
    setSearchTerm("");
    setShowSearchResults(false);
  };

  const handleRemoveRequirement = (key: string) => {
    removeRequirement(key);
  };

  const toggleExpanded = (key: string) => {
    toggleRequirementExpanded(key);
  };

  // Filter requirements for search
  const searchResults = React.useMemo(() => {
    if (!requirementsList || !searchTerm) return [];
    
    const searchLower = searchTerm.toLowerCase();
    return Object.entries(requirementsList)
      .filter(([key, metadata]) => 
        !selectedRequirements.includes(key) &&
        (key.toLowerCase().includes(searchLower) ||
         metadata.title?.toLowerCase().includes(searchLower) ||
         metadata.title_no_degree?.toLowerCase().includes(searchLower) ||
         metadata.medium?.toLowerCase().includes(searchLower))
      )
      .slice(0, 10); // Limit to 10 results
  }, [requirementsList, searchTerm, selectedRequirements]);

  if (isLoading) {
    return <div className="p-4 text-sm text-muted-foreground">Loading requirements...</div>;
  }

  return (
    <div className="space-y-4">
      {/* Search Bar */}
      <div className="relative">
        <input
          type="text"
          placeholder="Search to add requirements..."
          value={searchTerm}
          onChange={(e) => {
            setSearchTerm(e.target.value);
            setShowSearchResults(true);
          }}
          onFocus={() => setShowSearchResults(true)}
          onBlur={() => setTimeout(() => setShowSearchResults(false), 200)}
          className="w-full px-3 py-2 text-sm bg-gray-800 border border-gray-700 rounded focus:outline-none focus:ring-2 focus:ring-primary"
        />
        
        {/* Search Results Dropdown */}
        {showSearchResults && searchResults.length > 0 && (
          <div className="absolute z-10 w-full mt-1 bg-gray-800 border border-gray-700 rounded shadow-lg max-h-64 overflow-y-auto">
            {searchResults.map(([key, metadata]) => (
              <button
                key={key}
                onClick={() => handleAddRequirement(key)}
                className="w-full px-3 py-2 text-left text-sm hover:bg-gray-700 transition-colors"
              >
                <div className="font-medium">{metadata.title_no_degree || metadata.medium || metadata.title || key}</div>
                {metadata.short && metadata.short !== (metadata.title_no_degree || metadata.medium) && (
                  <div className="text-xs text-muted-foreground">{metadata.short}</div>
                )}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Selected Requirements Tree */}
      <div className="space-y-2">
        {selectedRequirements.map(reqKey => {
          const metadata = requirementsList?.[reqKey];
          const displayName = metadata?.title_no_degree || metadata?.medium || metadata?.title || reqKey;
          const isExpanded = expandedRequirements.includes(reqKey);

          return (
            <div key={reqKey} className="border border-border rounded p-3 space-y-2">
              <div className="flex items-start justify-between gap-2">
                <button
                  onClick={() => toggleExpanded(reqKey)}
                  className="flex items-center gap-1 flex-1 text-left"
                >
                  {isExpanded ? (
                    <ChevronDown className="h-4 w-4 shrink-0" />
                  ) : (
                    <ChevronRight className="h-4 w-4 shrink-0" />
                  )}
                  <span className="text-sm font-semibold">{displayName}</span>
                </button>
                <button
                  onClick={() => handleRemoveRequirement(reqKey)}
                  className="text-muted-foreground hover:text-red-400 transition-colors"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              {isExpanded && (
                <div className="pt-2">
                  <RequirementTreeView requirementKey={reqKey} />
                </div>
              )}
            </div>
          );
        })}

        {selectedRequirements.length === 0 && (
          <p className="text-sm text-muted-foreground text-center py-8">
            No requirements selected. Search above to add.
          </p>
        )}
      </div>
    </div>
  );
}
