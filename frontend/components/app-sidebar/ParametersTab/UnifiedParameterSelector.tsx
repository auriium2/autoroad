"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { optimizerApi, type ObjectiveMetadata, type ObjectiveConfig, type HardConstraintMetadata } from "@/services/optimizer";
import { X, ChevronDown, ChevronRight } from "lucide-react";
import { useOptimizationStore } from "@/stores/optimizationStore";
import { useGraphStore } from "@/stores/roadStore";
import { RequirementTreeView } from "./RequirementTreeView";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { TierSelector } from "./TierSelector";
import { Checkbox } from "@/components/ui/checkbox";

type ItemType = 'degree' | 'objective' | 'constraint';

interface RequirementMetadata {
  title_no_degree?: string;
  title?: string;
  short?: string;
  medium?: string;
}

interface SearchableItem {
  type: ItemType;
  key: string;
  displayName: string;
  searchableText: string;
  metadata?: RequirementMetadata | ObjectiveMetadata | HardConstraintMetadata;
}

interface UnifiedParameterSelectorProps {
  viewMode?: string;
}

export function UnifiedParameterSelector({ viewMode }: UnifiedParameterSelectorProps) {
  const [inputValue, setInputValue] = React.useState("");
  const [searchTerm, setSearchTerm] = React.useState("");
  const [showSearchResults, setShowSearchResults] = React.useState(false);
  const [expandedObjectives, setExpandedObjectives] = React.useState<Set<string>>(new Set());

  React.useEffect(() => { //debounce
    const timer = setTimeout(() => {
      setSearchTerm(inputValue);
    }, 100);
    return () => clearTimeout(timer);
  }, [inputValue]);

  const selectedRequirements = useOptimizationStore((state) => state.selectedRequirements);
  const addRequirement = useOptimizationStore((state) => state.addRequirement);
  const removeRequirement = useOptimizationStore((state) => state.removeRequirement);
  const expandedRequirements = useOptimizationStore((state) => state.expandedRequirements);
  const toggleRequirementExpanded = useOptimizationStore((state) => state.toggleRequirementExpanded);

  const selectedObjectives = useOptimizationStore((state) => state.selectedObjectives);
  const setObjectives = useOptimizationStore((state) => state.setObjectives);
  const objectiveTiers = useOptimizationStore((state) => state.objectiveTiers);
  const setObjectiveTier = useOptimizationStore((state) => state.setObjectiveTier);
  const selectedHardConstraints = useOptimizationStore((state) => state.selectedHardConstraints);
  const toggleHardConstraint = useOptimizationStore((state) => state.toggleHardConstraint);

  const lastCostBreakdown = useGraphStore((state) => state.lastCostBreakdown);

  const toggleObjectiveExpanded = (key: string) => {
    setExpandedObjectives(prev => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const { data: requirementsList, isLoading: requirementsLoading, error: requirementsError } = useQuery({
    queryKey: ['requirements-list'],
    queryFn: () => optimizerApi.getRequirementsList(),
    staleTime: 60 * 60 * 1000,
  });

  const { data: objectivesData, isLoading: objectivesLoading, error: objectivesError } = useQuery({
    queryKey: ['objectives'],
    queryFn: () => optimizerApi.getObjectives(),
    staleTime: 60 * 60 * 1000,
  });

  const { data: constraintsData, isLoading: constraintsLoading, error: constraintsError } = useQuery({
    queryKey: ['hard-constraints'],
    queryFn: () => optimizerApi.getHardConstraints(),
    staleTime: 60 * 60 * 1000,
  });

  // Initialize with GIRs by default
  React.useEffect(() => {
    if (requirementsList && selectedRequirements.length === 0) {
      addRequirement('girs');
    }
  }, [requirementsList, selectedRequirements.length, addRequirement]);

  // Initialize with default objectives if none selected
  React.useEffect(() => {
    if (objectivesData && selectedObjectives.length === 0) {
      setObjectives(objectivesData.defaultConfiguration);

      // Also initialize default tiers for these objectives
      objectivesData.defaultConfiguration.forEach(config => {
        const metadata = objectivesData.objectives.find(o => o.key === config.key);
        if (metadata && objectiveTiers[config.key] === undefined) {
          setObjectiveTier(config.key, metadata.defaultTier);
        }
      });
    }
  }, [objectivesData, selectedObjectives.length, setObjectives, objectiveTiers, setObjectiveTier]);

  const handleAddRequirement = (key: string) => {
    if (!selectedRequirements.includes(key)) {
      addRequirement(key);
    }
    setInputValue("");
    setShowSearchResults(false);
  };

  const handleRemoveRequirement = (key: string) => {
    removeRequirement(key);
  };

  const toggleExpanded = (key: string) => {
    toggleRequirementExpanded(key);
  };

  const handleToggleObjective = (objective: ObjectiveMetadata) => {
    const existing = selectedObjectives.find(o => o.key === objective.key);

    if (existing) {
      const newObjectives = selectedObjectives.filter(o => o.key !== objective.key);
      setObjectives(newObjectives);
    } else {
      const newObjectives = [
        ...selectedObjectives,
        {
          key: objective.key,
          parameters: { ...objective.defaultParameters },
        },
      ];
      setObjectives(newObjectives);
    }
    setInputValue("");
    setShowSearchResults(false);
  };

  const handleToggleConstraint = (key: string) => {
    toggleHardConstraint(key);
    setInputValue("");
    setShowSearchResults(false);
  };

  const handleParameterChange = (key: string, paramName: string, value: number) => {
    const newObjectives = selectedObjectives.map(obj =>
      obj.key === key
        ? { ...obj, parameters: { ...obj.parameters, [paramName]: value } }
        : obj
    );
    setObjectives(newObjectives);
  };

  // Build unified searchable items list - objectives first, then degrees, then hard constraints
  const objectives: SearchableItem[] = [];
  const degrees: SearchableItem[] = [];
  const constraints: SearchableItem[] = [];

  // Add hard constraints from API (only show in search if not enabled)
  if (constraintsData) {
    constraintsData.constraints.forEach(constraint => {
      const isEnabled = selectedHardConstraints.includes(constraint.key);

      // Only add to searchable list if not enabled
      if (!isEnabled) {
        const searchableText = [
          constraint.key,
          constraint.name,
          constraint.description,
          constraint.category,
        ].join(' ').toLowerCase();

        constraints.push({
          type: 'constraint',
          key: constraint.key,
          displayName: constraint.name,
          searchableText,
          metadata: constraint,
        });
      }
    });
  }

  // Add objectives (constraints)
  if (objectivesData) {
    objectivesData.objectives.forEach(objective => {
      if (!selectedObjectives.some(o => o.key === objective.key)) {
        const searchableText = [
          objective.key,
          objective.name,
          objective.description,
          objective.category,
        ].join(' ').toLowerCase();

        objectives.push({
          type: 'objective',
          key: objective.key,
          displayName: objective.name,
          searchableText,
          metadata: objective,
        });
      }
    });
  }

  // Add requirements (degrees)
  if (requirementsList) {
    Object.entries(requirementsList).forEach(([key, metadata]) => {
      if (!selectedRequirements.includes(key)) {
        const displayName = metadata.short || metadata.medium || key;
        const searchableText = [
          key,
          metadata.title,
          metadata.title_no_degree,
          metadata.medium,
          metadata.short,
        ].filter(Boolean).join(' ').toLowerCase();

        degrees.push({
          type: 'degree',
          key,
          displayName,
          searchableText,
          metadata,
        });
      }
    });
  }

  // Return objectives first, then degrees, then constraints
  const searchableItems = [...objectives, ...degrees, ...constraints];

  // Filter items for search - show all when empty, otherwise filter
  let filtered: SearchableItem[];

  if (!searchTerm) {
    // Show all available items when no search term
    filtered = searchableItems;
  } else {
    const searchLower = searchTerm.toLowerCase();
    filtered = searchableItems.filter(item => item.searchableText.includes(searchLower));
  }

  const objectivesCount = filtered.filter(item => item.type === 'objective').length;
  const degreesCount = filtered.filter(item => item.type === 'degree').length;
  const constraintsCount = filtered.filter(item => item.type === 'constraint').length;

  const displayLimit = searchTerm ? 20 : 30;
  const results = filtered.slice(0, displayLimit);

  const searchResults = results;
  const hasMoreResults = filtered.length > displayLimit;
  const totalCounts = {
    objectives: objectivesCount,
    degrees: degreesCount,
    constraints: constraintsCount,
  };

  const isRecommended = (key: string) => {
    return objectivesData?.defaultConfiguration.some(d => d.key === key) ?? false;
  };

  // Build unified list of all selected items (degrees first, then objectives, then constraints)
  const selectedDegrees: Array<{ type: 'degree' | 'objective' | 'constraint'; key: string }> = [];
  const selectedObjectiveItems: Array<{ type: 'degree' | 'objective' | 'constraint'; key: string }> = [];
  const selectedConstraintItems: Array<{ type: 'degree' | 'objective' | 'constraint'; key: string }> = [];

  selectedRequirements.forEach(reqKey => {
    selectedDegrees.push({ type: 'degree', key: reqKey });
  });

  selectedObjectives.forEach(config => {
    const objective = objectivesData?.objectives.find(o => o.key === config.key);
    if (objective) {
      selectedObjectiveItems.push({ type: 'objective', key: config.key });
    }
  });

  // Add enabled hard constraints to selected items
  if (constraintsData) {
    constraintsData.constraints.forEach(constraint => {
      const isEnabled = selectedHardConstraints.includes(constraint.key);
      if (isEnabled) {
        selectedConstraintItems.push({ type: 'constraint', key: constraint.key });
      }
    });
  }

  const allSelectedItems = [...selectedDegrees, ...selectedObjectiveItems, ...selectedConstraintItems];

  if (requirementsLoading || objectivesLoading) {
    return (
      <div className="space-y-2">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="border border-border rounded p-3">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-1.5 flex-1">
                <Skeleton className="h-4 w-4 shrink-0 bg-muted" />
                <Skeleton className="h-4 w-40 bg-muted" />
              </div>
              <Skeleton className="h-4 w-4 rounded-full shrink-0 bg-muted" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Unified Search Bar */}
      <div className="relative">
        <input
          type="text"
          placeholder="Search for degrees or constraints..."
          value={inputValue}
          onChange={(e) => {
            setInputValue(e.target.value);
            setShowSearchResults(true);
          }}
          onFocus={() => setShowSearchResults(true)}
          onBlur={() => setTimeout(() => setShowSearchResults(false), 200)}
          className="w-full px-3 py-2 text-sm bg-gray-800 border border-gray-700 rounded focus:outline-none focus:ring-2 focus:ring-primary"
        />

        {/* Search Results Dropdown */}
        {showSearchResults && (searchResults.length > 0 || inputValue.length > 0) && (
          <div className="absolute z-20 w-full mt-1 bg-gray-900 border border-gray-700 rounded shadow-xl max-h-80 overflow-y-auto backdrop-blur-sm">
            {/* Group results by type - objectives first, then degrees, then constraints */}
            {(() => {
              const degrees = searchResults.filter(item => item.type === 'degree');
              const objectives = searchResults.filter(item => item.type === 'objective');
              const constraints = searchResults.filter(item => item.type === 'constraint');

              return (
                <>
                  {objectives.length > 0 && (
                    <div>
                      <div className="sticky top-0 bg-gray-900/95 backdrop-blur-sm px-3 py-1.5 text-[10px] font-semibold text-purple-400 uppercase tracking-wider border-b border-gray-700/50">
                        Objectives ({totalCounts.objectives})
                      </div>
                      {objectives.map((item) => (
                        <button
                          key={`search-${item.type}-${item.key}`}
                          onClick={() => {
                            if (item.metadata && 'key' in item.metadata) {
                              handleToggleObjective(item.metadata as ObjectiveMetadata);
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

                  {degrees.length > 0 && (
                    <div>
                      <div className="sticky top-0 bg-gray-900/95 backdrop-blur-sm px-3 py-1.5 text-[10px] font-semibold text-blue-400 uppercase tracking-wider border-b border-gray-700/50">
                        Degrees ({totalCounts.degrees})
                      </div>
                      {degrees.map((item) => (
                        <button
                          key={`search-${item.type}-${item.key}`}
                          onClick={() => handleAddRequirement(item.key)}
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

                  {constraints.length > 0 && (
                    <div>
                      <div className="sticky top-0 bg-gray-900/95 backdrop-blur-sm px-3 py-1.5 text-[10px] font-semibold text-orange-400 uppercase tracking-wider border-b border-gray-700/50">
                        Hard Constraints
                      </div>
                      {constraints.map((item) => (
                        <button
                          key={`search-${item.type}-${item.key}`}
                          onClick={() => handleToggleConstraint(item.key)}
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

                  {searchResults.length === 0 && (
                    <div className="px-3 py-6 text-sm text-muted-foreground text-center">
                      No results found for &quot;{searchTerm}&quot;
                    </div>
                  )}

                  {hasMoreResults && (
                    <div className="sticky bottom-0 bg-gray-900/95 backdrop-blur-sm px-3 py-2 text-xs text-muted-foreground text-center border-t border-gray-700/50">
                      Type to search for more results...
                    </div>
                  )}
                </>
              );
            })()}
          </div>
        )}
      </div>

      {/* Unified list of all selected items */}
      {allSelectedItems.length > 0 ? (
        <div className="space-y-2">
          {allSelectedItems.map(item => {
            if (item.type === 'degree') {
              const metadata = requirementsList?.[item.key];
              const displayName = metadata?.title_no_degree || metadata?.medium || metadata?.title || item.key;
              const isExpanded = expandedRequirements.includes(item.key);

              return (
                <div key={`selected-${item.type}-${item.key}`} className="relative border border-border rounded overflow-hidden">
                  {/* Blue gradient overlay for degrees - bottom-left stays black, top-right becomes blue */}
                  <div className="absolute inset-0 pointer-events-none bg-gradient-to-tr from-transparent to-blue-500/15" />

                  <div className="relative z-10 p-3 space-y-2">
                  <div className="flex items-start justify-between gap-2">
                    <button
                      onClick={() => toggleExpanded(item.key)}
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
                      onClick={() => handleRemoveRequirement(item.key)}
                      className="text-muted-foreground hover:text-red-400 transition-colors"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>

                  {isExpanded && (
                    <div className="pt-2">
                      <RequirementTreeView requirementKey={item.key} />
                    </div>
                  )}
                  </div>
                </div>
              );
            } else if (item.type === 'objective') {
              // Objective card
              const config = selectedObjectives.find(o => o.key === item.key);
              const objective = objectivesData?.objectives.find(o => o.key === item.key);
              if (!objective || !config) return null;

              const isRecommendedType = isRecommended(objective.key);
              const isExpanded = expandedObjectives.has(item.key);

              // Get tier from state, or use the backend's default tier for this objective
              const objectiveTier = objectiveTiers[item.key] ?? objective.defaultTier;

              return (
                <div key={`selected-${item.type}-${item.key}`} className="relative border border-border rounded overflow-hidden">
                  {/* Red gradient overlay for recommended objectives - bottom-left stays black, top-right becomes red */}
                  {isRecommendedType && (
                    <div className="absolute inset-0 pointer-events-none bg-gradient-to-tr from-transparent to-red-500/15" />
                  )}

                  <div className="relative z-10 p-3 space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <button
                        onClick={() => toggleObjectiveExpanded(item.key)}
                        className="flex items-center gap-1 flex-1 text-left"
                      >
                        {isExpanded ? (
                          <ChevronDown className="h-4 w-4 shrink-0" />
                        ) : (
                          <ChevronRight className="h-4 w-4 shrink-0" />
                        )}
                        <span className="text-sm font-semibold">
                          {objective.name}
                        </span>
                      </button>
                      <div className="flex items-center gap-1.5">
                        {viewMode === "cost" && lastCostBreakdown && lastCostBreakdown[objective.key] !== undefined && (
                          <span className="text-xs font-mono tabular-nums text-orange-400 animate-pulse">
                            {lastCostBreakdown[objective.key]}
                          </span>
                        )}
                        <TierSelector
                          tier={objectiveTier}
                          onChange={(tier) => setObjectiveTier(item.key, tier)}
                          minTier={1}
                        />
                        <button
                          onClick={() => handleToggleObjective(objective)}
                          className="text-muted-foreground hover:text-red-400 transition-colors shrink-0"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                    {isExpanded && (
                      <>
                        <div className="space-y-1">
                          <p className="text-xs text-muted-foreground">
                            {objective.description}
                          </p>
                        </div>
                      {/* Parameters */}
                      {objective.hasParameters && (
                        <div className="space-y-2 pt-1">
                          {Object.entries(objective.defaultParameters).map(([paramName, defaultValue]) => (
                            <div key={paramName} className="flex items-center gap-2 min-w-0">
                              <Label className="text-xs text-muted-foreground capitalize shrink-0" style={{ width: '100px' }}>
                                {paramName.replace(/_/g, ' ')}:
                              </Label>
                              <input
                                type="number"
                                value={config.parameters[paramName] ?? defaultValue}
                                onChange={(e) => handleParameterChange(
                                  objective.key,
                                  paramName,
                                  typeof defaultValue === 'number' && !Number.isInteger(defaultValue)
                                    ? parseFloat(e.target.value)
                                    : parseInt(e.target.value)
                                )}
                                step={typeof defaultValue === 'number' && !Number.isInteger(defaultValue) ? 0.1 : 1}
                                className="w-14 px-2 py-1 text-xs bg-gray-800 border border-gray-700 rounded shrink-0 tabular-nums"
                              />
                            </div>
                          ))}
                        </div>
                      )}
                      </>
                    )}
                  </div>
                </div>
              );
            } else if (item.type === 'constraint') {
              // Hard constraint card
              const constraint = constraintsData?.constraints.find(c => c.key === item.key);
              if (!constraint) return null;

              // Determine if constraint is enabled
              return (
                <div key={`selected-${item.type}-${item.key}`} className="relative border border-border rounded overflow-hidden">
                  {/* Purple gradient overlay for hard constraints */}
                  <div className="absolute inset-0 pointer-events-none bg-gradient-to-tr from-transparent to-purple-500/15" />

                  <div className="relative z-10 p-3">
                    <div className="flex items-start gap-2">
                      <div className="flex-1">
                        <div className="flex items-center justify-between">
                          <Label className="text-sm font-semibold">
                            {constraint.name}
                          </Label>
                          <button
                            onClick={() => handleToggleConstraint(constraint.key)}
                            className="text-muted-foreground hover:text-red-400 transition-colors shrink-0"
                          >
                            <X className="h-4 w-4" />
                          </button>
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">
                          {constraint.description}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              );
            }
          })}

        </div>
      ) : (
        <p className="text-sm text-muted-foreground text-center py-8">
          No parameters selected. Search above to add degrees or objectives.
        </p>
      )}
    </div>
  );
}
