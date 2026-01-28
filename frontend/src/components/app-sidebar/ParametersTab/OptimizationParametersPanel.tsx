
import * as React from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { optimizerApi } from "@/services/optimizer";
import { fireroadApi, type RequirementNode } from "@/services/fireroad";
import { parametersApi } from "@/services/parameters";
import { queryKeys } from "@/lib/queryKeys";
import { Search } from "lucide-react";
import { useOptimizationStore } from "@/stores/optimizationStore";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { ParameterSearchDropdown } from "./ParameterSearchDropdown";
import { SelectedRequirementCard } from "./SelectedRequirementCard";
import { SelectedObjectiveCard } from "./SelectedObjectiveCard";
import { SelectedConstraintCard } from "./SelectedConstraintCard";
import { useRequirementProgressBatch } from "@/hooks/useRequirementProgress";
import { prefetchCourses } from "@/lib/cache";

interface OptimizationParametersPanelProps {
  viewMode?: string;
}

export function OptimizationParametersPanel({ viewMode }: OptimizationParametersPanelProps) {
  const [inputValue, setInputValue] = React.useState("");
  const [debouncedSearch, setDebouncedSearch] = React.useState("");
  const [showSearchResults, setShowSearchResults] = React.useState(false);
  const [expandedObjectives, setExpandedObjectives] = React.useState<Set<string>>(new Set());

  React.useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(inputValue);
    }, 500);
    return () => clearTimeout(timer);
  }, [inputValue]);

  const selectedRequirements = useOptimizationStore((state) => state.selectedRequirements);
  const addRequirement = useOptimizationStore((state) => state.addRequirement);
  const selectedObjectives = useOptimizationStore((state) => state.selectedObjectives);
  const setObjectives = useOptimizationStore((state) => state.setObjectives);
  const objectiveTiers = useOptimizationStore((state) => state.objectiveTiers);
  const setObjectiveTier = useOptimizationStore((state) => state.setObjectiveTier);
  const selectedHardConstraints = useOptimizationStore((state) => state.selectedHardConstraints);
  const toggleHardConstraint = useOptimizationStore((state) => state.toggleHardConstraint);

  const { data: requirementsList, isLoading: requirementsLoading } = useQuery({
    queryKey: queryKeys.requirements.list(),
    queryFn: () => fireroadApi.getRequirementsList(),
    staleTime: import.meta.env.DEV ? 60 * 1000 : 24 * 60 * 60 * 1000, // 1 min dev, 24h prod
  });

  const { data: objectivesData, isLoading: objectivesLoading } = useQuery({
    queryKey: queryKeys.objectives.list(),
    queryFn: () => optimizerApi.getObjectives(),
    staleTime: import.meta.env.DEV ? 60 * 1000 : 24 * 60 * 60 * 1000,
  });

  const { data: constraintsData } = useQuery({
    queryKey: queryKeys.constraints.hard(),
    queryFn: () => optimizerApi.getHardConstraints(),
    staleTime: import.meta.env.DEV ? 60 * 1000 : 24 * 60 * 60 * 1000,
  });

  const { data: searchResults, isLoading: searchLoading } = useQuery({
    queryKey: ['parameters', 'search', debouncedSearch, selectedRequirements, selectedObjectives.map(o => o.key), selectedHardConstraints.map(c => c.key)],
    queryFn: () => parametersApi.search({
      query: debouncedSearch || undefined,
      limit: 30,
      excludeRequirements: selectedRequirements,
      excludeObjectives: selectedObjectives.map(o => o.key),
      excludeConstraints: selectedHardConstraints.map(c => c.key),
    }),
    enabled: showSearchResults,
    staleTime: 5000,
  });

  const { data: requirementProgressMap, isLoading: progressLoading } = useRequirementProgressBatch(selectedRequirements);

  const queryClient = useQueryClient();
  const allRequirementCourseIds: string[] = [];
  const traverse = (node: RequirementNode) => {
    if (node.req) allRequirementCourseIds.push(node.req);
    if (node.reqs) node.reqs.forEach(traverse);
  };
  Object.values(requirementProgressMap).forEach(tree => {
    traverse(tree as RequirementNode);
  });
  const uniqueCourseIds = [...new Set(allRequirementCourseIds)];


  const [prefetchedCourseIds, setPrefetchedCourseIds] = React.useState<Set<string>>(new Set());
  React.useEffect(() => {
    const newCourseIds = uniqueCourseIds.filter(id => !prefetchedCourseIds.has(id));
    if (newCourseIds.length > 0) {
      prefetchCourses(queryClient, newCourseIds).then(() => {
        setPrefetchedCourseIds(prev => new Set([...prev, ...newCourseIds]));
      });
    }
  }, [uniqueCourseIds.join(','), queryClient]);

  const validCourseIds = new Set(
    uniqueCourseIds.filter(id => {
      if (id.startsWith('GIR:') || id.startsWith('HASS-') || id.startsWith('CI-')) return true;
      return queryClient.getQueryData(queryKeys.courses.details(id)) !== undefined;
    })
  );
  
  React.useEffect(() => {
    if (requirementsList && selectedRequirements.length === 0) {
      addRequirement('girs');
    }
  }, [requirementsList, selectedRequirements.length, addRequirement]);

  React.useEffect(() => {
    if (objectivesData && selectedObjectives.length === 0) {
      setObjectives(objectivesData.defaultConfiguration);
      objectivesData.defaultConfiguration.forEach(config => {
        const metadata = objectivesData.objectives.find(o => o.key === config.key);
        if (metadata && objectiveTiers[config.key] === undefined) {
          setObjectiveTier(config.key, metadata.defaultTier);
        }
      });
    }
  }, [objectivesData, selectedObjectives.length, setObjectives, objectiveTiers, setObjectiveTier]);

  const isRecommended = (key: string) => {
    return objectivesData?.defaultConfiguration.some(d => d.key === key) ?? false;
  };

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

  const allSelectedItems = [
    ...selectedRequirements.map(key => ({ type: 'degree' as const, key })),
    ...selectedObjectives
      .filter(o => o.key !== 'category_rewards')
      .map(o => ({ type: 'objective' as const, key: o.key })),
    ...selectedHardConstraints.map(c => ({ type: 'constraint' as const, key: c.key })),
    ...selectedObjectives
      .filter(o => o.key === 'category_rewards')
      .map(o => ({ type: 'objective' as const, key: o.key })),
  ];

  return (
    <div className="space-y-4">
      <div className="relative" data-tutorial="parameter-search">
        <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
        <Input
          type="text"
          placeholder="Search for degrees or constraints..."
          value={inputValue}
          onChange={(e) => {
            setInputValue(e.target.value);
            setShowSearchResults(true);
          }}
          onFocus={() => setShowSearchResults(true)}
          onBlur={() => setTimeout(() => setShowSearchResults(false), 200)}
          className="pl-8"
        />

        {showSearchResults && (
          <ParameterSearchDropdown
            searchResults={searchResults}
            isLoading={searchLoading}
            searchTerm={debouncedSearch}
            onSelectObjective={(objective) => {
              const newObjectives = [
                ...selectedObjectives,
                { key: objective.key, parameters: { ...objective.defaultParameters } },
              ];
              setObjectives(newObjectives);
              setInputValue("");
              setShowSearchResults(false);
            }}
            onSelectConstraint={(constraint) => {
              toggleHardConstraint(constraint.key, constraint.defaultParameters);
              setInputValue("");
              setShowSearchResults(false);
            }}
            onSelectRequirement={(key) => {
              if (!selectedRequirements.includes(key)) {
                addRequirement(key);
              }
              setInputValue("");
              setShowSearchResults(false);
            }}
          />
        )}
      </div>

      {allSelectedItems.length > 0 ? (
        <div className="space-y-2">
          {allSelectedItems.map(item => {
            if (item.type === 'degree') {
              return (
                <SelectedRequirementCard
                  key={`selected-${item.type}-${item.key}`}
                  requirementKey={item.key}
                  metadata={requirementsList?.[item.key]}
                  viewMode={viewMode}
                  requirementProgress={requirementProgressMap[item.key]}
                  isProgressLoading={progressLoading}
                  validCourseIds={validCourseIds}
                />
              );
            } else if (item.type === 'objective') {
              const objective = objectivesData?.objectives.find(o => o.key === item.key);
              if (!objective) return null;

              return (
                <SelectedObjectiveCard
                  key={`selected-${item.type}-${item.key}`}
                  objectiveKey={item.key}
                  objective={objective}
                  isRecommended={isRecommended(item.key)}
                  isExpanded={expandedObjectives.has(item.key)}
                  onToggleExpanded={() => toggleObjectiveExpanded(item.key)}
                  viewMode={viewMode}
                />
              );
            } else if (item.type === 'constraint') {
              const constraintMetadata = constraintsData?.constraints.find(c => c.key === item.key);
              const constraintConfig = selectedHardConstraints.find(c => c.key === item.key);
              if (!constraintMetadata || !constraintConfig) return null;

              return (
                <SelectedConstraintCard
                  key={`selected-${item.type}-${item.key}`}
                  metadata={constraintMetadata}
                  config={constraintConfig}
                />
              );
            }
            return null;
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
