import { UserX, BrainCircuit } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useGraphStore } from "@/stores/roadStore";
import { toast as showToast } from "@/hooks/useToast";

export function ClearButtons() {
  const markers = useGraphStore(state => state.markers);
  const optimizerNodes = useGraphStore(state => state.optimizerNodes);
  const loadRoadData = useGraphStore(state => state.loadRoadData);

  const handleClearMarkers = () => {
    loadRoadData({ markers: [] });
    showToast({
      title: "Markers cleared",
      description: "All course markers have been removed",
      duration: 2000,
    });
  };

  const handleClearOptimizer = () => {
    loadRoadData({ optimizerNodes: [] });
    showToast({
      title: "Optimizer results cleared",
      description: "All optimizer-suggested courses have been removed",
      duration: 2000,
    });
  };

  return (
    <div className="flex gap-1" data-tutorial="clear-buttons">
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="inline-block">
            <Button size="icon" variant="outline" onClick={handleClearMarkers} disabled={markers.length === 0} className="h-8 w-8">
              <UserX className="h-4 w-4" />
            </Button>
          </span>
        </TooltipTrigger>
        <TooltipContent>Clear Markers</TooltipContent>
      </Tooltip>

      <Tooltip>
        <TooltipTrigger asChild>
          <span className="inline-block" data-tutorial="clear-optimizer-button">
            <Button size="icon" variant="outline" onClick={handleClearOptimizer} disabled={optimizerNodes.length === 0} className="h-8 w-8">
              <BrainCircuit className="h-4 w-4" />
            </Button>
          </span>
        </TooltipTrigger>
        <TooltipContent>Clear Optimizer Results</TooltipContent>
      </Tooltip>
    </div>
  );
}
