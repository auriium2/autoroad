import * as React from "react";
import { Download, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useGraphStore } from "@/stores/roadStore";
import { useOptimizationStore } from "@/stores/optimizationStore";
import { fireroadApi } from "@/services/fireroad";
import { exportToRoadFormat, importFromRoadFormat, downloadRoadFile, uploadRoadFile } from "@/lib/roadFormat";
import { toast as showToast } from "@/hooks/useToast";

export function ImportExportToolbar() {
  const [isExportingMarkers, setIsExportingMarkers] = React.useState(false);
  const [isExportingGenerated, setIsExportingGenerated] = React.useState(false);
  const [isImporting, setIsImporting] = React.useState(false);

  const markers = useGraphStore(state => state.markers);
  const optimizerNodes = useGraphStore(state => state.optimizerNodes);
  const loadRoadData = useGraphStore(state => state.loadRoadData);
  const selectedRequirements = useOptimizationStore(state => state.selectedRequirements);

  const handleImport = async () => {
    try {
      setIsImporting(true);

      const roadData = await uploadRoadFile();

      if (!roadData) {
        return;
      }

      const { markers: importedMarkers, warnings } = importFromRoadFormat(roadData);

      loadRoadData({ markers: importedMarkers });

      if (warnings.length > 0) {
        showToast({
          title: "Import completed with warnings",
          description: `Imported ${importedMarkers.length} courses. ${warnings.length} generic requirement(s) skipped.`,
          variant: "destructive",
          duration: 5000,
        });
        console.warn('Import warnings:', warnings);
        warnings.forEach(warning => console.warn('- ' + warning));
      } else {
        showToast({
          title: "Import successful",
          description: `Imported ${importedMarkers.length} courses from .road file`,
          duration: 3000,
        });
      }
    } catch (error) {
      console.error('Error during import:', error);
      showToast({
        title: "Import failed",
        description: error instanceof Error ? error.message : "Unknown error occurred",
        variant: "destructive",
        duration: 5000,
      });
    } finally {
      setIsImporting(false);
    }
  };

  const handleExportMarkers = async () => {
    try {
      setIsExportingMarkers(true);

      const roadData = await exportToRoadFormat(
        markers,
        selectedRequirements,
        async (courseId) => {
          const details = await fireroadApi.getCourseDetails(courseId);
          return {
            title: details.title,
            total_units: details.total_units,
          };
        }
      );

      downloadRoadFile(roadData, "autoroad-markers.road");

      showToast({
        title: "Export successful",
        description: "Your markers have been exported to .road format",
        duration: 3000,
      });
    } catch (error) {
      console.error('Error during markers export:', error);
      showToast({
        title: "Export failed",
        description: error instanceof Error ? error.message : "Unknown error occurred",
        variant: "destructive",
        duration: 5000,
      });
    } finally {
      setIsExportingMarkers(false);
    }
  };

  const handleExportGenerated = async () => {
    try {
      setIsExportingGenerated(true);

      const generatedMarkers = optimizerNodes.map(node => ({
        uuid: `generated_${node.courseId}_${node.section}`,
        courseId: node.courseId,
        section: node.section,
        status: 'pin' as const,
      }));

      const roadData = await exportToRoadFormat(
        generatedMarkers,
        selectedRequirements,
        async (courseId) => {
          const details = await fireroadApi.getCourseDetails(courseId);
          return {
            title: details.title,
            total_units: details.total_units,
          };
        }
      );

      downloadRoadFile(roadData, "autoroad-generated.road");

      showToast({
        title: "Export successful",
        description: "Your generated schedule has been exported to .road format",
        duration: 3000,
      });
    } catch (error) {
      console.error('Error during generated export:', error);
      showToast({
        title: "Export failed",
        description: error instanceof Error ? error.message : "Unknown error occurred",
        variant: "destructive",
        duration: 5000,
      });
    } finally {
      setIsExportingGenerated(false);
    }
  };

  return (
    <div className="flex items-center gap-2">
      <Button variant="outline" size="sm" onClick={handleImport} disabled={isImporting}>
        <Upload className="h-4 w-4" />
        {isImporting ? "Importing..." : "Import"}
      </Button>
      <Button variant="outline" size="sm" onClick={handleExportMarkers} disabled={isExportingMarkers}>
        <Download className="h-4 w-4" />
        {isExportingMarkers ? "Exporting..." : "Export Markers"}
      </Button>
      <Button variant="outline" size="sm" onClick={handleExportGenerated} disabled={isExportingGenerated}>
        <Download className="h-4 w-4" />
        {isExportingGenerated ? "Exporting..." : "Export Generated"}
      </Button>
    </div>
  );
}
