import * as React from "react";
import { Download, Upload, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem } from "@/components/ui/dropdown-menu";
import { useGraphStore } from "@/stores/roadStore";
import { useOptimizationStore } from "@/stores/optimizationStore";
import { fireroadApi } from "@/services/fireroad";
import {
  exportToRoadFormat,
  exportToAroadFormat,
  importFromRoadFormat,
  importFromAroadFormat,
  downloadFile,
  uploadFile,
  type AroadFormat,
  type OptimizationStateSnapshot,
} from "@/lib/roadFormat";
import { toast as showToast } from "@/hooks/useToast";

const getCourseDetails = async (courseId: string) => {
  const details = await fireroadApi.getCourseDetails(courseId);
  return { title: details.title, total_units: details.total_units };
};

export function ImportExportToolbar() {
  const [busy, setBusy] = React.useState(false);

  const markers = useGraphStore(state => state.markers);
  const optimizerNodes = useGraphStore(state => state.optimizerNodes);
  const loadRoadData = useGraphStore(state => state.loadRoadData);
  const selectedRequirements = useOptimizationStore(state => state.selectedRequirements);
  const setRequirements = useOptimizationStore(state => state.setRequirements);
  const loadOptimizationState = useOptimizationStore(state => state.loadOptimizationState);

  const getOptimizationSnapshot = (): OptimizationStateSnapshot => {
    const s = useOptimizationStore.getState();
    return {
      selectedObjectives: s.selectedObjectives,
      objectiveTiers: s.objectiveTiers,
      requirementTiers: s.requirementTiers,
      requirementSources: s.requirementSources,
      selectedHardConstraints: s.selectedHardConstraints,
      customEquivalencies: s.customEquivalencies,
      selectedYear: s.selectedYear ?? "",
      lockPastSemesters: s.lockPastSemesters,
    };
  };

  const handleImportRoad = async () => {
    try {
      setBusy(true);
      const data = await uploadFile();
      if (!data) return;

      const { markers: importedMarkers, warnings, coursesOfStudy } = importFromRoadFormat(data);
      loadRoadData({ markers: importedMarkers });
      if (coursesOfStudy.length > 0) setRequirements(coursesOfStudy);

      if (warnings.length > 0) {
        showToast({
          title: "Import completed with warnings",
          description: `Imported ${importedMarkers.length} courses and ${coursesOfStudy.length} degree(s). ${warnings.length} item(s) skipped.`,
          variant: "destructive",
          duration: 5000,
        });
        warnings.forEach(w => console.warn("Import warning:", w));
      } else {
        showToast({
          title: "Import successful",
          description: `Imported ${importedMarkers.length} courses and ${coursesOfStudy.length} degree(s) from .road file`,
          duration: 3000,
        });
      }
    } catch (error) {
      console.error("Import error:", error);
      showToast({ title: "Import failed", description: error instanceof Error ? error.message : "Unknown error", variant: "destructive", duration: 5000 });
    } finally {
      setBusy(false);
    }
  };

  const handleImportAroad = async () => {
    try {
      setBusy(true);
      const data = await uploadFile();
      if (!data) return;

      const result = importFromAroadFormat(data as AroadFormat);
      loadRoadData({ markers: result.markers, optimizerNodes: result.optimizerNodes ?? [] });

      if (result.coursesOfStudy.length > 0) setRequirements(result.coursesOfStudy);
      if (result.optimizationState) {
        loadOptimizationState({
          ...result.optimizationState,
          selectedRequirements: result.coursesOfStudy.length > 0 ? result.coursesOfStudy : undefined,
        });
      }

      const nodeCount = result.optimizerNodes?.length ?? 0;
      if (result.warnings.length > 0) {
        showToast({
          title: "Import completed with warnings",
          description: `Imported ${result.markers.length} markers and ${nodeCount} suggestions. ${result.warnings.length} item(s) skipped.`,
          variant: "destructive",
          duration: 5000,
        });
        result.warnings.forEach(w => console.warn("Import warning:", w));
      } else {
        showToast({
          title: "Import successful",
          description: `Imported ${result.markers.length} markers and ${nodeCount} suggestions from .aroad file`,
          duration: 3000,
        });
      }
    } catch (error) {
      console.error("Import error:", error);
      showToast({ title: "Import failed", description: error instanceof Error ? error.message : "Unknown error", variant: "destructive", duration: 5000 });
    } finally {
      setBusy(false);
    }
  };

  const handleExportMarkersRoad = async () => {
    try {
      setBusy(true);
      const data = await exportToRoadFormat(markers, selectedRequirements, getCourseDetails);
      downloadFile(data, "autoroad-markers.road");
      showToast({ title: "Export successful", description: "Markers exported as .road file", duration: 3000 });
    } catch (error) {
      console.error("Export error:", error);
      showToast({ title: "Export failed", description: error instanceof Error ? error.message : "Unknown error", variant: "destructive", duration: 5000 });
    } finally {
      setBusy(false);
    }
  };

  const handleExportEverythingRoad = async () => {
    try {
      setBusy(true);
      const seen = new Set(markers.filter(m => m.status !== 'banish').map(m => `${m.courseId}:${m.section}`));
      const allMarkers = [
        ...markers,
        ...optimizerNodes
          .filter(node => !seen.has(`${node.courseId}:${node.section}`))
          .map(node => ({
            uuid: `generated_${node.courseId}_${node.section}`,
            courseId: node.courseId,
            section: node.section,
            status: 'pin' as const,
          })),
      ];
      const data = await exportToRoadFormat(allMarkers, selectedRequirements, getCourseDetails);
      downloadFile(data, "autoroad-full.road");
      showToast({ title: "Export successful", description: "Full schedule exported as .road file", duration: 3000 });
    } catch (error) {
      console.error("Export error:", error);
      showToast({ title: "Export failed", description: error instanceof Error ? error.message : "Unknown error", variant: "destructive", duration: 5000 });
    } finally {
      setBusy(false);
    }
  };

  const handleExportAroad = async () => {
    try {
      setBusy(true);
      const data = await exportToAroadFormat(markers, optimizerNodes, selectedRequirements, getOptimizationSnapshot(), getCourseDetails);
      downloadFile(data, "autoroad.aroad");
      showToast({ title: "Export successful", description: "Full state exported as .aroad file", duration: 3000 });
    } catch (error) {
      console.error("Export error:", error);
      showToast({ title: "Export failed", description: error instanceof Error ? error.message : "Unknown error", variant: "destructive", duration: 5000 });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex items-center gap-2">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="sm" disabled={busy}>
            <Upload className="h-4 w-4" />
            Import
            <ChevronDown className="h-3 w-3 ml-1 opacity-50" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start">
          <DropdownMenuItem onSelect={handleImportRoad}>From CourseRoad (.road)</DropdownMenuItem>
          <DropdownMenuItem onSelect={handleImportAroad}>From Autoroad (.aroad)</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="sm" disabled={busy}>
            <Download className="h-4 w-4" />
            Export
            <ChevronDown className="h-3 w-3 ml-1 opacity-50" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start">
          <DropdownMenuItem onSelect={handleExportMarkersRoad}>Markers as CourseRoad (.road)</DropdownMenuItem>
          <DropdownMenuItem onSelect={handleExportEverythingRoad}>Everything as CourseRoad (.road)</DropdownMenuItem>
          <DropdownMenuItem onSelect={handleExportAroad}>Everything as Autoroad (.aroad)</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
