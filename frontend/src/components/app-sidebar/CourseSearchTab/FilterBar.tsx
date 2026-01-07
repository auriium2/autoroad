
import * as React from "react";
import { Filter, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";

interface FilterOption {
  id: string;
  label: string;
  category: string;
}

interface FilterBarProps {
  activeFilters: Set<string>;
  allFilters: FilterOption[];
  onAddFilter: (filterId: string) => void;
  onRemoveFilter: (filterId: string) => void;
}

export function FilterBar({ activeFilters, allFilters, onAddFilter, onRemoveFilter }: FilterBarProps) {
  const [filterQuery, setFilterQuery] = React.useState("");
  const [showDropdown, setShowDropdown] = React.useState(false);

  const filterSuggestions = React.useMemo(() => {
    const query = filterQuery.toLowerCase();
    return allFilters.filter(f => !activeFilters.has(f.id) && (
      !query ||
      f.label.toLowerCase().includes(query) ||
      f.category.toLowerCase().includes(query)
    ));
  }, [filterQuery, activeFilters, allFilters]);

  const handleAddFilter = (filterId: string) => {
    onAddFilter(filterId);
    setFilterQuery("");
  };

  return (
    <div className="relative">
      <Filter className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground pointer-events-none z-10" />
      <div className="flex h-10 w-full rounded-md border border-input bg-background overflow-hidden">
        <div className="overflow-x-auto scrollbar-thin flex-1">
          <div className="flex gap-1 items-center pl-8 pr-3 py-2 w-max min-w-full h-full">
            {Array.from(activeFilters).map((filterId) => {
              const filter = allFilters.find(f => f.id === filterId);
              return filter ? (
                <Badge key={filterId} variant="secondary" className="text-xs whitespace-nowrap shrink-0">
                  {filter.label}
                  <X className="h-3 w-3 ml-1 cursor-pointer" onClick={() => onRemoveFilter(filterId)} />
                </Badge>
              ) : null;
            })}
            <input
              type="text"
              placeholder={activeFilters.size === 0 ? "Add filters..." : ""}
              value={filterQuery}
              onChange={(e) => setFilterQuery(e.target.value)}
              onFocus={() => setShowDropdown(true)}
              onBlur={() => setTimeout(() => setShowDropdown(false), 200)}
              className="flex-1 min-w-[100px] outline-none bg-transparent text-sm placeholder:text-muted-foreground ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium disabled:cursor-not-allowed disabled:opacity-50"
            />
          </div>
        </div>
      </div>
      {showDropdown && filterSuggestions.length > 0 && (
        <div className="absolute top-full left-0 right-0 mt-1 border rounded-md bg-popover shadow-md z-50 max-h-60 overflow-y-auto">
          {filterSuggestions.map((filter) => (
            <div
              key={filter.id}
              className="px-3 py-2 hover:bg-accent cursor-pointer text-xs"
              onClick={() => handleAddFilter(filter.id)}
            >
              <span className="text-muted-foreground text-[10px]">{filter.category}</span>
              <div>{filter.label}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
