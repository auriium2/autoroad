"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { optimizerApi, type ObjectiveMetadata, type ObjectiveConfig } from "@/services/optimizer";
import { X, ChevronDown, ChevronRight } from "lucide-react";
import { useOptimizationStore } from "@/stores/optimizationStore";
import { RequirementTreeView } from "./RequirementTreeView";
import { Label } from "@/components/ui/label";

type ItemType = 'degree' | 'objective';

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
  metadata?: RequirementMetadata | ObjectiveMetadata;
}

export function UnifiedParameterSelector() {
  const [searchTerm, setSearchTerm] = React.useState("");
  const [showSearchResults, setShowSearchResults] = React.useState(false);
  const [expandedObjectives, setExpandedObjectives] = React.useState<Set<string>>(new Set());

  const selectedRequirements = useOptimizationStore((state) => state.selectedRequirements);
  const addRequirement = useOptimizationStore((state) => state.addRequirement);
  const removeRequirement = useOptimizationStore((state) => state.removeRequirement);
  const expandedRequirements = useOptimizationStore((state) => state.expandedRequirements);
  const toggleRequirementExpanded = useOptimizationStore((state) => state.toggleRequirementExpanded);

  const selectedObjectives = useOptimizationStore((state) => state.selectedObjectives);
  const setObjectives = useOptimizationStore((state) => state.setObjectives);

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

  const { data: requirementsList, isLoading: requirementsLoading } = useQuery({
    queryKey: ['requirements-list'],
    queryFn: () => optimizerApi.getRequirementsList(),
    staleTime: 60 * 60 * 1000,
  });

  const { data: objectivesData, isLoading: objectivesLoading } = useQuery({
    queryKey: ['objectives'],
    queryFn: () => optimizerApi.getObjectives(),
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
    }
  }, [objectivesData, selectedObjectives.length, setObjectives]);

  const handleAddRequirement = (key: string) => {
    if (!selectedRequirements.includes(key)) {
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

  const handleToggleObjective = (objective: ObjectiveMetadata) => {
    const existing = selectedObjectives.find(o => o.key === objective.key);

    if (existing) {
      const newObjectives = selectedObjectives.filter(o => o.key !== objective.key);
      setObjectives(normalizeWeights(newObjectives));
    } else {
      const newObjectives = [
        ...selectedObjectives,
        {
          key: objective.key,
          weight: 0.1,
          parameters: { ...objective.defaultParameters },
        },
      ];
      setObjectives(normalizeWeights(newObjectives));
    }
    setSearchTerm("");
    setShowSearchResults(false);
  };

  const handleWeightChange = (key: string, newWeight: number) => {
    const newObjectives = selectedObjectives.map(obj =>
      obj.key === key ? { ...obj, weight: newWeight } : obj
    );
    setObjectives(normalizeWeights(newObjectives));
  };

  const handleParameterChange = (key: string, paramName: string, value: number) => {
    const newObjectives = selectedObjectives.map(obj =>
      obj.key === key
        ? { ...obj, parameters: { ...obj.parameters, [paramName]: value } }
        : obj
    );
    setObjectives(newObjectives);
  };

  // Build unified searchable items list - objectives first, then degrees
  const searchableItems = React.useMemo((): SearchableItem[] => {
    const objectives: SearchableItem[] = [];
    const degrees: SearchableItem[] = [];

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

    // Return objectives first, then degrees
    return [...objectives, ...degrees];
  }, [requirementsList, objectivesData, selectedRequirements, selectedObjectives]);

  // Filter items for search - show all when empty, otherwise filter
  const { searchResults, hasMoreResults, totalCounts } = React.useMemo(() => {
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

    const displayLimit = searchTerm ? 20 : 30;
    const results = filtered.slice(0, displayLimit);

    return {
      searchResults: results,
      hasMoreResults: filtered.length > displayLimit,
      totalCounts: {
        objectives: objectivesCount,
        degrees: degreesCount,
      }
    };
  }, [searchableItems, searchTerm]);

  const isConstraint = (key: string) => {
    return key.includes('limit') ||
           key.includes('avoid') ||
           key.includes('minimize_max') ||
           key.includes('minimize_finals');
  };

  const isRecommended = (key: string) => {
    return objectivesData?.defaultConfiguration.some(d => d.key === key) ?? false;
  };

  // Build unified list of all selected items (degrees first, then objectives)
  const allSelectedItems = React.useMemo(() => {
    const degrees: Array<{ type: 'degree' | 'objective'; key: string }> = [];
    const objectives: Array<{ type: 'degree' | 'objective'; key: string }> = [];

    selectedRequirements.forEach(reqKey => {
      degrees.push({ type: 'degree', key: reqKey });
    });

    selectedObjectives.forEach(config => {
      const objective = objectivesData?.objectives.find(o => o.key === config.key);
      if (objective) {
        objectives.push({ type: 'objective', key: config.key });
      }
    });

    return [...degrees, ...objectives];
  }, [selectedRequirements, selectedObjectives, objectivesData]);

  if (requirementsLoading || objectivesLoading) {
    return <div className="p-4 text-sm text-muted-foreground">Loading...</div>;
  }

  return (
    <div className="space-y-4">
      {/* Unified Search Bar */}
      <div className="relative">
        <input
          type="text"
          placeholder="Search for degrees or constraints..."
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
          <div className="absolute z-20 w-full mt-1 bg-gray-900 border border-gray-700 rounded shadow-xl max-h-80 overflow-y-auto backdrop-blur-sm">
            {/* Group results by type - objectives first, then degrees */}
            {(() => {
              const degrees = searchResults.filter(item => item.type === 'degree');
              const objectives = searchResults.filter(item => item.type === 'objective');

              return (
                <>
                  {objectives.length > 0 && (
                    <div>
                      <div className="sticky top-0 bg-gray-900/95 backdrop-blur-sm px-3 py-1.5 text-[10px] font-semibold text-purple-400 uppercase tracking-wider border-b border-gray-700/50">
                        Objectives ({totalCounts.objectives})
                      </div>
                      {objectives.map((item) => (
                        <button
                          key={`${item.type}-${item.key}`}
                          onClick={() => handleToggleObjective(item.metadata)}
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
                          key={`${item.type}-${item.key}`}
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
                <div key={`${item.type}-${item.key}`} className="relative border border-border rounded overflow-hidden">
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
            } else {
              // Objective card
              const config = selectedObjectives.find(o => o.key === item.key);
              const objective = objectivesData?.objectives.find(o => o.key === item.key);
              if (!objective || !config) return null;

              const isConstraintType = isConstraint(objective.key);
              const isRecommendedType = isRecommended(objective.key);
              const isExpanded = expandedObjectives.has(item.key);

              return (
                <div key={`${item.type}-${item.key}`} className="border border-border rounded p-3">
                  <div className="space-y-2">
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
                      <button
                        onClick={() => handleToggleObjective(objective)}
                        className="text-muted-foreground hover:text-red-400 transition-colors shrink-0"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </div>
                    {isExpanded && (
                      <>
                        <div className="space-y-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            {isConstraintType && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-orange-500/20 text-orange-400 font-medium border border-orange-500/30 shrink-0">
                                CONSTRAINT
                              </span>
                            )}
                            {isRecommendedType && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-primary/20 text-primary font-medium shrink-0">
                                RECOMMENDED
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-muted-foreground">
                            {objective.description}
                          </p>
                        </div>
                      {/* Weight slider for non-constraints */}
                      {!isConstraintType && (
                        <div className="flex items-center gap-3 min-w-0">
                          <Label className="text-xs text-muted-foreground w-16 shrink-0">Weight:</Label>
                          <input
                            type="range"
                            min="0"
                            max="100"
                            step="1"
                            value={Math.round(config.weight * 100)}
                            onChange={(e) => handleWeightChange(objective.key, Number(e.target.value) / 100)}
                            className="flex-1 min-w-0 h-1.5 bg-gray-700 rounded-lg appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary [&::-webkit-slider-thumb]:cursor-pointer"
                          />
                          <span className="text-xs font-medium w-10 text-right shrink-0 tabular-nums">
                            {Math.round(config.weight * 100)}
                          </span>
                        </div>
                      )}

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

function normalizeWeights(objectives: ObjectiveConfig[]): ObjectiveConfig[] {
  if (objectives.length === 0) return objectives;

  const totalWeight = objectives.reduce((sum, obj) => sum + obj.weight, 0);

  if (totalWeight === 0) {
    return objectives.map(obj => ({ ...obj, weight: 1 / objectives.length }));
  }

  return objectives.map(obj => ({
    ...obj,
    weight: obj.weight / totalWeight,
  }));
}
